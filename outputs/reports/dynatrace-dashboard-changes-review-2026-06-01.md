# Review: Dynatrace Confluent Cloud Dashboard — Dynatrace dashboard changes

**Date:** 2026-06-01
**Source files:** `dynatrace_dashboard_changes_handoff.md` (external handoff doc)
**Scope:** Confluent Cloud Metrics API field names + aggregation semantics, Dynatrace (Classic Metrics + DQL/Grail) dashboard construction, Davis anomaly detection vs static thresholds, per-CKU capacity limits, consumer-lag and Schema Registry observability.
**Claims extracted:** 24

---

## Summary

The handoff is **operationally sound and mostly accurate** — the aggregation-per-metric discipline (never sum percentiles, `max` for gauges, `sum` for throughput, `max by consumer_group_id` for lag) is correct and matches canon, and the static-vs-Davis split is the right call. There is **one hard factual error that must be fixed before redlines go live**: the per-CKU throughput figures (`50 MB/s ingress / 150 MB/s egress`) are wrong — Confluent's current published Dedicated per-CKU baseline is **60 MBps ingress / 180 MBps egress**. Every ingress/egress alert threshold derived from those numbers is ~17–20% too low and will fire early. Three metric identities (`partition_count`, `successful_authentication_count`, and `request_count`'s `response_code` dimension) could not be confirmed against the last MCP descriptor fetch and should be validated against the live tenant before tiles depend on them.

---

## Claim Validation

