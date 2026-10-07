# Dynatrace Confluent Cloud Metrics — Glossary by Producer / Consumer / Cluster

**Date:** 2026-06-23
**Source:** `outputs/reports/dynatrace-dashboard-changes-review-2026-06-01.md` (metric identities + thresholds already MCP-validated there)
**Format:** per-metric card — Description · Recommended Range · Pros (healthy value) · Cons (anomalous value)

> **Threshold provenance.** Per-CKU capacity = **60 MBps ingress / 180 MBps egress** and **4,500 partitions/CKU** (Confluent Dedicated, confirmed via `confluent-docs` in the source review — *not* the 50/150 the original handoff used). Throughput redlines below are expressed as a % of provisioned capacity; resolve the live figure from **CC Console → Cluster Settings → Capacity** and bind it to a dashboard variable rather than hardcoding.
>
> **Direction note.** The template's *Pros (Low) / Cons (High)* maps cleanly to error/lag/latency/saturation metrics. For **rate and count** metrics (record rates, auth-success), the *bad* direction is a **drop**, not a spike — those cards are inverted and labeled accordingly.

---

## 1. Producer (produce path — ingress)

### 1.1 record-error-rate  *(client-side JMX — `kafka.producer:type=producer-metrics`)*
**Description:** Rate at which records fail permanently after retries are exhausted.
**Recommended Range:**
- Healthy: `0.0`
- Critical: `> 0.01`

**Pros (Low Value):** A low `record-error-rate` indicates a stable, reliable producer pipeline — records are succeeding, brokers are responsive, and no data-loss condition exists. It confirms network paths, broker health, and producer config (`acks=all`, `retries`, `enable.idempotence=true`) are working correctly.
**Cons (High Value):** A high value indicates consistent message failures — broker unavailability, authentication/ACL failures, or persistent network faults. It can lead to data loss if idempotence/retries are not configured and signals the producer cannot guarantee delivery. **FSI:** any non-zero sustained rate on an exactly-once / regulatory-reporting pipeline is a reportable integrity event.

### 1.2 received_bytes  *(CC Metrics API — ingress throughput)*
**Description:** Bytes the cluster received from producers (produce-side throughput). Aggregate with `sum` over topics for a cluster total; never average.
**Recommended Range:**
- Healthy: `< 70%` of provisioned ingress (`CKU × 60 MBps`)
- Critical: `> 80%` sustained ≥ 10 min → add CKUs

