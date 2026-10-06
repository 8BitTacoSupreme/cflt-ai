# Connect Dynatrace Monitoring: DQL Queries & Dashboard Config

> **Companion to** `Connect_Dynatrace_Monitoring_Guide.md`. The Guide explains the architecture, collection model, security baseline, and dashboard layout. This doc is the **query and dashboard JSON reference** — every DQL expression below is real Dynatrace **Grail DQL** (pipe-based), and every JMX MBean / attribute name is verified against Apache Kafka 4.x `connect_monitoring` documentation.

## DQL syntax note (read first)

Dynatrace supports two query languages:

- **v2 metric selector** — older, colon-prefixed (`metric.name:max:splitBy("x")`). Used by `metrics:query` REST endpoint and the legacy alerting engine ("metric event" rules). Limited to pre-defined numeric metric IDs.
- **Grail DQL** — current, pipe-based (`timeseries val=avg(metric), by:{x} | filter ... | summarize ...`). Queries logs, events, metrics, spans, and business events. Powers Davis AI alerts.

**This doc uses Grail DQL throughout.** A few alert-rule examples additionally show the metric-selector equivalent where the metric-event rule type is more ergonomic. The two languages are **not interchangeable** — copy/pasting v2 selectors into a DQL prompt will fail.

## Splunk SPL → Grail DQL concept mapping

| Splunk Concept | Grail DQL Equivalent |
|---|---|
| `source=… metric_name=X` | `timeseries val = avg(X), by:{...}` |
| `\| stats latest(value)` | `\| fieldsAdd latest = val[-1]` |
| `\| stats avg(value)` | `timeseries val = avg(metric), …` |
| `\| stats count` | `\| summarize n = count()` |
| `\| stats … by dim` | `by:{dim}` in `timeseries` / `summarize` |
| `\| where value > t` | `\| filter val[-1] > t` |
| `\| timechart avg(value)` | `timeseries val = avg(metric), interval:1m` |
| `\| alert` | DQL-based alert rule with severity field |

**Example:** Splunk `source=confluent_metrics metric_name=cluster_load_percent | stats latest(value)` becomes:

```dql
timeseries load = max(confluent_kafka.server.cluster_load_percent),
           by:{dt.entity.confluent_kafka_cluster},
           from:now()-5m
| fieldsAdd latest = load[-1]
```

---

## Part A: DQL Queries for Connect JMX Metrics

The Dynatrace JMX Extension 2.0 ingests Apache Kafka Connect MBean attributes as Dynatrace metrics under the namespace `kafka.connect.*` (your extension YAML decides the exact names; the examples below use one canonical mapping — adapt to your extension if you renamed things).

**Status-attribute enum mapping.** Connect's `status` MBean attribute is a string (`running`/`failed`/`paused`/`unassigned`/`destroyed`/`restarting`). The extension must map it to an integer for alerting. Canonical mapping:

| `status` value | `status_code` |
|---|---|
| `running` | 0 |
| `paused` | 1 |
| `unassigned` | 2 |
| `restarting` | 3 |
| `failed` | 4 |
| `destroyed` | 5 |
| (any other) | -1 |

Alert on `status_code >= 4`. See `Connect_Dynatrace_Monitoring_Guide.md` §1.3 for the extension YAML.

### A.1 Connector State & Task Summary

**Query: All connectors with task-state rollup**

```dql
// Connector-level health (one row per connector)
timeseries
    total    = max(kafka.connect.connector.task.count),
    running  = max(kafka.connect.connector.task.running),
    failed   = max(kafka.connect.connector.task.failed),
    paused   = max(kafka.connect.connector.task.paused),
    by:{connector, connector_class, connector_type},
    from:now()-5m
| fieldsAdd
    total_v   = total[-1],
    running_v = running[-1],
    failed_v  = failed[-1],
    paused_v  = paused[-1]
| fieldsAdd health = if(failed_v > 0, "red",
                         if(running_v < total_v, "yellow", "green"))
| sort failed_v desc, connector asc
```

Sources: `kafka.connect:type=connector-metrics` attributes `connector-total-task-count`, `connector-running-task-count`, `connector-failed-task-count`, `connector-paused-task-count`, `connector-class`, `connector-type` (Apache Kafka ≥ 2.3, KIP-475).

**Query: Per-task state with status text**

```dql
timeseries code = avg(kafka.connect.task.status_code),
           by:{connector, task_id, status_text},
           from:now()-15m
| filter connector == "$connector_name"
| fieldsAdd current = code[-1]
| sort task_id asc
```

### A.2 Task State Transitions & Restarts

**Query: How long has the task been in its current state?**

```dql
// status-time-ms reports time in current state (since Apache Kafka 2.0)
timeseries age = max(kafka.connect.task.status_time_ms),
           by:{connector, task_id, status_text},
           from:now()-1h
| filter connector == "$connector_name"
| fieldsAdd seconds_in_state = age[-1] / 1000
```

**Query: Task startup failures (proxy for restart count)**

Connect's MBean tree does not expose a per-task "restart count." Use worker-level startup-failure counters instead, or derive from status-transition log events.

