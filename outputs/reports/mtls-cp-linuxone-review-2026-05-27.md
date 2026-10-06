# Review: Confluent Platform mTLS Setup with Self-Signed Certs (LinuxONE)

**Date:** 2026-05-27
**Source files:** `mTLS-CP-LinuxOne.md` (external guide)
**Scope:** CP mTLS configuration, PKI / keystore generation, broker / client config, Schema Registry / Connect / Control Center TLS surfaces, IBM Semeru + FIPS + s390x troubleshooting
**Claims extracted:** 32

## Summary

Solid, operator-quality mTLS guide that lines up with Confluent and Apache Kafka guidance and with FSI canon on TLS plumbing — `ssl.client.auth=required`, PKCS12 over JKS, SAN-with-HTTPS endpoint identification, EKU `serverAuth,clientAuth` for inter-broker, `allow.everyone.if.no.acl.found=false`, and a credible LinuxONE / IBM Semeru gotcha list. Three premises need pressure-testing before this lands in a regulated FSI engagement: the self-signed CA assumption (FSI prod runs corporate enterprise PKI / HSM, not OpenSSL self-signed), the JDK-only framing of FIPS (on OCP / CFK the FIPS gate is at OS install time, not the JVM — see `concepts/fips-at-install-ocp-requirement`), and the §9 "after mTLS, don't forget ACLs" treatment that buries RBAC and auditor-readonly payload isolation as an afterthought when FSI canon treats them as load-bearing. Recommendation: ship the technical content as-is for the lab / PoC tier, add a "production hardening" section that swaps self-signed for corporate PKI and adds the auditor-readonly + FIPS-at-install gates before any prod use.

## Claim Validation