**Pros (Low Value):** Headroom against the per-CKU ingress ceiling; producers are not throttled, and the cluster can absorb burst traffic without backpressure or quota rejection.
**Cons (High Value):** Approaching the ingress cliff. Beyond the limit Confluent throttles produce requests, driving up produce latency and `record-error-rate`. On **Enterprise/elastic** tiers this absolute math is misleading — use `cluster_load_percent` instead (see Premise #1 in source review).

### 1.3 received_records  *(CC Metrics API — produce record rate)* — **inverted (drop is bad)**
**Description:** Count of records produced into the cluster. The canonical "Messages Produced" signal (the old named tile duplicated this).
**Recommended Range:**
- Healthy: within Davis auto-adaptive baseline band for the time-of-day
- Critical: sustained drop toward `0` during expected traffic **or** spike beyond ingress capacity

**Pros (Healthy Value):** Steady, baseline-consistent record flow confirms upstream producers are live and the produce path is healthy end-to-end.
**Cons (Anomalous Value):** A sustained drop signals a stalled/dead producer or upstream outage — for exactly-once and regulatory pipelines this is a **completeness gap**, so pair the Davis baseline with a **static floor** so a slow drift can't be normalized away. A spike risks hitting the ingress cliff (see 1.2).

### 1.4 request_bytes  *(CC Metrics API — produce bytes by `principal_id`)*
**Description:** Produce-side request bytes attributed per principal; the produce half of the showback pair (consume half = `response_bytes`).
**Recommended Range:**
- Healthy: within each principal's expected envelope
- Critical: anomalous spike vs that principal's baseline

**Pros (Low/Stable Value):** Clean per-principal attribution for chargeback/showback; no single producer dominating cluster ingress.
**Cons (High Value):** A runaway or misconfigured producer (noisy neighbor) consuming disproportionate ingress — a cost and a capacity risk. Best surfaced as a drill-down split by `principal_id`, not a top-level alert.

### 1.5 rest_produce_request_bytes  *(CC Metrics API — REST v3 Produce)*
**Description:** Bytes produced via the v3 REST Produce API; a **subset** of `received_bytes`. Only meaningful if REST Proxy is in use.
**Recommended Range:**
- Healthy: within REST-client baseline (or `0` if REST Proxy is not deployed)
- Critical: unexpected non-zero where REST is not authorized, or spike vs baseline

**Pros (Low Value):** Confirms REST produce traffic is within expectation; the bulk of ingress is going through native clients (lower per-record overhead).
**Cons (High Value):** REST produce carries higher per-request overhead than native protocol; a rising share can inflate request latency. *Verdict in source review: semantics reasonable but MCP-unconfirmed — validate only if REST Proxy is actually deployed.*

### 1.6 producer.request.latency.avg  *(KIP-714 client telemetry — requires librdkafka ≥ 2.5.3)*
**Description:** End-to-end produce request latency including network + client queue time (broader than broker-side `request_latencies`).
**Recommended Range:** **tier-scoped — set from the workload's FSI SLA budget**
- Healthy: within SLA tier (sub-ms market data · <10 ms risk · <100 ms compliance · async reconciliation)
- Critical: `>` the tier budget

**Pros (Low Value):** Confirms the full client→broker→ack path meets the workload's latency SLA, including client-queue and network contributions the broker metric can't see.
**Cons (High Value):** Breach of the workload's latency budget — for a risk-tier workload an 80 ms latency is already 8× over budget. *Exact metric key + librdkafka floor flagged as a separate workstream in the source review — confirm against the deployed client build before alerting.*

---

## 2. Consumer (consume path — egress)

### 2.1 consumer_lag_offsets  *(CC Metrics API — per `(group, topic, partition)` offset lag)*
**Description:** Offset distance between latest produced and last committed offset, per consumer group/topic/partition. Aggregate `max by consumer_group_id` at the top level — **summing across unrelated groups is meaningless**.
**Recommended Range:**
- Healthy: stable/near-zero; **time-lag** within the consumer's SLA
- Critical: monotonic growth, or time-lag `>` SLA

**Pros (Low Value):** Consumers are keeping pace with producers; data is fresh and downstream SLAs (risk, compliance) are met.
**Cons (High Value):** Consumers falling behind — under-provisioned consumer parallelism, slow processing, or rebalancing. **Prefer time-based lag (Lag Exporter)** over offset-based for alerting: 10k offsets means nothing without the produce rate to convert it to a time budget.

### 2.2 sent_bytes  *(CC Metrics API — egress throughput)*
**Description:** Bytes the broker sent to consumers (consume-side throughput; note: *sent*, not consumer-acked). `sum` over topics for cluster total.
**Recommended Range:**
- Healthy: `< 70%` of provisioned egress (`CKU × 180 MBps`)
- Critical: `> 80%` sustained ≥ 10 min → add CKUs

**Pros (Low Value):** Egress headroom; fan-out consumers and replication reads are served without throttling.
**Cons (High Value):** Approaching the egress cliff — high consumer fan-out or catch-up reads after lag can saturate egress faster than ingress. Throttled fetches increase consumer lag. Use `cluster_load_percent` on elastic tiers.

### 2.3 sent_records  *(CC Metrics API — consume record rate)* — **inverted (drop is bad)**
**Description:** Records the broker sent to consumers. The canonical "Messages Consumed" signal (the old named tile duplicated this); reflects what was *sent*, not consumer-confirmed.
**Recommended Range:**
- Healthy: within Davis baseline band, tracking `received_records`
- Critical: sustained drop while `received_records` holds (consumers stalled → lag building)

**Pros (Healthy Value):** Consume rate tracking produce rate confirms the end-to-end pipeline is balanced and consumers are draining the log.
**Cons (Anomalous Value):** A drop while production continues is the leading indicator of building `consumer_lag_offsets` — a stalled or crash-looping consumer group. Cross-reference with 2.1.

### 2.4 response_bytes  *(CC Metrics API — consume bytes by `principal_id`)*
**Description:** Consume-side response bytes per principal; the consume half of the showback pair (produce half = `request_bytes`).
**Recommended Range:**
- Healthy: within each principal's expected envelope
- Critical: anomalous spike vs that principal's baseline

**Pros (Low/Stable Value):** Clean per-consumer egress attribution for chargeback; no single consumer group dominating egress.
**Cons (High Value):** A runaway consumer (e.g., repeated full-history re-reads, offset reset to earliest) driving disproportionate egress and cost. Drill-down by `principal_id`.

---

## 3. Cluster

### 3.1 cluster_load_percent  *(Dedicated / Enterprise only)*
**Description:** Composite saturation index (CPU + network + request queues), already cluster-scoped and normalized 0–100. Aggregate `avg`, no split. The correct headline health metric — especially for elastic tiers where absolute throughput math doesn't apply.
**Recommended Range:**
- Healthy: `< 70%`
- Critical: `> 80%` sustained ≥ 10 min → scale CKUs

**Pros (Low Value):** A single, capacity-normalized health signal. Low values mean the cluster has headroom across *all* saturation dimensions, not just one. Immune to the 60/180 hardcoding problem.
**Cons (High Value):** Composite saturation cliff — produce/consume latency and throttling rise sharply past 80%. **Not emitted on Basic/Standard** — the tile renders empty there; confirm tier before leading the Health Summary with it.

### 3.2 partition_count  *(CC Metrics API — gauge)*
**Description:** Total partitions on the cluster. A **gauge** — aggregate `max`, never `sum`. *(Metric existence flagged MCP-unverified in the source review — validate against the live Metrics descriptor before building the tile.)*
**Recommended Range:**
- Healthy: `< 80%` of `CKU × 4,500`
- Critical: `> 90%` (immediate, no sustain window)

**Pros (Low Value):** Headroom against the hard per-CKU partition ceiling; new topics/partitions can be created without hitting a wall.
**Cons (High Value):** Partition limits are a **hard cliff** — at the ceiling, topic/partition creation fails outright. Immediate alert (no sustain window) because it blocks provisioning, not just degrades performance.

### 3.3 request_latencies  *(CC Metrics API — broker-side processing time, percentile-labeled)*
**Description:** Broker-side request processing time, **excludes network**. Percentile-labeled (`metric.percentile`) — aggregate `avg` over cluster but **keep the percentile dimension; never sum percentiles**.
**Recommended Range:** **tier-scoped, not cluster-global**
- Healthy: p99 within the workload's SLA tier
- Critical: p99 `>` tier budget *(placeholder 80 ms warn / 100 ms crit — Produce vs FetchConsumer differ materially; do not ship as a fixed FSI redline)*

**Pros (Low Value):** Broker is processing requests well within budget; the broker is not the latency bottleneck (isolates broker time from network/client).
**Cons (High Value):** Broker-side contention (queue buildup, GC, hot partitions). A single cluster-wide 80/100 ms redline is **meaningless across mixed FSI workloads** — already 8–10× over a risk-tier budget, irrelevant for reconciliation. Tag each latency tile with its SLA tier.

### 3.4 request_count {response_code = 429}  *(quota throttling)*
**Description:** Rate of throttled requests (HTTP 429) — the cluster is rejecting requests for exceeding a quota. *(Depends on `request_count` exposing a response-code dimension — MCP-unconfirmed in the source review; validate before building.)*
**Recommended Range:**
- Healthy: `0`
- Critical: rate `> 0`

**Pros (Low Value):** No quota throttling — clients are operating within provisioned ingress/egress/connection quotas.
**Cons (High Value):** Active throttling — a client is over quota; produce/consume latency rises and `record-error-rate` can follow. Indicates either an under-provisioned cluster or a misbehaving client. If the dimension is absent, source 429s client-side instead.

### 3.5 request_count {response_code = 403}  *(ACL / auth failures)*
**Description:** Rate of forbidden requests (HTTP 403) — failed authorization (ACL/RBAC) or credential issues. Same dimension caveat as 3.4.
**Recommended Range:**
- Healthy: `0`
- Critical: any sustained rise `> 0`

**Pros (Low Value):** No authorization failures — service accounts, ACLs, and RBAC bindings are correctly configured; no credential drift.
**Cons (High Value):** Rising 403s signal expired/rotated credentials, missing ACLs after a deploy, or — in an **FSI/mTLS+RBAC** context — a potential unauthorized-access probe worth a security review, not just an ops alert.

### 3.6 successful_authentication_count  *(CC Metrics API)* — **inverted (drop is bad)**
**Description:** Count of successful client authentications. *(Metric existence MCP-unverified in the source review.)*
**Recommended Range:**
- Healthy: within baseline for connected client population
- Critical: sustained **drop** (auth path failing) — Davis "drop-only" detection **plus a static floor**

**Pros (Healthy Value):** Steady auth success confirms clients are connecting and credentials/mTLS handshakes are valid across the fleet.
**Cons (Anomalous Value):** A drop means clients can no longer authenticate — broker auth outage, cert/credential expiry, or identity-provider failure. **FSI:** auth-success has regulatory consequence, so keep a hard static floor under the Davis baseline so a slow sustained decline can't be normalized away.

### 3.7 schema_count  *(Schema Registry — `io.confluent.kafka.schema_registry/schema_count`)*
**Description:** Total registered schemas across all subjects in the Schema Registry.
**Recommended Range:**
- Healthy: within the SR plan's schema/subject limit, growth tracking known onboarding
- Critical: approaching the registry cap, or unexpected growth (uncontrolled schema churn)

**Pros (Low/Stable Value):** Controlled schema growth indicates disciplined contract governance — `BACKWARD`/`FULL` compatibility gates are doing their job and schemas aren't proliferating per-deploy.
**Cons (High Value):** Approaching the registry limit blocks new subject registration. Runaway growth often signals a client registering a new schema version per restart (bad subject-naming or non-deterministic serialization) — a governance smell worth investigating.

---

## Producer / Consumer / Cluster bucket summary

| Bucket | Metrics |
|--------|---------|
| **Producer (ingress)** | `record-error-rate`*, `received_bytes`, `received_records`, `request_bytes`, `rest_produce_request_bytes`, `producer.request.latency.avg`* |
| **Consumer (egress)** | `consumer_lag_offsets`, `sent_bytes`, `sent_records`, `response_bytes` |
| **Cluster** | `cluster_load_percent`, `partition_count`, `request_latencies`, `request_count{429}`, `request_count{403}`, `successful_authentication_count`, `schema_count` |

\* client-side telemetry, not the CC Metrics API (JMX `record-error-rate`; KIP-714 `producer.request.latency.avg`).

**Carry-over validation flags from the source review (don't build tiles before confirming):** `partition_count` existence · `successful_authentication_count` existence · `request_count` response-code dimension (drives 3.4/3.5) · KIP-714 metric key + librdkafka floor · `rest_produce_request_bytes` (only if REST Proxy deployed). On **Enterprise/elastic** tiers, drop the absolute `CKU × limit` throughput redlines (1.2 / 2.2) in favor of `cluster_load_percent`.

---

*Validated against Confluent docs via MCP (2026-06-01, inherited from source review). 24 claims checked there, 3 corrected (per-CKU 50/150 → 60/180), 5 unverifiable/live-tenant-pending (carried as flags above).*