### A. Aggregate tile changes — aggregation semantics

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| dynatrace-1 | Top-level tiles collapse all dimensions (`splitBy()` / no `by:`), filter by `resource.kafka.id`; drill-downs split by `topic`/`principal_id` | observability-metrics-mapping | confluent-docs (DQL syntax) | — | — | Confirmed |
| dynatrace-2 | `cluster_load_percent` → `avg`, already cluster-scoped, no split | cc-cluster-tiers; observability-metrics-mapping | confluent-docs | — | — | Confirmed |
| dynatrace-3 | `partition_count` → `max` (gauge, don't sum) | observability-metrics-mapping (⚠️ flags metric unverified) | — | — | — | Unverifiable |
| dynatrace-4 | `received_bytes`/`sent_bytes` → `sum` over topics for cluster throughput | observability-metrics-mapping | confluent-docs | — | — | Confirmed |
| dynatrace-5 | `request_latencies` → `avg` over cluster, **keep `metric.percentile` dim, never sum percentiles** | observability-metrics-mapping | — | — | — | Confirmed |
| dynatrace-6 | `consumer_lag_offsets` → `max by consumer_group_id` at top level; summing across unrelated groups is meaningless | consumer-lag-monitoring; observability-metrics-mapping | confluent-docs | — | — | Confirmed |

**Corrections:** none. Aggregation logic is correct throughout. Note on #3: the *aggregator choice* (`max`) is right for a gauge — the caveat is metric-existence (see Gaps), not the math.

### B. Tile rename / remove / relocate — metric identity

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| dynatrace-7 | "Messages Produced" duplicates `received_records`; "Messages Consumed" duplicates `sent_records` | observability-metrics-mapping | — | — | — | Confirmed |
| dynatrace-8 | `received_records` = records produced; `sent_records` = records broker *sent* to consumers (not consumer-acked) | observability-metrics-mapping | — | — | — | Confirmed |
| dynatrace-9 | Second "Request bytes by principal" tile is actually `response_bytes`; pairs with `request_bytes` for showback | — | — | — | — | Unverifiable |

**Corrections:** none blocking. #9 is a local dashboard-config assertion (which tile holds which metric) — not externally verifiable from canon; trust the dashboard owner's tile inspection. The `request_bytes` (produce) / `response_bytes` (consume) showback pairing is conceptually correct.

### C. Alerts — thresholds and modes

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| dynatrace-10 | `cluster_load_percent` static 70% warn / 80% crit, 10 min sustained → scale CKUs | cc-cluster-tiers | confluent-docs | — | — | Confirmed |
| dynatrace-11 | **`received_bytes` redline = 70% of `CKU × 50 MB/s`** | cc-cluster-tiers (60 MBps) | confluent-docs (cluster-types) | — | — | **Corrected** |
| dynatrace-12 | **`sent_bytes` redline = 70% of `CKU × 150 MB/s`** | cc-cluster-tiers (180 MBps) | confluent-docs (cluster-types) | — | — | **Corrected** |
| dynatrace-13 | **"Per-CKU values current as of Confluent docs: 50 MB/s ingress, 150 MB/s egress per CKU"** | cc-cluster-tiers (60/180) | confluent-docs (cluster-types) | — | — | **Corrected** |
| dynatrace-14 | `partition_count` static 80/90% of `CKU × per_CKU_limit`, immediate | cc-cluster-tiers (4,500/CKU) | — | — | — | Confirmed (method) |
| dynatrace-15 | Broker Request Latency (`request_latencies`) p99 static 80 ms / 100 ms | observability-metrics-mapping | — | — | — | Unverifiable |
| dynatrace-16 | `request_count{code=429}` rate>0 → quota throttle; `{code=403}` rise → ACL/cred issue | observability-metrics-mapping | — | — | — | Unverifiable |
| dynatrace-17 | Static for cliff metrics, Davis auto-adaptive baseline for gradient metrics | observability-metrics-mapping | — | — | — | Confirmed |
| dynatrace-18 | Time-based lag (via Lag Exporter) preferred over offset-based for `consumer_lag_offsets` alerting | consumer-lag-monitoring | — | — | — | Confirmed |

**Corrections:**
- **Claim #dynatrace-11/12/13 (per-CKU throughput):** The handoff states **50 MB/s ingress / 150 MB/s egress per CKU**. Confluent's current published figures for Dedicated are **60 MBps ingress / 180 MBps egress per CKU** (confirmed via `confluent-docs` MCP, `clusters/cluster-types.html` — the per-eCKU/CKU row reads Ingress `5|25|60|60|60`, Egress `15|75|180|180|180` across Basic/Standard/Enterprise/Dedicated/Freight; cross-checked by the doc's own elastic-scaling line "an additional 4 eCKU of capacity (240 MBps ingress / 720 MBps egress)" → 240/4 = 60, 720/4 = 180). Wiki `cc-cluster-tiers.md` (validated 2026-05-14) independently lists 60/180. **Impact:** every ingress/egress redline computed from 50/150 is ~17% (ingress) / ~17% (egress) too low; a 70% warn at the wrong base = warning at ~58% of true capacity. Recompute all throughput thresholds against 60/180, or — better, per the doc's own advice — pull live limits from CC Console → Cluster Settings → Capacity and stop hardcoding. The doc's process guidance ("store resolved limits in a dashboard variable, recompute on CKU change") is correct; only the seed numbers are wrong.
- **Claim #dynatrace-15 (p99 80/100 ms):** plausible but not a canonical value — broker `request_latencies` p99 thresholds are workload- and request-type-dependent (Produce vs FetchConsumer differ materially). Treat 80/100 ms as a starting placeholder and confirm against this cluster's observed baseline; do not ship as a fixed FSI redline without a per-workload SLA reference (see Premise Challenge #3).
- **Claim #dynatrace-16 (`request_count` filtered by response code):** the alerting design depends on `request_count` exposing a `metric.response_code` (or equivalent) label so 429/403 can be isolated. That dimension was **not** confirmed in the last MCP descriptor fetch (the wiki maps `request_count` to `RequestsPerSec` with `request=*` type labels, not response codes). Validate that `response_code` is a queryable dimension on `request_count` in this tenant before building the 429/403 tiles; if it is not, these alerts need a different metric source (e.g., client-side or audit-log-derived).

### D. Per-metric glossary

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| dynatrace-19 | `cluster_load_percent` = composite saturation (CPU+network+queues), available on **Dedicated/Enterprise** | cc-cluster-tiers | confluent-docs | — | — | Confirmed |
| dynatrace-20 | `consumer_lag_offsets` = per-(group,topic,partition) **offset** lag, not time lag | consumer-lag-monitoring | — | — | — | Confirmed |
| dynatrace-21 | `request_latencies` = broker-side processing time, percentile-labeled, **excludes network** | observability-metrics-mapping | — | — | — | Confirmed |
| dynatrace-22 | KIP-714 `producer.request.latency.avg` = end-to-end incl. network + client queue; requires librdkafka ≥ 2.5.3 | — | — | — | — | Unverifiable |
| dynatrace-23 | `schema_count` = total registered schemas across all subjects (`io.confluent.kafka.schema_registry/schema_count`) | schema-registry-observability; observability-metrics-mapping | confluent-docs | kafka-schema-registry | Out-of-scope | Confirmed |
| dynatrace-24 | `rest_produce_request_bytes` = bytes via v3 REST Produce API, subset of `received_bytes` | observability-metrics-mapping | — | — | — | Unverifiable |

**Corrections:**
- **Claim #dynatrace-22 (KIP-714):** directionally correct — KIP-714 client telemetry surfaces producer-side end-to-end latency and the librdkafka-≥2.5.3 floor is the right order of magnitude — but the exact metric key (`producer.request.latency.avg`) and the version pin should be confirmed against the client build in use; the doc itself scopes this as a separate workstream (Open Question #5), so this is a known-soft area, not an error.
- **Skill note:** schema-metric claims (#23) route to `kafka-schema-registry`, but that skill governs schema *extraction / PII tagging / Terraform registration*, not SR *observability metrics* — verdict **Out-of-scope**; MCP + wiki remain authoritative and confirm `schema_count`.

---

## Premise Challenge

| # | Premise | Assumption | Challenge | Severity |
|---|---------|------------|-----------|----------|
| 1 | Per-CKU capacity is a fixed, known constant suitable for hardcoded static redlines | Cluster is **Dedicated** with a stable manually-sized CKU count | If the cluster is **Enterprise** (eCKU-elastic, auto-scaling), there is no fixed CKU count — capacity floats with load, so static `CKU × per_CKU_limit` redlines are a moving target. `cluster_load_percent` (a saturation %, already normalized) is the correct top-level saturation signal for elastic tiers, not absolute throughput math. Confirm tier before committing static throughput thresholds. | Critical |
| 2 | `cluster_load_percent` is available as the headline health metric | Cluster is Dedicated or Enterprise | The doc correctly notes this metric is **Dedicated/Enterprise only** — but the whole "Health Summary" top row leads with it. On Basic/Standard there is no `cluster_load_percent`; the top tile would render empty. Verify the tier matches the metric set (Open Question #2 is the right place to resolve this). | Moderate |
| 3 | Static p99 latency redlines (80/100 ms broker, per-workload producer) map to FSI SLA tiers | A single latency threshold fits all workloads on the cluster | Under FSI SLA tiers (sub-ms market data, <10 ms risk, <100 ms compliance, async reconciliation), a cluster-wide 80/100 ms broker-latency redline is meaningless for a risk-tier workload (already 8–10× its budget) and irrelevant for reconciliation. Latency redlines must be per-workload/per-tier, not cluster-global. The doc gestures at this ("per-workload SLA" for producer latency) but hardcodes 80/100 for broker. | Moderate |
| 4 | Davis auto-adaptive baselines are appropriate for the listed gradient metrics in a regulated context | Anomaly-on-deviation is acceptable for all non-cliff signals | For metrics tied to **regulatory reporting completeness** (e.g., `successful_authentication_count`, produce/consume record rates feeding exactly-once pipelines), a learned baseline can normalize a slow, sustained drift and suppress an alert that compliance would want raised. Keep a static floor alongside Davis for any metric whose absence/drop has regulatory consequence. The doc's instinct (static for cliffs, Davis for gradients) is sound; the FSI overlay just narrows what counts as a "gradient." | Moderate |
| 5 | `request_count` can be filtered by HTTP/response code for 429/403 tiles | CC `request_count` exposes a response-code dimension | Not confirmed in the last MCP descriptor; if absent, the 429 quota-throttle and 403 ACL tiles have no data source. | Moderate |

---

## Canon Compliance

| Area | Status | Notes |
|------|--------|-------|
| Per-CKU capacity figures | ❌ Deviation | Doc uses 50/150 MB/s; canon (`cc-cluster-tiers.md`, MCP-confirmed) is **60/180 MBps**. Must fix. |
| Aggregation discipline (gauges `max`, throughput `sum`, never sum percentiles) | ✅ Compliant | Matches `observability-metrics-mapping.md` DQL examples. |
| Consumer-lag approach (offset vs time-based, `max by consumer_group_id`) | ✅ Compliant | Matches `consumer-lag-monitoring.md`; doc correctly flags time-based as preferred. |
| FSI SLA-tier alignment of latency redlines | ⚠️ Partial | Cluster-global static p99 conflicts with per-tier SLA framing (sub-ms / <10ms / <100ms / async). Make latency redlines tier-scoped. |
| Security/RBAC posture (auditor isolation, mTLS) | ➖ N/A | Read-only dashboard doc; no RBAC/credential claims. WIKI-03 payload-isolation trigger did not fire (no cluster-scoped DeveloperRead claim present). |
| Metric-existence validation against live descriptor | ⚠️ Partial | `partition_count`, `successful_authentication_count`, `request_count.response_code` not MCP-confirmed in the 2026-05-20 fetch (per wiki ⚠️ markers). Validate against live tenant. |

---

## Gaps

Claims that could not be verified by wiki or MCP and are candidates for live-tenant validation:

1. **`partition_count` metric existence** — `observability-metrics-mapping.md` explicitly flags this as unverified against the 2026-05-20 Metrics API descriptor. The `max` aggregator is correct *if* the metric exists; confirm against the live [Metrics Reference](https://docs.confluent.io/cloud/current/monitoring/metrics-reference.html).
2. **`successful_authentication_count` metric existence** — same ⚠️ marker in the wiki; the Davis "drop only" design depends on it being emitted.
3. **`request_count` response-code dimension** — required for the 429/403 alert tiles; not confirmed (see Correction #16).
4. **KIP-714 `producer.request.latency.avg` exact key + librdkafka floor** — confirm against the deployed client build (doc already scopes as a separate workstream).
5. **`rest_produce_request_bytes` / `_request_count` semantics** — "subset of `received_bytes`" and derived-avg-payload-size logic are reasonable but unconfirmed; validate only if REST Proxy is actually in use (Open Question #3).

No new auto-stubs queued — all claim topics are covered by existing wiki articles (`observability-metrics-mapping`, `consumer-lag-monitoring`, `cc-cluster-tiers`, `schema-registry-observability`).

---

## Recommendations

1. **Fix the per-CKU numbers before anything ships.** Replace `50 MB/s ingress / 150 MB/s egress` with **60 MBps / 180 MBps** everywhere (Section C table rows for `received_bytes`/`sent_bytes`, and the "Per-CKU values" callout). Better: implement the doc's own variable-driven approach — resolve limits from CC Console → Cluster Settings → Capacity at build time and bind to a dashboard variable, so the figures can never drift again.
2. **Resolve the cluster tier first (Open Question #2 is load-bearing).** If Enterprise/elastic, drop static throughput-vs-CKU redlines in favor of `cluster_load_percent` saturation and Davis-on-throughput; static `CKU × limit` math only makes sense on Dedicated.
3. **Make latency redlines per-workload, not cluster-global.** Tag each latency tile with its FSI SLA tier and set the redline from the tier budget (risk <10 ms, compliance <100 ms). The blanket broker 80/100 ms will both over- and under-alert across mixed workloads.
4. **Validate the three soft metrics against the live tenant** (`partition_count`, `successful_authentication_count`, `request_count.response_code`) before building tiles that depend on them — a tile bound to a non-existent metric/dimension renders empty and erodes trust in the board.
5. **Keep a static floor under regulatory-sensitive Davis baselines.** For auth-success and produce/consume record rates feeding exactly-once / regulatory pipelines, pair the auto-adaptive baseline with a hard floor so a slow sustained drop can't be normalized away.
6. **Everything else is good to build.** Aggregation semantics, the remove/rename/relocate plan, the two-tier top-level/drill-down structure, the static-vs-Davis split, and pinning the Davis problem feed at the top are all sound and consistent with canon.

---

Canon stack: base + industry/fsi | Hash: 437a88b8eb364e19 | MANIFEST: 1.1.0 | Floor: claude-opus-4-8 | Generated: 2026-06-02T02:14:22Z
