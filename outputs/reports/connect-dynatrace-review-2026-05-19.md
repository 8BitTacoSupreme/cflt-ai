# Review: Connect Dynatrace Monitoring (DQL Dashboard + Migration Guide)

**Date:** 2026-05-19
**Source files:** `Connect_DQL_Dashboard_Config.md`, `Connect_Dynatrace_Monitoring_Guide.md`
**Scope:** Confluent Kafka Connect (self-managed, distributed), Dynatrace observability (DQL, OneAgent JMX, dashboards, alerting), Splunk → Dynatrace migration, Connect DLQ monitoring, Terraform-based IaC for Dynatrace.
**Claims extracted:** 32 (dql: 15, guide: 17)

## Summary

Both documents are **directionally useful as design sketches** for a Connect observability rollout, but they share a **load-bearing technical error**: the "DQL" examples are not Dynatrace Grail DQL — they use a colon-prefixed selector syntax (`:fields()`, `:splitBy()`, `:filter()`, `:max`, `:rate()`) that resembles the older **Dynatrace Metric Selector v2** language, not the Grail query language Dynatrace markets as "DQL" today. Every dashboard query, alert expression, and migration example in both files will need to be rewritten before it executes. Secondary issues: several Connect JMX MBean attribute names are wrong (`connector-errors-total`, `connector-status`, `connector-state`, `put_rate` placement, `__dlq-{connector_name}` consumer-group convention), the JMX exposure configuration **directly violates FSI security canon** (`jmxremote.authenticate=false`, `jmxremote.ssl=false`), and the implicit DLQ monitoring model assumes a consumer group that Connect does not create automatically. Recommend treating both docs as architecture-level scaffolding only and rebuilding the query/alert layer against real DQL + actual Connect 3.x/4.x MBean names before hand-off.

## Claim Extraction (YAML)

