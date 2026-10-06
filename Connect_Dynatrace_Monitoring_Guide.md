# Dynatrace Monitoring for Self-Managed Confluent Connect

## Scope & Deployment-Model Disclaimer

This guide targets **self-managed Confluent Connect (distributed mode)** as the observability subject. For most FSI deployments, the canonical default is **fully-managed Confluent Cloud connectors** with the Confluent Cloud Metrics API → Dynatrace Confluent extension path; that path inherits Confluent SLAs and removes the JMX/agent layer entirely (see `wiki/patterns/connect-deployment-models.md` and `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md`).

Pick self-managed Connect only when one of these triggers applies:
- Fully-managed CC connectors don't cover the required source/sink (CFK custom connector, on-prem-only target, regulated runtime)
- Exactly-once source semantics that the managed offering doesn't yet expose
- Network locality (low-latency sink in a VPC the managed plane can't reach)

Everything below assumes that trigger has been met and you are deploying Connect on Kubernetes (or VMs) inside a tenant network.

---

## Context: Splunk → Dynatrace Migration (If Applicable)

If migrating from Splunk, this guide supports the **monitoring stack migration** for Confluent platforms:

| Data Type | Current (Splunk) | Future (Dynatrace) | Rationale |
|---|---|---|---|
| **Performance metrics** | Splunk HEC ingestion | Dynatrace native (API + OneAgent) | Real-time alerting, correlation, cost optimization |
| **Monitoring dashboards** | Splunk searches → dashboards | Dynatrace dashboards (this guide) | Richer visualization, Davis AI anomaly detection |
| **Alert rules** | Splunk alert rules | Dynatrace alert rules (DQL- or selector-based) | DQL is more expressive; enables Davis AI |
| **Audit logs** | Existing SIEM (retained) | **Existing SIEM (no change, if compliance requires)** | Audit logs remain in the existing SIEM if compliance requires; kept separate |

**Key transition points (if migrating from Splunk):**
1. Confluent Cloud metrics: Replace Splunk HEC receiver with Dynatrace Confluent Cloud extension + API key
2. Self-managed Connect: Replace Splunk JMX forwarders with Dynatrace OneAgent + JMX Extension 2.0
3. Existing Splunk dashboards: Retire (or archive 30 days) after Dynatrace dashboards go live
4. Alert routing: Splunk alerts → PagerDuty/Slack; migrate to Dynatrace alerts + notification channels

---

## Executive Summary

A typical Confluent Cloud dashboard architecture (three-dashboard pattern with 7-row cluster deep dive) translates to self-managed Connect with two critical differences:

1. **Data model:** Connect's health model is a **state machine** (RUNNING / PAUSED / FAILED / UNASSIGNED / DESTROYED / RESTARTING), not a capacity series. You alert on state transitions and per-task error counters, not on load percentages.
2. **Dashboard scope:** Connect deserves its own deep-dive dashboard (Dashboard 4) linked from Platform Overview, because connector diagnostics flow state → DLQ → source/sink — not load → lag → latency.

This guide assumes you reuse Cloud standards for Dynatrace configuration (Management Zones, variables, query patterns) and adapt metrics accordingly.

---

## Part 1: Getting Metrics from Self-Managed Connect into Dynatrace

### 1.1 Collection Architecture: JMX Extension 2.0

**Recommended: OneAgent + Dynatrace JMX Extension 2.0**

Self-managed Connect workers expose metrics over JMX. The deciding factor between native JMX and Prometheus is operational fit (do you already run a Prometheus stack?), not scrape jitter — Dynatrace's JMX extension is also poll-based (default 1-minute interval, configurable). Pick native JMX if you're starting fresh; Prometheus-via-JMX-exporter if Prometheus is already in place.

**Setup flow:**

1. **Enable JMX on Connect workers — production-hardened (FSI baseline)**

   Bind JMX to **localhost** and let OneAgent (running on the same node) scrape locally. JMX never traverses the network. This is the FSI-canon-compliant pattern:

   ```bash
   # connect-distributed.properties launcher / Docker env — PROD
   KAFKA_JMX_PORT=9999
   KAFKA_JMX_HOSTNAME=127.0.0.1
   KAFKA_OPTS="\
     -Dcom.sun.management.jmxremote=true \
     -Dcom.sun.management.jmxremote.port=9999 \
     -Dcom.sun.management.jmxremote.rmi.port=9999 \
     -Dcom.sun.management.jmxremote.local.only=true \
     -Dcom.sun.management.jmxremote.authenticate=true \
     -Dcom.sun.management.jmxremote.password.file=/etc/connect/jmxremote.password \
     -Dcom.sun.management.jmxremote.access.file=/etc/connect/jmxremote.access \
     -Dcom.sun.management.jmxremote.ssl=true \
     -Djavax.net.ssl.keyStore=/etc/connect/jmx.keystore.jks \
     -Djavax.net.ssl.keyStorePassword=$JMX_KEYSTORE_PASSWORD \
     -Djava.rmi.server.hostname=127.0.0.1"
   ```

   `/etc/connect/jmxremote.password` and `jmxremote.access` are mounted from Vault-backed secrets with `0400` permissions and owned by the Connect runtime user. Keystore password comes from the same secret store, never from Git.

   > **There is no canonical Confluent JMX port for Connect.** Apache Kafka uses `9999` by convention in CP examples; CFK and various Helm charts pick different ports (7203, 9101, 9876). Standardize on one port per environment and document it explicitly.

   **Dev-only convenience config (NEVER for prod):**

   ```bash
   # connect-distributed.properties launcher — DEV LAPTOPS ONLY
   KAFKA_JMX_PORT=9999
   KAFKA_OPTS="-Dcom.sun.management.jmxremote \
     -Dcom.sun.management.jmxremote.port=9999 \
     -Dcom.sun.management.jmxremote.authenticate=false \
     -Dcom.sun.management.jmxremote.ssl=false \
     -Dcom.sun.management.jmxremote.local.only=true"
   ```

   `authenticate=false ssl=false` on a network-exposed JMX port is a **P0 security finding** in FSI (it exposes heap-dump and runtime-config controls). It would fail any pre-prod security review. If you see this in a production-bound config, treat it as a release blocker.

2. **Configure Dynatrace JMX Extension 2.0**

   Use a YAML extension (uploaded via `dt-cli` or the Dynatrace Hub) rather than legacy custom-extension JS. Example excerpt:

   ```yaml
   name: custom:kafka-connect
   version: 1.0.0
   minDynatraceVersion: 1.270
   jmx:
     - group: kafka.connect.connector
       interval:
         minutes: 1
       subgroups:
         - subgroup: connector-metrics
           query: "kafka.connect:type=connector-metrics,connector=*"
           queryFilters: []
           dimensions:
             - key: connector
               value: property:connector
           metrics:
             - value: attribute:connector-total-task-count
               type: gauge
               key: kafka.connect.connector.task.count
             - value: attribute:connector-running-task-count
               type: gauge
               key: kafka.connect.connector.task.running
             - value: attribute:connector-failed-task-count
               type: gauge
               key: kafka.connect.connector.task.failed
             - value: attribute:connector-paused-task-count
               type: gauge
               key: kafka.connect.connector.task.paused
             # 'status' is a string attribute — see §1.3
             - value: attribute:status
               type: string
               key: kafka.connect.connector.status
   ```

3. **Wire OneAgent to the Dynatrace tenant** (standard ActiveGate path; no Connect-specific config beyond the extension above).

### 1.2 Must-Have Connect Metrics (Apache Kafka 4.x MBean names)

These metrics answer "what's wrong with Connect?" using the actual Apache Kafka Connect MBean tree (https://kafka.apache.org/documentation/#connect_monitoring). Use these names verbatim — earlier drafts of this guide used invented names that don't exist.

| # | What | MBean | Attribute(s) | Alert Threshold | Dashboard |
|---|------|-------|--------------|-----------------|-----------|
| 1 | **Task state** | `kafka.connect:type=connector-task-metrics,connector=*,task=*` | `status` (string: `running`/`failed`/`paused`/`unassigned`/`destroyed`/`restarting`), `status-time-ms` (ms in current state) | Any task in `failed` for >1 min = **P1** | Dashboard 4 Row 1 |
| 2 | **Connector roll-up** | `kafka.connect:type=connector-metrics,connector=*` | `status` (string), `connector-class`, `connector-version`, `connector-type` (`source`/`sink`), `connector-total-task-count`, `connector-running-task-count`, `connector-failed-task-count`, `connector-paused-task-count`, `connector-unassigned-task-count`, `connector-destroyed-task-count` | `connector-failed-task-count > 0` = **P1** | Dashboard 4 Row 1 |
| 3 | **Sink throughput** | `kafka.connect:type=sink-task-metrics,connector=*,task=*` | `sink-record-read-rate`, `sink-record-send-rate`, `sink-record-active-count`, `put-batch-avg-time-ms`, `put-batch-max-time-ms`, `partition-count`, `offset-commit-completion-rate`, `offset-commit-skip-rate` | `sink-record-send-rate == 0` sustained >5 min on healthy task = **P2** | Dashboard 4 Row 2 |
| 4 | **Source throughput / lag** | `kafka.connect:type=source-task-metrics,connector=*,task=*` | `source-record-poll-rate`, `source-record-write-rate`, `source-record-poll-total`, `source-record-write-total`, `poll-batch-avg-time-ms`, `poll-batch-max-time-ms`, `source-record-active-count` | `source-record-poll-rate == 0` sustained >5 min = **P2** | Dashboard 4 Row 2 |
| 5 | **Error counters & DLQ produces** | `kafka.connect:type=task-error-metrics,connector=*,task=*` | `total-record-errors`, `total-record-failures`, `total-records-skipped`, `total-retries`, `total-errors-logged`, `deadletterqueue-produce-requests`, `deadletterqueue-produce-failures`, `last-error-timestamp` | `rate(total-record-errors) > 5/min` sustained 5 min = **P2**; `deadletterqueue-produce-requests` rate-of-change > 0 sustained 3 min = **P1** | Dashboard 4 Row 3 |
| 6 | **Worker stability & restarts** | `kafka.connect:type=connect-worker-metrics` and `kafka.connect:type=connect-worker-rebalance-metrics` | `connector-startup-attempts-total`, `connector-startup-success-total`, `connector-startup-failure-total`, `task-startup-attempts-total`, `task-startup-failure-total`, `rebalance-avg-time-ms`, `time-since-last-rebalance-ms` | `rate(task-startup-failure-total) > 3/h` = **P2** | Dashboard 4 Row 1 (overlay) |
| 7 | **Source-system lag (CDC)** | Source-specific: Debezium `debezium.<flavor>:type=connector-metrics,context=streaming,name=*` → `MilliSecondsBehindSource`, `SourceEventPosition`, `NumberOfDisconnects`; or upstream system (`pg_stat_replication.replay_lsn`) | n/a | Source-tier specific (e.g., >30 s for risk-tier CDC, >5 min for compliance-tier) = **P2** | Dashboard 4 Row 4 |

**Connector-level `status` via REST as a backup.** `kafka.connect:type=connector-metrics … status` is exposed since Apache Kafka 2.0, but if your distribution doesn't surface it cleanly, fall back to `GET /connectors/{name}/status` on the Connect REST API and scrape it with a Dynatrace HTTP-monitor extension. Don't try to invent a `connector-state` attribute — it doesn't exist.

### 1.3 String JMX attributes need an enum mapping

OneAgent's JMX extension treats MBean attributes as **numeric metrics** by default. Connect's `status` attribute is a **string** (`running`, `failed`, etc.) — without explicit handling it either drops or arrives as a dimension on a synthetic constant metric, and you can't alert on `status == "FAILED"` directly.

Two viable patterns:

1. **Enum-to-int mapping in the extension** (recommended for alerts):

   ```yaml
   # excerpt from custom:kafka-connect extension
   - value: 'expression(case(attribute:status, "running", 0, "paused", 1, "unassigned", 2, "restarting", 3, "failed", 4, "destroyed", 5, -1))'
     type: gauge
     key: kafka.connect.task.status_code
     dimensions:
       - key: status_text
         value: attribute:status
   ```

   Then alert on `kafka.connect.task.status_code >= 4` (failed or destroyed) and keep the `status_text` dimension for human display.

2. **Ingest as log events** via the Connect log appender, then alert with DQL `fetch logs | filter ...`. Use this if you want full status-transition history with timestamps (useful for "restarts in last hour").

**Pick pattern 1 for the must-have dashboard tiles**, pattern 2 to support the "restart frequency" derivation in Row 1.

---

## Part 2: Dashboard Architecture

### 2.1 Four-Dashboard Pattern (adapting your Cloud pattern)

| Dashboard | Cloud Equivalent | Purpose | Audience | Linked From |
|---|---|---|---|---|
| **Dashboard 1: Platform Overview** | Cloud Platform Overview | "Is anything failing across brokers AND connectors?" | On-call | Home |
| **Dashboard 2: Cluster Deep Dive** | Cloud Cluster Deep Dive | Broker diagnostics (unchanged) | Broker troubleshooting | Platform Overview |
| **Dashboard 3: DR Readiness** | Cloud DR Readiness | Cluster Link + failover state (unchanged) | DR ops | Platform Overview |
| **Dashboard 4: Connect Deep Dive** | Cloud Row 7 (isolated) | Connector/task diagnostics | Connect owner / on-call | Platform Overview |

### 2.2 Integration Points: Shared Variables

Define these at Dashboard 1 and propagate to 2/3/4:

```
$cluster_id           → dt.entity.confluent_kafka_cluster (current prod cluster)
$environment          → Tag: environment (prod/dr/staging)
$connector_pattern    → Text: regex filter for connector names (e.g., ".*-prod.*")
```

Dashboard 4 adds:

```
$connector_name       → Dimension: connector name (e.g., "s3-sink-users", "postgres-cdc-source")
$task_id              → Dimension: task ID within the connector (0, 1, 2…)
```

### 2.3 Dashboard 4: Connect Deep Dive Layout

**Primary variable: $connector_name** (dropdown, populated from all deployed connectors)

All tiles filter to that connector and its tasks.

#### Row 1: Health Summary

- **Connector State** (single-value): `running` / `paused` / `failed` (text + color)
- **Total Tasks** (single-value): `connector-total-task-count`
- **Running Tasks** (single-value): `connector-running-task-count`
- **Failed Tasks** (single-value): `connector-failed-task-count` (red if >0)
- **Status Timeline** (time-series): per-task `status_code` over 24 h (visual of state thrash)
- **DLQ Produce Rate** (single-value): `rate(deadletterqueue-produce-requests)` (red if >0)

**Real Grail DQL (status-code-mapped):**

```dql
// Failed tasks count
timeseries failed_tasks = max(kafka.connect.connector.task.failed),
           by:{connector},
           from:now()-15m
| filter connector == "$connector_name"
| fieldsAdd alert = if(failed_tasks > 0, "red", "green")
```

```dql
// Per-task status timeline (24h)
timeseries task_status = avg(kafka.connect.task.status_code),
           by:{connector, task_id, status_text},
           from:now()-24h,
           interval:1m
| filter connector == "$connector_name"
```

#### Row 2: Throughput

- **Sink send rate** (line chart): `sink-record-send-rate` split by `task_id`
- **Source poll rate** (line chart, source connectors): `source-record-poll-rate` split by `task_id`
- **Records active** (single-value): `sink-record-active-count` / `source-record-active-count` (in-flight count)
- **Batch latency** (line chart): `put-batch-max-time-ms` / `poll-batch-max-time-ms`

**What to watch:** Send/poll rate drops to zero while source continues → investigate task state and DLQ.

#### Row 3: Errors & DLQ

- **Error rate** (line chart): `rate(total-record-errors)` per task
- **DLQ produce rate** (line chart): `rate(deadletterqueue-produce-requests)` per task — **the canonical DLQ-growth signal**
- **DLQ produce failures** (single-value): `rate(deadletterqueue-produce-failures)` — these are records that failed even the DLQ write (data loss)
- **Records skipped** (single-value): `total-records-skipped` — records dropped by `errors.tolerance=all`
- **Last error timestamp** (single-value): `last-error-timestamp`
- **Error stage** (table, if log ingest enabled): per-stage breakdown — `KEY_CONVERTER` / `VALUE_CONVERTER` / `HEADER_CONVERTER` / `TRANSFORMATION` / `KAFKA_CONSUME` / `KAFKA_PRODUCE`. Converter errors are the #1 FSI failure mode (schema/format mismatch).

#### Row 4: Source-System Lag (Source Connectors)

- **Source-system lag** (single-value): Debezium `MilliSecondsBehindSource` or upstream-system metric
- **Source position** (line chart): connector's `SourceEventPosition` (Debezium) or equivalent
- **Offset commit latency** (time-series): `offset-commit-completion-rate` / `offset-commit-skip-rate` on the task

#### Row 5: Worker Resource Utilization (OneAgent JVM)

- **Worker heap** (line chart): per-pod JVM heap used % (OneAgent)
- **GC pause max** (single-value): GC pause time max (alert if >500 ms)
- **Rebalance time** (single-value): `time-since-last-rebalance-ms` and `rebalance-avg-time-ms`
- **CPU per pod** (line chart): OneAgent process CPU split by pod

#### Row 6: Linked Context (downstream correlation)

- **Sink target health**: link to S3 bucket / DB dashboard
- **Source system status**: link to Postgres / Oracle / mainframe dashboard
- **Schema Registry health**: subject compatibility errors (see Part 3.2)
- **Runbook links**: task failure / DLQ replay / converter mismatch

**Why Row 6 matters:** Most Connect failures are downstream, not in Connect itself.

---

## Part 3: Must-Have vs. Nice-to-Have Metrics

### 3.1 Must-haves (alert on these)

1. **Connector + task state** — string-mapped via extension enum
2. **`sink-record-send-rate` / `source-record-poll-rate`** — throughput confirmation
3. **`rate(total-record-errors)`** — SLO tracking
4. **`rate(deadletterqueue-produce-requests)`** — data-loss-adjacent signal
5. **`rate(task-startup-failure-total)`** — stability signal

### 3.2 Converter / Schema Registry monitoring (FSI must-have)

The **#1 silent failure mode** in FSI Connect deployments is converter mismatch — Avro/Protobuf produced upstream, JSON converter configured on the sink, every record flows straight to DLQ. The error counters above will spike but the root cause lives in Schema Registry interactions.

Add these tiles to Row 3 or as a dedicated Row 3.5:

- **Per-stage error breakdown** — ingest Connect logs and split `total-record-errors` by stage. Spike on `VALUE_CONVERTER` = converter mismatch.
- **Schema Registry subject compatibility errors** — scrape `_schemas` topic for failed registration attempts (or scrape SR `/subjects/{subject}/versions` 409 responses).
- **Connect converter config drift** — compare deployed connector config (`GET /connectors/{name}/config`) against Git-stored canonical config; flag drift.

### 3.3 Nice-to-haves (dashboard only, no alerts)

- Per-task CPU / heap memory (OneAgent JVM metrics)
- Connector configuration change audit (Dynatrace events)
- Custom SMT transform performance
- Connect REST API latency (worker liveness signal)

---

## Part 4: Alerting Rules (P1/P2/P3)

| Alert | Metric | Condition (DQL) | Tier | Window | Route |
|---|---|---|---|---|---|
| **Task Failed** | `kafka.connect.task.status_code` | `max() >= 4` | **P1** | 1 min | Page on-call |
| **Connector Unhealthy** | `kafka.connect.connector.task.failed` | `max() > 0` | **P1** | 2 min | Page on-call |
| **DLQ Growing** | `kafka.connect.task.dlq.produce.requests` (counter) | `rate(1m) > 0` | **P1** | 3 min | Page on-call |
| **DLQ Write Failed (data loss)** | `kafka.connect.task.dlq.produce.failures` | `rate(1m) > 0` | **P1** | 1 min | Page on-call |
| **Error Rate Spike** | `kafka.connect.task.errors.total` (counter) | `rate(1m) > 5` | **P2** | 5 min | Slack #data-engineering |
| **Task Startup Failures** | `kafka.connect.worker.task.startup.failure.total` | `rate(1h) > 3` | **P2** | 30 min | Slack #data-engineering |
| **Processing Halted** | `kafka.connect.sink.record.send.rate` (or `source.record.poll.rate`) | `max() == 0` | **P2** | 5 min | Slack #data-engineering |
| **Offset Commit Lag** (source only) | `kafka.connect.task.offset_commit.skip.rate` | `> 0` sustained | **P3** | 10 min | Slack #data-engineering |
| **Converter Errors** | per-stage error count (log-derived) | `stage == "VALUE_CONVERTER" AND rate > 0` | **P2** | 5 min | Slack #data-engineering |
| **Worker Rebalance Storm** | `kafka.connect.worker.rebalance.time.ms` (`time-since-last-rebalance-ms`) | `< 60_000` repeated | **P2** | 15 min | Slack #data-engineering |

DQL-based alert example (Dynatrace Davis alert rule):

```dql
// Task Failed (P1)
timeseries failed = max(kafka.connect.task.status_code),
           by:{connector, task_id, status_text},
           from:now()-5m
| filter failed >= 4
| fieldsAdd severity = "CRITICAL"
```

---

## Part 5: One Dashboard or Many? (Your Architecture Question)

**Recommendation: One dedicated Dashboard 4 + visible KPIs on Dashboard 1.**

### Why NOT a shared dashboard

- **Diagnostic flow is different:** Broker issues are "check lag, check load, check latency." Connect issues are "check task state, check DLQ, check source/sink connectivity."
- **Audiences diverge:** Broker on-call may not know Connect. Connect owner may not have broker context.
- **Clutter:** Adding Connect to the 7-row Cloud dashboard either compresses existing rows or makes it scroll-heavy.

### Why NOT separate dashboards for each connector

- **Too granular:** 10 connectors = 10 dashboards to maintain
- **The pattern you want:** Platform Overview answers "is anything wrong?" → click into the affected connector's deep dive

### Your architecture

**Dashboard 1 (Platform Overview)** — keep your existing three tables and add:

- **Connector Health Table** (new row)
  - Columns: connector name, type (source/sink), status, running/total tasks, error rate, DLQ produce rate, last status change
  - One row per deployed connector
  - Sort by status (failed first)
  - Color: green for all-tasks-running, yellow for 1+ failed task, red for connector unhealthy or DLQ growing

Click a row → Dashboard 4 with `$connector_name` pre-populated.

**Dashboard 4 (Connect Deep Dive)** — the 6-row layout above:
- Variable: `$connector_name`
- One dashboard definition, filters dynamically per connector
- Correlation links to source/sink system dashboards

---

## Part 6: Deployment & Environment Management

**Canonical Kubernetes topology (FSI):**

1. **Connect workers** — `Deployment` (or CFK `Connect` CR), **not** StatefulSet.
   Connect workers are stateless w.r.t. pod identity; framework state (offsets, configs, status) lives in internal Kafka topics (`connect-offsets`, `connect-configs`, `connect-status`). Use `Deployment` + `HorizontalPodAutoscaler` and rely on the headless `Service` for JMX scrape targeting. StatefulSet is over-prescriptive and adds rolling-update friction without benefit.

2. **OneAgent** — `DaemonSet` (or Dynatrace Operator, which manages OneAgent + extensions declaratively).

3. **JMX credentials** — Vault → Kubernetes `Secret` mounted as files (`/etc/connect/jmxremote.password`, keystore). Never in env vars; never in Git.

4. **Dynatrace config** — Terraform `dynatrace-oss/dynatrace ~> 1.50` (current as of 2026). Dashboards, alert rules, notification channels, and the JMX Extension 2.0 YAML are all version-controlled.

```yaml
# k8s Deployment skeleton (excerpt)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka-connect
  namespace: confluent-connect
spec:
  replicas: 3
  selector:
    matchLabels:
      app: kafka-connect
  template:
    metadata:
      labels:
        app: kafka-connect
      annotations:
        dynatrace.com/inject: "true"
    spec:
      containers:
        - name: connect
          image: confluentinc/cp-kafka-connect:7.7.0
          env:
            - name: KAFKA_JMX_PORT
              value: "9999"
            - name: KAFKA_JMX_HOSTNAME
              value: "127.0.0.1"
            - name: KAFKA_OPTS
              value: >-
                -Dcom.sun.management.jmxremote=true
                -Dcom.sun.management.jmxremote.port=9999
                -Dcom.sun.management.jmxremote.rmi.port=9999
                -Dcom.sun.management.jmxremote.local.only=true
                -Dcom.sun.management.jmxremote.authenticate=true
                -Dcom.sun.management.jmxremote.password.file=/etc/connect/jmx/password
                -Dcom.sun.management.jmxremote.access.file=/etc/connect/jmx/access
                -Dcom.sun.management.jmxremote.ssl=true
                -Djavax.net.ssl.keyStore=/etc/connect/jmx/keystore.jks
                -Djavax.net.ssl.keyStorePassword=$(JMX_KEYSTORE_PASSWORD)
                -Djava.rmi.server.hostname=127.0.0.1
            - name: JMX_KEYSTORE_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: connect-jmx-secrets
                  key: keystore-password
          volumeMounts:
            - name: jmx-creds
              mountPath: /etc/connect/jmx
              readOnly: true
      volumes:
        - name: jmx-creds
          secret:
            secretName: connect-jmx-secrets
            defaultMode: 0400
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: kafka-connect-hpa
  namespace: confluent-connect
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: kafka-connect
  minReplicas: 3
  maxReplicas: 12
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

**Environment configuration** (per-env `.env`, **never** committed):

```bash
DT_ENVIRONMENT=prod
DT_TENANT_URL=https://{environment-id}.live.dynatrace.com
DT_API_TOKEN=dt0c01....         # from Dynatrace UI
DT_PAAS_TOKEN=...               # for OneAgent deployment

KUBE_NAMESPACE=confluent-connect
KUBE_CLUSTER_PROD=prod-cluster
KUBE_CLUSTER_DR=dr-cluster
```

**Versioning & handoff:**
- Dashboard JSON, alert rules, Terraform, and extension YAML live in `/monitoring` alongside IaC
- All Dynatrace config is auditable via Git history
- Platform team maintains independently after hand-off using Terraform + Dynatrace provider

---

## Part 7: Configuration Checklist

- [ ] **Deployment-model trigger documented** (why self-managed Connect, not fully-managed CC)
- [ ] **JMX hardened on all prod Connect workers**: `authenticate=true`, `ssl=true`, bound to `127.0.0.1`, credentials from Vault, `0400` permissions
- [ ] **JMX dev/prod separation enforced** (no `authenticate=false` config can reach prod CI)
- [ ] **OneAgent deployed** (DaemonSet) on all Connect nodes
- [ ] **Dynatrace JMX Extension 2.0 deployed** with status-code enum mapping
- [ ] **Dashboard 4 variable defined:** `$connector_name`
- [ ] **Dashboard 1 updated:** Connector Health Table + click-through to Dashboard 4
- [ ] **Alert rules created** (see Part 4 — 10 rules)
- [ ] **DLQ topic naming** follows wiki canon: `dlq.<connector-name>` (no `__` prefix)
- [ ] **Converter / SR monitoring** in place (per-stage error breakdown, subject compatibility errors)
- [ ] **Runbook links added** to Dashboard 4:
  - Task failure runbook
  - Connector unhealthy runbook
  - DLQ investigation + replay runbook
  - Converter mismatch runbook (per Part 3.2)
- [ ] **Management Zone scoped** (dev/staging/prod)
- [ ] **Connect workers deployed as `Deployment`** (not StatefulSet) with HPA
- [ ] **Deployment tested** (local Docker dev + Kubernetes prod)

---

## Part 8: Cloud Metrics → Self-Managed Connect Mapping

**The Cloud broker health model is capacity-shaped (load, lag, latency). The Connect health model is state-shaped (state machine + error counters + DLQ produces).** Don't try to map metric-for-metric — map the diagnostic question instead.

| Cloud diagnostic question | Cloud metric (capacity model) | Self-managed Connect equivalent (state model) |
|---|---|---|
| "Is the cluster healthy?" | `cluster_load_percent` < 70 | `connector-failed-task-count == 0` across all connectors |
| "Are consumers keeping up?" | `consumer_lag_offsets` < threshold | `sink-record-send-rate > 0` AND `source-record-poll-rate > 0` |
| "Is throughput OK?" | `received_bytes` rate | `sink-record-send-rate` + `source-record-write-rate` |
| "Are requests succeeding?" | `request_latencies` p99 | `total-record-failures` rate near zero, `deadletterqueue-produce-requests` rate near zero |
| "Is anything restarting?" | (N/A — managed brokers don't expose this) | `rate(task-startup-failure-total)`, `time-since-last-rebalance-ms` |

The dashboard layout (Row 1 health, Row 2 throughput, Row 3 errors, Row 6 downstream context) is shared. The query bodies and alert thresholds are not.

---

## Appendix A: Splunk → Dynatrace Migration Strategy (If Migrating from Splunk)

### A.1 Metrics Ingestion Cutover

**Before cutover (Splunk):**
```
Confluent Cloud Metrics API → Splunk HEC → Splunk Dashboards → Alerts → PagerDuty
Self-Managed Connect JMX    → Splunk Forwarder → Splunk Dashboards → Alerts → PagerDuty
```

**After cutover (Dynatrace):**
```
Confluent Cloud Metrics API → Dynatrace Confluent extension → Dynatrace Dashboards → Alerts → PagerDuty
Self-Managed Connect JMX    → OneAgent + JMX Extension 2.0 → Dynatrace Dashboards → Alerts → PagerDuty
```

**Audit logs remain in the existing SIEM (no change) if compliance requires.**

### A.2 Dashboard Migration Checklist

| Step | Splunk Owner | Dynatrace Owner | Acceptance Criteria |
|---|---|---|---|
| 1. Inventory Splunk dashboards | Platform team | Consultant/implementation partner | List all Confluent-related dashboards by cluster/component |
| 2. Map Splunk searches to DQL | Consultant/implementation partner | Consultant/implementation partner + platform team | Mapping doc: each Splunk query → equivalent Grail DQL |
| 3. Build Dynatrace dashboards | Consultant/implementation partner | Consultant/implementation partner | Dashboards 1-4 created, tested in dev environment |
| 4. Validate metric parity | Consultant/implementation partner + platform team | Consultant/implementation partner + platform team | Splunk values ≈ Dynatrace values (within scrape jitter) |
| 5. Build Dynatrace alerts | Consultant/implementation partner | Consultant/implementation partner | 10 must-have alerts + any custom alerts |
| 6. Test alerts (non-prod) | Consultant/implementation partner | Consultant/implementation partner + platform team | Alerts fire correctly, notifications route properly |
| 7. Parallel run (2 weeks) | Both teams | Both teams | Both stacks active; one source of truth TBD |
| 8. Cutover | Platform team | Platform team + Consultant/implementation partner | Splunk metrics archived; Dynatrace becomes primary |
| 9. Splunk dashboard retirement | Platform team | — | Archive Splunk dashboards (30-day grace) |
| 10. Runbook updates | Platform team + Consultant/implementation partner | Platform team | Runbooks point to Dynatrace dashboards, not Splunk |

### A.3 Splunk Search → Grail DQL Translation

Real Grail DQL is **pipe-chained**. It is not the metric-selector `:max :splitBy("dim")` syntax. Earlier drafts of this doc confused the two — the table below uses real DQL.

**Example 1: Broker cluster load (single-value tile)**

Splunk:
```spl
source=confluent_metrics metric_name=cluster_load_percent cluster_id=lkc-prod
| stats latest(value) as load_pct
| eval load_pct=round(load_pct, 2)
```

Real Grail DQL:
```dql
timeseries load = max(confluent_kafka.server.cluster_load_percent),
           by:{dt.entity.confluent_kafka_cluster},
           from:now()-5m
| filter dt.entity.confluent_kafka_cluster == "lkc-prod"
| fieldsAdd load_pct = round(load[-1], decimals:2)
```

**Example 2: Consumer lag by group (time chart)**

Splunk:
```spl
source=confluent_metrics metric_name=consumer_lag_offsets cluster_id=lkc-prod
| stats avg(value) by consumer_group, topic, _time
| timechart avg(value) by consumer_group
```

Real Grail DQL:
```dql
timeseries lag = avg(confluent_kafka.server.consumer_lag_offsets),
           by:{consumer_group_id, topic, dt.entity.confluent_kafka_cluster},
           from:now()-1h,
           interval:1m
| filter dt.entity.confluent_kafka_cluster == "lkc-prod"
```

**Example 3: Alert rule (lag growing)**

Splunk alert:
```spl
source=confluent_metrics metric_name=consumer_lag_offsets cluster_id=lkc-prod consumer_group=payments-*
| stats avg(value) by consumer_group
| where avg(value) > 100000
| alert
```

Dynatrace DQL alert:
```dql
timeseries lag = avg(confluent_kafka.server.consumer_lag_offsets),
           by:{consumer_group_id, dt.entity.confluent_kafka_cluster},
           from:now()-5m
| filter dt.entity.confluent_kafka_cluster == "lkc-prod"
| filter matchesPhrase(consumer_group_id, "payments-")
| filter lag[-1] > 100000
| fieldsAdd severity = "CRITICAL"
```

### A.4 Splunk SPL → DQL Concept Mapping

| Splunk Concept | Grail DQL Equivalent |
|---|---|
| `source=… metric_name=X` | `timeseries val = avg(X), by:{...}` |
| `\| stats latest(value)` | `\| fieldsAdd latest = val[-1]` |
| `\| stats avg(value)` | `timeseries val = avg(metric), …` |
| `\| stats count` | `\| summarize n = count()` |
| `\| stats … by dimension` | `by:{dimension}` in `timeseries`/`summarize` |
| `\| where value > threshold` | `\| filter val[-1] > threshold` |
| `\| timechart avg(value)` | `timeseries val = avg(metric), interval:1m` |
| `\| alert` | DQL-based alert rule with severity field |

### A.5 Notification Routing (No Change)

Dynatrace alert rules route to the same PagerDuty / Opsgenie / Slack / Email channels Splunk used. On-call procedures and runbooks are unchanged — only the source of truth shifts.

### A.6 Audit Log Retention (Existing SIEM Unchanged)

```
Kafka audit events → existing SIEM (e.g. Splunk HEC → Splunk; retention per compliance)
Dynatrace events   → Dynatrace event store (30-day default, extendable per tenant SKU)
```

**Key difference:** Dynatrace events are correlation-focused, not audit-focused. Keep both systems if compliance requires the Kafka audit trail in the existing SIEM.

### A.7 Migration Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Metric ingestion gap during cutover** | Missed alerts | Parallel run Splunk + Dynatrace for 2 weeks before cutover |
| **Alert fatigue from different thresholds** | Splunk tuning ≠ Dynatrace tuning | Run new alerts in audit-only mode for 1 week |
| **Splunk dashboards drift from prod state** | Stale dashboards in use | Archive day 1 of cutover (prevent accidental use) |
| **Audit logs accidentally moved** | Compliance violation | Explicitly exclude audit topics from Dynatrace ingestion |
| **On-call unfamiliar with Dynatrace UI** | Slower MTTR | 1-hour training session with on-call before cutover |
| **DQL/selector confusion** | Dashboards built on wrong query language | Pin to Grail DQL (this guide); reject any v2-metric-selector PR in review |

### A.8 Post-Migration Validation

1. **Metric continuity** (spot-check 5 random metrics)
   - Pick a metric healthy in Splunk; confirm same value in Dynatrace within 5 min
   - Verify trend direction matches

2. **Alert accuracy** (one synthetic test per alert type)
   - Trigger a known condition (force a task into FAILED)
   - Verify Dynatrace alert fires within 1 min
   - Verify notification reaches PagerDuty/Slack

3. **Dashboard completeness**
   - Open Dashboards 1-4; verify no "no data" tiles
   - Verify drill-down links (Platform Overview → Connect Deep Dive) pass `$connector_name`

4. **Runbook accuracy**
   - Pick 3 runbooks tied to Confluent alerts
   - Verify runbook steps reference Dynatrace, not Splunk
   - Update any Splunk-search examples to Grail DQL

---

## Summary: Why a Separate Dashboard for Connect?

**Three-dashboard pattern for brokers works because:**
- Overview → Deep Dive → DR all operate on the same metrics family (load, lag, latency)
- One observability grammar (thresholds, tile types, alert rules)

**Connect requires its own dashboard because:**
- Metrics are fundamentally different (state machines + error counters, not capacity time-series)
- Diagnostics flow differently (state → DLQ → source/sink, not load → lag → latency)
- Downstream correlation (source/sink dashboards) is part of the diagnostic flow

**Your architecture:**

```
Platform Overview (Broker + Link + Connector tables)
    ↓
    ├→ Dashboard 2: Cluster Deep Dive (broker-centric, 7 rows)
    ├→ Dashboard 3: DR Readiness (cluster-link, hard-filtered)
    └→ Dashboard 4: Connect Deep Dive (connector-centric, 6 rows + downstream links)
```

Scales cleanly: 1 platform overview + 3 deep-dive dashboards, no matter how many connectors you add.
