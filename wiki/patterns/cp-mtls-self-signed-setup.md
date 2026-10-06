---
title: Confluent Platform mTLS Setup with Self-Signed Certs
tags: [confluent-platform, mtls, tls, ssl, kafka, security, pkcs12, acls, fsi, linuxone]
sources:
  - "internal field notes (mTLS on CP / LinuxONE)"
related:
  - concepts/linuxone-jdk-tls-gotchas
  - patterns/cp-tls-debugging-by-component
  - concepts/fips-at-install-ocp-requirement
  - concepts/linuxone-kafka-integration
  - patterns/auditor-readonly-rbac-payload-isolation
confidence: high
last_updated: 2026-05-27
last_validated: 2026-05-27
---

# Confluent Platform mTLS Setup with Self-Signed Certs

## Summary

End-to-end procedure for standing up mutual TLS on Confluent Platform brokers and clients using a self-signed CA. Written with LinuxONE / IBM Semeru / FIPS in mind but the procedure is JDK-agnostic. Key trade-off: a self-signed CA keeps you out of the corporate PKI dependency for non-prod and air-gapped environments at the cost of operating CA-key rotation yourself; LinuxONE / FIPS deployments must generate keystores on the target platform — cross-JDK PKCS12 portability is the most common footgun.

## Pattern

### 0. Prerequisites and Ground Rules

- **Generate everything on the target platform.** Don't mint keystores on macOS and copy them to LinuxONE. IBM JDK + FIPS reads PKCS12 MACs differently than OpenJDK on x86.
- **Use PKCS12, not JKS.** JKS is deprecated; PKCS12 is what works cleanly across OpenJDK, Semeru, and FIPS-mode Bouncy Castle.
- **Pick strong, explicit algorithms** so FIPS doesn't silently reject things: RSA 2048+, SHA-256 signatures, TLS 1.2/1.3 — never rely on defaults.
- **Every broker cert needs SANs** covering every DNS name and IP clients will dial. Modern TLS clients (and `ssl.endpoint.identification.algorithm=HTTPS`) reject certs that only have the hostname in the CN.
- **Tools:** `openssl` (1.1.1+ or 3.x) and `keytool` from the JDK Kafka will run on — ideally IBM Semeru on the broker hosts.

Variables used throughout:

```bash
export CA_PASS='changeme-ca'
export KS_PASS='changeme-keystore'
export TS_PASS='changeme-truststore'
export VALIDITY=3650          # CA validity in days
export CERT_VALIDITY=825      # leaf cert validity (browsers cap at 825)
export DOMAIN='kafka.example.internal'
```

### 1. Create the Self-Signed Root CA

```bash
mkdir -p ca && cd ca

# CA private key (RSA 4096 for the root)
openssl genrsa -aes256 -passout pass:$CA_PASS -out ca-key.pem 4096

# Self-signed CA certificate
openssl req -x509 -new -nodes -key ca-key.pem -sha256 -days $VALIDITY \
  -passin pass:$CA_PASS \
  -subj "/C=US/ST=ST/L=Anytown/O=Example/OU=Platform/CN=Example-Kafka-Root-CA" \
  -out ca-cert.pem

# Verify
openssl x509 -in ca-cert.pem -noout -text | head -20
```

Keep `ca-key.pem` locked down (`chmod 400`, ideally on an offline host or HSM). You only need it when signing new broker/client certs.

### 2. Generate a Broker Keystore (repeat per broker)

Each broker needs its own keypair, its own cert with SANs for *its* hostnames, and the signed cert + CA imported back in.

```bash
BROKER=broker0
BROKER_FQDN=broker0.$DOMAIN
BROKER_IP=10.20.30.40

# 2a. Generate keystore with a fresh keypair
keytool -genkeypair \
  -keystore $BROKER.keystore.p12 -storetype PKCS12 \
  -alias $BROKER \
  -keyalg RSA -keysize 2048 -sigalg SHA256withRSA \
  -validity $CERT_VALIDITY \
  -dname "CN=$BROKER_FQDN,OU=Platform,O=Example,L=Anytown,ST=ST,C=US" \
  -ext "SAN=dns:$BROKER_FQDN,dns:$BROKER,ip:$BROKER_IP" \
  -storepass $KS_PASS -keypass $KS_PASS

# 2b. Create a CSR
keytool -certreq \
  -keystore $BROKER.keystore.p12 -storetype PKCS12 \
  -alias $BROKER \
  -file $BROKER.csr \
  -ext "SAN=dns:$BROKER_FQDN,dns:$BROKER,ip:$BROKER_IP" \
  -storepass $KS_PASS

# 2c. Sign the CSR with the CA (SANs must be re-asserted in the signed cert)
cat > $BROKER.ext <<EOF
subjectAltName = DNS:$BROKER_FQDN,DNS:$BROKER,IP:$BROKER_IP
extendedKeyUsage = serverAuth,clientAuth
EOF

openssl x509 -req -in $BROKER.csr \
  -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
  -passin pass:$CA_PASS \
  -out $BROKER-signed.pem -days $CERT_VALIDITY -sha256 \
  -extfile $BROKER.ext

# 2d. Import the CA cert first, then the signed broker cert
keytool -importcert -keystore $BROKER.keystore.p12 -storetype PKCS12 \
  -alias CARoot -file ca-cert.pem -storepass $KS_PASS -noprompt

keytool -importcert -keystore $BROKER.keystore.p12 -storetype PKCS12 \
  -alias $BROKER -file $BROKER-signed.pem -storepass $KS_PASS -noprompt

# 2e. Sanity check — should show a 2-cert chain
keytool -list -v -keystore $BROKER.keystore.p12 -storetype PKCS12 \
  -storepass $KS_PASS | grep -E 'Alias|Owner|Issuer|SAN'
```

