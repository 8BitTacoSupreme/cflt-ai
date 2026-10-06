# Confluent Platform mTLS Provisioning — Ansible

End-to-end Ansible playbooks for minting a self-signed CA, provisioning per-broker and per-client certs, building PKCS12 keystores/truststores, and configuring Kafka brokers for mTLS. Written for LinuxONE / IBM JDK / FIPS targets but works on any x86/ARM Linux Kafka deployment.

Companion to `cp-mtls-self-signed-setup.md` / `.docx` — those cover the manual / conceptual walkthrough. This automates §1–§6 of that guide.

## Design

- **Private keys never cross the wire.** Brokers and clients generate their own keys and CSRs locally. Only CSRs (→ CA host) and signed certs (→ target host) travel.
- **CA lives on its own host** (`cert_authority` group) — can be offline or airgapped, just needs an Ansible run from the controller.
- **Declarative with `community.crypto`** for cert operations; idempotent by default.
- **Keystore assembly happens on the target host**, using the target's Python + openssl. On LinuxONE this means the OS FIPS posture and JDK-adjacent crypto libraries are honored, avoiding the "minted on x86, broken on s390x" trap.
- **Secrets in ansible-vault**, never in plaintext group_vars.

## Directory layout

```
ansible-mtls/
├── README.md                        ← you are here
├── ansible.cfg
├── requirements.yml                 ← collection deps (community.crypto, ansible.posix)
├── site.yml                         ← runs all playbooks in order
├── inventory/
│   └── hosts.yml.example            ← copy to hosts.yml, fill in
├── group_vars/
│   ├── all.yml                      ← non-secret config
│   └── vault.yml.example            ← copy to vault.yml, encrypt with ansible-vault
├── playbooks/
│   ├── 01-generate-ca.yml
│   ├── 02-provision-broker-certs.yml
│   ├── 03-provision-client-certs.yml
│   ├── 04-configure-mtls.yml
│   └── 99-verify-mtls.yml
├── roles/
│   ├── kafka_ca/                    ← mints root CA on cert_authority host
│   ├── kafka_broker_cert/           ← per-broker key + CSR + signed cert + PKCS12 keystore
│   ├── kafka_client_cert/           ← per-client equivalent
│   ├── kafka_truststore/            ← CA truststore on every host
│   └── kafka_ssl_config/            ← renders SSL block into server.properties
└── files/
    ├── csrs/                        ← fetched CSRs (temp staging, safe to commit empty)
    ├── signed/                      ← fetched signed certs (temp staging)
    └── clients/                     ← fetched client cert bundles for distribution
```

## Assumptions (adjust as needed)

These are defaults; adjust paths to match your layout. If you have existing conventions in the repo for any of these, override them before running.

| Assumption | Where it lives | Change it if… |
|---|---|---|
| Kafka user/group is `cp-kafka:confluent` | `group_vars/all.yml` → `kafka_ssl_owner`/`kafka_ssl_group` | you use a different install (e.g., Cloudera, self-compiled) |
| SSL files land in `/etc/kafka/ssl` | `group_vars/all.yml` → `kafka_ssl_dir` | your installer uses a different path |
| `server.properties` is at `/etc/kafka/server.properties` | `group_vars/all.yml` → `kafka_server_properties` | you're on CP-for-K8s or use a wrapper |
| Brokers in inventory group `kafka_brokers`, clients in `kafka_clients`, CA in `cert_authority` | `inventory/hosts.yml.example` | your inventory uses different group names |
| Kafka service name for restart handler is `confluent-kafka` | `roles/kafka_ssl_config/handlers/main.yml` | you wrap it in a different systemd unit |
| SSL block goes into an existing `server.properties` via `blockinfile` | `roles/kafka_ssl_config/tasks/main.yml` | you generate the whole file from a template in your existing roles |

## Quickstart

```bash
# 1. Install collection dependencies
ansible-galaxy collection install -r requirements.yml

# 2. Copy and edit inventory
cp inventory/hosts.yml.example inventory/hosts.yml
$EDITOR inventory/hosts.yml

# 3. Copy and encrypt vault
cp group_vars/vault.yml.example group_vars/vault.yml
$EDITOR group_vars/vault.yml            # replace the placeholder passphrases
ansible-vault encrypt group_vars/vault.yml

# 4. (Optional) Review non-secret defaults
$EDITOR group_vars/all.yml

# 5. Run the whole sequence
ansible-playbook --ask-vault-pass site.yml

# or step-by-step
ansible-playbook --ask-vault-pass playbooks/01-generate-ca.yml
ansible-playbook --ask-vault-pass playbooks/02-provision-broker-certs.yml
ansible-playbook --ask-vault-pass playbooks/03-provision-client-certs.yml
ansible-playbook --ask-vault-pass playbooks/04-configure-mtls.yml
ansible-playbook --ask-vault-pass playbooks/99-verify-mtls.yml
```

