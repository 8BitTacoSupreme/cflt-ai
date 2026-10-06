---
title: Architecture Decision Records — Index
tags: [adr fsi architecture]
sources:
  - fsi-dsp://adr/001
  - fsi-dsp://adr/002
  - fsi-dsp://adr/003
  - fsi-dsp://adr/004
  - fsi-dsp://adr/005
  - fsi-dsp://adr/006
  - fsi-dsp://adr/007
  - fsi-dsp://adr/008
  - fsi-dsp://adr/009
related: [concepts/fsi-data-streaming-platform, concepts/sla-tiers, concepts/schema-evolution-strategies, patterns/fsi-governance-automation, patterns/dr-cluster-linking, patterns/dr-mirrormaker2, patterns/dr-multi-region-cluster, patterns/topic-naming]
confidence: high
last_updated: 2026-04-11
last_validated: 2026-04-28
---

# Architecture Decision Records — Index

## Summary

Eight illustrative reference ADRs capture the foundational architectural decisions for an FSI data streaming platform: serialization format (Avro), compatibility governance (tier-based), service discovery (Consul), connector deployment (self-managed on-prem), DR backend (Cluster Linking for CC), authentication (OAuth primary), topic naming convention, and DR tier classification.

## ADR Summary Table

| ADR | Title | Status | Key Decision |
|-----|-------|--------|-------------|
| 001 | Avro as default schema format | Accepted | Avro mandatory; Protobuf with platform-team approval; JSON Schema banned in prod |
| 002 | Compatibility modes by SLA tier | Accepted | critical/compliance → FULL_TRANSITIVE; standard → BACKWARD_TRANSITIVE; best-effort → BACKWARD |
| 003 | Consul for service discovery | Accepted | Single KV key flips Kafka + SR + Oracle endpoints atomically during DR |
| 004 | Self-managed Connect on-prem | Accepted | Connect workers co-located with Oracle for sub-ms JDBC latency |
| 005 | Cluster Linking over MRC | Accepted | CL for CC deployments (async, managed); MRC only for CP RPO=0 |
| 006 | OAuth vs API Keys | Accepted | OAUTHBEARER primary for CC; API keys as fallback and for Terraform provider |
| 007 | Topic naming convention | Accepted | `{domain}.{application}.{version}.{entity}` with dot separators |
| 008 | DR tier classification | Accepted | Four tiers with distinct RPO/RTO targets and DR backend selection per deployment model |

## Detail

### ADR-001: Avro as Default Schema Format

**Decision:** Apache Avro is the default for all FSI topics. Protobuf acceptable with platform-team approval for teams with existing infrastructure. JSON Schema not permitted in production.

**Rationale:** Compact binary serialization reduces CC costs. Strong financial logical types (decimal, timestamp-millis). FULL_TRANSITIVE compatibility well-defined in SR. First-class support across Connect, Flink SQL, TableFlow. Industry-dominant format in FSI Kafka deployments.

**Consequences:** Teams must learn Avro schema authoring (mitigated by reference schemas). Protobuf services need adapter or exception. Avro's lack of RPC definition is irrelevant (Kafka is the transport).

**Wiki links:** [Schema Evolution Strategies](concepts/schema-evolution-strategies.md)

---

### ADR-002: Compatibility Modes by SLA Tier

**Decision:** Compatibility mode derived from SLA tier automatically. `compatibility_override` variable exists for documented exceptions.

| Tier | Mode | Effect |
|------|------|--------|
| critical | FULL_TRANSITIVE | Add optional fields with defaults only |
| standard | BACKWARD_TRANSITIVE | Consumers upgrade before producers |
| best-effort | BACKWARD | Checks against latest version only |

Exception: OFAC topics use FULL_TRANSITIVE regardless of tier.

**Consequences:** Critical topics cannot have fields removed or types changed. Schema evolution for critical topics is limited to additive changes. Shift-left design is essential.

**Wiki links:** [Schema Evolution Strategies](concepts/schema-evolution-strategies.md), [SLA Tiers](concepts/sla-tiers.md)

---

### ADR-003: Consul for Service Discovery

**Decision:** HashiCorp Consul for all DR-sensitive endpoints. Single KV key (`fsi/kafka/active-region`) determines active region.

**Rationale:** Single KV update flips three endpoints atomically (vs. 3 DNS records). Health checks detect Oracle failover. Integrates with Vault for credential rotation. Configurable DNS TTL (down to 0). Reduces failover runbook from 17 steps to 6.

**Consequences:** Consul becomes HA dependency for DR. Connect workers and apps must resolve via Consul DNS. Same mechanism works for Oracle, Neo4j, and future databases.

**Wiki links:** [DR — Cluster Linking](patterns/dr-cluster-linking.md), [DR — MirrorMaker 2](patterns/dr-mirrormaker2.md)

---

### ADR-004: Self-Managed Connect On-Prem