**Why `extendedKeyUsage = serverAuth,clientAuth`?** Kafka's inter-broker traffic has the broker acting as both TLS server *and* TLS client. Without the `clientAuth` EKU, inter-broker mTLS fails with a confusing "certificate unknown" error even when the chain validates.

Repeat §2 for every broker. Scripting this is strongly recommended.

### 3. Build the Shared Truststore

Everyone — brokers, clients, Schema Registry, Connect, Control Center — needs to trust the CA. Same truststore file everywhere; nothing broker- or client-specific.

```bash
keytool -importcert \
  -keystore kafka.truststore.p12 -storetype PKCS12 \
  -alias CARoot -file ca-cert.pem \
  -storepass $TS_PASS -noprompt
```

### 4. Generate a Client Keystore

Same pattern as a broker, but with `extendedKeyUsage = clientAuth` and a CN that will become the Kafka principal.

```bash
CLIENT=example-app1
CLIENT_CN="$CLIENT"

keytool -genkeypair \
  -keystore $CLIENT.keystore.p12 -storetype PKCS12 \
  -alias $CLIENT \
  -keyalg RSA -keysize 2048 -sigalg SHA256withRSA \
  -validity $CERT_VALIDITY \
  -dname "CN=$CLIENT_CN,OU=Apps,O=Example,L=Anytown,ST=ST,C=US" \
  -storepass $KS_PASS -keypass $KS_PASS

keytool -certreq -keystore $CLIENT.keystore.p12 -storetype PKCS12 \
  -alias $CLIENT -file $CLIENT.csr -storepass $KS_PASS

cat > $CLIENT.ext <<EOF
extendedKeyUsage = clientAuth
EOF

openssl x509 -req -in $CLIENT.csr \
  -CA ca-cert.pem -CAkey ca-key.pem -CAcreateserial \
  -passin pass:$CA_PASS \
  -out $CLIENT-signed.pem -days $CERT_VALIDITY -sha256 \
  -extfile $CLIENT.ext

keytool -importcert -keystore $CLIENT.keystore.p12 -storetype PKCS12 \
  -alias CARoot -file ca-cert.pem -storepass $KS_PASS -noprompt
keytool -importcert -keystore $CLIENT.keystore.p12 -storetype PKCS12 \
  -alias $CLIENT -file $CLIENT-signed.pem -storepass $KS_PASS -noprompt
```

The CN (`example-app1`) is what Kafka uses as the principal for ACLs — pick something meaningful and stable.

### 5. Broker Configuration (server.properties)

```properties
# --- Listeners ---
listeners=SSL://0.0.0.0:9093
advertised.listeners=SSL://broker0.kafka.example.internal:9093
listener.security.protocol.map=SSL:SSL
inter.broker.listener.name=SSL

# --- Keystore (broker's own identity) ---
ssl.keystore.type=PKCS12
ssl.keystore.location=/etc/kafka/ssl/broker0.keystore.p12
ssl.keystore.password=changeme-keystore
ssl.key.password=changeme-keystore

# --- Truststore (who we accept) ---
ssl.truststore.type=PKCS12
ssl.truststore.location=/etc/kafka/ssl/kafka.truststore.p12
ssl.truststore.password=changeme-truststore

# --- mTLS: require clients to present certs ---
ssl.client.auth=required

# --- Hostname verification (prevents MITM with wrong-host cert) ---
ssl.endpoint.identification.algorithm=HTTPS

# --- Protocol pinning ---
ssl.enabled.protocols=TLSv1.3,TLSv1.2
ssl.protocol=TLSv1.3

# --- Principal derivation from cert DN ---
# Extract CN as the principal; fall back to the full DN otherwise
ssl.principal.mapping.rules=RULE:^CN=([^,]+).*$/$1/,DEFAULT

# --- Authorizer (ACLs keyed on CN; KRaft path) ---
authorizer.class.name=org.apache.kafka.metadata.authorizer.StandardAuthorizer
super.users=User:broker0;User:broker1;User:broker2
allow.everyone.if.no.acl.found=false
```