## Run order and what each playbook does

1. **`01-generate-ca.yml`** — on `cert_authority`: generates the CA private key, CSR, self-signed cert. CA cert is fetched to `files/ca-cert.pem` on the controller for distribution. CA private key stays on the CA host only.
2. **`02-provision-broker-certs.yml`** — per broker: generates private key + CSR locally → CSR fetched to controller → shipped to CA host → CA signs → signed cert fetched back → shipped to broker → broker assembles PKCS12 keystore with key + signed cert + CA chain. Also installs the truststore.
3. **`03-provision-client-certs.yml`** — same flow as brokers, for each host in `kafka_clients`. CN is `client_cn` from host vars (used for ACL principal mapping).
4. **`04-configure-mtls.yml`** — renders the SSL config block into `server.properties` on each broker using `blockinfile` so it coexists with existing config. Restart via handler.
5. **`99-verify-mtls.yml`** — runs `openssl s_client` and `kafka-broker-api-versions` against each broker to confirm the handshake works end-to-end.

## Integration with an existing repo

If you already have Kafka provisioning roles in `fsi-dsp/ansible`, the likely integration points are:

- **Inventory**: reuse existing `kafka_brokers` group definitions; just add a `cert_authority` group if it's not already there.
- **Service restart**: swap `roles/kafka_ssl_config/handlers/main.yml` to use whatever handler name your existing Kafka role exposes (e.g., `restart confluent-kafka` or a role-scoped handler).
- **`server.properties` management**: if your existing role templates the whole file, drop `roles/kafka_ssl_config` and instead merge `roles/kafka_ssl_config/templates/ssl-block.properties.j2` into that template.
- **Role namespacing**: rename roles to match your convention (`goodlabs.kafka.ca`, `fsi_dsp_kafka_ca`, etc.) — current names are unprefixed for portability.

## Idempotency notes

- `community.crypto.openssl_privatekey` and `x509_certificate` check file presence + validity before regenerating. Re-running the playbook won't churn certs.
- `community.crypto.openssl_pkcs12` rebuilds the keystore only if source files changed or passphrase differs.
- The SSL block in `server.properties` uses `blockinfile` with a stable marker; re-runs update the block in place.
- **Cert rotation** is manual for now: delete the broker cert on the target (`/etc/kafka/ssl/<broker>-cert.pem`) and re-run `02-provision-broker-certs.yml`. A scheduled rotation playbook is a reasonable next step.

## Safety rails

- CA private key on cert_authority host: mode `0400`, owner `root`. Never fetched back to controller.
- Broker private keys: mode `0400`, owner `cp-kafka`. Never fetched.
- All passphrases come from `group_vars/vault.yml` which must be encrypted.
- `files/csrs/` and `files/signed/` on the controller are staging only — safe to commit empty, but `.gitignore` excludes actual CSR/cert files from being committed accidentally.

## Known limitations

- **No HSM / PKCS#11 support.** If CEX cards must back broker keys, this playbook is software-keys only. PKCS#11 requires a separate path (custom `java.security` + `ssl.keystore.type=PKCS11`) that's outside Ansible's normal cert lifecycle.
- **CP components beyond brokers** (Schema Registry, Connect, ksqlDB, Control Center) aren't in scope here. The cert generation pattern is identical — add groups to inventory and parameterize the role.
- **Cluster rollout strategy** for `04-configure-mtls.yml` is `serial: 1` with a restart handler. For large clusters, adjust `serial` and add a health check between brokers.
- **No automatic cert expiry monitoring.** Wire Prometheus/Alertmanager (or whatever monitoring stack you use) to scrape cert expiry separately.

## When it fails

Enable verbose Ansible output and JVM TLS debug on the target broker at the same time:

```bash
ansible-playbook -vvv --ask-vault-pass playbooks/99-verify-mtls.yml
```

Cross-reference failures against Appendix B of `cp-mtls-self-signed-setup.md` — the debug capture steps there apply directly to any failure surface this playbook can produce.