```dql
// Worker-level task startup failures, last hour
timeseries failed_starts = sum(kafka.connect.worker.task_startup.failure.total),
           by:{worker_host},
           from:now()-1h,
           interval:5m
| fieldsAdd rate_per_hour = failed_starts[-1] - failed_starts[0]
```

Source: `kafka.connect:type=connect-worker-metrics` → `task-startup-failure-total`.

**Alert: Task Failed (DQL-based)**

```dql
timeseries code = max(kafka.connect.task.status_code),
           by:{connector, task_id, status_text},
           from:now()-5m
| filter code[-1] >= 4
| fieldsAdd severity = "CRITICAL"
```

Condition: Any task with `status_code >= 4` for ≥ 1 minute → P1 page.

### A.3 Throughput: Send / Poll Rates

**Sink task send rate (records/sec written to destination):**

```dql
timeseries send_rate = avg(kafka.connect.sink.record.send.rate),
           by:{connector, task_id},
           from:now()-1h,
           interval:1m
| filter connector == "$connector_name"
```

Source: `kafka.connect:type=sink-task-metrics` → `sink-record-send-rate` (records/sec, already a rate — **do not** wrap in another rate function).

**Sink task read rate (records/sec read from Kafka):**

```dql
timeseries read_rate = avg(kafka.connect.sink.record.read.rate),
           by:{connector, task_id},
           from:now()-1h,
           interval:1m
| filter connector == "$connector_name"
```

Source: `sink-task-metrics` → `sink-record-read-rate`.

**Source task poll rate (records/sec read from upstream):**

```dql
timeseries poll_rate = avg(kafka.connect.source.record.poll.rate),
           by:{connector, task_id},
           from:now()-1h,
           interval:1m
| filter connector == "$connector_name"
```

Source: `kafka.connect:type=source-task-metrics` → `source-record-poll-rate`.

**Source task write rate (records/sec written to Kafka):**

```dql
timeseries write_rate = avg(kafka.connect.source.record.write.rate),
           by:{connector, task_id},
           from:now()-1h,
           interval:1m
| filter connector == "$connector_name"
```

Source: `source-task-metrics` → `source-record-write-rate`.

**Records active (in-flight):**

```dql
timeseries active = avg(kafka.connect.sink.record.active.count),
           by:{connector, task_id},
           from:now()-1h
| filter connector == "$connector_name"
```

Source: `sink-task-metrics` → `sink-record-active-count` (or `source-record-active-count` for source connectors).

**Batch latency:**

```dql
timeseries
    put_avg_ms = avg(kafka.connect.sink.put.batch.avg.time.ms),
    put_max_ms = max(kafka.connect.sink.put.batch.max.time.ms),
    by:{connector, task_id},
    from:now()-1h,
    interval:1m
| filter connector == "$connector_name"
```

Source: `sink-task-metrics` → `put-batch-avg-time-ms`, `put-batch-max-time-ms` (or `poll-batch-*-time-ms` on source).

### A.4 Errors & Dead Letter Queue

Connect error counters live on **`kafka.connect:type=task-error-metrics`** (one MBean per task), not on `connector-metrics`.

**Query: Cumulative error counters per task**

```dql
timeseries
    errors    = max(kafka.connect.task.errors.total),
    failures  = max(kafka.connect.task.failures.total),
    skipped   = max(kafka.connect.task.skipped.total),
    retries   = max(kafka.connect.task.retries.total),
    by:{connector, task_id},
    from:now()-1h,
    interval:1m
| filter connector == "$connector_name"
```

Sources: `task-error-metrics` → `total-record-errors`, `total-record-failures`, `total-records-skipped`, `total-retries`.

**Query: Error rate (per minute, derived from cumulative counter)**

```dql
timeseries err = max(kafka.connect.task.errors.total),
           by:{connector, task_id},
           from:now()-1h,
           interval:1m
| filter connector == "$connector_name"
| fieldsAdd err_per_min = (err[-1] - err[0]) / 60
```

For a streaming rate use the `rate()` aggregator on the counter:

```dql
timeseries err_rate = rate(kafka.connect.task.errors.total, time:1m),
           by:{connector, task_id},
           from:now()-1h,
           interval:1m
| filter connector == "$connector_name"
```

### A.5 Dead Letter Queue — the right way

**Connect does not create a consumer group reading the DLQ topic.** Querying `confluent_kafka.server.consumer_lag_offsets` for a group like `__dlq-<connector>` returns nothing because that group does not exist. Use one of the three patterns below instead.

**Topic naming:** wiki canon is `dlq.<connector-name>` (e.g., `dlq.jdbc-sink-orders`). **Do not** prefix with `__` — that prefix is reserved for Kafka internal topics (`__consumer_offsets`, `__transaction_state`). Set the topic via the connector config `errors.deadletterqueue.topic.name`.

**Pattern 1 (most direct): DLQ produce counters from the connector itself**

```dql
// Records the connector wrote TO the DLQ
timeseries dlq_produced = rate(kafka.connect.task.dlq.produce.requests, time:1m),
           by:{connector, task_id},
           from:now()-1h,
           interval:1m
| filter connector == "$connector_name"
```

