# Confluent Cloud → Dynatrace Metrics Glossary

Metrics recommended for export to Dynatrace, organized by **Producer**, **Consumer**, and **Cluster**. Each card follows the standard format: Description · Recommended Range · Pros (healthy value) · Cons (anomalous value).

> **Capacity baseline.** Throughput and partition redlines are expressed as a percentage of provisioned capacity. Per-CKU figures for Confluent Cloud **Dedicated** are **60 MBps ingress / 180 MBps egress** and **4,500 partitions per CKU**. Resolve the live figure from **CC Console → Cluster Settings → Capacity** and bind it to a dashboard variable rather than hardcoding it.
>
> **Reading the direction.** The *Pros (Low) / Cons (High)* framing maps cleanly to error, lag, latency, and saturation metrics. For **rate and count** metrics (record rates, authentication success), the unhealthy direction is a **drop**, not a spike — those cards are inverted and labeled accordingly.

---

## 1. Producer (produce path — ingress)

### 1. record-error-rate
**Description:**
Rate at which records fail permanently after retries are exhausted.

**Recommended Range:**
- Healthy: `0.0`
- Critical: `> 0.01`

**Pros (Low Value):**
A low record-error-rate indicates a stable and reliable producer pipeline where records are succeeding, brokers are responsive, and no data-loss condition exists. It confirms network paths, broker health, and producer configuration (`acks=all`, `retries`, `enable.idempotence=true`) are working correctly.

**Cons (High Value):**
A high value indicates consistent message failures, often caused by broker unavailability, authentication issues, ACL failures, or persistent network faults. It can lead to data loss if idempotence or retries are not configured, and typically signals that the producer cannot guarantee delivery. In an exactly-once or regulatory-reporting pipeline, any sustained non-zero rate is a reportable integrity event.

### 2. received_bytes
**Description:**
Bytes the cluster received from producers (produce-side throughput). Aggregate with `sum` over topics for a cluster total; never average.

**Recommended Range:**
- Healthy: `< 70%` of provisioned ingress (`CKU × 60 MBps`)
- Critical: `> 80%` sustained for ≥ 10 min → add CKUs

**Pros (Low Value):**
Headroom against the per-CKU ingress ceiling. Producers are not throttled and the cluster can absorb burst traffic without backpressure or quota rejection.

**Cons (High Value):**
The cluster is approaching the ingress cliff. Beyond the limit Confluent throttles produce requests, driving up produce latency and record-error-rate. On **Enterprise/elastic** tiers this absolute math is misleading — use `cluster_load_percent` instead.

### 3. received_records  *(inverted — a drop is the unhealthy direction)*
**Description:**
Count of records produced into the cluster. The canonical "Messages Produced" signal.

**Recommended Range:**
- Healthy: within the auto-adaptive baseline band for the time of day
- Critical: sustained drop toward `0` during expected traffic, **or** spike beyond ingress capacity

**Pros (Healthy Value):**
A steady, baseline-consistent record flow confirms upstream producers are live and the produce path is healthy end-to-end.

**Cons (Anomalous Value):**
A sustained drop signals a stalled or dead producer, or an upstream outage. For exactly-once and regulatory pipelines this is a completeness gap, so pair the adaptive baseline with a **static floor** so a slow drift cannot be normalized away. A spike risks hitting the ingress cliff (see received_bytes).

### 4. request_bytes
**Description:**
Produce-side request bytes attributed per principal (`principal_id`); the produce half of the showback pair (consume half is `response_bytes`).

**Recommended Range:**
- Healthy: within each principal's expected envelope
- Critical: anomalous spike versus that principal's baseline

**Pros (Low/Stable Value):**
Clean per-principal attribution for chargeback/showback, with no single producer dominating cluster ingress.

**Cons (High Value):**
A runaway or misconfigured producer (noisy neighbor) consuming disproportionate ingress — both a cost and a capacity risk. Best surfaced as a drill-down split by `principal_id`, not a top-level alert.

### 5. rest_produce_request_bytes
**Description:**
Bytes produced via the v3 REST Produce API; a subset of `received_bytes`. Only meaningful if REST Proxy is in use.

**Recommended Range:**
- Healthy: within REST-client baseline (or `0` if REST Proxy is not deployed)
- Critical: unexpected non-zero where REST is not authorized, or a spike versus baseline

**Pros (Low Value):**
Confirms REST produce traffic is within expectation and the bulk of ingress is going through native clients, which carry lower per-record overhead.

**Cons (High Value):**
REST produce carries higher per-request overhead than the native protocol; a rising share can inflate request latency. Validate only if REST Proxy is actually deployed.

### 6. producer.request.latency.avg  *(KIP-714 client telemetry — requires librdkafka ≥ 2.5.3)*
**Description:**
End-to-end produce request latency including network and client-queue time (broader than broker-side `request_latencies`).

