---
title: Wiki Observability Expansion — CC vs Self-Managed Gap Closure
date: 2026-05-20
query: "Does the wiki/repo have sufficient telemetry to cover Confluent Cloud vs self-managed?"
wiki_sources:
  - concepts/observability-metrics-mapping
  - concepts/confluent-platform-broker-jmx
  - concepts/schema-registry-observability
  - concepts/ksqldb-observability
  - patterns/cfk-observability-baseline
  - patterns/cluster-linking-observability
  - concepts/fsi-data-streaming-platform (back-pointer patch)
claims_checked: 30+
claims_corrected: 4
claims_unverifiable: 9
---

# Wiki Observability Expansion — CC vs Self-Managed Gap Closure

## TL;DR

Six new wiki articles closed the largest gap in the cflt-ai observability coverage — self-managed Schema Registry, ksqlDB, broker JMX (canonical reference), CFK Helm/Prometheus baseline, and Cluster Linking DR dashboards. Expected coverage lift: ~40% → ~75% of the Confluent deployment landscape. Residual gaps (REST Proxy, KIP-714 client telemetry) flagged as backlog. All articles MCP-validated against `confluent-docs` on 2026-05-20; confidence levels and inline `⚠️ unverified` markers are noted per article.

## Coverage Matrix — Before / After

Same matrix as the 2026-05-19 audit, updated cells in **bold**.

| Component | CC Managed | Self-Managed VM | Self-Managed K8s/CFK |
|---|---|---|---|
| Broker/Cluster | ✓ Consumer Lag Monitoring, FSI-DSP article | **✓ confluent-platform-broker-jmx** (was ~) | **✓ cfk-observability-baseline + broker-jmx** (was ~) |
| Connect | ~ Audit log only | ✓ Connect_Dynatrace docs (root-level) | ✓ Same |
| Schema Registry | **✓ schema-registry-observability** (was ✗) | **✓ schema-registry-observability** (was ✗) | **✓ schema-registry-observability + cfk-baseline** (was ✗) |
| Flink | ✓ flink-runtime-models | ~ Mentioned (CMF) | ~ LinuxONE article |
| ksqlDB | **✓ ksqldb-observability** (was ✗) | **✓ ksqldb-observability** (was ✗) | **✓ ksqldb-observability + cfk-baseline** (was ✗) |
| Cluster Linking | ✓ DR pattern + metrics-mapping raw | **✓ cluster-linking-observability** (was ~) | **✓ cluster-linking-observability + cfk-baseline** (was ~) |
| REST Proxy | ✗ | ✗ | ✗ (out of scope; low FSI demand) |
| Client (KIP-714) | ✗ | ✗ | ✗ (out of scope; CP 7.7+ required) |
| Security/Audit logs | ✓ Audit Log SIEM Integration | ✗ | ✗ |

## Analysis

### Articles Created (6)

1. **`wiki/concepts/observability-metrics-mapping.md`** (concept, 122 lines, confidence: medium) — the spine. Cross-provider mapping table (CC Metrics API + JMX MBean → PromQL/DQL/SPL/NRQL/Datadog/Instana) grouped into Cluster Health / Consumer Lag / Connect / DR / Flink / Schema Registry / ksqlDB. Sourced from the un-wikified `raw/repos/fsi-dsp/observability/metrics-mapping.md` plus MCP-validated CC Metrics API namespace.
2. **`wiki/concepts/confluent-platform-broker-jmx.md`** (concept, ~150 lines, confidence: medium) — canonical broker MBean reference. Organized by subsystem (Replication+ISR / Throughput / Network request-stages / FetcherLag / Controller / Storage). Per-tier alert threshold matrix + Prometheus JMX exporter rule excerpt. Sourced from the production-validated fsi-dsp `jmx-exporter-config.yaml` (9 patterns) plus the well-established Apache Kafka broker MBean tree.
3. **`wiki/concepts/schema-registry-observability.md`** (concept, ~120 lines, confidence: high) — 3 SR JMX MBeans (`jetty-metrics`, `master-slave-role`, `jersey-metrics` with per-endpoint attributes) MCP-confirmed via confluent-docs schema-registry/monitoring.html. CC surface (`schema_count`) documented as a known thin surface; client-side wrapper compensation pattern included.
4. **`wiki/patterns/cfk-observability-baseline.md`** (pattern, ~180 lines, confidence: high) — Prometheus + JMX exporter + Grafana wiring for CFK. CR `spec.metrics` fields, Vault-injected JMX credentials (with file permissions 0600/0644), ServiceMonitor scrape with mTLS, log aggregation patterns, FSI overlay. MCP-validated against confluent-docs operator/co-monitor-cp.html + co-deploy-cfk.html.
5. **`wiki/patterns/cluster-linking-observability.md`** (pattern, ~150 lines, confidence: medium) — DR/RPO/RTO dashboards. Mirror lag (CC Metrics API + CLI `PartitionMirrorLag` + CP JMX) + mirror topic state machine (`PENDING_STOPPED`/`STOPPED`/`SOURCE_UNAVAILABLE`) + per-SLA-tier ADR-008 thresholds + failover-readiness checklist. MCP-validated against confluent-docs cluster-linking/dr-failover.html.
6. **`wiki/concepts/ksqldb-observability.md`** (concept, ~150 lines, confidence: medium) — closes the only zero-coverage component gap. CC Metrics API surface (10 metrics MCP-confirmed) + self-managed JMX (`io.confluent.ksql.metrics:*`) + underlying Kafka Streams runtime MBeans + alert patterns + DLQ routing.

