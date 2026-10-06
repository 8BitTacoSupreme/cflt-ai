---
title: Flink COE — Security (RBAC, Service Accounts, Principals)
tags: [flink, confluent-cloud, coe, security, rbac, service-accounts, mtls, fsi, stub]
sources:
  - https://docs.confluent.io/cloud/current/flink/operate-and-deploy/flink-rbac.html
  - raw/repos/fsi-dsp/accelerators/confluent-on-linuxone/layers/05-flink/rolebindings
  - outputs/reports/flink-confluent-cloud-setup-privatelink-architecture.md
related: [patterns/flink-coe-managed-cc-overview, patterns/flink-coe-aws-privatelink-refarch, patterns/fsi-governance-automation, patterns/auditor-readonly-rbac-payload-isolation]
confidence: low
last_updated: 2026-07-30
last_validated: 2026-07-30
---

# Flink COE — Security (RBAC, Service Accounts, Principals)

> ⚠️ Stub — seeded with validated facts; expand per use case once chosen. The RBAC role catalog and the service-account-principal model are the load-bearing pieces to get right before any regulated data flows.

## Summary

<!-- Used verbatim in _index.md -->
Security sub-page for the [Flink COE](flink-coe-managed-cc-overview.md). CC Flink needs **two role planes** — control-plane (Flink) roles to submit/manage statements *and* data-plane (Kafka/SR) roles for the topics and subjects a statement touches. Production statements must run **as service accounts, not users**. For FSI, bind roles to IdP groups, not individuals, and treat statement authorship as change-controlled.

## Pattern

### Two role planes (CC — seed, validate before production commit)

Users need **both** planes; missing either fails at submit or at first topic access.

**Control-plane (Flink) roles:**

| Role | Grants |
|---|---|
| `FlinkDeveloper` | Create/run statements, manage workspaces (scope: env or pool) |
| `FlinkAdmin` | FlinkDeveloper + manage compute pools |
| `FlinkFunctionDeveloper` | UDF artifacts + external connectivity |
| `Assigner` (on the SA) | Delegate statement execution to a service account — the role that lets a human submit statements that **run as** the SA |
| `Operator` | Metadata access to tables/DBs/catalogs |

**Data-plane (Kafka/SR) roles the statement's principal needs:**
- `DeveloperRead` on **source** topics
- `DeveloperWrite` on **sink** topics
- Both on `Transactional-Id` prefix `_confluent-flink_*` (EOS sinks)
- `DeveloperRead` on source **SR subjects**; `DeveloperWrite` on sink SR subjects — **required**, because the avro-confluent format defaults to `auto-register-schemas=true`; without sink-subject write the job gets **403 → CrashLoopBackOff** (concrete gotcha).

### Service-account principal model

- **Bind production statements to service accounts, not user accounts** — prevents disruption when a user's status changes. The `Assigner` role on the SA is what enables human-submitted-runs-as-SA.
- **Terraform:** a `confluent_flink_statement` must have a principal — `flink_principal_id` on the provider (or `FLINK_PRINCIPAL_ID`) or a `principal {}` block on the resource. Omitting it fails with `one of provider.flink principal id … must be set`. (See [Overview](flink-coe-managed-cc-overview.md) blockers.)
- **`DROP TABLE` deletes the underlying topic + data** — withhold table-drop from developer roles; change-control any drop.

### CMF / CP contrast (for your organization's self-managed comparison)

- CMF roles: `FlinkDeveloper` (submit/run + own workspaces), `FlinkAdmin` (full env admin + pools), `Operator` (metadata-only). **`FlinkEnvironmentAdmin` is NOT a real role** — a doc inconsistency in some materials; use `FlinkDeveloper`.
- FSI RBAC shape (`fsi-dsp` layer 05): bind to **LDAP/IdP groups, never individuals** (revocation via group membership → SOX/FFIEC access-change logging); scope to the Flink environment, not cluster-wide; four separate bindings (source read, sink write+txn, SR read, SR write) for independent auditability.
- **mTLS** on self-managed: job Kafka identity = certificate CN/SAN matching the SA in MDS, signed by the shared `confluent-ca-issuer` (no new PKI). CC uses API keys / OAuth / mTLS to the managed endpoints instead.
- **Checkpoint state encryption** (CMF): `state.checkpoints.dir` must be an encrypted StorageClass or S3/GCS SSE-KMS — unencrypted checkpoint state may hold txn amounts/account numbers = PCI-DSS 3.4 / GLBA finding. (Not applicable on CC — checkpoints are managed.)
- Flink topic access is **auto-audited** — `ConfluentServerAuthorizer` emits authz events to `confluent-audit-log-events` on every access (see [Audit Log SIEM Integration](audit-log-siem-integration.md)).

## Caveats

- CC and CMF role catalogs overlap in name but differ in scope — don't assume a CMF binding maps 1:1 to CC.
- <!-- TODO: field-level encryption / CSFLE for Flink, tag-based data governance, per-use-case least-privilege bindings once workloads chosen -->

## Related

- [Flink COE — Overview](flink-coe-managed-cc-overview.md)
- [Flink COE — AWS PrivateLink Reference Architecture](flink-coe-aws-privatelink-refarch.md) — network security boundary
- [FSI Governance Automation](fsi-governance-automation.md) — RBAC-as-code context
- [Auditor Read-Only RBAC & Payload Isolation](auditor-readonly-rbac-payload-isolation.md) — related least-privilege pattern
