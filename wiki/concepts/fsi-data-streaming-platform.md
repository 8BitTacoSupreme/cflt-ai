---
title: FSI Data Streaming Platform
tags: [kafka fsi confluent-cloud confluent-platform cfk]
sources: [fsi-dsp://scenario/cc-aws, fsi-dsp://module/topic]
related: [concepts/sla-tiers, concepts/schema-evolution-strategies, concepts/fsi-compliance, patterns/fsi-governance-automation, patterns/dr-cluster-linking, patterns/dr-mirrormaker2, patterns/dr-multi-region-cluster, patterns/topic-naming]
confidence: high
last_updated: 2026-10-25
last_validated: 2026-04-28
---

# FSI Data Streaming Platform

## Summary

A universal, automation-first platform for standing up governed Kafka, Flink, and Schema Registry infrastructure across six deployment models (CC on AWS/Azure/GCP, CFK on OpenShift, CP on RHEL, Private Cloud). Packages FSI-specific C4E assets — Terraform modules, Ansible roles, reference implementations, observability templates, DR automation, and schema governance — into scenario-based starter kits. Any FSI team can deploy a fully governed, DR-ready cluster and onboard their first topic in under a day.

## Detail

### Deployment Models

All six scenarios enforce identical governance: topic naming, schema compatibility, RBAC patterns, and SLA-tier defaults.

| Scenario | IaC | Infrastructure |
|----------|-----|----------------|
| CC — AWS | Terraform | Confluent Cloud dedicated cluster |
| CC — Azure | Terraform | Confluent Cloud dedicated cluster |
| CC — GCP | Terraform | Confluent Cloud dedicated cluster |
| CFK on OpenShift | Helm / CFK Operator | OCP 4.x with operator lifecycle |
| CP on RHEL | Ansible / systemd | Self-managed brokers |
| Private Cloud | Terraform | Confluent Private Cloud |

### Shared Governance Model

A single reusable Terraform module (`modules/topic/`) produces a fully governed topic in one call: topic creation + Avro schema registration + RBAC bindings + metadata tags + DR mirror. Configuration is derived from SLA tier — critical, standard, best-effort, or compliance — removing per-topic guesswork. See [SLA Tiers](concepts/sla-tiers.md).

For CFK and CP deployments, nine Ansible roles provide equivalent lifecycle management: topic CRUD via Admin REST v3, schema registration with two-pass compatibility, MDS RBAC reconciliation, connector lifecycle, observability, and DR automation (MM2 and MRC). All roles support `--check` mode for audit-ready dry runs.

### DR Automation

Three DR backends are supported, selected by deployment model:

- **Cluster Linking** (CC): Bidirectional link, 6-step scripted failover, Consul-based atomic endpoint flip. See [DR — Cluster Linking](patterns/dr-cluster-linking.md).
- **MirrorMaker 2** (CFK/CP): Connector-based replication, simpler failover (no mirror promotion). See [DR — MirrorMaker 2](patterns/dr-mirrormaker2.md).
- **Multi-Region Cluster** (CP): Synchronous replication, RPO=0, automatic observer promotion. See [DR — MRC](patterns/dr-multi-region-cluster.md).

A unified CLI (`fsi-dr.sh`) abstracts backend differences. DR SLA targets are defined per tier in [SLA Tiers](concepts/sla-tiers.md).

### Observability

Pre-built dashboard templates for six providers (Dynatrace, Datadog, Splunk, Grafana/Prometheus, New Relic, IBM Instana). Each provides cluster health, application view, Connect, and DR readiness dashboards with auto-discovery rules, SLA-tier alert thresholds, and JMX exporter configs. The cross-provider mapping spine — every CC Metrics API metric and self-managed JMX MBean translated to PromQL/DQL/SPL/NRQL/Datadog/Instana query syntax — lives in [Observability Metrics Mapping](observability-metrics-mapping.md). Component-specific deep dives: [Confluent Platform Broker JMX](confluent-platform-broker-jmx.md), [Schema Registry Observability](schema-registry-observability.md), [ksqlDB Observability](ksqldb-observability.md), [CFK Observability Baseline](../patterns/cfk-observability-baseline.md), and [Cluster Linking Observability](../patterns/cluster-linking-observability.md).

### Reference Implementations

Working producer/consumer implementations in Java 17, .NET, and Python. All follow canonical patterns: idempotent producers (`acks=all`, `enable.idempotence=true`), manual offset commit consumers, DLQ with 3-retry backoff and error categorization, Avro serialization with Schema Registry. Plus: JDBC Connect configs, Flink SQL templates, Docker Compose local dev, and integration test roundtrip.

### Security

- RBAC: CC role bindings (Terraform), CFK ACLs + MDS (Helm), CP MDS (Ansible)
- Encryption: mTLS across all deployment models, cert-manager for CFK
- Secrets: Vault, Azure Key Vault, AWS Secrets Manager, Google Secret Manager
- FIPS 140-2: Automated validation for CP on RHEL and CFK on FIPS-enabled OpenShift (x86/ARM; CP FIPS mode is not yet supported on s390x)
- Authentication: OAuth/OAUTHBEARER primary for CC; LDAP/MDS for CP/CFK (see ADR-006)

### CI/CD

C4E pre-check validates topic naming, SLA tiers, schema compatibility, retention, and RBAC across all IaC formats. Schema validation (Avro syntax + compatibility) on every PR. Override detection flags governance exceptions for C4E review. See [FSI Compliance](concepts/fsi-compliance.md).

## Related

- [SLA Tiers](concepts/sla-tiers.md) — tier definitions driving all governance defaults
- [Schema Evolution Strategies](concepts/schema-evolution-strategies.md) — compatibility modes and evolution runbooks
- [FSI Compliance](concepts/fsi-compliance.md) — audit trail and regulatory mapping
- [Governance Automation Pattern](patterns/fsi-governance-automation.md) — the Terraform + Ansible + CI pattern
- [Topic Naming](patterns/topic-naming.md) — naming convention and enforcement
- [ADR Index](synthesis/adr-index.md) — architecture decision records