### Articles Modified (1)

- **`wiki/concepts/fsi-data-streaming-platform.md`** — Observability section patched with back-pointers to the new spine and the 5 component-specific articles.

### Wiki Plumbing Updated

- `wiki/_index.md`: 6 new Concepts/Patterns entries
- `wiki/_graph.md`: 35 new outbound + 21 new inbound backlinks across 6 new sections
- `raw/_ingest.md`: 6 entries moved Pending → Processed with full MCP-validation notes

### MCP Validation Summary

| Tool | Pages fetched | Confirmed claims | Unverified flags |
|---|---|---|---|
| `confluent-docs/cloud/.../monitoring/metrics-api.html` | 1 | 13 (CC namespace structure + 10+ exact metric names) | — |
| `confluent-docs/platform/.../kafka/monitoring.html` + `jmx-overview.html` | 2 | Broker MBean families confirmed by reference; specific attributes from production-validated source | 2 (extended controller MBeans, conversion timing) |
| `confluent-docs/platform/.../schema-registry/monitoring.html` | 1 | 3 SR MBeans + all attribute sets | 1 (CC SR rate-limit thresholds) |
| `confluent-docs/operator/.../co-monitor-cp.html` + `co-deploy-cfk.html` | 2 | CFK Helm install, Vault sidecar JMX injection, file permissions, CRD fields | — |
| `confluent-docs/cloud/.../cluster-linking/dr-failover.html` + `index.html` | 2 | CL mirror state machine, CLI surfaces, RPO/RTO concepts, `cluster_link_destination_response_bytes` | 2 (exact mirror lag metric ID, CP self-managed CL JMX MBean) |
| `confluent-docs/platform/.../ksqldb/.../monitoring.html` + `streams/monitoring.html` | 2 | ksqlDB MBean families (engine, queries, pull-queries, push-queries) and Kafka Streams MBean tree by reference | 1 (exact ksqlDB attribute names) |

### Corrections Surfaced

Four claims from the source material were corrected during ingest:

1. CC Flink CFU metric: source repo uses `current_cfu` + `max_cfu`; MCP-confirmed canonical name is `compute_pool_utilization` (consolidated). Flagged in article 1.
2. CC `cluster_link_mirror_topic_offset_lag` exact name not surfaced in 2026-05-20 MCP fetch; the CL family does include `cluster_link_destination_response_bytes`. Marked unverified pending live-tenant revalidation. Flagged in articles 1 and 5.
3. CC `partition_count` and `successful_authentication_count`: not surfaced in 2026-05-20 metrics descriptor; may have moved namespace. Marked unverified in article 1.
4. JMX port convention: source uses 9101 (open-source convention); CFK bundled exporter uses 7203. Both documented in article 4 with explicit "standardize one per env" guidance.

## Decision Framework — When to use which article

- **If diagnosing or building monitoring for any Confluent component across providers** → start at `observability-metrics-mapping`, then drill into the component-specific article
- **If self-managed broker JMX exposure on CP/CFK** → `confluent-platform-broker-jmx` for the MBean reference + `cfk-observability-baseline` for the K8s wiring
- **If Schema Registry governance / FSI compliance audit** → `schema-registry-observability` (covers both CC + self-managed)
- **If DR readiness dashboards / RPO-RTO reporting** → `cluster-linking-observability`
- **If ksqlDB query observability (any deployment)** → `ksqldb-observability`
- **If FSI/CFK Prometheus stack rollout** → `cfk-observability-baseline` end-to-end

## Caveats

- **No `/wiki:validate` run yet.** Most articles set `confidence: medium`. A follow-up `/wiki:validate --scope observability` is recommended within 90 days to promote articles whose unverified markers resolve cleanly.
- **9 inline `⚠️ unverified` markers** distributed across the 6 articles (per article 1's 3 markers, article 2's 2, article 3's 1, article 5's 2, article 6's 1). All represent claims sourced from authoritative material that the 2026-05-20 MCP fetch did not surface cleanly — verify against live tenant or current Metrics Reference before high-stakes production use.
- **REST Proxy and KIP-714 client telemetry remain ✗** in the coverage matrix. Deferred to backlog per plan; low FSI demand.
- **Per-provider query syntax** in the spine is sourced from the fsi-dsp repo (authoritative for that platform's deployment) but not re-validated against current Grafana/Dynatrace/Splunk/New Relic/Datadog/Instana docs. The DQL Connect docs revision (root-level `Connect_Dynatrace_Monitoring_Guide.md`) showed this kind of staleness can bite.
- **Lint clean** but the pre-existing vendor-source DRIFT on `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` (source=1.0.0… vs pin=91d1871e…) is unrelated to this expansion and remains for a future cleanup pass.

## Next Actions (Backlog)

1. **`/wiki:validate --scope observability`** — promote articles to `confidence: high` where MCP-validated; queue `Unverified Claims to Resolve` items in `wiki/_queue.md`
2. **REST Proxy observability stub** — add to `wiki/_queue.md` Stubs to Create for the next ingest cycle
3. **KIP-714 client telemetry article** — add to `wiki/_queue.md` (CP 7.7+ dependency)
4. **Commit cadence** — atomic article commits deferred during this expansion due to tangled pre-existing un-committed state in `wiki/_index.md`, `wiki/_graph.md`, `raw/_ingest.md`. User to commit at preferred granularity.

---

*Validated against Confluent docs via confluent-docs MCP (2026-05-20). 30+ claims checked, 4 corrected, 9 unverifiable (flagged inline).*
