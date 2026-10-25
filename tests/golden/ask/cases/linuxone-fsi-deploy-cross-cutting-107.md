---
id: linuxone-fsi-deploy-cross-cutting-107
query: "What are the FSI hardening controls in the LinuxONE Confluent accelerator?"
expected_route: wiki+mcp
floor_model: sonnet
tags: [linuxone, fsi, hardening, accelerator, cross-cutting, wiki-05]
required_claims:
  - "RBAC"
  - "mTLS"
  - "Schema Registry"
  - "audit"
  - "Flink"
forbidden_claims:
  - "I cannot help"
  - "no information"
---

## Case: Cross-cutting FSI hardening controls in the LinuxONE accelerator (WIKI-05)

**What the answer MUST contain:**
- RBAC (layer 01) — auditor-readonly payload isolation, 6 FSI roles, LDAP-group identity boundary
- mTLS (layer 02) — confluent-ca-issuer, TLS 1.2/1.3; no CP FIPS mode (not yet supported on s390x, G-02)
- Schema Registry governance (layer 03) — FULL_TRANSITIVE compatibility
- Audit logging (layer 04) — Connect-based SIEM shipping (Splunk Sink / HTTP Sink → Dynatrace)
- Flink (layer 05) — mTLS to brokers, encrypted checkpoint storage

**What the answer MUST NOT contain:**
- Refusal to answer about FSI hardening
- Suggestion that all layers are optional

**Negative-space trigger:** NO
