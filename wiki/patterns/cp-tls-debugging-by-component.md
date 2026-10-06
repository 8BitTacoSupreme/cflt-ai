---
title: Confluent Platform TLS Debugging by Component
tags: [confluent-platform, mtls, tls, ssl, debugging, troubleshooting, schema-registry, connect, control-center, kafka, tcpdump, fsi]
sources:
  - "internal field notes (mTLS on CP / LinuxONE)"
related:
  - patterns/cp-mtls-self-signed-setup
  - concepts/linuxone-jdk-tls-gotchas
  - concepts/schema-registry-best-practices
  - patterns/connect-deployment-models
confidence: high
last_updated: 2026-05-27
last_validated: 2026-05-27
---

# Confluent Platform TLS Debugging by Component

## Summary

Component-by-component recipes for capturing and interpreting TLS / mTLS handshake failures across the CP stack: clients, brokers (inter-broker), Schema Registry (split kafkastore-vs-REST TLS contexts), Control Center (multi-downstream), Connect (worker / REST / per-task), application producers/consumers, network-level packet capture, and a one-shot diagnostic bundle for L1 escalations. Universal knob is `-Djavax.net.debug=ssl:handshake:verbose`; the value-add of this pattern is **where to inject it** and **which log to read** for each component, because every CP component respects a different `*_OPTS` env var.

## Pattern

### Universal Knob

`-Djavax.net.debug=ssl:handshake:verbose` is the universal JVM TLS debug switch. Every CP component respects a `*_OPTS` environment variable that gets appended to the JVM invocation — that's the clean injection point.

> ⚠️ unverified — exact env-var names for SR / C3 (`SCHEMA_REGISTRY_OPTS`, `CONTROL_CENTER_OPTS`) are the long-standing operational convention but were not surfaced in the docs pages fetched on 2026-05-27. `KAFKA_OPTS` for brokers, Connect workers, and Streams apps is the well-established convention. Confirm against the local installation's systemd unit if a debug flag fails to land.

### B.1 — Client Handshake Failure

**Step 1: isolate TLS from Kafka.** The openssl client proves whether it's a pure TLS problem or something Kafka-specific:

```bash
openssl s_client -connect broker0.kafka.example.internal:9093 \
  -CAfile ca-cert.pem \
  -cert example-app1-signed.pem -key example-app1.key \
  -showcerts -tls1_3 -state 2>&1 | tee /tmp/openssl-handshake.log
```

If this fails, the problem is certs / TLS / network — Kafka isn't the issue. If it succeeds but the Kafka client fails, the problem is in the client's Java SSL config.

**Step 2: JVM TLS debug from the client side.** For CLI tools:

```bash
export KAFKA_OPTS="-Djavax.net.debug=ssl:handshake:verbose"
kafka-console-producer --bootstrap-server ... 2> /tmp/client-handshake.log
```

For packaged Java apps:

```bash
java -Djavax.net.debug=ssl:handshake:verbose -jar myapp.jar 2> /tmp/client-handshake.log
```

For containerized clients:

```bash
docker run -e JAVA_TOOL_OPTIONS="-Djavax.net.debug=ssl:handshake:verbose" ...
```

**What to grep the log for:**

| Marker | What it tells you |
|--------|-------------------|
| `*** ClientHello` | Cipher suites and TLS versions the client offered |
| `*** ServerHello` | What the server chose (or fatal alert if nothing matched) |
| `*** Certificate chain` / `Verify return code` | Whether chain validation succeeded |
| `*** CertificateRequest` | Server is asking for a client cert (proves mTLS is on) |
| `*** CertificateVerify` | Client is proving it holds the private key |
| `SSLHandshakeException` | Read the line before it for the actual cause |
| `unable to find valid certification path` | Truststore doesn't contain the CA |
| `No subject alternative names matching` | Cert SAN doesn't cover the hostname the client dialed |
| `no cipher suites in common` | Cipher list intersection is empty (common x86↔s390x symptom) |