Things to call out:

- **`ssl.client.auth=required`** is what turns TLS into mTLS. `requested` is a trap — clients that don't present a cert fall through unauthenticated. Confluent docs explicitly discourage `requested`.
- **`super.users`** should be the broker CNs so inter-broker traffic works without explicit ACLs.
- **Principal mapping** — tune the regex to match what you put in the DN. Test with `kafka-acls --principal User:example-app1 ...` before relying on it.
- **`StandardAuthorizer`** is the KRaft authorizer at `org.apache.kafka.metadata.authorizer.StandardAuthorizer`. ZK-based clusters used `kafka.security.authorizer.AclAuthorizer`; this guide assumes KRaft.
- **File permissions on keystores:** `chown kafka:kafka`, `chmod 600`. The Kafka process user needs read; nobody else does.

### 6. Client Configuration

Standard `client.properties`:

```properties
security.protocol=SSL

ssl.keystore.type=PKCS12
ssl.keystore.location=/etc/kafka/ssl/example-app1.keystore.p12
ssl.keystore.password=changeme-keystore
ssl.key.password=changeme-keystore

ssl.truststore.type=PKCS12
ssl.truststore.location=/etc/kafka/ssl/kafka.truststore.p12
ssl.truststore.password=changeme-truststore

ssl.endpoint.identification.algorithm=HTTPS
ssl.enabled.protocols=TLSv1.3,TLSv1.2
```

For Schema Registry, Connect, ksqlDB, and Control Center, the same block applies — they're all Kafka clients in this regard. Each of those services typically needs three overlapping configs: its own listener (if it exposes REST/HTTPS), its client config for talking to Kafka, and its client config for talking to Schema Registry. **Don't collapse them.**

**Important property-name distinction:** On the **broker**, the mTLS knob is `ssl.client.auth` (values: `required` / `requested` / `none`). On **Schema Registry** (and on the Connect REST API via `listeners.https.*`), the equivalent knob is `ssl.client.authentication` (values: `NONE` / `REQUESTED` / `REQUIRED`). Confluent's REST-tier components use the longer name; the broker uses the shorter one. Easy footgun.

### 7. Verification

**Step 1: Raw TLS handshake** (before Kafka enters the picture):

```bash
openssl s_client -connect broker0.kafka.example.internal:9093 \
  -CAfile ca-cert.pem \
  -cert example-app1-signed.pem -key example-app1.key \
  -showcerts -tls1_3
```

Look for `Verify return code: 0 (ok)` and a completed handshake. If this fails, it's a pure TLS/cert problem, not a Kafka problem.

**Step 2: Kafka client sanity check**:

```bash
kafka-broker-api-versions --bootstrap-server broker0.kafka.example.internal:9093 \
  --command-config client.properties
```

**Step 3: Produce/consume roundtrip**:

```bash
kafka-topics --bootstrap-server broker0.kafka.example.internal:9093 \
  --command-config client.properties \
  --create --topic mtls-test --partitions 1 --replication-factor 3

echo "hello mtls" | kafka-console-producer \
  --bootstrap-server broker0.kafka.example.internal:9093 \
  --producer.config client.properties --topic mtls-test

kafka-console-consumer \
  --bootstrap-server broker0.kafka.example.internal:9093 \
  --consumer.config client.properties \
  --topic mtls-test --from-beginning --max-messages 1
```

**Step 4: When it fails, get the handshake log.** Add `-Djavax.net.debug=ssl:handshake:verbose` to the JVM invocation. The `ClientHello` / `ServerHello` / `Certificate` / `CertificateVerify` messages will tell you exactly what's broken. Component-specific recipes for capturing that log live in [cp-tls-debugging-by-component](cp-tls-debugging-by-component.md).

### 8. After mTLS — Apply ACLs

mTLS only gives you authentication. Without ACLs, any client with a valid cert can do anything. Once the handshake works:

```bash
kafka-acls --bootstrap-server broker0.kafka.example.internal:9093 \
  --command-config admin.properties \
  --add --allow-principal User:example-app1 \
  --operation Read --operation Describe \
  --topic mtls-test --group example-app1-consumers
```

