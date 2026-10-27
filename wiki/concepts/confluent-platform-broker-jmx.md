---
title: Confluent Platform Broker JMX — Canonical MBean Reference
tags: [observability jmx mbean broker confluent-platform cfk kafka monitoring prometheus fsi]
sources:
  - fsi-dsp://observability/grafana
  - https://kafka.apache.org/documentation/#monitoring
  - https://docs.confluent.io/platform/current/kafka/monitoring.html
related:
  - concepts/observability-metrics-mapping
  - concepts/sla-tiers
  - concepts/consumer-lag-monitoring
  - patterns/aks-kafka-tuning
  - patterns/dr-cluster-linking
confidence: medium
last_updated: 2026-05-20
last_validated: 2026-05-20
---

# Confluent Platform Broker JMX — Canonical MBean Reference

## Summary

Self-managed Kafka brokers (Confluent Platform on RHEL, Confluent for Kubernetes, vanilla Apache Kafka) expose their entire operational surface via JMX. This article is the canonical MBean reference: which MBean answers which operational question, what aggregator to read (`Value`, `OneMinuteRate`, `Mean`), how to map it into a Prometheus exporter rule, and which SLA tier the metric belongs to. Pair this with [Observability Metrics Mapping](observability-metrics-mapping.md) (the cross-provider spine) and [SLA Tiers](sla-tiers.md) (alert thresholds) to instrument any self-managed Confluent cluster end-to-end. For Confluent Cloud, broker JMX is abstracted away — use the CC Metrics API namespaces in the spine instead.

## Detail

### MBean namespace layout

The broker exposes five namespaces, plus the controller:

| Namespace | What it measures |
|---|---|
| `kafka.server:type=BrokerTopicMetrics` | Per-broker (and optionally per-topic) throughput, conversions, and rejection counters |
| `kafka.server:type=ReplicaManager` | Replication health (under-replicated, ISR shrinks/expands, partition counts) |
| `kafka.server:type=FetcherLagMetrics` | Follower-side consumer lag (the broker fetching from a leader) |
| `kafka.network:type=RequestMetrics` | Request-stage timing and queue depth (produce, fetch, metadata, etc.) |
| `kafka.controller:type=KafkaController` | Controller liveness and global counts (KRaft or ZooKeeper-era) |
| `kafka.log:type=Log` | Per-partition log size, segment counts, log-end and log-start offsets |

### Replication & ISR

| MBean | Attribute | Subsystem signal | Alert (FSI tier) |
|---|---|---|---|
| `kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions` | `Value` | Partitions whose ISR is below `replication.factor` — primary broker-health signal | `> 0` sustained 5 min = P1 (critical/standard tiers) |
| `kafka.server:type=ReplicaManager,name=UnderMinIsrPartitionCount` | `Value` | Partitions below `min.insync.replicas` — produce-blocking signal under `acks=all` | `> 0` = P1 (immediate; producers stalling) |
| `kafka.server:type=ReplicaManager,name=OfflinePartitionsCount` | `Value` | Partitions with no live leader — data unavailable | `> 0` = P1 |
| `kafka.server:type=ReplicaManager,name=PartitionCount` | `Value` | Total partitions hosted on this broker — load balance indicator | Compare across brokers; skew > 20% = P3 |
| `kafka.server:type=ReplicaManager,name=LeaderCount` | `Value` | Partitions for which this broker is leader | Skew > 20% across brokers = P3 |
| `kafka.server:type=ReplicaManager,name=IsrShrinksPerSec` | `OneMinuteRate` | ISR shrink events — indicates flapping followers or network issues | Sustained > 0 for 10 min = P2 |
| `kafka.server:type=ReplicaManager,name=IsrExpandsPerSec` | `OneMinuteRate` | ISR expansion events — pairs with shrinks to detect oscillation | Cross-reference with shrinks |

### Throughput

| MBean | Attribute | Signal |
|---|---|---|
| `kafka.server:type=BrokerTopicMetrics,name=MessagesInPerSec` | `OneMinuteRate` | Incoming message rate (per broker; with `,topic=*` for per-topic) |
| `kafka.server:type=BrokerTopicMetrics,name=BytesInPerSec` | `OneMinuteRate` | Incoming byte rate — primary ingress capacity signal |
| `kafka.server:type=BrokerTopicMetrics,name=BytesOutPerSec` | `OneMinuteRate` | Outgoing byte rate — fan-out indicator (egress >> ingress for high fan-out topics) |
| `kafka.server:type=BrokerTopicMetrics,name=BytesRejectedPerSec` | `OneMinuteRate` | Records rejected (quota, oversized) — should be near zero |
| `kafka.server:type=BrokerTopicMetrics,name=TotalProduceRequestsPerSec` | `OneMinuteRate` | Produce request rate (request, not record) |
| `kafka.server:type=BrokerTopicMetrics,name=TotalFetchRequestsPerSec` | `OneMinuteRate` | Fetch request rate from all consumers and follower fetchers |