Source: `task-error-metrics` → `deadletterqueue-produce-requests` (cumulative; wrap in `rate()`).

**Records the connector FAILED to write to the DLQ (silent data loss):**

```dql
timeseries dlq_failed = rate(kafka.connect.task.dlq.produce.failures, time:1m),
           by:{connector, task_id},
           from:now()-1h,
           interval:1m
| filter connector == "$connector_name"
```

Source: `task-error-metrics` → `deadletterqueue-produce-failures`.

**Pattern 2: DLQ topic log-end-offset rate (broker-side)**

```dql
// Rate of new messages landing in the DLQ topic
timeseries leo = rate(confluent_kafka.server.log_end_offset, time:1m),
           by:{topic, partition, dt.entity.confluent_kafka_cluster},
           from:now()-1h,
           interval:1m
| filter matchesPhrase(topic, "dlq.")
| filter dt.entity.confluent_kafka_cluster == "$cluster_id"
```

Source: broker-side `kafka.log:type=Log,name=LogEndOffset,topic=<dlq>,partition=*` (or equivalent Confluent metric).

**Pattern 3: Deliberate replay-consumer lag**

If you operate a DLQ replay consumer (a service that reads the DLQ to retry or quarantine records), monitor *its* lag:

```dql
timeseries lag = avg(confluent_kafka.server.consumer_lag_offsets),
           by:{consumer_group_id, topic, dt.entity.confluent_kafka_cluster},
           from:now()-15m
| filter consumer_group_id == "dlq-replay-$connector_name"
| filter matchesPhrase(topic, "dlq.")
```

This is the only valid case for `consumer_lag_offsets` against DLQ topics — you own the consumer group.

**Alert: DLQ growing (Pattern 1, recommended)**

```dql
timeseries dlq_rate = rate(kafka.connect.task.dlq.produce.requests, time:1m),
           by:{connector, task_id},
           from:now()-5m
| filter dlq_rate[-1] > 0
| fieldsAdd severity = "CRITICAL"
```

Condition: any DLQ produces sustained ≥ 3 min → P1 page (data quality / loss risk).

### A.6 Per-Stage Error Breakdown (FSI Must-Have)

The **#1 silent failure mode in FSI Connect** is converter mismatch (Avro/Protobuf produced upstream, JSON converter configured on the sink → every record hits DLQ). The error counters above show the spike but not where in the pipeline it broke.

Connect logs the stage on each error event (`KEY_CONVERTER`, `VALUE_CONVERTER`, `HEADER_CONVERTER`, `TRANSFORMATION`, `KAFKA_CONSUME`, `KAFKA_PRODUCE`, `TASK_PUT`, `TASK_POLL`). Ingest the Connect log into Dynatrace (Log Management) and query:

```dql
fetch logs, from:now()-1h
| filter dt.process.name == "kafka-connect"
| filter matchesPhrase(content, "ERROR")
| parse content, """LD '[' DATA:stage ']'"""
| summarize errors = count(),
            by:{connector, task_id, stage}
| sort errors desc
```

Spike on `stage == "VALUE_CONVERTER"` → converter mismatch. Spike on `KAFKA_PRODUCE` → sink-side Kafka issue. Spike on `TRANSFORMATION` → SMT bug.

### A.7 Source-System Lag

This is connector-specific. The doc-DQL-config view focuses on three common shapes:

**Debezium (Postgres, MySQL, MongoDB, SQL Server, Oracle):**

Debezium exposes its own MBeans (not under `kafka.connect:*`). Example for Postgres:

```dql
// MilliSecondsBehindSource = how far behind the WAL the connector is
timeseries lag_ms = max(debezium.postgres.streaming.MilliSecondsBehindSource),
           by:{server_name},
           from:now()-1h,
           interval:1m
```

Source: `debezium.postgres:type=connector-metrics,context=streaming,name=<server>` → `MilliSecondsBehindSource`, `NumberOfDisconnects`, `SourceEventPosition`. Equivalent MBeans exist for `debezium.mysql`, `debezium.mongodb`, `debezium.sqlserver`, `debezium.oracle`.

**Backup pattern — query Postgres directly:**

```sql
-- pg_stat_replication, queried via Dynatrace SQL Extension
SELECT application_name,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replay_lag_bytes,
       pg_wal_lsn_diff(pg_current_wal_lsn(), flush_lsn)  AS flush_lag_bytes
  FROM pg_stat_replication
 WHERE application_name = 'connect-pg-cdc-orders';
```

**JDBC source (poll-based, not CDC):**

```dql
timeseries
    poll_max_ms = max(kafka.connect.source.poll.batch.max.time.ms),
    poll_rate   = avg(kafka.connect.source.record.poll.rate),
    by:{connector, task_id},
    from:now()-1h,
    interval:1m
| filter connector == "$connector_name"
| fieldsAdd stuck = if(poll_rate[-1] == 0 AND poll_max_ms[-1] > 30000, true, false)
```

Detect stuck polls: poll-batch-max exceeding `poll.interval.ms` while rate is 0.