### B.2 — Broker-to-Broker Failure

**Symptoms:** brokers can't form a cluster, replica fetcher threads flood the log with errors, ISRs thrash, controller election never completes.

**Enable debug on every broker** (edit `/etc/sysconfig/kafka` or the systemd unit environment):

```bash
export KAFKA_OPTS="-Djavax.net.debug=ssl:handshake:verbose"
```

Restart rolling. Then tail:

```bash
tail -F /var/log/kafka/server.log \
        /var/log/kafka/controller.log \
        /var/log/kafka/state-change.log \
  | grep -iE 'ssl|tls|handshake|replicafetcher|authenticat'
```

**High-signal grep patterns:**

```bash
grep -E 'SSLHandshakeException|SSLAuthenticationException' /var/log/kafka/server.log
grep -E 'Connection to node -?[0-9]+ .* failed authentication' /var/log/kafka/server.log
grep 'ReplicaFetcherThread' /var/log/kafka/server.log | grep -i ssl
```

**Verify the listener actually exists and uses the right protocol:**

```bash
grep -E '^(listeners|advertised.listeners|inter.broker.listener.name|listener.security.protocol.map|ssl\.)' /etc/kafka/server.properties
```

**Common causes specifically for inter-broker:**

- Broker cert missing `clientAuth` EKU (§2 of [cp-mtls-self-signed-setup](cp-mtls-self-signed-setup.md)).
- Broker CN not in `super.users`, so authZ blocks inter-broker ops even after authN succeeds.
- `inter.broker.listener.name` pointing to a listener that isn't SSL.
- Time skew between brokers >2 minutes — handshake sees "not yet valid" or "expired" cert. Confirm NTP / STP is running on all hosts.

### B.3 — Schema Registry

Schema Registry has **two independent TLS contexts** that fail in different ways:

1. **SR → Kafka** (backing store) — configured with `kafkastore.ssl.*` keys.
2. **Clients → SR** (REST API) — configured with `ssl.*` keys and `listeners=https://...`.

**Enable debug:**

```bash
export SCHEMA_REGISTRY_OPTS="-Djavax.net.debug=ssl:handshake"
systemctl restart confluent-schema-registry
```

**Log:** `/var/log/confluent/schema-registry/schema-registry.log`

**Distinguishing the two failure modes:**

- Startup errors, `Failed to create Kafka client`, or `Timed out waiting for Kafka store to reach end` → **kafkastore side** is broken. SR can't talk to brokers. Check `kafkastore.*` SSL config.
- SR starts cleanly but clients hitting `https://sr:8081` get `SSLHandshakeException` → **REST listener side** is broken. Check SR's own `ssl.*` config and the listener definition.

Relevant config slice (`schema-registry.properties`):

```properties
# --- SR → Kafka (backing store) ---
kafkastore.bootstrap.servers=SSL://broker0:9093,SSL://broker1:9093
kafkastore.security.protocol=SSL
kafkastore.ssl.truststore.type=PKCS12
kafkastore.ssl.truststore.location=/etc/schema-registry/ssl/kafka.truststore.p12
kafkastore.ssl.truststore.password=...
kafkastore.ssl.keystore.type=PKCS12
kafkastore.ssl.keystore.location=/etc/schema-registry/ssl/sr.keystore.p12
kafkastore.ssl.keystore.password=...
kafkastore.ssl.key.password=...

# --- Clients → SR (REST) ---
listeners=https://0.0.0.0:8081
ssl.truststore.type=PKCS12
ssl.truststore.location=/etc/schema-registry/ssl/kafka.truststore.p12
ssl.truststore.password=...
ssl.keystore.type=PKCS12
ssl.keystore.location=/etc/schema-registry/ssl/sr.keystore.p12
ssl.keystore.password=...
ssl.key.password=...
ssl.client.authentication=NONE   # or REQUIRED for mTLS on the REST tier too
```

Note the property-name difference: SR uses `ssl.client.authentication` (long form, values `NONE` / `REQUESTED` / `REQUIRED`); brokers use `ssl.client.auth` (short form). Both are canonical for their respective tiers.