```yaml
claims:
  - id: dql-1
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "Migration Note: Splunk → Dynatrace DQL Translation"
    category: config_value
    text: "Splunk `stats latest`/`avg`/`count`/`by` map to DQL `:max`/`:latest`/`:avg`/`:count()`/`:splitBy(\"dim\")` and `where value>x` maps to `:filter(gt(\"field\", threshold))`."
  - id: dql-2
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "Migration Note"
    category: config_value
    text: "Example DQL: `confluent_kafka.server.cluster_load_percent :max`."
  - id: dql-3
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "A.1 Connector State & Task Summary"
    category: config_value
    text: "Connect MBean `kafka.connect:type=connector-task-metrics` has dimensions `connector`, `task_id` and field `status`; `kafka.connect:type=connector-metrics` has fields `connector_status = status` and `connector_state`."
  - id: dql-4
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "A.2 Task State & Restarts"
    category: metric_sla
    text: "Any task with status = FAILED for 1+ minute → P1 page."
  - id: dql-5
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "A.3 Throughput"
    category: config_value
    text: "Sink task put rate via `kafka.connect:type=sink-task-metrics … :fields(put_rate)`; source task via `:fields(poll_rate)`; `:rate()` converts cumulative metric to trend over time."
  - id: dql-6
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "A.4 Errors & Dead Letter Queue"
    category: config_value
    text: "Error count via `kafka.connect:type=connector-metrics … :fields(connector_errors_total) :rate()`; DLQ topic naming is `__dlq-{sink_name}`."
  - id: dql-7
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "A.4 Errors & Dead Letter Queue"
    category: architecture_choice
    text: "Monitor DLQ via `confluent_kafka.server.consumer_lag_offsets :filter(eq(\"consumer_group_id\", \"__dlq-{connector_name}\"))`."
  - id: dql-8
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "A.5 Source Connector Offset Lag"
    category: config_value
    text: "Postgres CDC offset lag via `consumer_group_id=\"postgres-cdc-offsets\"`."
  - id: dql-9
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "A.5 Source Connector Offset Lag"
    category: config_value
    text: "REST-API source has `time_since_last_poll_ms` on source-task-metrics."
  - id: dql-10
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "B Dashboard 4 Configuration"
    category: architecture_choice
    text: "Dashboard 4 driven by single `$connector_name` variable plus optional `$task_id`; six rows from Health → Throughput → Errors → Offsets → Resources → Operational Links."
  - id: dql-11
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "C Alert Rules"
    category: metric_sla
    text: "Error Rate >5 errors/min sustained 5 min → P2 Slack."
  - id: dql-12
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "C Alert Rules"
    category: metric_sla
    text: "Put rate == 0 sustained >5 min → P2 (no records being written)."
  - id: dql-13
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "C Alert Rules"
    category: metric_sla
    text: "Task restart count >3 transitions per hour → P2 (instability)."
  - id: dql-14
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "F Deployment Automation"
    category: config_value
    text: "Use Terraform provider `dynatrace-oss/dynatrace ~> 1.0`; store API token in HashiCorp Vault, not Git."
  - id: dql-15
    source_file: Connect_DQL_Dashboard_Config.md
    source_section: "Row 5 Resource Utilization"
    category: metric_sla
    text: "GC pause time max > 500 ms warrants investigation; correlate via OneAgent JVM metrics."

  - id: guide-1
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "1.1 Collection Architecture"
    category: config_value
    text: "Connect exposes JMX on a configurable port, typically 9101."
  - id: guide-2
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "1.1 Collection Architecture"
    category: config_value
    text: "Recommended JMX KAFKA_OPTS: `jmxremote.port=9101 jmxremote.authenticate=false jmxremote.ssl=false`."
  - id: guide-3
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "1.1 Collection Architecture"
    category: comparison
    text: "JMX scraping is preferred over Prometheus because OneAgent has native JMX support, delivers real-time metrics without Prometheus scrape-interval jitter, and integrates with Java process monitoring."
  - id: guide-4
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "1.2 Must-Have Connect Metrics"
    category: config_value
    text: "Task State MBean `kafka.connect:type=connector-task-metrics,connector={name},task={id}` exposes `status`; connector-level state via `kafka.connect:type=connector-metrics,connector={name}` → `connector-status`."
  - id: guide-5
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "1.2 Must-Have Connect Metrics"
    category: config_value
    text: "Throughput exposed on `kafka.connect:type=connector-task-metrics` as `put-rate` and `put-total`."
  - id: guide-6
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "1.2 Must-Have Connect Metrics"
    category: config_value
    text: "Connector error counter is `kafka.connect:type=connector-metrics … connector-errors-total`."
  - id: guide-7
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "1.2 Must-Have Connect Metrics"
    category: config_value
    text: "Restart count derived from `kafka.connect:type=task-metrics … status-time-ms`."
  - id: guide-8
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "1.2 Must-Have Connect Metrics"
    category: behavior_assertion
    text: "Some MBean states are strings (`status=RUNNING`), so alert rules use string matching; error counters are cumulative and require `:rate` for trend."
  - id: guide-9
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "1.2 Must-Have Connect Metrics"
    category: architecture_choice
    text: "DLQ records monitored by querying sink connector's `__dlq-{sink_name}` topic offset lag."
  - id: guide-10
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "2.1 Four-Dashboard Pattern"
    category: architecture_choice
    text: "Four-dashboard pattern: Platform Overview, Cluster Deep Dive, DR Readiness, Connect Deep Dive — with Connect deserving its own dashboard, not folded into broker views."
  - id: guide-11
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "Part 4 Alerting Rules"
    category: metric_sla
    text: "Task Failed = P1 (1 check); Connector Unhealthy = P1 (2 checks); DLQ Growing = P1 (3 min); Error rate >5/min = P2 (5 min); Task restarts >3/h = P2 (30 min); put-rate == 0 >5min = P2; Offset commit lag >60s = P3 (10 min)."
  - id: guide-12
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "Part 6 Deployment"
    category: architecture_choice
    text: "On FSI deployments deploy Connect workers as Kubernetes StatefulSet and OneAgent as DaemonSet."
  - id: guide-13
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "Part 8 Transitions from Cloud Metrics"
    category: comparison
    text: "Cloud `cluster_load_percent` is N/A for Connect (Connect is stateless); Cloud `task_failed_total` ≈ self-managed `connector-task-metrics.status`."
  - id: guide-14
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "A.3 Splunk Search → DQL Translation"
    category: config_value
    text: "Example DQL: `confluent_kafka.server.cluster_load_percent :filter(eq(\"dt.entity.confluent_kafka_cluster\",\"lkc-prod\")) :max`."
  - id: guide-15
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "A.4 Notification Routing"
    category: architecture_choice
    text: "Notification routing (PagerDuty/Opsgenie/Slack/Email) unchanged from Splunk; only the source of truth shifts."
  - id: guide-16
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "A.5 Audit Log Retention"
    category: architecture_choice
    text: "Kafka audit events remain in Splunk indefinitely; Dynatrace events default to 30 days, optionally extended."
  - id: guide-17
    source_file: Connect_Dynatrace_Monitoring_Guide.md
    source_section: "A.6 Migration Risks"
    category: architecture_choice
    text: "Parallel-run Splunk + Dynatrace for 2 weeks before cutover; run new alerts in audit/log-only mode for 1 week."
```

## Claim Validation

### Connect_DQL_Dashboard_Config.md — DQL Syntax

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| dql-1 | DQL aggregators `:max`/`:avg`/`:splitBy()`/`:filter(gt(...))` | — | Dynatrace Docs (DQL Grail reference) | **Corrected** |
| dql-2 | DQL expression `confluent_kafka.server.cluster_load_percent :max` | — | Dynatrace Docs | **Corrected** |
| dql-14 | Terraform `dynatrace-oss/dynatrace ~> 1.0`, secrets in Vault | — | Terraform Registry | Confirmed (provider exists) — pin to ~> 1.50 (current as of 2026) |
| dql-15 | GC pause > 500 ms = investigate | — | — | Confirmed (commonly accepted heuristic; not canon) |

**Corrections:**

- **dql-1, dql-2 (and pervasive throughout both docs):** This syntax is **not Dynatrace DQL**. It is the older **Dynatrace v2 Metric Selector** language (e.g., `builtin:host.cpu.usage:max:splitBy("dt.entity.host")`). Real Grail DQL is pipe-chained, e.g.:
  ```dql
  timeseries val = avg(kafka.connect.task.status), by:{connector, task_id}
  | filter connector == "$connector_name"
  | filter val == "FAILED"
  ```
  or for log/event data:
  ```dql
  fetch logs, from:now()-1h
  | filter dt.source_entity == "kafka_connect"
  | summarize count(), by:{connector, status}
  ```
  **All 30+ query/alert expressions in both documents must be rewritten** before they execute against a Grail tenant. The two languages are not interchangeable: metric selectors only address pre-defined metric IDs, while DQL queries any bucket (logs, events, metrics, spans, business events). For alert rules, Dynatrace supports both selector-based and DQL-based alerts; the docs conflate the two.

### Connect_DQL_Dashboard_Config.md — Connect JMX Claims

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| dql-3 | `connector-task-metrics` has `connector`/`task_id` dims and `status` field; `connector-metrics` has `connector_status = status` and `connector_state` | [kafka-connect-deployment-models](wiki/concepts/kafka-connect-deployment-models.md) | Apache Kafka Connect monitoring docs | **Corrected** |
| dql-4 | Task FAILED 1+ min → P1 | [dead-letter-queue-design](wiki/patterns/dead-letter-queue-design.md) (monitoring section) | — | Confirmed |
| dql-5 | `put_rate`/`poll_rate` fields; `:rate()` converts cumulative to rate | — | Connect JMX docs | **Corrected** |
| dql-6 | `connector_errors_total` on connector-metrics; DLQ topic `__dlq-{sink_name}` | [dead-letter-queue-design](wiki/patterns/dead-letter-queue-design.md) | Connect KIP-298 docs | **Corrected** |
| dql-7 | DLQ monitored via `consumer_lag_offsets` filter `__dlq-{connector_name}` | [dead-letter-queue-design](wiki/patterns/dead-letter-queue-design.md) | — | **Corrected** |
| dql-8 | Postgres CDC lag via consumer group `postgres-cdc-offsets` | [cdc-source-connector-setup](wiki/concepts/cdc-source-connector-setup.md) | — | **Corrected** |
| dql-9 | Source-task-metrics has `time_since_last_poll_ms` | — | Connect JMX docs | **Corrected** |
| dql-10 | 6-row dashboard layout | — | — | Confirmed (design choice; no canon contradiction) |
| dql-11 | Error rate >5/min sustained 5 min → P2 | [dead-letter-queue-design](wiki/patterns/dead-letter-queue-design.md) (DLQ rate >5% of throughput heuristic) | — | Confirmed |
| dql-12 | Put-rate == 0 >5 min → P2 | — | — | Confirmed (reasonable heuristic) |
| dql-13 | Restart count >3/hour → P2 | — | — | Confirmed (reasonable heuristic) |

**Corrections:**

- **dql-3:** Connect's actual MBean attribute names:
  - `kafka.connect:type=connector-task-metrics` exposes `status` (string: `running`/`failed`/`paused`/`unassigned`/`destroyed`/`restarting`), `status-time-ms`, `offset-commit-success-percentage`, `offset-commit-failure-percentage`, etc. ✓
  - `kafka.connect:type=connector-metrics` does **not** expose attributes named `connector_status` or `connector_state`. Real attributes are `connector-class`, `connector-version`, `connector-type` (source/sink), `status` (since Apache Kafka 2.0 — string). Connector-level health is canonically retrieved via the **REST API** (`GET /connectors/{name}/status`), not JMX.
- **dql-5:** Sink throughput is not `put_rate`. Real Connect 3.x/4.x sink attributes on `kafka.connect:type=sink-task-metrics`: `sink-record-read-rate`, `sink-record-send-rate`, `sink-record-active-count`, `put-batch-avg-time-ms`, `put-batch-max-time-ms`, `partition-count`. Source attributes on `source-task-metrics`: `source-record-poll-rate`, `source-record-write-rate`, `source-record-write-total`. There is no `put_rate` or `poll_rate` attribute. Also, `:rate()` is not a DQL function — DQL uses `rate()` inside `timeseries` (e.g., `timeseries val=rate(metric)`).
- **dql-6:** Connect cumulative error counters live on `kafka.connect:type=task-error-metrics,connector={n},task={n}`, not on `connector-metrics`. Real attributes: `total-record-errors`, `total-record-failures`, `total-records-skipped`, `total-retries`, `deadletterqueue-produce-requests`, `deadletterqueue-produce-failures`, `last-error-timestamp`. There is no attribute named `connector-errors-total` / `connector_errors_total`. Also, DLQ topic naming is not `__dlq-<sink_name>` — Connect has **no default DLQ topic**; the operator names it via `errors.deadletterqueue.topic.name`. Wiki convention (`wiki/patterns/dead-letter-queue-design.md`) is `dlq.<connector-name>` (e.g., `dlq.jdbc-sink-orders`). The `__` (double-underscore) prefix is reserved for Kafka internal topics (`__consumer_offsets`, `__transaction_state`) and should not be used for application topics.
- **dql-7:** Connect does **not** create a consumer group reading the DLQ topic. `confluent_kafka.server.consumer_lag_offsets` reports lag of *existing* consumer groups; there is no group called `__dlq-{connector_name}`. To measure DLQ growth you query the DLQ topic's **log-end-offset / message rate** directly, or you deploy a dedicated DLQ replay consumer and monitor *its* lag. Use `confluent_kafka.server.received_records` filtered to the DLQ topic, or the broker's `kafka.log:type=Log,name=LogEndOffset,topic=<dlq>,partition=*` metric.
- **dql-8:** Postgres-CDC connectors (Debezium) **do not write progress into a Kafka consumer group named `postgres-cdc-offsets`**. Debezium writes WAL position progress into the Connect framework's `offset.storage.topic` (one internal Kafka topic for the whole worker cluster) keyed by connector name. To monitor logical-replication lag you either (a) query Postgres directly (`pg_stat_replication.replay_lsn` vs `pg_current_wal_lsn()`), or (b) use Debezium's own metrics MBean `debezium.postgres:type=connector-metrics,context=streaming,name={server}` which exposes `MilliSecondsBehindSource`, `NumberOfDisconnects`, `SourceEventPosition`.
- **dql-9:** `time_since_last_poll_ms` is not a standard Connect source-task-metrics attribute. Real source attributes include `poll-batch-avg-time-ms`, `poll-batch-max-time-ms`, `source-record-poll-rate`. To detect a stuck source you watch for `source-record-poll-rate == 0` sustained, or correlate `poll-batch-max-time-ms` exceeding `poll.interval.ms`.

### Connect_Dynatrace_Monitoring_Guide.md — JMX / Collection

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| guide-1 | JMX exposed on configurable port, typically 9101 | — | Confluent Platform docs | **Corrected** |
| guide-2 | KAFKA_OPTS uses port=9101, authenticate=false, ssl=false | — | Apache Kafka docs | **Corrected** (FSI canon violation) |
| guide-3 | OneAgent native JMX preferred over Prometheus | — | Dynatrace Extensions docs | Unverifiable as stated |

**Corrections:**

- **guide-1:** There is no canonical Confluent default JMX port for Connect. The Confluent Platform `cp-kafka-connect` Docker image exposes JMX via the `KAFKA_JMX_PORT` env var, conventionally set to **9999** in CP examples, not 9101. CFK (Confluent for Kubernetes) defaults to `7203` for some components. Cite an authoritative source or remove "typically 9101" — the number reads as canonical but isn't.
- **guide-2:** This config disables JMX authentication and TLS. **This directly violates the FSI canon's security baseline** (CLAUDE.md → "Security: mTLS + RBAC in regulated environments; never username/password in FSI"). Acceptable on a developer laptop, never acceptable on a prod FSI Connect cluster. The doc should:
  - Set `jmxremote.authenticate=true` with a password file (`jmxremote.password.file`) or JAAS config
  - Set `jmxremote.ssl=true` with proper keystore/truststore
  - Bind JMX to localhost only and have OneAgent scrape locally (so JMX never traverses the network in cleartext)
  - Document explicitly that the `authenticate=false ssl=false` form is **dev-only**
- **guide-3:** The comparison "JMX has no scrape-interval jitter, Prometheus does" is misleading. Dynatrace's JMX extension is also poll-based (default 1-minute scrape, configurable). Native JMX vs Prometheus-via-JMX-exporter is a real choice, but the deciding factor is operational fit (do you already run a Prometheus stack?), not scrape jitter. Recommendation stands ("JMX if starting fresh, Prometheus if already in place") but rationale needs rewriting.

### Connect_Dynatrace_Monitoring_Guide.md — Connect Metric Names

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| guide-4 | Task state via `connector-task-metrics.status`; connector via `connector-metrics.connector-status` | [kafka-connect-deployment-models](wiki/concepts/kafka-connect-deployment-models.md) | Apache Kafka docs | **Corrected** |
| guide-5 | Throughput on `connector-task-metrics.put-rate`/`put-total` | — | Apache Kafka docs | **Corrected** |
| guide-6 | Errors on `connector-metrics.connector-errors-total` | — | Apache Kafka docs | **Corrected** |
| guide-7 | Restart count derived from `task-metrics.status-time-ms` | — | Apache Kafka docs | **Corrected** |
| guide-8 | Some states are strings; error counters need `:rate` | — | Apache Kafka docs | Confirmed (concept) |
| guide-9 | DLQ via querying `__dlq-{sink_name}` topic offset lag | [dead-letter-queue-design](wiki/patterns/dead-letter-queue-design.md) | — | **Corrected** |

**Corrections:**

- **guide-4:** Per-task `status` attribute is correct (on `connector-task-metrics`). However `connector-status` is **not** an attribute name on `connector-metrics`. The connector-level rollup status is exposed via REST `GET /connectors/{name}/status`, not JMX. If you need it in Dynatrace, scrape the REST API via an extension or shell out and synthesize the metric.
- **guide-5:** Same correction as dql-5. The Connect MBean attributes for sink throughput are on `kafka.connect:type=sink-task-metrics` (not `connector-task-metrics`) and are named `sink-record-send-rate`, `sink-record-active-count`, etc. `put-rate` and `put-total` are not standard attribute names. Source-side uses `source-task-metrics` with `source-record-poll-rate`, `source-record-write-rate`.
- **guide-6:** Connect error counters live on `kafka.connect:type=task-error-metrics,connector={n},task={n}` with attributes `total-record-errors`, `total-record-failures`, `total-records-skipped`. `connector-errors-total` is not real.
- **guide-7:** No MBean `task-metrics` exists; the prefix is `connector-task-metrics`. `status-time-ms` exists and reports the time the task has been in its current status (useful for "how long in FAILED" alerts), but is not a restart counter. Restart count must be derived from `connector-startup-attempts-total` / `connector-startup-failure-total` on `connector-metrics`, or from log/event ingestion of state transitions.
- **guide-9:** As with dql-7: no auto-created consumer group reads the DLQ. Monitor the DLQ topic's log-end-offset rate-of-change, or instrument a replay consumer and watch its lag.

### Connect_Dynatrace_Monitoring_Guide.md — Architecture & Migration

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| guide-10 | Four-dashboard pattern with separate Connect dashboard | — | — | Confirmed (sound choice; aligns with concept-deep-dive separation in wiki) |
| guide-11 | P1/P2/P3 alert thresholds | [dead-letter-queue-design](wiki/patterns/dead-letter-queue-design.md) (monitoring) | — | Confirmed (reasonable; tune per workload) |
| guide-12 | K8s StatefulSet for workers + DaemonSet for OneAgent | [kafka-connect-deployment-models](wiki/concepts/kafka-connect-deployment-models.md) | — | Unverifiable / **Corrected** |
| guide-13 | Cloud `cluster_load_percent` N/A for Connect; `task_failed_total` ≈ self-managed status | — | Confluent Cloud Metrics API docs | Confirmed |
| guide-14 | Example DQL with `:filter(eq("dt.entity.confluent_kafka_cluster","lkc-prod")) :max` | — | Dynatrace Docs | **Corrected** (same DQL-syntax issue as dql-1/2) |
| guide-15 | Notification routing unchanged from Splunk | — | — | Confirmed |
| guide-16 | Audit logs stay in Splunk; Dynatrace events default 30 days | [fsi-compliance](wiki/concepts/fsi-compliance.md), [audit-log-siem-integration](wiki/patterns/audit-log-siem-integration.md) | — | Confirmed (aligns with FSI audit-retention canon) |
| guide-17 | 2-week parallel run + 1-week audit-mode alerts | — | — | Confirmed (sound migration risk control) |

**Corrections:**

- **guide-12:** Connect distributed workers are **stateless** with respect to per-pod identity — there is no stable per-pod state to preserve (offsets/configs/status all live in Kafka topics, not on disk). The canonical Kubernetes deployment is **Deployment** (or CFK's `Connect` CR which uses StatefulSet for ordering but the framework requirement is just "N workers sharing a group.id"). StatefulSet is over-prescriptive and adds rolling-update friction without benefit. Recommendation: Deployment (or CFK Connect CR) + HPA. JMX port stability comes from the service, not StatefulSet identity. See `wiki/concepts/kafka-connect-deployment-models.md` for the framework state model.

## Premise Challenge

| # | Premise | Assumption | Challenge | Severity |
|---|---------|------------|-----------|----------|
| 1 | "DQL" in the dashboard examples is real Dynatrace Grail DQL. | Customer can paste the queries into Dynatrace and they'll execute. | The syntax used (`:fields()`, `:splitBy()`, `:filter()`, `:rate()`) is the **v2 metric selector** language, not DQL. Real Grail DQL is pipe-based (`timeseries val=avg(metric) | filter ... | summarize ...`). Every query will need to be rewritten. The migration table claiming "Splunk → DQL" mapping is itself wrong — it maps Splunk SPL to the selector language. | **Critical** |
| 2 | OneAgent can natively scrape JMX string attributes (`status=RUNNING`) and surface them as alert-queryable metrics. | "String states are fine, alert rules use string matching." | OneAgent's JMX extension treats JMX attributes as numeric metrics by default. String-valued attributes (Connect's `status`) require an extension that maps each string to a numeric enum (e.g., `running=1, failed=2`) or ingestion as log/event data. The doc skips this — without the mapping layer the "Failed Tasks count" tile cannot be built as described. | **Critical** |
| 3 | JMX can be exposed `jmxremote.authenticate=false jmxremote.ssl=false` in production. | These flags are acceptable defaults; "proper SSL for prod" is a checklist item, not a blocker. | This directly violates the FSI security canon (mTLS + RBAC, never plaintext auth). For FSI deployments this configuration would fail any pre-prod security review and likely fail an SR / compliance gate. JMX exposes process-level controls (heap dump, runtime config); a plaintext JMX port on a FSI host is a P0 security finding. | **Critical** (FSI overlay) |
| 4 | The DLQ has, or should have, an auto-created consumer group named `__dlq-{connector_name}` that we can monitor via `consumer_lag_offsets`. | Querying consumer lag gives us "DLQ growing" signal. | Connect does not create a DLQ consumer group. The DLQ is a producer-only target. "Lag" of zero on a non-existent group is meaningless. Real DLQ growth monitoring uses log-end-offset rate-of-change on the DLQ topic, or instruments a replay consumer separately. | **Critical** |
| 5 | The full Cloud "broker health" mental model maps to self-managed Connect. | Translation tables ("Cloud `cluster_load_percent` → self-managed X") capture the relevant differences. | Connect's health model is fundamentally state-machine + REST-API-shaped, not capacity-shaped. The doc acknowledges this in Part 5 ("Connect requires its own dashboard") but the Part 1.2 / Part 8 mapping tables undermine that by listing "Cloud metric → Connect metric" rows for metrics that don't map. Make the rows say "Cloud: capacity model. Connect: state model." | Moderate |

## Canon Compliance

| Area | Status | Notes |
|------|--------|-------|
| Topic Design (naming, RF, ISR) | N/A — not addressed | The docs don't speak to Kafka topic design. |
| Schema Registry | N/A — not addressed | — |
| Producer / Consumer defaults | N/A — not addressed | — |
| Flink SQL | N/A — not addressed | — |
| Cluster Linking / DR | N/A — not addressed | DR dashboard mentioned only as out-of-scope (Dashboard 3, unchanged). |
| **Security (mTLS, RBAC, audit log)** | **Violation** | JMX exposure `authenticate=false ssl=false` (guide §1.1, §6) directly contradicts FSI canon. Must be hardened or explicitly scoped to dev. The Vault-for-secrets pattern (dql-14) is canon-compliant. |
| **Audit log retention** | **Compliant** | Keeping Kafka audit events in Splunk (guide §A.5) aligns with FSI long-retention compliance overlay. |
| **FSI vendor-backing rule (Confluent contract coverage)** | Aligned | The docs target self-managed Connect (acceptable when fully-managed gap exists — see `wiki/patterns/connect-deployment-models.md`). The implicit assumption that Connect is self-managed should be made explicit; for net-new FSI deployments the canon default is fully-managed CC connectors (`wiki/patterns/fsi-canon-overlay-for-confluent-skills.md`). |
| **DLQ canon (naming, headers)** | Drift | Both docs use `__dlq-<name>` prefix; wiki canon (`wiki/patterns/dead-letter-queue-design.md`) is `dlq.<connector-name>`. `__` is reserved for Kafka internal topics. |
| **Connect deployment model** | Drift | Both docs assume self-managed-distributed. FSI canon defaults to fully-managed; self-managed is the escape hatch when there's no managed connector match, EOS source matters, or network locality forces it. Doc should state the trigger explicitly. |
| Kubernetes runtime topology | Drift (minor) | StatefulSet is over-prescriptive; Deployment or CFK Connect CR is canonical. |

## Gaps

The following claims could not be verified against wiki or MCP within this review:

- Exact Dynatrace Grail DQL function names and pipe grammar (validated against general Dynatrace docs knowledge; should be re-validated against the target tenant version — Grail DQL has evolved across 2024–2026 releases).
- Real-world OneAgent JMX extension behavior for **string-valued** MBean attributes (does it ingest as dimension on a synthetic metric, drop, or require explicit string-to-enum mapping?). The guide assumes this works transparently — needs confirmation against Dynatrace Extensions 2.0 spec.
- Whether `dynatrace_event_alert` (Terraform provider) supports DQL-based alert conditions natively, or only metric-selector conditions. The Terraform snippet in dql-14 leaves this unspecified.
- Per-tenant retention for Dynatrace events beyond the default 30 days — quote `guide-16` says "adjustable" without a citation.
- Debezium / Postgres-CDC offset lag MBean (`MilliSecondsBehindSource`) availability across all CDC source types. The guide handles only Debezium-shaped sources.

Auto-stub candidates added to `wiki/_queue.md`:
- `dynatrace-connect-observability` — Dynatrace dashboards/alerts for self-managed Kafka Connect, mapping JMX to Dynatrace extension metrics.
- `dynatrace-dql-for-confluent` — Real Grail DQL patterns for Confluent (cluster, consumer-lag, Connect) — needed because both reviewed docs got the syntax wrong.

## Recommendations

1. **Rewrite all query/alert expressions in real DQL.** Replace `metric.name :max :splitBy("x")` with `timeseries val=avg(metric.name), by:{x}`. Replace `:filter(eq(...))` with `| filter <field> == <val>`. For alert rules in Dynatrace, choose **explicitly** between metric-selector-based and DQL-based alerts and stay consistent within the doc. **Until this is fixed, neither document is hand-off-ready.**
2. **Audit every Connect JMX MBean / attribute against Apache Kafka 4.x docs.** The Connect MBean tree is well-documented at https://kafka.apache.org/documentation/#connect_monitoring — copy attribute names verbatim. Specific fixes:
   - `connector-errors-total` → `total-record-errors` / `total-record-failures` (on `task-error-metrics`)
   - `put-rate` / `poll-rate` → `sink-record-send-rate` / `source-record-poll-rate` (on `sink-task-metrics` / `source-task-metrics`)
   - Connector-level `status` → REST API `GET /connectors/{name}/status`, not JMX
3. **Harden JMX exposure for FSI.** Replace the `authenticate=false ssl=false` block with a JAAS- or password-file-backed JMX auth + truststore/keystore TLS, or scope JMX to `localhost` and let OneAgent (running on the same node) scrape locally. Add an explicit "dev vs prod" callout box so the dev-laptop config can't accidentally ship to prod.
4. **Rewrite the DLQ monitoring section.** Replace the `consumer_lag_offsets` filter on `__dlq-{connector}` with one of: (a) topic-level log-end-offset rate (broker-side metric), (b) connector's own `deadletterqueue-produce-requests` counter on `task-error-metrics` (most direct), (c) a dedicated DLQ replay consumer whose lag you monitor. Update DLQ topic naming to the wiki canon `dlq.<connector-name>` and drop the `__` prefix.
5. **Make the deployment model explicit.** State at the top of the guide: "This guide targets **self-managed Connect distributed** — choose this only when fully-managed CC connectors do not cover your source/sink (see `wiki/patterns/connect-deployment-models.md`)." For the FSI default, point to the fully-managed observability path (CC Metrics API → Dynatrace Confluent extension).
6. **Switch StatefulSet to Deployment** (or CFK Connect CR) for Connect workers. Add a one-sentence rationale: "Workers are stateless w.r.t. pod identity; framework state lives in internal Kafka topics. Deployment + HPA is the canonical topology."
7. **Add a converter / Schema Registry monitoring section.** Both docs are silent on the most common Connect failure mode in FSI: converter mismatch (Avro/Protobuf source produced + JSON sink converter configured = silent DLQ flood). Watch `total-record-errors` per stage = `VALUE_CONVERTER`.
8. **Drop the bare `connector_state` attribute reference** in the DQL doc — there is no such attribute; the field exists only in the REST API response. Either document the REST-scrape pattern or remove the row.
9. **Validate against the target Dynatrace tenant before publishing.** Many of the corrections above are documentation-level; the only way to verify Dynatrace-side claims is to run them in the actual environment.

---

Canon stack: base + industry/fsi | Hash: pending (no resolver invocation in this run) | MANIFEST: pending | Floor: claude-opus-4-7 | Generated: 2026-05-19T14:28:34Z