Principal name here must match what `ssl.principal.mapping.rules` extracts from the client cert DN — which is why a stable, meaningful CN matters. For FSI audit-isolation patterns, see [auditor-readonly-rbac-payload-isolation](auditor-readonly-rbac-payload-isolation.md).

## Automation

Two automation paths exist depending on whether you're inside the fsi-dsp harness or standalone:

- **Inside the fsi-dsp harness (fsi-dsp scenarios):** use `fsi-dsp/ansible/roles/cp_mtls/`. The role covers §1–§6 of this pattern, includes a PKCS#11 / CEX HSM mode for HSM-backed broker keys, is molecule-tested, and wires into `site.yml` via the `cp-rhel` / `cp-rhel-linuxone` scenarios. Live-cluster verification lives in `fsi-dsp/scenarios/cp-rhel-linuxone/playbooks/verify-mtls.yml`. This is the canonical automation in the fsi-dsp harness.
- **Outside the fsi-dsp scenario harness:** a standalone Ansible companion bundle is parked at `raw/articles/ansible-cp-mtls-bundle/` (see [INGEST-NOTES](../../raw/articles/ansible-cp-mtls-bundle/INGEST-NOTES.md)). It automates §1–§6 with five `kafka_*` roles and is portable to any Linux Kafka deployment. The bundle does **not** cover PKCS#11/HSM (acknowledged limitation); software keys only. It was evaluated against fsi-dsp on 2026-05-27 and declined for FSI use because `cp_mtls` is strictly more comprehensive — but it stands on its own for portable distribution alongside this pattern.

## When to Use

- New CP / CFK cluster needing mTLS for the FSI mTLS+RBAC canon default
- Non-prod / air-gapped clusters where the corporate PKI isn't available
- LinuxONE deployments where keystores must be generated on s390x against IBM Semeru
- Lab and PoC environments standing up a full Confluent stack with realistic security posture
- Pre-prod dry-runs of a corporate-PKI-issued cert flow — the procedure is identical apart from §1

## Caveats

- **Self-signed CA is not the FSI production answer.** FSI prod terminates back to the corporate PKI or an HSM-backed intermediate. This pattern is the lab / sandbox / lower-env shape; promote the same procedure to a corporate-issued cert flow before going to prod.
- **Cert rotation is on you.** With a self-signed CA you own the rotation calendar end-to-end: 825-day leaf certs and 3650-day root means a rotation event somewhere every 1–2 years.
- **Inter-broker EKU is non-obvious.** Missing `clientAuth` in `extendedKeyUsage` on broker certs surfaces as a generic "certificate unknown" error during inter-broker handshakes — not as anything that points at the EKU. Always include both `serverAuth` and `clientAuth` on broker certs.
- **The mTLS property-name footgun.** Broker: `ssl.client.auth`. SR REST + Connect REST `listeners.https.*`: `ssl.client.authentication`. Don't copy-paste blindly.
- **PKCS12 portability across JDKs.** Keystores minted on x86 OpenJDK keytool sometimes fail to load on s390x IBM Semeru (especially under FIPS). Always generate on the target platform — see [linuxone-jdk-tls-gotchas](../concepts/linuxone-jdk-tls-gotchas.md).
- **Hostname verification is unforgiving.** `ssl.endpoint.identification.algorithm=HTTPS` will fail the handshake if the client dials by IP but the cert only lists DNS SANs. Either add IP SANs or always connect by name.

## Related

- [LinuxONE JDK/TLS Gotchas](../concepts/linuxone-jdk-tls-gotchas.md) — IBM Semeru provider order, FIPS mode, PKCS12 MAC algorithm, cipher intersection, CEX/PKCS#11
- [CP TLS Debugging by Component](cp-tls-debugging-by-component.md) — per-component handshake debug recipes (broker, SR, Connect, C3, apps)
- [FIPS-at-install OCP Requirement](../concepts/fips-at-install-ocp-requirement.md) — silent-failure trip-wire if OCP wasn't installed in FIPS mode
- [LinuxONE Kafka Integration](../concepts/linuxone-kafka-integration.md) — z/OS bridge and CP-on-LinuxONE positioning
- [Auditor-Readonly RBAC Payload Isolation](auditor-readonly-rbac-payload-isolation.md) — ACL design once mTLS is up

---

*MCP-validated against Confluent docs (encrypt-tls.html, ACL overview, SR config) on 2026-05-27: confirmed `ssl.client.auth=required` is the canonical recommendation (`requested` discouraged), `StandardAuthorizer` at `org.apache.kafka.metadata.authorizer.StandardAuthorizer` for KRaft, `ssl.principal.mapping.rules` syntax, `super.users` / `allow.everyone.if.no.acl.found` semantics, and the `ssl.client.authentication` vs `ssl.client.auth` distinction across broker vs REST tiers.*