### B.4 — Control Center

C3 is the most complex to debug because it speaks TLS to **everything** downstream: brokers (streams backend), Schema Registry, each registered Connect cluster, each registered ksqlDB cluster, and its monitoring interceptors ship back to Kafka on yet another TLS context.

**Enable debug:**

```bash
export CONTROL_CENTER_OPTS="-Djavax.net.debug=ssl:handshake"
systemctl restart confluent-control-center
```

**Log:** `/var/log/confluent/control-center/control-center.log`

**Isolate which downstream connection is failing.** C3 errors name the component in the stack trace. Grep for the URL or cluster name:

```bash
grep -E 'SSLHandshakeException|Failed to|Unable to connect' \
  /var/log/confluent/control-center/control-center.log | head -50
```

**C3 config namespaces** (all live in `control-center-production.properties`):

```properties
# C3 → Kafka (internal streams backend)
confluent.controlcenter.streams.security.protocol=SSL
confluent.controlcenter.streams.ssl.truststore.location=...
confluent.controlcenter.streams.ssl.keystore.location=...
# + passwords

# C3 → Schema Registry
confluent.controlcenter.schema.registry.url=https://sr:8081
confluent.controlcenter.schema.registry.ssl.truststore.location=...

# C3 → Connect (repeat per cluster — <name> is the cluster label)
confluent.controlcenter.connect.fsi-connect.cluster=https://connect:8083
confluent.controlcenter.connect.fsi-connect.ssl.truststore.location=...

# C3 → ksqlDB
confluent.controlcenter.ksql.fsi-ksql.url=https://ksqldb:8088
confluent.controlcenter.ksql.fsi-ksql.ssl.truststore.location=...

# Monitoring interceptors (ship metrics to Kafka)
confluent.monitoring.interceptor.security.protocol=SSL
confluent.monitoring.interceptor.ssl.truststore.location=...
```

> ⚠️ unverified — the `confluent.monitoring.interceptor.*` namespace is the standard operational name for the monitoring interceptors block (the interceptors are a JAR loaded into producer/consumer/Streams/Connect JVMs that ship records back to a metrics topic for C3 to consume); the C3 configuration page fetched on 2026-05-27 covered the four `confluent.controlcenter.*` namespaces but not the interceptor namespace explicitly. Confirm against installed `*.jar`'s `META-INF` if in doubt.

**Common trap:** copying `confluent.controlcenter.streams.*` SSL config but forgetting the separate `confluent.monitoring.interceptor.*` block. The UI loads fine, but the monitoring tab is empty because interceptors can't ship.

### B.5 — Kafka Connect

Connect has **three TLS surfaces**:

1. **Worker → Kafka** (internal topics + connector producers/consumers). Configured via top-level `ssl.*` and optionally `producer.ssl.*`, `consumer.ssl.*`, `admin.ssl.*`.
2. **Worker REST API** (`POST /connectors`, etc.). Configured via `listeners.https.*` (the `listeners.https` prefix overrides top-level `ssl.*` for the REST tier).
3. **Connector → external system** (not Kafka TLS; each connector has its own config surface).

**Enable debug:**

```bash
export KAFKA_OPTS="-Djavax.net.debug=ssl:handshake"
systemctl restart confluent-kafka-connect
```

(Connect respects `KAFKA_OPTS`, not a Connect-specific variable.)

**Logs:** `/var/log/confluent/kafka-connect/connect.log` (or `/var/log/confluent/connect/connect.log` depending on packaging).

**Distinguishing failures:**

- Worker won't start, errors reference `connect-configs` / `connect-offsets` / `connect-status` → **Worker → Kafka** SSL is broken.
- Worker starts, `/connectors` REST call fails with TLS error → **REST listener** SSL is broken.
- Worker runs, connectors deploy, but one connector fails with SSL errors → that connector's downstream system config, not Kafka TLS.

**Config slice (`connect-distributed.properties`):**