**Recommended Range:** *tier-scoped — set from the workload's SLA budget*
- Healthy: within the SLA tier (sub-ms market data · < 10 ms risk · < 100 ms compliance · async reconciliation)
- Critical: greater than the tier budget

**Pros (Low Value):**
Confirms the full client→broker→ack path meets the workload's latency SLA, including the client-queue and network contributions the broker-side metric cannot see.

**Cons (High Value):**
A breach of the workload's latency budget — for a risk-tier workload an 80 ms latency is already 8× over budget. Confirm the exact metric key and librdkafka floor against the deployed client build before alerting.

---

## 2. Consumer (consume path — egress)

### 1. consumer_lag_offsets
**Description:**
Offset distance between the latest produced and the last committed offset, per `(group, topic, partition)`. Aggregate `max by consumer_group_id` at the top level — summing across unrelated groups is meaningless.

**Recommended Range:**
- Healthy: stable / near-zero; time-lag within the consumer's SLA
- Critical: monotonic growth, or time-lag greater than SLA

**Pros (Low Value):**
Consumers are keeping pace with producers; data is fresh and downstream SLAs (risk, compliance) are met.

**Cons (High Value):**
Consumers are falling behind — under-provisioned consumer parallelism, slow processing, or rebalancing. **Prefer time-based lag (Lag Exporter)** over offset-based for alerting: 10,000 offsets means nothing without the produce rate to convert it into a time budget.

### 2. sent_bytes
**Description:**
Bytes the broker sent to consumers (consume-side throughput; note this is *sent*, not consumer-acked). Aggregate `sum` over topics for a cluster total.

**Recommended Range:**
- Healthy: `< 70%` of provisioned egress (`CKU × 180 MBps`)
- Critical: `> 80%` sustained for ≥ 10 min → add CKUs

**Pros (Low Value):**
Egress headroom; fan-out consumers and replication reads are served without throttling.

**Cons (High Value):**
The cluster is approaching the egress cliff. High consumer fan-out or catch-up reads after lag can saturate egress faster than ingress, and throttled fetches increase consumer lag. Use `cluster_load_percent` on elastic tiers.

### 3. sent_records  *(inverted — a drop is the unhealthy direction)*
**Description:**
Records the broker sent to consumers. The canonical "Messages Consumed" signal; reflects what was sent, not consumer-confirmed.

**Recommended Range:**
- Healthy: within the adaptive baseline band, tracking `received_records`
- Critical: sustained drop while `received_records` holds (consumers stalled → lag building)

**Pros (Healthy Value):**
A consume rate tracking the produce rate confirms the end-to-end pipeline is balanced and consumers are draining the log.

**Cons (Anomalous Value):**
A drop while production continues is the leading indicator of building `consumer_lag_offsets` — a stalled or crash-looping consumer group. Cross-reference with consumer_lag_offsets.

### 4. response_bytes
**Description:**
Consume-side response bytes per principal (`principal_id`); the consume half of the showback pair (produce half is `request_bytes`).

**Recommended Range:**
- Healthy: within each principal's expected envelope
- Critical: anomalous spike versus that principal's baseline

**Pros (Low/Stable Value):**
Clean per-consumer egress attribution for chargeback, with no single consumer group dominating egress.

**Cons (High Value):**
A runaway consumer (for example, repeated full-history re-reads or an offset reset to earliest) driving disproportionate egress and cost. Surface as a drill-down by `principal_id`.

---

## 3. Cluster

### 1. cluster_load_percent  *(Dedicated / Enterprise only)*
**Description:**
Composite saturation index (CPU + network + request queues), already cluster-scoped and normalized 0–100. Aggregate `avg`, no split. The correct headline health metric, especially for elastic tiers where absolute throughput math does not apply.

**Recommended Range:**
- Healthy: `< 70%`
- Critical: `> 80%` sustained for ≥ 10 min → scale CKUs

**Pros (Low Value):**
A single, capacity-normalized health signal. Low values mean the cluster has headroom across all saturation dimensions, not just one, and it is immune to the per-CKU hardcoding problem.

**Cons (High Value):**
A composite saturation cliff — produce/consume latency and throttling rise sharply past 80%. Not emitted on Basic/Standard, where the tile renders empty; confirm the tier before leading the Health Summary with it.

### 2. partition_count  *(gauge)*
**Description:**
Total partitions on the cluster. A gauge — aggregate `max`, never `sum`.

**Recommended Range:**
- Healthy: `< 80%` of `CKU × 4,500`
- Critical: `> 90%` (immediate, no sustain window)

**Pros (Low Value):**
Headroom against the hard per-CKU partition ceiling; new topics and partitions can be created without hitting a wall.

**Cons (High Value):**
Partition limits are a hard cliff — at the ceiling, topic/partition creation fails outright. Alert immediately (no sustain window) because it blocks provisioning, not just degrades performance.

### 3. request_latencies  *(broker-side processing time, percentile-labeled)*
**Description:**
Broker-side request processing time, excluding network. Percentile-labeled (`metric.percentile`) — aggregate `avg` over the cluster but keep the percentile dimension; never sum percentiles.