**Decision:** Kafka Connect workers deployed on-premises next to Oracle, connecting to CC via PrivateLink.

**Rationale:** Co-location with Oracle for sub-ms JDBC latency (vs. 5-20ms through PrivateLink). Core-banking transaction throughput is latency-sensitive. On-prem workers use Consul for Oracle endpoint resolution during DR. Managed connectors on CC don't support data contract rules execution.

**Consequences:** Platform ops manages Connect health, upgrades, scaling. Distributed properties maintained for East and West bootstrap. DR includes connector pause/resume. JMX metrics exported to Dynatrace via OneAgent.

---

### ADR-005: Cluster Linking Over MRC

**Decision:** Cluster Linking between two CC dedicated clusters (East active, West passive DR). MRC documented as future-state option for CP.

**Rationale:** A typical ~2h RPO target easily met by CL (mirror lag typically seconds). CL is fully managed on CC. MRC requires CP (self-managed) contradicting CC adoption direction. Consul pattern reduces CL failover to 6 scripted steps. RTO bottleneck is Oracle DG (5-30 min), not Kafka.

**Consequences:** RPO > 0 (typically seconds, within 2h target). Failover not fully automatic (6 steps). If RPO tightens to zero, must migrate to CP + MRC. Two clusters = separate CC billing.

**Wiki links:** [DR — Cluster Linking](patterns/dr-cluster-linking.md), [DR — Multi-Region Cluster](patterns/dr-multi-region-cluster.md)

---

### ADR-006: OAuth vs API Keys

**Decision:** OAUTHBEARER primary for CC deployments. API keys as fallback for non-IdP environments and Terraform provider (which doesn't support OAuth).

| Deployment | Primary | Fallback | IdP |
|-----------|---------|----------|-----|
| CC Azure | OAUTHBEARER | API Keys | Azure AD (Entra ID) |
| CC AWS | OAUTHBEARER | API Keys | AWS IAM Identity Center |
| CC GCP | OAUTHBEARER | API Keys | Google Cloud Identity |
| CFK/OCP | LDAP/AD via MDS | RBAC tokens | Active Directory |
| CP/RHEL | MDS with LDAP | SASL/PLAIN | AD / LDAP |

**Consequences:** Automatic credential rotation for OAuth workloads. Centralized identity via IdP. Instant revocation. But: requires IdP setup coordination, Terraform stays API-key-based, local dev may use API keys.

---

### ADR-007: Topic Naming Convention

**Decision:** `{domain}.{application}.{version}.{entity}` with dot separators.

**Rationale:** Prefix-based RBAC wildcards (`corebanking.*`). Dashboard auto-discovery by domain. Dots are Kafka's standard hierarchical separator. Version segment enables breaking change migration. Avoids underscore/dot metric collision.

**Consequences:** Topic discovery by domain prefix. RBAC wildcards per domain. Breaking changes via versioned topics. Long names (max ~125 chars, within Kafka's 255 limit). Domain boundaries must be agreed upfront.

**Wiki links:** [Topic Naming](patterns/topic-naming.md)

---

### ADR-008: DR Tier Classification

**Decision:** Four DR tiers with distinct RPO/RTO targets. DR backend selected by deployment model.

| Tier | RPO | RTO | Priority | Mirror Lag Alert |
|------|-----|-----|----------|-----------------|
| critical | < 5 min | < 15 min | P1 | 60s |
| compliance | = 0 | < 15 min | P1 | 30s |
| standard | < 2 hours | < 1 hour | P2 | 15 min |
| best-effort | < 24 hours | < 4 hours | P3 | 4 hours |

DR backend: CL for CC (any cloud), MM2 for CFK/OCP, CL or MRC for CP/RHEL. Compliance RPO=0 achievable only via MRC on CP; CC uses critical-tier CL with enhanced monitoring.

**Consequences:** Clear per-topic SLA expectations. Mirror lag alerts derived from tier (not manual). Failover priority ordering enables triage. Compliance RPO=0 on CC requires accepting near-zero (regulatory approval needed). MRC adds produce latency.

**Wiki links:** [SLA Tiers](concepts/sla-tiers.md), [DR — Cluster Linking](patterns/dr-cluster-linking.md), [DR — MirrorMaker 2](patterns/dr-mirrormaker2.md), [DR — Multi-Region Cluster](patterns/dr-multi-region-cluster.md)

## Related

- [FSI Data Streaming Platform](concepts/fsi-data-streaming-platform.md) — platform these decisions govern
- [SLA Tiers](concepts/sla-tiers.md) — tier system referenced across multiple ADRs
- [Schema Evolution Strategies](concepts/schema-evolution-strategies.md) — ADR-001 and ADR-002
- [Topic Naming](patterns/topic-naming.md) — ADR-007
- [Governance Automation](patterns/fsi-governance-automation.md) — implements these decisions
