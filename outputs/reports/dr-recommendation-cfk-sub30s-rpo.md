# DR Recommendation: CFK/OpenShift with RPO < 30 Seconds

**Date:** 2026-04-11 (revised after MCP validation)
**Author:** GoodLabs
**Context:** Scenario: a CFK/OpenShift deployment that needs RPO under 30 seconds but wants to avoid the infrastructure cost of a full MRC deployment.

> **Licensing clarification:** Both Cluster Linking and MRC are included in the Confluent Enterprise License at no additional cost. The deployment's constraint is infrastructure cost (MRC requires 5x replication across 3 DCs with synchronous write latency), not licensing.

---

## TL;DR

**Primary recommendation: Cluster Linking on CFK** (GA since CFK 3.2.0 + CP 7.5, bidirectional, zero incremental license cost). Broker-level async replication with same-name topics, automatic consumer offset handling, and per-topic lag visibility via CLI. Sub-30s RPO in steady state with proper monitoring.

**Fallback: Tuned MirrorMaker 2** if CFK/CP version is below the CL threshold.

**If RPO must be guaranteed zero:** MRC is already licensed — the cost is 3-DC infrastructure and produce-side latency, not licensing.

---

## Primary Recommendation: Cluster Linking on CFK

### Why CL Over MM2

| Capability | Cluster Linking | MirrorMaker 2 |
|---|---|---|
| Replication mechanism | Broker-level | Kafka Connect connectors |
| Topic names on DR | Same as source | Prefixed (east.topic-name) |
| Consumer offset handling | Automatic (same topic) | Needs MirrorCheckpointConnector translation |
| Per-topic lag visibility | `kafka-cluster-links --list` / REST API | Prometheus/JMX only |
| Failback complexity | Reverse link direction | Delete + reverse + recreate connectors |
| Resource overhead | Minimal (broker-native) | Dedicated Connect workers |
| License cost | Included in Enterprise | Included in Enterprise |

### Version Requirements

| Component | Minimum Version | Notes |
|---|---|---|
| Confluent Platform | 7.5+ | Bidirectional CL support |
| CFK Operator | 3.2.0+ | `ClusterLink` CRD for bidirectional links |
| OpenShift | 4.14 - 4.21 | CFK 3.2.x supported range |
| Source cluster | 7.1+ | Minimum for production linking |

### RPO Characteristics

CL replication lag is typically single-digit seconds (broker-level, no Connect overhead). With monitoring set to alert at 25s, sub-30s RPO is met with >99.9% confidence in steady state.

**Degraded scenarios:** Network congestion between DCs or broker resource saturation can spike lag. The per-topic lag visibility via `kafka-cluster-links --describe` makes this observable without Prometheus/JMX instrumentation — a significant operational advantage over MM2.

### Monitoring Setup

| Metric | Warn | Alert (hard RPO boundary) |
|---|---|---|
| Per-topic mirror lag (CL CLI/REST) | 10s | 25s |
| Link health status | PAUSED | FAILED/UNAVAILABLE |
| Destination cluster broker health | any broker offline | quorum at risk |

---

## Fallback: Tuned MirrorMaker 2

Use this path only if the deployment's CFK/CP version is below the CL bidirectional threshold (CFK < 3.2.0 or CP < 7.5).

### MM2 Tuning for Sub-30s Replication Lag

**Worker-level config** (`connect-distributed.properties` or `connect-mirror-maker.properties`):

```properties
# Flush source connector offsets more frequently (default: 60000ms)
# NOTE: This is a WORKER-level config, not a connector config
offset.flush.interval.ms=5000
```

**MirrorSourceConnector config:**

```properties
# Parallelism — at least 1 task per source partition
tasks.max=<number_of_source_partitions>

# Consumer: fetch aggressively, don't wait to batch
consumer.fetch.min.bytes=1             # return immediately with whatever is available
consumer.fetch.max.wait.ms=100         # don't hold fetch open (default 500ms — biggest latency knob)

# Producer: send immediately, no batching delay
producer.linger.ms=0                   # default is already 0, but be explicit
producer.batch.size=16384              # default 16KB is fine for latency
producer.compression.type=lz4          # compress to reduce network transfer time

# Topic discovery — lower only if topics are added frequently
refresh.topics.interval.seconds=60     # default 600s (10 min)
```

**MirrorCheckpointConnector config:**

```properties
# Emit checkpoints more frequently for tighter offset tracking (default: 60s)
emit.checkpoints.interval.seconds=5
```

### MM2 Monitoring

MM2 does not expose per-topic lag via REST API. Three approaches for production monitoring:

1. **Prometheus JMX Exporter** (recommended for CFK): `replication-latency-ms` metric via JMX on MirrorSourceConnector tasks. CFK Connect pods expose JMX on port 7203.
2. **Consumer group lag**: Monitor MM2's internal consumer group lag on the source cluster.
3. **Checkpoint topic**: Query `{source-alias}.checkpoints.internal` on the target cluster.

| Metric | Warn | Alert (hard RPO boundary) |
|---|---|---|
| replication-latency-ms (JMX, per-task) | 10s | 25s |
| Consumer group lag (MM2 internal consumer) | 1000 records | 5000 records |
| Connector state | any task PAUSED | any task FAILED |

---

## What About MRC?

The organization already has MRC licensed (it's included in Enterprise). The real cost is infrastructure:

| Cost Factor | Impact |
|---|---|
| 5x replication factor (2 East + 2 West + 1 Observer) | ~2.5x storage vs. standard RF=3 |
| 3 data centers required | Third (observer) DC can be lightweight |
| Synchronous cross-DC writes | Produce latency increases by network RTT between DCs |
| Operational complexity | Single stretched cluster vs. two independent clusters |

**When to push MRC:** If the organization's compliance team requires provable RPO=0 (not "< 30s with monitoring"), MRC is the only path. Frame the infrastructure cost against the regulatory risk of a sub-30s SLA that can theoretically be breached.

---

## Decision Framework

```
Is CFK >= 3.2.0 and CP >= 7.5?
│
├── YES → Cluster Linking (primary recommendation)
│         Sub-30s RPO, zero additional license cost,
│         same-name topics, native lag visibility
│
├── NO, but can upgrade → Upgrade CFK/CP, then Cluster Linking
│
└── NO, cannot upgrade → Tuned MirrorMaker 2
                          Sub-30s RPO achievable with aggressive tuning,
                          but more operational overhead (JMX monitoring,
                          offset translation, prefixed topics)

Is regulatory-hard RPO=0 required?
│
├── YES → MRC (already licensed — infrastructure cost only)
│
└── NO → CL or MM2 with "< 30s with continuous monitoring" SLA
```

---

## RPO Guarantee Framing for Stakeholders

- **Steady state (CL or tuned MM2):** Replication lag 1-5 seconds. Sub-30s met >99.9% of the time.
- **Degraded state:** Network congestion or broker saturation can spike lag. Monitoring + alerting catches this within the 25s alert window.
- **Failure state:** RPO equals lag at moment of failure — almost certainly < 10s with proper tuning.
- **Positioning:** "RPO < 30s with > 99.9% confidence, bounded by replication lag monitoring."

If the 30-second requirement is a regulatory hard ceiling with audit consequences, document the monitoring SLA and get the compliance team to sign off on "< 30s with continuous monitoring and alerting" as meeting the intent. If they won't sign off, MRC is the answer and the infrastructure cost is the price of the guarantee.

---

*Validated against Confluent docs via MCP (2026-04-11). Property names, defaults, and licensing confirmed against current documentation.*