```properties
# --- Worker → Kafka ---
bootstrap.servers=SSL://broker0:9093,SSL://broker1:9093
security.protocol=SSL
ssl.truststore.type=PKCS12
ssl.truststore.location=...
ssl.truststore.password=...
ssl.keystore.type=PKCS12
ssl.keystore.location=...
ssl.keystore.password=...
ssl.key.password=...

# Per-subsystem overrides (these inherit from top-level ssl.* unless set)
producer.security.protocol=SSL
producer.ssl.truststore.location=...
consumer.security.protocol=SSL
consumer.ssl.truststore.location=...
admin.security.protocol=SSL
admin.ssl.truststore.location=...

# --- REST API ---
listeners=https://0.0.0.0:8083
listeners.https.ssl.truststore.location=...
listeners.https.ssl.keystore.location=...
listeners.https.ssl.keystore.password=...
listeners.https.ssl.key.password=...
```

**Gotcha:** top-level `ssl.*` applies to the worker's own internal Kafka clients, but `producer.*` / `consumer.*` / `admin.*` overrides are used for connector-created clients. If you configure the top-level block but omit the subsystem blocks, workers come up healthy but individual connector tasks fail with SSL errors on their producer or consumer. Either set the top-level `ssl.*` and let everything inherit, or set all four consistently — don't mix. (For per-connector overrides, see `connector.client.config.override.policy` and the `producer.override.` / `consumer.override.` / `admin.override.` prefixes.)

### B.6 — Producer / Consumer Applications

**Enable in code:**

```java
System.setProperty("javax.net.debug", "ssl:handshake:verbose");
```

Or via environment before launch:

```bash
export JAVA_TOOL_OPTIONS="-Djavax.net.debug=ssl:handshake:verbose"
```

**Less noisy alternative — Log4j targeted loggers** in `log4j.properties` or `logback.xml`:

```properties
log4j.logger.org.apache.kafka.common.network.SslTransportLayer=DEBUG
log4j.logger.org.apache.kafka.common.security.ssl.SslFactory=DEBUG
log4j.logger.org.apache.kafka.common.security.authenticator.SaslClientAuthenticator=DEBUG
log4j.logger.org.apache.kafka.clients.NetworkClient=DEBUG
```

This gives you Kafka's view of the handshake (context about which node, which principal, which listener) without drowning in raw TLS byte dumps.

### B.7 — Network-Level Capture

When JVM debug shows handshake failure but doesn't clearly say why, a packet capture confirms what's actually on the wire:

```bash
tcpdump -i any -s 0 -w /tmp/kafka-ssl.pcap \
  'port 9093 and host broker0.kafka.example.internal'
```

Open in Wireshark, right-click the first packet → **Decode As → TLS**. Handshake messages are visible even without decryption.

**Smoking guns to look for:**

| Wire pattern | Likely cause |
|--------------|--------------|
| ClientHello → immediate fatal alert from server | No cipher in common, or server rejected SNI |
| ServerHello + Certificate → TCP RST from client | Client rejected the cert chain (check JVM debug for why) |
| Client never sends a second flight after CertificateRequest | Client keystore missing or unreadable |
| No ServerHello at all, just TCP handshake | Wrong port, LB in front doing non-TLS passthrough, or broker not actually listening on SSL |
| Retransmits and eventual timeout | Firewall / security group dropping after SYN-ACK |

### B.8 — One-Shot Diagnostic Bundle

When opening an L1-specific ticket or escalating internally, grab this set in one pass:

```bash
# JDK + crypto provider info
java -version 2> jdk.txt
java -XshowSettings:properties 2>&1 | grep -E 'security.provider|java.home|fips' > jdk-props.txt

# FIPS state
cat /proc/sys/crypto/fips_enabled > fips.txt
grep -i fips /var/log/messages | tail -20 > fips-messages.txt 2>/dev/null

# Effective config
cp /etc/kafka/server.properties kafka-config.txt
grep -E '^(listeners|ssl\.|security|inter)' kafka-config.txt > kafka-ssl-config.txt

# Cert chain (broker side)
keytool -list -v -keystore /etc/kafka/ssl/broker0.keystore.p12 \
  -storetype PKCS12 -storepass $KS_PASS > keystore-dump.txt

# Handshake log already produced via KAFKA_OPTS above

# Packet capture sample
timeout 30 tcpdump -i any -s 0 -w kafka-ssl.pcap 'port 9093' &
# trigger the failure, then kill the tcpdump

tar czf l1-ssl-diag-$(date +%Y%m%d-%H%M).tgz \
  jdk*.txt fips*.txt kafka*.txt keystore-dump.txt *.pcap *.log
```

That bundle is usually enough to get a support engineer past the first three rounds of "can you send us…".

## When to Use

- TLS handshake failing somewhere in the stack and you need to localize the failure to a specific component before tuning
- Reproducing a customer-reported issue and wanting the cleanest possible diagnostic bundle to attach to a ticket
- Routine pre-cutover validation of mTLS across SR, Connect, C3 before opening to clients
- LinuxONE / IBM Semeru bring-up where cipher / FIPS / PKCS12 quirks need to be ruled in or out fast
- Building runbooks for the L1 on-call who'll be paged at 3am with a broken handshake somewhere

## Caveats

- **`javax.net.debug=ssl:handshake:verbose` is loud.** Production-rate workloads can generate gigabytes per minute. Enable only during reproduction; switch to the Log4j targeted-logger alternative for steady-state.
- **JVM-only.** None of this catches issues in non-JVM clients (librdkafka, Go, Rust). For those, lean harder on the openssl + tcpdump steps in B.1 and B.7.
- **`*_OPTS` injection point varies by packaging.** The variable name is right; *where* you set it (systemd unit drop-in, `/etc/sysconfig/kafka`, container env) depends on how the component was installed. Confirm the systemd unit picks it up before assuming the flag didn't land.
- **Don't mix top-level `ssl.*` and per-subsystem `producer.ssl.*` / `consumer.ssl.*` / `admin.ssl.*` half-and-half on Connect.** All-or-nothing is the only sane operational shape.
- **Property name asymmetry is real.** Brokers: `ssl.client.auth=required`. SR + Connect REST: `ssl.client.authentication=REQUIRED`. Don't copy-paste blindly.
- **FIPS hosts will reject some of this verbatim.** Cipher pinning, PKCS12 MAC algorithms, and provider order all shift under FIPS — see [linuxone-jdk-tls-gotchas](../concepts/linuxone-jdk-tls-gotchas.md) before debugging on LinuxONE.

## Related

- [CP mTLS Self-Signed Setup](cp-mtls-self-signed-setup.md) — the canonical setup procedure this pattern debugs against
- [LinuxONE JDK/TLS Gotchas](../concepts/linuxone-jdk-tls-gotchas.md) — IBM Semeru / FIPS / s390x specific failure modes
- [Schema Registry Best Practices](../concepts/schema-registry-best-practices.md) — production SR posture beyond TLS
- [Kafka Connect Deployment Models](connect-deployment-models.md) — when SSL config lives where across CC / CFK / self-managed

---

*MCP-validated against Confluent docs (Connect security, SR config, C3 config) on 2026-05-27: confirmed `producer.ssl.*` / `consumer.ssl.*` / `admin.ssl.*` per-subsystem overrides, `listeners.https.*` REST-API SSL override, `kafkastore.ssl.*` vs REST-tier `ssl.*` split on SR, C3 namespaces `confluent.controlcenter.streams.ssl.*` / `confluent.controlcenter.connect.<name>.*` / `confluent.controlcenter.ksql.*` / `confluent.controlcenter.schema.registry.*`. Two inline ⚠️ unverified markers retained on `SCHEMA_REGISTRY_OPTS` / `CONTROL_CENTER_OPTS` env var names and the `confluent.monitoring.interceptor.*` namespace — operational convention rather than doc-cited.*