**File-based / object-store sources (S3 source, FilePulse):**

```dql
timeseries
    poll_rate  = avg(kafka.connect.source.record.poll.rate),
    write_rate = avg(kafka.connect.source.record.write.rate),
    by:{connector, task_id},
    from:now()-1h,
    interval:1m
| filter connector == "$connector_name"
```

There's no generic "files processed" attribute — instrument that in the connector or via S3 inventory if you need it.

### A.8 Sink Target Correlation

If the sink target is instrumented by OneAgent, correlate Connect throughput with target latency.

**Sink target = database (OneAgent DB monitoring):**

```dql
timeseries
    sink_rate    = avg(kafka.connect.sink.record.send.rate),
    db_latency   = avg(dt.entity.database_service.response_time),
    by:{connector, task_id},
    from:now()-1h
| filter connector == "$connector_name"
```

**Sink target = S3 / object store:**

S3 has no native "lag." Use object-write latency from AWS CloudWatch (via Dynatrace AWS integration) or correlate `put-batch-max-time-ms` from the connector itself.

---

## Part B: Dashboard 4 Configuration (Connect Deep Dive)

### B.1 Dashboard-Level Variables

**Variable 1: `$connector_name`**

```
Name: $connector_name
Type: Dimension (string)
Source: timeseries kafka.connect.connector.task.count, by:{connector}
Display format: Dropdown
Default: (first connector alphabetically)
Propagation: All tiles on dashboard
```

**Variable 2: `$task_id`** (optional, for deep drill-downs)

```
Name: $task_id
Type: Dimension (string)
Source: timeseries kafka.connect.task.status_code, by:{task_id}
Default: All (no filter)
Propagation: Rows 2-4 (task-level detail)
```

### B.2 Dashboard Structure (6 Rows)

#### Row 1: Health Summary

| Tile | Type | Metric / Query | Threshold | Notes |
|---|---|---|---|---|
| 1.1 | Single-value | Connector State (`status_text`) | `failed`/`destroyed` = red | Text + color from latest `status_code` |
| 1.2 | Single-value | Total Tasks (`connector-total-task-count`) | — | Informational |
| 1.3 | Single-value | Running Tasks (`connector-running-task-count`) | `< total` = yellow | Shows degradation |
| 1.4 | Single-value | Failed Tasks (`connector-failed-task-count`) | `> 0` = red, P1 alert | Critical |
| 1.5 | Single-value | Error rate (errors/min) | spike = yellow | `rate(total-record-errors)` |
| 1.6 | Single-value | DLQ Produce rate (records/min) | `> 0` = red, P1 | `rate(deadletterqueue-produce-requests)` |
| 1.7 | Time-series | Per-task `status_code` over 24h | spikes = restarts | Full-width row |

**Row 1 DQL (failed-task tile, 1.4):**

```dql
timeseries failed = max(kafka.connect.connector.task.failed),
           by:{connector},
           from:now()-5m
| filter connector == "$connector_name"
| fieldsAdd value = failed[-1]
```

#### Row 2: Throughput

| Tile | Type | Metric / Query | Notes |
|---|---|---|---|
| 2.1 | Line chart | `sink-record-send-rate` (sink) or `source-record-poll-rate` (source), split by `task_id` | Load balance across tasks |
| 2.2 | Line chart | `sink-record-active-count` (in-flight records) | Backpressure indicator |
| 2.3 | Line chart | `put-batch-max-time-ms` (sink) or `poll-batch-max-time-ms` (source) | Latency to target |

#### Row 3: Errors & DLQ

| Tile | Type | Metric / Query | Notes |
|---|---|---|---|
| 3.1 | Single-value | `rate(total-record-errors)` | Errors / minute |
| 3.2 | Time-series | `rate(total-record-errors)` 24h | Trend |
| 3.3 | Time-series | `rate(deadletterqueue-produce-requests)` 24h | DLQ growth |
| 3.4 | Single-value | `rate(deadletterqueue-produce-failures)` | **Silent data loss** if > 0 |
| 3.5 | Table | Per-stage error breakdown (DQL §A.6) | Identifies converter/SMT/Kafka failures |
| 3.6 | Markdown | DLQ runbook link | Inline ops guide |

#### Row 4: Source Lag (Source Connectors Only)

| Tile | Type | Metric / Query | Notes |
|---|---|---|---|
| 4.1 | Single-value | Debezium `MilliSecondsBehindSource` or upstream lag | How far behind source |
| 4.2 | Time-series | `SourceEventPosition` or LSN over time | Position advancement |
| 4.3 | Single-value | `offset-commit-completion-rate` | Connect framework health |
| 4.4 | Single-value | `offset-commit-skip-rate` | Stalled commits |

**Omit Row 4 for sink connectors.**

#### Row 5: Worker Resource Utilization (OneAgent)