> ⚠️ unverified — `MessageConversionsTimeMs` (produce/fetch down-conversion timing on `BrokerTopicMetrics`) is well-attested in upstream Apache Kafka docs but not directly MCP-confirmed in this pass. Use to detect down-conversion overhead when older clients connect.

### Network — request stages

Each request type (`Produce`, `Fetch`, `Metadata`, `OffsetCommit`, `OffsetFetch`, `LeaderAndIsr`, etc.) exposes a stage timing breakdown under `kafka.network:type=RequestMetrics,name=<stage>,request=<type>`. Use `Mean`/`99thPercentile` attributes for the latency view.

| Stage MBean (under `kafka.network:type=RequestMetrics,request=<type>`) | What it captures |
|---|---|
| `name=RequestsPerSec` | Request rate per type (read `OneMinuteRate`) |
| `name=RequestQueueTimeMs` | Time the request waited in the request queue before a handler thread picked it up |
| `name=LocalTimeMs` | Time spent processing on the leader broker (the most informative latency component) |
| `name=RemoteTimeMs` | Time waiting on remote brokers (e.g., replication ack for produce) |
| `name=ResponseQueueTimeMs` | Time the response waited to be sent |
| `name=ResponseSendTimeMs` | Time taken to actually send the response on the wire |
| `name=TotalTimeMs` | Sum of all stages — the end-to-end broker-side latency |
| `name=RequestQueueSize` | Depth of the unhandled-request queue (capacity = `queued.max.requests`) |

Aggregated separately:

| MBean | Attribute | Signal |
|---|---|---|
| `kafka.network:type=SocketServer,name=NetworkProcessorAvgIdlePercent` | `Value` | Idle fraction of network I/O threads (target ≥ 0.3) — < 0.2 = saturation |
| `kafka.server:type=KafkaRequestHandlerPool,name=RequestHandlerAvgIdlePercent` | `Value` | Idle fraction of request-handler threads (target ≥ 0.3) — < 0.2 = saturation |

### Follower fetcher lag (broker-side consumer-lag MBean)

`kafka.server:type=FetcherLagMetrics,name=ConsumerLag,clientId=<>,topic=<>,partition=<>` exposes how far behind a follower replica is from the leader's log-end offset. This is **not** application consumer lag — that lives on the client (see [Consumer Lag Monitoring](consumer-lag-monitoring.md)). Use `clientId=ReplicaFetcherThread-<i>-<broker_id>` filter to identify the source.

| MBean | Attribute | Signal |
|---|---|---|
| `kafka.server:type=FetcherLagMetrics,name=ConsumerLag,clientId=*,topic=*,partition=*` | `Value` | Records the follower is behind the leader for this partition |
| `kafka.server:type=FetcherLagMetrics,name=MaxLag` | `Value` | Max follower lag across all replicas this broker is fetching |

### Controller (KRaft or ZooKeeper era)

| MBean | Attribute | Signal |
|---|---|---|
| `kafka.controller:type=KafkaController,name=ActiveControllerCount` | `Value` | Exactly 1 expected (cluster-wide sum). 0 or > 1 = split-brain or election failure = P1 |
| `kafka.controller:type=KafkaController,name=OfflinePartitionsCount` | `Value` | Partitions without a leader (controller view; complements the per-broker ReplicaManager metric) |
| `kafka.controller:type=KafkaController,name=GlobalPartitionCount` | `Value` | Cluster-wide partition total |
| `kafka.controller:type=KafkaController,name=GlobalTopicCount` | `Value` | Cluster-wide topic total |

> ⚠️ unverified — KRaft-mode controller adds `kafka.controller:type=KafkaController,name=LastAppliedRecordOffset` and `LastAppliedRecordTimestamp` for raft-log progress on the active controller, but ZooKeeper-era brokers expose neither. Verify mode (KRaft vs ZK) before alerting on these.

### Storage (per-partition log MBeans)

| MBean | Attribute | Signal |
|---|---|---|
| `kafka.log:type=Log,name=Size,topic=*,partition=*` | `Value` | On-disk size of this partition (bytes) |
| `kafka.log:type=Log,name=NumLogSegments,topic=*,partition=*` | `Value` | Segment file count — high values indicate frequent rolling |
| `kafka.log:type=Log,name=LogStartOffset,topic=*,partition=*` | `Value` | Oldest offset still retained |
| `kafka.log:type=Log,name=LogEndOffset,topic=*,partition=*` | `Value` | Highest offset written — paired with consumer offset to derive lag broker-side |
| `kafka.log:type=LogFlushStats,name=LogFlushRateAndTimeMs` | `Mean` / `OneMinuteRate` | Log-flush latency and rate (disk performance signal) |

### JMX exporter rule excerpt (Prometheus-style)