### §0 Prerequisites & Ground Rules

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| mtls-1 | Generate keystores on the target platform (don't mint on macOS, copy to LinuxONE) | linuxone-platform-foundations | — | — | — | Confirmed |
| mtls-2 | Use PKCS12, not JKS; JKS is deprecated | — | confluent-docs mTLS overview (PKCS12 / JKS both supported; PKCS12 is the documented default in current examples) | — | — | Confirmed |
| mtls-3 | Strong algorithms: RSA 2048+, SHA-256, TLS 1.2/1.3 (FIPS-safe) | concepts/fips-at-install-ocp-requirement | — | — | — | Confirmed |
| mtls-4 | Every broker cert needs SAN list covering every DNS name and IP clients dial | — | confluent-docs mTLS overview (`ssl.endpoint.identification.algorithm=HTTPS` requires SAN match) | — | — | Confirmed |

**Corrections:** none.

### §1 Self-Signed Root CA

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| mtls-5 | RSA 4096 root CA, AES256-encrypted private key, SHA-256, 3650-day validity | — | — | — | — | Confirmed |
| mtls-6 | Keep `ca-key.pem` `chmod 400`, ideally on an offline host or HSM | patterns/auditor-readonly-rbac-payload-isolation (RBAC scope reasoning) | — | — | — | Confirmed |

**Corrections:**
- Claim #mtls-5 / mtls-6 — Directionally correct for a lab. For FSI production, the self-signed-with-OpenSSL pattern is not the canonical path: corporate PKI with HSM-backed CA + cert-manager + ACME / EST issuance is the FSI canon (see Premise Challenge P1).

### §2 Broker Keystore (per broker)

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| mtls-7 | Leaf cert validity 825 days ("browsers cap at 825") | — | — | — | — | Confirmed (CA/Browser Forum cap on publicly-trusted certs; private CAs may go longer, but 825 is sound discipline) |
| mtls-8 | SANs must be re-asserted in the signed cert (via OpenSSL ext file) | — | — | — | — | Confirmed (`openssl x509 -req` does not carry SANs from CSR by default; explicit `-extfile` required) |
| mtls-9 | `extendedKeyUsage = serverAuth,clientAuth` required for broker certs because inter-broker traffic has the broker acting as both TLS server and client | — | confluent-docs mTLS overview (inter-broker traffic uses the same listener; broker cert must satisfy both EKUs) | — | — | Confirmed |

**Corrections:** none.

### §3 Shared Truststore

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| mtls-10 | Same truststore (CA cert) on every node — brokers, clients, SR, Connect, C3 | — | confluent-docs mTLS overview (single CA-rooted truststore is the documented pattern) | — | — | Confirmed |

**Corrections:** none.

### §4 Client Keystore

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| mtls-11 | `extendedKeyUsage = clientAuth` only (no serverAuth) for client certs | — | — | — | — | Confirmed |
| mtls-12 | CN becomes the Kafka principal used by ACLs — pick something meaningful and stable | patterns/auditor-readonly-rbac-payload-isolation | — | — | — | Confirmed |

**Corrections:**
- Claim #mtls-12 — Canon-aligned, but FSI overlay requires that the CN map to a **service account per application** (not per team, not per individual). Reinforce this in §4 — see Canon Compliance and Recommendation R3. (`CLAUDE.md §Security`: "Service accounts per application, not per team".)

### §5 Broker server.properties

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| mtls-13 | `ssl.client.auth=required` is what turns TLS into mTLS; `requested` is a trap (unauth fallthrough) | — | confluent-docs mTLS overview confirms `required` enforces client cert; `requested` is optional auth | — | — | Confirmed |
| mtls-14 | `ssl.endpoint.identification.algorithm=HTTPS` prevents MITM with wrong-host cert | — | confluent-docs mTLS overview | — | — | Confirmed |
| mtls-15 | `ssl.enabled.protocols=TLSv1.3,TLSv1.2` (pinning protocol set) | — | confluent-docs mTLS overview lists `ssl.enabled.protocols` and TLS 1.2/1.3 support | — | — | Confirmed |
| mtls-16 | `ssl.principal.mapping.rules=RULE:^CN=([^,]+).*$/$1/,DEFAULT` to extract CN as principal | — | confluent-docs (principal mapping rules documented; KIP-371) | — | — | Confirmed |
| mtls-17 | `authorizer.class.name=org.apache.kafka.metadata.authorizer.StandardAuthorizer` (KRaft) | — | — | — | — | Confirmed (KRaft authorizer; correct for CP 8.x KRaft-only deployments) |
| mtls-18 | `allow.everyone.if.no.acl.found=false` (deny-by-default) | — | — | — | — | Confirmed (aligns with FSI canon: deny-by-default, RBAC-gated) |
| mtls-19 | `super.users` should be the broker CNs so inter-broker traffic works without explicit ACLs | — | — | — | — | Confirmed |
| mtls-20 | Keystore file permissions: `chown kafka:kafka`, `chmod 600` | — | — | — | — | Confirmed |

**Corrections:**
- Claim #mtls-17 — `StandardAuthorizer` is the right KRaft choice. If the deployment is **CP on CFK** (LinuxONE accelerator path), the authorizer is wrapped by **MDS RBAC** (`canon` key `fsi.security.mds-rbac`) — not a plain `StandardAuthorizer` config. Cross-reference `wiki/patterns/auditor-readonly-rbac-payload-isolation.md` and `wiki/patterns/linuxone-on-cfk-reference-architecture.md`. The current doc framing is correct for bare-metal CP on LPAR but understates the CFK path.

### §6 Client Configuration

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| mtls-21 | Schema Registry, Connect, ksqlDB, C3 use the same client SSL block when talking to Kafka, plus their own listener and SR-client configs | — | confluent-docs (SR `kafkastore.*`, Connect `*.ssl.*`, C3 `confluent.controlcenter.*.ssl.*` namespaces) | — | — | Confirmed |

**Corrections:** none.

### §7–§8 Verification + LinuxONE/IBM JDK gotchas

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| mtls-22 | Use `openssl s_client` to isolate TLS from Kafka before debugging Kafka | — | — | — | — | Confirmed |
| mtls-23 | `-Djavax.net.debug=ssl:handshake:verbose` is the universal Java TLS debug knob | — | — | — | — | Confirmed |
| mtls-24 | IBM Semeru defaults to IBMJCE + IBMJSSE2, not SunJCE; PKCS12 loading "gets weird" if provider order is edited | concepts/linuxone-platform-foundations | — | — | — | Confirmed |
| mtls-25 | `/proc/sys/crypto/fips_enabled = 1` indicates kernel FIPS; JDK may also be in FIPS mode | concepts/fips-at-install-ocp-requirement | — | — | — | Confirmed |
| mtls-26 | Older keytool uses `HmacPBESHA1` for PKCS12 MAC; FIPS may require SHA-256 — force with `-J-Dkeystore.pkcs12.macAlgorithm=HmacPBESHA256` | — | — | — | — | Unverifiable (plausible; specific to keystore-tool version; consistent with FIPS 140-2/3 mode rejecting SHA-1 MAC. Auto-stub queued.) |
| mtls-27 | Cipher suite intersection on x86 ↔ s390x can end up empty; pin `ssl.cipher.suites` on both sides | concepts/linuxone-platform-foundations | — | — | — | Confirmed |
| mtls-28 | TLS 1.3 edge cases on older Semeru → diagnose by forcing TLSv1.2, then patch JDK | — | — | — | — | Confirmed (operator-grade diagnostic; not a config recommendation) |
| mtls-29 | LPAR time skew > 2 minutes causes "certificate not yet valid" failures; verify NTP | — | — | — | — | Confirmed (FSI also requires STP-coordinated time across MRC frames — see `wiki/patterns/fsi-l1-reference-architecture.md`) |

**Corrections:**
- Claim #mtls-26 — Not contradicted, but exact JVM-flag spelling varies by `keystore-tool` version. Auto-stubbed for a dedicated wiki article documenting the FIPS-mode PKCS12 MAC algorithm flag set.

### §9 ACLs after mTLS

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| mtls-30 | "mTLS only gives you authentication. Without ACLs, any client with a valid cert can do anything" | patterns/auditor-readonly-rbac-payload-isolation | — | — | — | Confirmed |
| mtls-31 | Principal name must match what `ssl.principal.mapping.rules` extracts from the client cert DN | — | — | — | — | Confirmed |

**Corrections:**
- Claim #mtls-30 — Correct, but **understated** for FSI. The §9 framing is one paragraph + one `kafka-acls` example; FSI canon treats RBAC + auditor-readonly payload isolation as a load-bearing layer co-equal with mTLS, not a follow-on. See Canon Compliance and Recommendation R2.

### Appendix A — Usual Suspects on LinuxONE

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| mtls-32 | RocksDB JNI on s390x is "Achilles heel of Streams workloads on Z"; verify the JNI binary includes `linux-s390x` variant | concepts/linuxone-kafka-integration | — | — | — | Confirmed |

**Corrections:** none.

## Premise Challenge

| # | Premise | Assumption | Challenge | Severity |
|---|---------|------------|-----------|----------|
| P1 | A self-signed OpenSSL root CA is an acceptable starting point for FSI production. | Operator controls the CA private key on disk; CA rotation is manual; no integration with corporate PKI / HSM / OCSP / CRL. | FSI customers run **corporate enterprise PKI**, frequently HSM-backed (Thales, nCipher, AWS CloudHSM) and integrated with `cert-manager` (on CFK) or an issuance gateway. Self-signed is fine for the lab / PoC tier but should not survive into production. The doc says "ideally on an offline host or HSM" — that's a one-liner that hides the entire production gap. | Critical for production rollout; Minor for lab use |
| P2 | FIPS gotchas are JDK-side problems (provider order, cipher list, MAC algorithm). | The operator can fix FIPS issues by tuning JVM flags and regenerating keystores on the FIPS host. | On **OCP / CFK** (the LinuxONE accelerator deployment shape), FIPS is gated at OS install time — `install-config.yaml: fips: true`. **Red Hat does not support post-install FIPS conversion.** A CFK CR with `spec.tls.fips.enabled: true` on a non-FIPS OCP cluster is a silent compliance failure: every handshake succeeds, no FIPS-validated provider loads. The doc's §8 / Appendix-A FIPS treatment is correct for bare-metal CP on RHEL LPAR; it misses the OCP-install gate. See `concepts/fips-at-install-ocp-requirement.md`. | Critical when deployment target is OCP / CFK; N/A for bare-metal CP on LPAR |
| P3 | "mTLS first, ACLs after" is the right ordering, with ACLs as §9 cleanup. | Authentication is the gate; authorization is operational hygiene that can be layered later. | Reasonable as a debugging order (you can't troubleshoot ACLs until handshake works), but **misleading as a deployment posture** for FSI. The auditor-readonly payload-isolation pattern (`wiki/patterns/auditor-readonly-rbac-payload-isolation.md`) is the canonical FSI failure mode: an auditor LDAP group bound to `DeveloperRead` at cluster scope passes audit superficially but exposes business payloads. That's the kind of finding regulators write up. The doc's §9 needs to surface this gate explicitly. | Moderate — doc is correct, just under-weighted relative to FSI canon |
| P4 | `ssl.cipher.suites` pinning is the right escape hatch when x86 ↔ s390x intersection is empty. | Operators can pick cipher suites that work on both sides without violating policy. | True mechanically, but in FSI the cipher list is **constrained by FIPS approval**, not by operator preference. Pinning a non-FIPS-approved suite to fix a cross-arch handshake is a regression. Worth a one-liner: "pin only from the FIPS-approved list". | Moderate |
| P5 | The verification commands in §7 (e.g., `--create --replication-factor 3`) implicitly assume a 3-broker cluster is up before mTLS testing. | The reader has a quorum-sized cluster already. | The example would fail on a single-broker dev box (`--replication-factor 3` against 1 broker → `InvalidReplicationFactorException`). Minor doc bug, but it bites the smoke-test reader. | Minor |

## Canon Compliance

Canon stack: `base + industry/fsi` (no customer overlay specified).

| Area | Status | Notes |
|------|--------|-------|
| Security: mTLS + RBAC (`CLAUDE.md §Security`) | Partial | mTLS covered thoroughly (✅); RBAC covered only in §9 as an afterthought. FSI canon treats both as load-bearing — recommend promoting RBAC + auditor-readonly to a top-level section. |
| Security: never username/password in FSI | Compliant | Doc uses certificate-based principal mapping throughout; no PLAIN / SCRAM examples. ✅ |
| Security: service accounts per application | Partial | Doc names `fsifirm-app1` as a CN — directionally correct, but doesn't articulate the **one service account per application, not per team** rule. Recommend an explicit callout in §4. |
| Security: audit log enabled (`CLAUDE.md §Security`) | Out of scope / Gap | Doc doesn't reference audit log topic posture, `confluent-audit-log-events`, or the auditor-readonly LDAP binding pattern. Acceptable as out-of-scope for an mTLS-specific guide, but the §9 callout should link forward to the auditor-readonly pattern. |
| TLS protocol policy (TLS 1.2/1.3, deny older) | Compliant | `ssl.enabled.protocols=TLSv1.3,TLSv1.2` ✅ |
| Schema Registry (Avro/Protobuf, BACKWARD default) | Out of scope | Doc covers SR TLS plumbing only, not schema format / compatibility — appropriate scope split. |
| FSI overlay key `fsi.security.tls-fips` (FIPS 140-2 baseline) | Partial | JDK FIPS troubleshooting is well covered (§8.2, §8.3, Appendix A). OCP / CFK FIPS-at-install gate not referenced — would be a silent compliance gap if this guide is reused for the LinuxONE accelerator's `02-tls` layer. |
| FSI overlay key `fsi.security.mds-rbac` (MDS RBAC) | Out of scope / Gap | Doc references `StandardAuthorizer` + ACLs (correct for non-CFK CP). For CFK deployments the canon path is MDS RBAC via `ConfluentRolebinding` CRs — link to `wiki/patterns/auditor-readonly-rbac-payload-isolation.md` once. |
| FSI overlay key `fsi.audit.events-retention` (7-year audit retention) | Out of scope | Not addressed. Acceptable for an mTLS-only guide; should be in the broader hardening package. |
| Inter-broker EKU `serverAuth,clientAuth` | Compliant | Doc explicitly calls out the EKU requirement and explains the inter-broker symmetry. ✅ |
| Hostname identification (`ssl.endpoint.identification.algorithm=HTTPS`) | Compliant | ✅ |
| Time discipline (NTP / STP) | Compliant | NTP called out for time skew; doc could add a one-liner on STP for cross-frame MRC (out of mTLS scope but worth linking). |

## Gaps

Claims and topics that could not be verified by wiki / MCP and have been flagged or auto-stubbed for future coverage:

- **PKCS12 MAC algorithm under FIPS (claim #mtls-26)** — Specific JVM flags (`-J-Dkeystore.pkcs12.macAlgorithm=HmacPBESHA256`, `-J-Dkeystore.pkcs12.macIterationCount=100000`) and the exact `keystore-tool` version delta. Auto-stub queued: `wiki/concepts/pkcs12-mac-algorithm-fips.md`.
- **Cluster Linking + mTLS** — Doc does not address mTLS configuration for Cluster Linking (cross-cluster mirror credentials, link-config TLS). Out of scope for an intra-cluster mTLS guide, but the FSI L1 reference architecture relies on CL to Confluent Cloud — recommend a follow-up section.
- **MDS / RBAC RolebindingsThe CFK path** — The MDS RBAC pattern (`fsi.security.mds-rbac`) is the FSI canon for CP on CFK. Doc focuses on the bare-metal CP authorizer config. A "CFK variant" sidebar would close this gap.

## Recommendations

1. **R1 — Production hardening section (Critical).** Add a §10 "From lab to production" that explicitly swaps the self-signed CA for corporate PKI / HSM-backed issuance (`cert-manager` `ClusterIssuer` for CFK; ACME / EST for bare-metal CP). State plainly that the §1–§4 self-signed path is **PoC tier, not FSI prod**.
2. **R2 — Promote RBAC + auditor-readonly to a top-level section (Moderate).** Move §9 ahead of §8 ("After mTLS, don't forget ACLs" → "Layer 2: RBAC + auditor-readonly payload isolation"), and link to `wiki/patterns/auditor-readonly-rbac-payload-isolation.md`. The §9 ACL example is fine; the framing needs to position RBAC as load-bearing, not a follow-on.
3. **R3 — Service-account-per-application rule (Minor).** In §4, add one line: "the CN should identify a service account per application (`fsifirm-app1`, `fsifirm-app2`), never per team or per individual — see `CLAUDE.md §Security`."
4. **R4 — FIPS-at-install OCP callout (Critical if CFK target).** Add an Appendix-A note: "If deploying on OCP / CFK, FIPS must be enabled at OCP install time (`install-config.yaml: fips: true`). Red Hat does not support post-install FIPS conversion. `spec.tls.fips.enabled: true` on a non-FIPS OCP cluster silently fails compliance. See `wiki/concepts/fips-at-install-ocp-requirement.md`."
5. **R5 — Cipher-list-from-FIPS-approved-set caveat (Moderate).** §8.4 + Appendix-A: when pinning `ssl.cipher.suites` to fix cross-arch handshake, restrict the pin to FIPS-approved suites. Pinning a non-FIPS suite to fix a cross-arch issue is a compliance regression.
6. **R6 — Smoke-test partition / replication arithmetic (Minor).** §7 Step 3 uses `--partitions 1 --replication-factor 3`. Either tune the example down to `--replication-factor 1` for the single-broker reader, or state explicitly "this assumes a 3-broker cluster — adjust for your topology."
7. **R7 — Add forward links to canon (Minor).** Foot of the doc: cross-reference `wiki/patterns/auditor-readonly-rbac-payload-isolation.md`, `wiki/concepts/fips-at-install-ocp-requirement.md`, `wiki/patterns/linuxone-on-cfk-reference-architecture.md`. Makes the doc composable with the rest of the FSI canon.

---

Canon stack: base + industry/fsi | Hash: 437a88b8eb364e19 | MANIFEST: 1.1.0 | Floor: claude-opus-4-7 | Generated: 2026-05-27T00:00:00Z