| Tile | Type | Metric / Query | Notes |
|---|---|---|---|
| 5.1 | Single-value | JVM heap % (OneAgent) | Per worker pod |
| 5.2 | Time-series | CPU per pod (OneAgent) | Detect noisy-neighbor tasks |
| 5.3 | Single-value | GC pause max (OneAgent) | > 500 ms = investigate |
| 5.4 | Single-value | `time-since-last-rebalance-ms` (`connect-worker-rebalance-metrics`) | Frequent rebalances = instability |

#### Row 6: Operational Links & Context

| Tile | Type | Content |
|---|---|---|
| 6.1 | Markdown | Task failure runbook |
| 6.2 | Markdown | Source-system dashboard link (Postgres / Oracle / mainframe) |
| 6.3 | Markdown | Sink-system dashboard link (DB / S3 / HTTP) |
| 6.4 | Markdown | Schema Registry / converter mismatch runbook |
| 6.5 | Markdown | Connector config snippet (truncated `GET /connectors/{name}/config`) |

---

## Part C: Alert Rules (Dynatrace Davis)

Each rule uses **DQL-based alerting** (Davis 3+). Metric-event rules can also be used for cumulative-counter rate thresholds where DQL is overkill.

### Rule 1: Task Failed (P1)

```dql
timeseries code = max(kafka.connect.task.status_code),
           by:{connector, task_id, status_text},
           from:now()-5m
| filter code[-1] >= 4
| fieldsAdd severity = "CRITICAL"
```

```
Name: "Connect Task Failed"
Evaluation: 1 min
Severity: CRITICAL (P1)
Notification: PagerDuty "p1-connect-failures"
Dashboard link: Dashboard 4 ($connector_name pre-filled)
```

### Rule 2: Connector Unhealthy (P1)

```dql
timeseries failed = max(kafka.connect.connector.task.failed),
           by:{connector},
           from:now()-5m
| filter failed[-1] > 0
| fieldsAdd severity = "CRITICAL"
```

```
Name: "Connect Connector Unhealthy (failed tasks > 0)"
Evaluation: 2 min (allow brief flap during rolling restart)
Severity: CRITICAL (P1)
Notification: PagerDuty "p1-connect-failures"
```

### Rule 3: DLQ Growing (P1)

```dql
timeseries dlq_rate = rate(kafka.connect.task.dlq.produce.requests, time:1m),
           by:{connector, task_id},
           from:now()-5m
| filter dlq_rate[-1] > 0
| fieldsAdd severity = "CRITICAL"
```

```
Name: "Connect DLQ Growing (data quality risk)"
Evaluation: 3 min (require sustained rate, not single spike)
Severity: CRITICAL (P1)
Notification: PagerDuty "p1-connect-failures"
Description: "Records being written to DLQ. Investigate and replay/quarantine."
```

### Rule 4: DLQ Write Failed (P1 — data loss)

```dql
timeseries dlq_failed = rate(kafka.connect.task.dlq.produce.failures, time:1m),
           by:{connector, task_id},
           from:now()-5m
| filter dlq_failed[-1] > 0
| fieldsAdd severity = "CRITICAL"
```

```
Name: "Connect DLQ Write Failed (SILENT DATA LOSS)"
Evaluation: 1 min
Severity: CRITICAL (P1)
Notification: PagerDuty "p1-connect-failures"
Description: "Records failed even DLQ write. Data loss risk. Page immediately."
```

### Rule 5: Error Rate Spike (P2)

```dql
timeseries err_rate = rate(kafka.connect.task.errors.total, time:1m),
           by:{connector, task_id},
           from:now()-5m
| filter err_rate[-1] > 5
| fieldsAdd severity = "WARNING"
```

```
Name: "Connect Error Rate High (>5 errors/min)"
Evaluation: 5 min (require sustained)
Severity: WARNING (P2)
Notification: Slack #data-engineering
```

### Rule 6: Processing Halted (P2)

```dql
// Sink: send rate flat-lined despite tasks reporting RUNNING
timeseries
    rate_v = avg(kafka.connect.sink.record.send.rate),
    code   = max(kafka.connect.task.status_code),
    by:{connector, task_id},
    from:now()-10m
| filter code[-1] == 0   // RUNNING
| filter rate_v[-1] == 0
| fieldsAdd severity = "WARNING"
```

```
Name: "Connect Sink Send Rate Zero (task RUNNING but not processing)"
Evaluation: 5 min sustained
Severity: WARNING (P2)
Notification: Slack #data-engineering
```

For source connectors, mirror with `kafka.connect.source.record.poll.rate`.

### Rule 7: Task Startup Failures (P2)

```dql
timeseries failures = rate(kafka.connect.worker.task_startup.failure.total, time:1h),
           by:{worker_host},
           from:now()-1h
| filter failures[-1] > 3
| fieldsAdd severity = "WARNING"
```

```
Name: "Connect Worker Task Startup Failures >3/h"
Evaluation: 30 min
Severity: WARNING (P2)
Notification: Slack #data-engineering
```

### Rule 8: Converter Errors (P2 — FSI must-have)

```dql
fetch logs, from:now()-10m
| filter dt.process.name == "kafka-connect"
| parse content, """LD '[' DATA:stage ']'"""
| filter stage == "VALUE_CONVERTER" OR stage == "KEY_CONVERTER"
| filter matchesPhrase(content, "ERROR")
| summarize errors = count(), by:{connector, task_id, stage}
| filter errors > 0
| fieldsAdd severity = "WARNING"
```

