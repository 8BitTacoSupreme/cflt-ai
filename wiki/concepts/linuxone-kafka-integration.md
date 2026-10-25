---
title: LinuxONE Kafka Integration for z/OS Offload
tags: [linuxone ibm mainframe z/os mq kafka-connect fips dr]
sources: [fsi-dsp://adr/009]
related: [concepts/fsi-data-streaming-platform, concepts/sla-tiers, concepts/fsi-compliance, patterns/dr-cluster-linking]
confidence: high
last_updated: 2026-10-25
last_validated: 2026-10-25
---

# LinuxONE Kafka Integration for z/OS Offload

## Summary

IBM LinuxONE (Emperor 4 or Rockhopper III+) is the preferred compute platform for bridging z/OS workloads into Apache Kafka via the IBM MQ Source Connector. Running a native Linux environment on the same physical frame as z/OS, LinuxONE provides sub-millisecond latency via HiperSockets while avoiding mainframe software license overhead, delivering 99.999% availability with CPACF hardware crypto acceleration (CP FIPS mode is not yet supported on s390x) and full standard Linux tooling compatibility. The canonical integration pattern is: z/OS Application → IBM MQ Queue → MQ Source Connector (on LinuxONE) → Kafka Topic.

## Detail

### Bridge Pattern

Mainframe applications write to IBM MQ queues — a well-understood z/OS pattern requiring no application changes. The Confluent-certified IBM MQ Source Connector, running in Kafka Connect distributed mode on LinuxONE, consumes from those queues and produces to Kafka topics:

```
z/OS Application -> IBM MQ Queue -> MQ Source Connector (LinuxONE) -> Kafka Topic
```

This pattern preserves existing z/OS application interfaces while enabling downstream event-driven consumers in modern Kafka-based architectures.

### Why LinuxONE

| Property | Value |
|----------|-------|
| Latency to z/OS | Sub-millisecond via HiperSockets (no external network hop) |
| License overhead | None — Linux workloads carry no mainframe software license cost |
| Availability | 99.999% — inherits z/OS frame reliability |
| FIPS | CP FIPS mode not yet supported on s390x; FIPS-mandated broker tiers run on x86/ARM (ADR-009 Amendment 2026-10-24) |
| Tooling | Standard Linux tooling (Ansible, Terraform, Docker) works on LinuxONE |
| Architecture | s390x supported from CP 8.2.0 (IBM Z entitlement required); verify connector/client versions before deploy |

HiperSockets provides an in-memory channel between z/OS LPARs and LinuxONE — there is no external network adapter involved, which eliminates the 5-20ms round-trip latency of a PrivateLink or physical NIC path. This makes LinuxONE the only viable platform for `market_data` (sub-millisecond) and `risk` (<10ms) SLA tiers where the data source is z/OS.

### Configuration

**Hardware:** IBM LinuxONE Emperor 4 or Rockhopper III+, running RHEL 8.x/9.x or Ubuntu 22.04 LTS.

**Network:** HiperSockets for z/OS-to-LinuxONE communication. Requires IBM z/VM or PR/SM setup for the HiperSockets channel.

**Connector:** Confluent-certified IBM MQ Source Connector, deployed on Kafka Connect in distributed mode on LinuxONE. Connector consumes from MQ queues on the z/OS side and produces to Kafka topics.

**Serialization:** Avro with Schema Registry per [ADR-001](synthesis/adr-index.md). Schemas registered at the connector level; all governed topic defaults apply (compatibility mode derived from SLA tier).

**Security:** CP FIPS mode is not yet supported on s390x, so a tier whose policy requires FIPS 140 validated broker crypto runs its brokers on x86/ARM (ADR-009 Amendment 2026-10-24). mTLS between Kafka clients and brokers per [ADR-006](synthesis/adr-index.md). Service accounts provisioned per application, not per team (per FSI security defaults).

**DR:** LinuxONE instances deployed in both primary and DR regions. Cluster Linking replicates topics cross-region per [ADR-005](synthesis/adr-index.md). Failover orchestration follows the Cluster Linking DR pattern.

### SLA Tier Fit

| SLA Tier | Latency Requirement | HiperSockets Fit |
|----------|---------------------|------------------|
| market_data (critical) | Sub-millisecond | Yes — in-memory channel |
| risk (critical) | < 10ms | Yes |
| compliance | < 100ms | Yes |
| reconciliation (standard/best-effort) | Async | Yes |

For compliance-tier topics requiring RPO=0, deploy MRC on Confluent Platform alongside LinuxONE. For Confluent Cloud deployments, use critical-tier Cluster Linking with enhanced monitoring (as close to RPO=0 as CC permits).

### Considerations

- **Procurement lead time:** LinuxONE hardware has 6-12 month lead times. Plan infrastructure acquisition early in engagement timelines.
- **MQ queue manager coordination:** The MQ Source Connector requires MQ queue manager configuration on the z/OS side — coordinate with the mainframe team well in advance.
- **HiperSockets setup:** Requires IBM z/VM or PR/SM setup expertise; involve IBM mainframe practice for initial configuration.
- **s390x compatibility:** Not all Confluent components are certified for s390x architecture. Verify specific connector and client versions against the Confluent compatibility matrix before deployment.

### Related ADRs

| ADR | Relevance |
|-----|-----------|
| ADR-001 | Avro as default schema format — applies to MQ Source Connector output |
| ADR-005 | Cluster Linking for cross-region DR — replicates LinuxONE-produced topics |
| ADR-006 | OAuth vs API Keys — mTLS on LinuxONE matches FSI security baseline |
| ADR-009 | LinuxONE as preferred compute for z/OS Kafka offload (this decision) |

## Related

- [FSI Data Streaming Platform](concepts/fsi-data-streaming-platform.md) — platform overview including LinuxONE integration context
- [SLA Tiers](concepts/sla-tiers.md) — latency tiers that drive LinuxONE adoption for market_data and risk workloads
- [FSI Compliance](concepts/fsi-compliance.md) — audit trail requirements; FIPS 140 is not met by CP on s390x brokers today
- [DR — Cluster Linking](patterns/dr-cluster-linking.md) — DR pattern for topics produced by LinuxONE MQ Source Connector
- [ADR Index](synthesis/adr-index.md) — ADR-009 (LinuxONE decision), ADR-001, ADR-005, ADR-006