**Recommended Range:** *tier-scoped, not cluster-global*
- Healthy: p99 within the workload's SLA tier
- Critical: p99 greater than the tier budget (placeholder 80 ms warn / 100 ms crit; Produce vs FetchConsumer differ materially — do not ship as a fixed redline)

**Pros (Low Value):**
The broker is processing requests well within budget and is not the latency bottleneck (this isolates broker time from network and client time).

**Cons (High Value):**
Broker-side contention (queue buildup, GC, hot partitions). A single cluster-wide 80/100 ms redline is meaningless across mixed FSI workloads — already 8–10× over a risk-tier budget and irrelevant for reconciliation. Tag each latency tile with its SLA tier.

### 4. request_count {response_code = 429}  *(quota throttling)*
**Description:**
Rate of throttled requests (HTTP 429) — the cluster is rejecting requests for exceeding a quota.

**Recommended Range:**
- Healthy: `0`
- Critical: rate `> 0`

**Pros (Low Value):**
No quota throttling — clients are operating within provisioned ingress, egress, and connection quotas.

**Cons (High Value):**
Active throttling — a client is over quota; produce/consume latency rises and record-error-rate can follow. Indicates either an under-provisioned cluster or a misbehaving client. If the response-code dimension is absent in your tenant, source 429s client-side instead.

### 5. request_count {response_code = 403}  *(ACL / auth failures)*
**Description:**
Rate of forbidden requests (HTTP 403) — failed authorization (ACL/RBAC) or credential issues.

**Recommended Range:**
- Healthy: `0`
- Critical: any sustained rise `> 0`

**Pros (Low Value):**
No authorization failures — service accounts, ACLs, and RBAC bindings are correctly configured with no credential drift.

**Cons (High Value):**
Rising 403s signal expired or rotated credentials, missing ACLs after a deploy, or — in an mTLS+RBAC context — a potential unauthorized-access probe worth a security review, not just an ops alert.

### 6. successful_authentication_count  *(inverted — a drop is the unhealthy direction)*
**Description:**
Count of successful client authentications.

**Recommended Range:**
- Healthy: within baseline for the connected client population
- Critical: sustained drop (auth path failing) — use drop-only anomaly detection plus a static floor

**Pros (Healthy Value):**
Steady auth success confirms clients are connecting and that credentials / mTLS handshakes are valid across the fleet.

**Cons (Anomalous Value):**
A drop means clients can no longer authenticate — a broker auth outage, certificate or credential expiry, or identity-provider failure. Auth success has regulatory consequence, so keep a hard static floor under the adaptive baseline so a slow sustained decline cannot be normalized away.

### 7. schema_count  *(Schema Registry — `io.confluent.kafka.schema_registry/schema_count`)*
**Description:**
Total registered schemas across all subjects in the Schema Registry.

**Recommended Range:**
- Healthy: within the SR plan's schema/subject limit, with growth tracking known onboarding
- Critical: approaching the registry cap, or unexpected growth (uncontrolled schema churn)

**Pros (Low/Stable Value):**
Controlled schema growth indicates disciplined contract governance — `BACKWARD`/`FULL` compatibility gates are doing their job and schemas are not proliferating per deploy.

**Cons (High Value):**
Approaching the registry limit blocks new subject registration. Runaway growth often signals a client registering a new schema version per restart (bad subject-naming strategy or non-deterministic serialization) — a governance smell worth investigating.

---

## Summary

| Bucket | Metrics |
|--------|---------|
| **Producer (ingress)** | `record-error-rate`*, `received_bytes`, `received_records`, `request_bytes`, `rest_produce_request_bytes`, `producer.request.latency.avg`* |
| **Consumer (egress)** | `consumer_lag_offsets`, `sent_bytes`, `sent_records`, `response_bytes` |
| **Cluster** | `cluster_load_percent`, `partition_count`, `request_latencies`, `request_count{429}`, `request_count{403}`, `successful_authentication_count`, `schema_count` |

\* Client-side telemetry, not the Confluent Cloud Metrics API (`record-error-rate` is JMX `kafka.producer:type=producer-metrics`; `producer.request.latency.avg` is KIP-714 client telemetry).

**Before building tiles, confirm against your tenant:** `partition_count` existence · `successful_authentication_count` existence · the `request_count` response-code dimension (drives the 429/403 tiles) · the KIP-714 metric key and librdkafka floor · `rest_produce_request_bytes` (only if REST Proxy is deployed). On **Enterprise/elastic** tiers, drop the absolute `CKU × limit` throughput redlines (`received_bytes` / `sent_bytes`) in favor of `cluster_load_percent`.

---

*Validated against Confluent docs via MCP (2026-06-01, inherited from the source dashboard review). 24 claims checked there, 3 corrected (per-CKU 50/150 → 60/180 MBps), 5 carried as live-tenant validation flags above.*