```
Name: "Connect Converter Errors (schema/format mismatch)"
Evaluation: 5 min
Severity: WARNING (P2)
Notification: Slack #data-engineering
Description: "Records failing in (de)serialization stage. Check Schema Registry subject and converter config."
```

### Rule 9: Worker Rebalance Storm (P2)

```dql
timeseries since_rebalance = min(kafka.connect.worker.rebalance.time.ms),
           by:{worker_host},
           from:now()-30m,
           interval:1m
// If repeatedly < 60s, workers are thrashing
| summarize storm = count() filter (since_rebalance < 60000),
            by:{worker_host}
| filter storm > 5
| fieldsAdd severity = "WARNING"
```

```
Name: "Connect Worker Rebalance Storm"
Evaluation: 15 min
Severity: WARNING (P2)
Notification: Slack #data-engineering
```

### Rule 10: Source Offset Commit Lag (P3, source only)

```dql
timeseries skip_rate = avg(kafka.connect.task.offset_commit.skip.rate),
           by:{connector, task_id},
           from:now()-30m
| filter skip_rate[-1] > 0
| fieldsAdd severity = "INFO"
```

```
Name: "Connect Source Offset Commit Skip (stale offsets)"
Evaluation: 10 min
Severity: INFO (P3)
Notification: Slack #data-engineering
```

---

## Part D: Sample Dashboard JSON (Dynatrace Config)

Partial Dynatrace dashboard configuration (Grail-DQL-based tiles):

```json
{
  "dashboardName": "Connect Deep Dive",
  "dashboardDescription": "Per-connector diagnostics for self-managed Confluent Connect",
  "variables": [
    {
      "name": "connector_name",
      "type": "DIMENSION",
      "query": "timeseries val = max(kafka.connect.connector.task.count), by:{connector} | sort connector asc",
      "dimensionField": "connector",
      "defaultValue": "",
      "multiSelect": false
    }
  ],
  "rows": [
    {
      "rowName": "Row 1: Health Summary",
      "tiles": [
        {
          "tileType": "singleValue",
          "title": "Connector State",
          "dql": "timeseries code = max(kafka.connect.task.status_code), by:{connector, status_text}, from:now()-5m | filter connector == \"$connector_name\" | fieldsAdd state = status_text",
          "thresholds": [
            {"color": "green", "value": "running"},
            {"color": "yellow", "value": "paused"},
            {"color": "red", "value": "failed"}
          ],
          "position": {"x": 0, "y": 0, "width": 3, "height": 2}
        },
        {
          "tileType": "singleValue",
          "title": "Total Tasks",
          "dql": "timeseries v = max(kafka.connect.connector.task.count), by:{connector}, from:now()-5m | filter connector == \"$connector_name\"",
          "position": {"x": 3, "y": 0, "width": 2, "height": 2}
        },
        {
          "tileType": "singleValue",
          "title": "Running Tasks",
          "dql": "timeseries v = max(kafka.connect.connector.task.running), by:{connector}, from:now()-5m | filter connector == \"$connector_name\"",
          "thresholds": [
            {"color": "yellow", "rule": "<total"}
          ],
          "position": {"x": 5, "y": 0, "width": 2, "height": 2}
        },
        {
          "tileType": "singleValue",
          "title": "Failed Tasks",
          "dql": "timeseries v = max(kafka.connect.connector.task.failed), by:{connector}, from:now()-5m | filter connector == \"$connector_name\"",
          "thresholds": [
            {"color": "red", "rule": ">0"}
          ],
          "position": {"x": 7, "y": 0, "width": 2, "height": 2}
        },
        {
          "tileType": "singleValue",
          "title": "DLQ Produce Rate (records/min)",
          "dql": "timeseries v = rate(kafka.connect.task.dlq.produce.requests, time:1m), by:{connector}, from:now()-5m | filter connector == \"$connector_name\"",
          "thresholds": [
            {"color": "red", "rule": ">0"}
          ],
          "position": {"x": 9, "y": 0, "width": 3, "height": 2}
        },
        {
          "tileType": "timeSeries",
          "title": "Per-Task Status Timeline (24h)",
          "dql": "timeseries code = avg(kafka.connect.task.status_code), by:{connector, task_id, status_text}, from:now()-24h, interval:1m | filter connector == \"$connector_name\"",
          "position": {"x": 0, "y": 2, "width": 12, "height": 4}
        }
      ]
    },
    {
      "rowName": "Row 2: Throughput",
      "tiles": [
        {
          "tileType": "lineChart",
          "title": "Send / Poll Rate (records/sec)",
          "dql": "timeseries rate_v = avg(kafka.connect.sink.record.send.rate), by:{connector, task_id}, from:now()-1h, interval:1m | filter connector == \"$connector_name\"",
          "position": {"x": 0, "y": 0, "width": 6, "height": 4}
        },
        {
          "tileType": "lineChart",
          "title": "Records Active (in-flight)",
          "dql": "timeseries active = avg(kafka.connect.sink.record.active.count), by:{connector, task_id}, from:now()-1h, interval:1m | filter connector == \"$connector_name\"",
          "position": {"x": 6, "y": 0, "width": 6, "height": 4}
        }
      ]
    },
    {
      "rowName": "Row 3: Errors & DLQ",
      "tiles": [
        {
          "tileType": "singleValue",
          "title": "Error Rate (errors/min)",
          "dql": "timeseries err = rate(kafka.connect.task.errors.total, time:1m), by:{connector}, from:now()-5m | filter connector == \"$connector_name\"",
          "position": {"x": 0, "y": 0, "width": 3, "height": 2}
        },
        {
          "tileType": "lineChart",
          "title": "Error Trend (24h)",
          "dql": "timeseries err = rate(kafka.connect.task.errors.total, time:1m), by:{connector, task_id}, from:now()-24h, interval:5m | filter connector == \"$connector_name\"",
          "position": {"x": 3, "y": 0, "width": 9, "height": 4}
        },
        {
          "tileType": "lineChart",
          "title": "DLQ Produce Rate (24h)",
          "dql": "timeseries dlq = rate(kafka.connect.task.dlq.produce.requests, time:1m), by:{connector, task_id}, from:now()-24h, interval:5m | filter connector == \"$connector_name\"",
          "position": {"x": 0, "y": 4, "width": 9, "height": 4}
        },
        {
          "tileType": "singleValue",
          "title": "DLQ Write Failures (data loss)",
          "dql": "timeseries fails = rate(kafka.connect.task.dlq.produce.failures, time:1m), by:{connector}, from:now()-5m | filter connector == \"$connector_name\"",
          "thresholds": [
            {"color": "red", "rule": ">0"}
          ],
          "position": {"x": 9, "y": 4, "width": 3, "height": 2}
        },
        {
          "tileType": "table",
          "title": "Per-Stage Error Breakdown",
          "dql": "fetch logs, from:now()-1h | filter dt.process.name == \"kafka-connect\" | filter matchesPhrase(content, \"ERROR\") | parse content, \"\"\"LD '[' DATA:stage ']'\"\"\" | summarize errors = count(), by:{connector, task_id, stage} | filter connector == \"$connector_name\" | sort errors desc",
          "position": {"x": 0, "y": 8, "width": 9, "height": 4}
        },
        {
          "tileType": "markdown",
          "title": "DLQ Handling",
          "content": "[Reprocess DLQ Messages](https://wiki/connect-dlq-runbook)\n[Converter Mismatch Runbook](https://wiki/connect-converter-mismatch)\n[Source Troubleshoot](https://wiki/source-troubleshoot)\n[Sink Troubleshoot](https://wiki/sink-troubleshoot)",
          "position": {"x": 9, "y": 8, "width": 3, "height": 4}
        }
      ]
    }
  ]
}
```