The minimal set of patterns the [fsi-dsp Grafana stack](https://github.com/8BitTacoSupreme/fsi-dsp) ships with — covers the 90% of broker health questions for an FSI tier-1 deployment:

```yaml
hostPort: "{{JMX_EXPORTER_HOST}}:9101"
lowercaseOutputName: true
lowercaseOutputLabelNames: true
rules:
  - pattern: "kafka.server<type=ReplicaManager, name=UnderReplicatedPartitions><>Value"
    name: kafka_server_replica_manager_under_replicated_partitions
    type: GAUGE
  - pattern: "kafka.server<type=BrokerTopicMetrics, name=BytesInPerSec><>OneMinuteRate"
    name: kafka_server_broker_topic_metrics_bytes_in_per_sec
    type: GAUGE
  - pattern: "kafka.server<type=BrokerTopicMetrics, name=BytesOutPerSec><>OneMinuteRate"
    name: kafka_server_broker_topic_metrics_bytes_out_per_sec
    type: GAUGE
  - pattern: "kafka.controller<type=KafkaController, name=ActiveControllerCount><>Value"
    name: kafka_controller_active_controller_count
    type: GAUGE
  - pattern: "kafka.server<type=ReplicaManager, name=PartitionCount><>Value"
    name: kafka_server_replica_manager_partition_count
    type: GAUGE
  - pattern: "kafka.server<type=FetcherLagMetrics, name=ConsumerLag, clientId=(.*), topic=(.*), partition=(.*)><>Value"
    name: kafka_server_fetcher_lag_metrics_consumer_lag
    type: GAUGE
    labels: { client_id: "$1", topic: "$2", partition: "$3" }
  - pattern: "kafka.network<type=RequestMetrics, name=RequestsPerSec, request=(.*)><>OneMinuteRate"
    name: kafka_network_request_metrics_requests_per_sec
    type: GAUGE
    labels: { request: "$1" }
  - pattern: "kafka.server<type=ReplicaManager, name=IsrShrinksPerSec><>OneMinuteRate"
    name: kafka_server_replica_manager_isr_shrinks_per_sec
    type: GAUGE
  - pattern: "kafka.server<type=ReplicaManager, name=IsrExpandsPerSec><>OneMinuteRate"
    name: kafka_server_replica_manager_isr_expands_per_sec
    type: GAUGE
```

For the full per-provider query mapping (PromQL / DQL / SPL / NRQL / Datadog / Instana), see [Observability Metrics Mapping](observability-metrics-mapping.md).

### Alert threshold matrix by SLA tier

| Signal | Critical | Standard | Best-effort |
|---|---|---|---|
| `under_replicated_partitions > 0` sustained | 1 min = P1 | 5 min = P1 | 15 min = P2 |
| `under_min_isr_partition_count > 0` | Immediate P1 | Immediate P1 | 5 min = P2 |
| `offline_partitions_count > 0` | Immediate P1 | Immediate P1 | Immediate P1 |
| `active_controller_count != 1` (cluster sum) | Immediate P1 | Immediate P1 | Immediate P1 |
| `request_handler_avg_idle_percent < 0.2` | 5 min = P2 | 10 min = P2 | 15 min = P3 |
| `isr_shrinks_per_sec > 0` sustained | 5 min = P2 | 10 min = P3 | informational |
| `fetcher_lag (replica) > N records` | per topic SLA | per topic SLA | per topic SLA |

See [SLA Tiers](sla-tiers.md) for tier-to-workload mapping. The same JMX-exporter rule set powers every provider in the [observability-metrics-mapping](observability-metrics-mapping.md) spine — only the alert-rule syntax changes (Prometheus AlertManager, Dynatrace Davis, Splunk alert, NRQL alert condition, etc.).

### Where this article does not cover

- **Client-side metrics** (producer/consumer JMX): tracked separately in [Consumer Lag Monitoring](consumer-lag-monitoring.md) and [Producer Batching Configuration](producer-batching-config.md). Client JMX uses the `kafka.producer:type=*` and `kafka.consumer:type=*` namespaces.
- **Kafka Connect MBeans**: see the root-level `Connect_Dynatrace_Monitoring_Guide.md` and `Connect_DQL_Dashboard_Config.md`. Connect uses `kafka.connect:type=*`.
- **Schema Registry MBeans**: see `schema-registry-observability.md` (pending in this expansion).
- **ksqlDB MBeans**: see `ksqldb-observability.md` (pending in this expansion).
- **Cluster Linking MBeans (self-managed)**: covered in `cluster-linking-observability.md` (pending).

## Related

- [Observability Metrics Mapping](observability-metrics-mapping.md) — cross-provider spine consuming these JMX MBeans
- [SLA Tiers](sla-tiers.md) — alert thresholds per tier
- [Consumer Lag Monitoring](consumer-lag-monitoring.md) — client-side lag deep dive (complement to FetcherLagMetrics)
- [AKS Kafka Tuning](../patterns/aks-kafka-tuning.md) — Azure-specific broker tuning with JMX exporter configuration overlap
- [DR — Cluster Linking](../patterns/dr-cluster-linking.md) — DR-side MBean considerations