---

## Part E: Integration with Platform Overview (Dashboard 1)

### Add to Dashboard 1: Connector Health Table

**Title:** "Connector Status"

**Query (real Grail DQL):**

```dql
timeseries
    total    = max(kafka.connect.connector.task.count),
    running  = max(kafka.connect.connector.task.running),
    failed   = max(kafka.connect.connector.task.failed),
    err_rate = rate(kafka.connect.task.errors.total, time:1m),
    dlq_rate = rate(kafka.connect.task.dlq.produce.requests, time:1m),
    by:{connector, connector_class, connector_type},
    from:now()-5m
| fieldsAdd
    total_v    = total[-1],
    running_v  = running[-1],
    failed_v   = failed[-1],
    err_pm     = err_rate[-1],
    dlq_pm     = dlq_rate[-1]
| fieldsAdd health = if(failed_v > 0 OR dlq_pm > 0, "red",
                         if(running_v < total_v, "yellow", "green"))
| fields connector, connector_type, health, running_v, total_v, err_pm, dlq_pm
| sort health asc, connector asc
```

**Table Columns:**

| Column | Source | Sortable | Threshold |
|---|---|---|---|
| Connector Name | `connector` | Yes | — |
| Type | `connector_type` (`source`/`sink`) | No | — |
| Health | Derived (`health` field) | Yes | red → yellow → green |
| Tasks (Running/Total) | `running_v` / `total_v` | Yes | `running<total` = yellow |
| Error Rate | `err_pm` | Yes | spike = yellow |
| DLQ Rate | `dlq_pm` | Yes | `>0` = red |

**Click behavior:** Clicking a row navigates to Dashboard 4 with `$connector_name` pre-populated.

---

## Part F: Deployment Automation (Infrastructure-as-Code)

For professional-services hand-offs, Dynatrace configuration is managed via Terraform and stored in Git.

```hcl
# terraform/dynatrace-connect-monitoring.tf

terraform {
  required_providers {
    dynatrace = {
      source  = "dynatrace-oss/dynatrace"
      version = "~> 1.50"  # current as of 2026
    }
  }
}

provider "dynatrace" {
  dt_env_url   = var.dynatrace_tenant_url
  dt_api_token = var.dynatrace_api_token
}

# Upload JMX Extension 2.0 YAML
resource "dynatrace_extension_v2" "kafka_connect" {
  source = file("${path.module}/extensions/custom_kafka-connect.yaml")
  active = true
}

# Dashboard 4: Connect Deep Dive
resource "dynatrace_json_dashboard" "connect_deep_dive" {
  contents = file("${path.module}/dashboards/connect_deep_dive.json")
}

# Alert rule: Task Failed (P1) — DQL-based metric event
resource "dynatrace_metric_events" "connect_task_failed" {
  enabled  = true
  name     = "Connect Task Failed"
  severity = "ERROR"

  query_definition {
    type = "DQL"
    dql_query = <<-EOT
      timeseries code = max(kafka.connect.task.status_code),
                 by:{connector, task_id, status_text},
                 from:now()-5m
      | filter code[-1] >= 4
    EOT
  }

  event_template {
    title         = "Connect task {dims:task_id} on {dims:connector} is {dims:status_text}"
    description   = "Task has been in failed state for over 1 minute."
    event_type    = "ERROR_EVENT"
    davis_merge   = true
  }

  model_properties {
    type                          = "STATIC_THRESHOLD"
    threshold                     = 4
    alert_condition               = "ABOVE_OR_EQUAL"
    samples                       = 1
    violating_samples             = 1
    dealerting_samples            = 5
  }
}

# Alert rule: DLQ Growing (P1)
resource "dynatrace_metric_events" "connect_dlq_growing" {
  enabled  = true
  name     = "Connect DLQ Growing"
  severity = "ERROR"

  query_definition {
    type = "DQL"
    dql_query = <<-EOT
      timeseries dlq_rate = rate(kafka.connect.task.dlq.produce.requests, time:1m),
                 by:{connector, task_id},
                 from:now()-5m
    EOT
  }

  event_template {
    title       = "DLQ growing on {dims:connector} task {dims:task_id}"
    description = "Records being written to DLQ. Investigate root cause and replay."
    event_type  = "ERROR_EVENT"
  }

  model_properties {
    type               = "STATIC_THRESHOLD"
    threshold          = 0
    alert_condition    = "ABOVE"
    samples            = 5
    violating_samples  = 3
    dealerting_samples = 5
  }
}

variable "dynatrace_tenant_url" {
  description = "Dynatrace tenant URL (e.g., https://xxxx.live.dynatrace.com)"
  type        = string
}

variable "dynatrace_api_token" {
  description = "Dynatrace API token (Vault-backed; never in Git)"
  type        = string
  sensitive   = true
}
```

**Deployment workflow (standard):**

```bash
# 1. Store credentials in Vault
vault kv put secret/dynatrace/prod \
  tenant_url="https://xxxx.live.dynatrace.com" \
  api_token="dt0c01....."

# 2. Plan & apply
terraform plan  -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars

# 3. Validate
#    - Dashboards visible in Dynatrace UI
#    - Extension shows "active" with ingested metrics
#    - Alert rules listed under Davis settings; force a synthetic failure to verify firing

# 4. Commit to Git
git add terraform/ dashboards/ extensions/
git commit -m "Add Connect monitoring (dashboards + alerts + JMX extension) for prod"
git push origin main
```

**Post-hand-off maintenance:**
- The platform team owns the `/monitoring` folder in their infra repo
- Dashboard JSON, alert rules, extension YAML, and Terraform are version-controlled
- Updates follow standard change control (PR → review → merge → deploy)

---

## Summary Table: Which Query for Which Purpose

| Use Case | Query Shape | Source Metric / MBean | Tile Type |
|---|---|---|---|
| "Is the connector healthy?" | Point-in-time | `kafka.connect.task.status_code` (extension-mapped from `status`) | Single-value |
| "Are tasks running?" | Count | `kafka.connect.connector.task.running` | Single-value |
| "What's the error rate?" | Rate | `rate(kafka.connect.task.errors.total, time:1m)` (from `task-error-metrics.total-record-errors`) | Single-value / Line |
| "Is data moving?" | Throughput | `sink-record-send-rate` / `source-record-poll-rate` | Line chart |
| "Why did it break?" | Per-stage breakdown | Log-derived (DQL §A.6) — `KEY/VALUE_CONVERTER`, `TRANSFORMATION`, `KAFKA_*` | Table |
| "Did it restart?" | Worker counter | `task-startup-failure-total` (worker MBean) | Time-series |
| "Show me all connectors" | Multi-dim | `kafka.connect.connector.*` `by:{connector}` | Table |
| "Is DLQ growing?" | Counter rate | `rate(deadletterqueue-produce-requests, time:1m)` | Single-value / Line |
| "Is DLQ losing data?" | Counter rate | `rate(deadletterqueue-produce-failures, time:1m)` | Single-value |
| "Where is the source lag?" | Source-specific | Debezium `MilliSecondsBehindSource` / Postgres `pg_stat_replication` | Single-value |
| "How long in failed state?" | State age | `status-time-ms` filtered to `status==failed` | Single-value |
