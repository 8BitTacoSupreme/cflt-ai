---
title: "Confluent Cloud → Dynatrace Metrics Integration"
type: runbook
scope: Confluent Cloud Metrics API → Dynatrace extension via Environment ActiveGate
audience: platform / observability engineering
created: 2026-08-13
validated_against: [confluent-docs MCP 2026-08-13, wiki/concepts/observability-metrics-mapping, outputs/reports/dynatrace-metrics-*]
status: ready-to-execute
---

# Runbook — Confluent Cloud → Dynatrace Metrics

**Outcome:** Confluent Cloud telemetry (Kafka clusters, connectors, Schema Registry, Flink compute pools/statements, ksqlDB, Cluster Links) flowing into Dynatrace, populating the prebuilt dashboard, within one maintenance window.

**Estimated time:** 45–60 min, most of it waiting on the first poll cycle and on firewall change approval.

**Who needs to be in the room:** someone with Confluent Cloud **OrganizationAdmin** (or environment-level admin) to create the role binding, someone with Dynatrace **settings write** on the target environment, and — the one people forget — whoever approves **egress firewall rules for the ActiveGate host**.

---

## 0. The thing that breaks most of these installs

> **The Dynatrace extension talks to two different Confluent hosts, and they are commonly on different firewall rules.**

| Host | Carries | Symptom if blocked |
|---|---|---|
| `api.confluent.cloud` | Resource **discovery** — listing environments, clusters, connectors, compute pools | Monitoring config saves, but the resource picker is empty |
| `api.telemetry.confluent.cloud` | The **metrics** themselves (Metrics API v2) | Resources appear and are selectable, config looks healthy, **no data ever arrives** |

The second failure is the nasty one: everything in the UI looks correct and the dashboard just stays empty. Allowlist **both**, on TCP 443, from the ActiveGate host — not from OneAgent hosts.

*Validated 2026-08-13 against `confluent-docs`: the Metrics API is served from `https://api.telemetry.confluent.cloud/v2/metrics/cloud/...` (descriptors, discovery, query, export endpoints).*

---

## 1. Preconditions

Tick all of these before starting. Each one is a real failure mode.

- [ ] **An Environment ActiveGate** (or Dynatrace-managed ActiveGate) is running and connected to the target environment.
  Not a Cluster ActiveGate alone, and **not OneAgent** — see the note below.
- [ ] That ActiveGate has the **Extension Execution Controller (EEC)** running. Extensions 2.0 execute on the EEC; an ActiveGate without it will accept the config and never poll.
- [ ] **Egress from the ActiveGate host** to both hosts in §0 on 443, direct or via a proxy the ActiveGate is configured to use.
- [ ] Confluent Cloud **OrganizationAdmin** (or `EnvironmentAdmin` on every environment in scope) available to bind `MetricsViewer`.
- [ ] Dynatrace permission to install from Hub and write monitoring configuration.
- [ ] A decision on **scope**: which environments and which resource types. Decide before you start; changing it later re-triggers discovery and briefly gaps the data.

### OneAgent's actual role here

OneAgent does **not** poll Confluent Cloud. Confluent Cloud is SaaS — there is no host for OneAgent to instrument. The ActiveGate extension is the collector for everything in this runbook.

OneAgent remains useful, but for the other half of the picture: your **producer and consumer applications** — JVM/process metrics, distributed traces, and the `traceparent` propagation that lets you correlate an application span with the Kafka topic it wrote to. If your goal includes end-to-end latency from application through Kafka and back, you want both, and they meet in the dashboard, not in the collection path.

---

## 2. Confluent Cloud — service account, role, API key

### 2.1 Create a dedicated service account

Do not use a user account or an existing shared key. One service account per integration.

```bash
confluent login --organization-id <ORG_ID>

confluent iam service-account create "dynatrace-metrics-collector" \
  --description "Read-only Metrics API access for Dynatrace extension. Owner: <team>. Rotate: <date>"
# → returns sa-xxxxxx — record this
```

### 2.2 Bind the MetricsViewer role

`MetricsViewer` is the only role required. Grant at the **organization** level to cover all environments, or per-environment for tighter scope.

```bash
# Organization-wide (simplest; covers environments added later)
confluent iam rbac role-binding create \
  --principal User:sa-xxxxxx \
  --role MetricsViewer \
  --organization <ORG_ID>

# OR per-environment (tighter; must be repeated for each new environment)
confluent iam rbac role-binding create \
  --principal User:sa-xxxxxx \
  --role MetricsViewer \
  --environment env-xxxxx
```

**Verify the binding landed** — this is a two-minute check that saves an hour of 403 debugging:

```bash
confluent iam rbac role-binding list --principal User:sa-xxxxxx
```

You can also confirm in the Console under **Accounts & access → Service accounts → <sa> → Access**.

### 2.3 Create a resource-scoped API key — the right kind

> ⚠️ **This is the step that fails most often.** The key must be scoped to **Cloud resource management**, not to a Kafka cluster. Confluent's documentation states it plainly: *"API keys resource-scoped for Kafka clusters cause an authentication error."* A cluster-scoped key will authenticate fine against the cluster and fail against the Metrics API — which reads as "wrong password" and sends people back to rotate a perfectly good key.

```bash
confluent api-key create \
  --resource cloud \
  --service-account sa-xxxxxx \
  --description "Dynatrace Confluent Cloud extension — metrics polling"
```

`--resource cloud` is the whole distinction. If you find yourself passing `--resource lkc-xxxxx`, stop — that is the wrong key type.

Store the secret immediately; Confluent will not show it again.

### 2.4 Gate — prove the credential works before touching Dynatrace

**Run this from the ActiveGate host**, not from your laptop. The point is to test the credential *and* the network path in one shot.

```bash
curl -s -u "<API_KEY>:<API_SECRET>" \
  'https://api.telemetry.confluent.cloud/v2/metrics/cloud/descriptors/resources' \
  | head -c 500
```

| Result | Meaning | Action |
|---|---|---|
| JSON listing resource descriptors (`kafka`, `connector`, `schema_registry`, `compute_pool`, `ksql`…) | ✅ Credential and network path both good | Proceed to §3 |
| `401 Unauthorized` | Wrong key type (cluster-scoped) or bad secret | Return to §2.3 |
| `403 Forbidden` | Key is right, `MetricsViewer` missing or bound at the wrong scope | Return to §2.2 |
| Connection timeout / DNS failure | Egress to `api.telemetry.confluent.cloud` not permitted | Firewall — see §0 |
| Proxy auth error | ActiveGate proxy not configured for this host | Configure proxy on the ActiveGate |

Also confirm the discovery host separately, since it is a different rule:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -u "<API_KEY>:<API_SECRET>" \
  'https://api.confluent.cloud/org/v2/environments'
# expect 200
```

**Do not proceed past this gate.** Every downstream symptom becomes ambiguous if the credential path is unproven.

---

## 3. Dynatrace — install the extension

1. **Dynatrace → Hub → Extensions**, search **"Confluent Cloud (Kafka)"**.
2. **Add to environment**. Note the extension **version** — you will need it when a metric turns out to be missing (§6).
3. Confirm it is an **Extensions 2.0** (EEC-executed) extension and that at least one ActiveGate group is eligible to run it.

*Dynatrace UI navigation changes between releases; treat the path above as indicative and the outcome — "extension present in the environment" — as the actual step.*

---

## 4. Dynatrace — monitoring configuration

Create one monitoring configuration per Confluent Cloud **organization**. Split per environment only if you need different ActiveGate groups or different polling intervals.

| Field | Value | Notes |
|---|---|---|
| **ActiveGate group** | The group whose hosts passed the §2.4 gate | Not "any" — pin it, so you know which host to check when polling stops |
| **API key / secret** | From §2.3 | Store as a Dynatrace credential, not inline, so rotation is one edit |
| **Resources** | Select clusters, connectors, Schema Registry, Flink compute pools, ksqlDB apps in scope | Discovery populates this from `api.confluent.cloud` — an empty list here means §0 host 1 is blocked |
| **Feature sets** | See below | Each feature set is a polling cost; enable deliberately |
| **Polling interval** | Default unless you have a reason | Shorter intervals increase Metrics API request volume — see §6 on rate limits |

### Feature sets

The extension exposes these; enable what maps to a dashboard or an alert you actually have:

| Feature set | Covers | Enable when |
|---|---|---|
| **Server Metrics** | Broker/cluster: throughput, partition count, retained bytes, request latency | Always |
| **Connector Metrics** | Managed connector throughput and status | You run managed connectors |
| **Connector CDC Metrics** | Debezium-family CDC — Postgres, MySQL, SQL Server, Oracle, MariaDB, DynamoDB | You run CDC connectors; pairs with `patterns/transactional-outbox.md` |
| **Cluster Link Metrics** | Mirror lag, link throughput | You use Cluster Linking — mandatory if it is your DR path |
| **Flink Statement Metrics** | Per-statement records in/out, pending records, statement status | You run CC Flink |
| **Compute Pool Metrics** | CFU utilisation | You run CC Flink |
| **Schema Registry Metrics** | Schema count, request rates | Always, if you have SR (you do) |
| **KSQL Metrics** | ksqlDB app health | You run ksqlDB |

**Save.** First poll typically lands within a few minutes.

---

## 5. Verify ingestion

Do not rely on the dashboard rendering as your proof — an empty dashboard and a broken dashboard look identical.

### 5.1 Confirm metrics are arriving

**Discover the actual metric keys first — do not assume them.** Three naming conventions are in play and they are easy to confuse:

| Layer | Form | Example |
|---|---|---|
| CC Metrics API (native) | `io.confluent.<component>/<metric>` | `io.confluent.kafka.server/received_bytes` |
| Prometheus-flavoured (`/export`, Grafana) | all separators → `_` | `confluent_kafka_server_received_bytes` |
| **Dynatrace DQL** | underscored namespace, **dot** before the metric name | `confluent_kafka_server.received_bytes` |

Run this in **Dynatrace → Notebooks** first and work from what it returns:

```dql
fetch metric.series
| filter matchesPhrase(metric.key, "confluent")
| summarize count(), by: { metric.key }
| sort `count()` desc
| limit 100
```

Then spot-check a known-good series (Dynatrace form, per `wiki/concepts/observability-metrics-mapping.md`):

```dql
timeseries v = rate(confluent_kafka_server.received_bytes, time:5m), by: { kafka_id }, from: -30m
```

Expected namespaces once feature sets are on:

| Namespace | From |
|---|---|
| `confluent_kafka_server.*` | Server Metrics |
| `confluent_kafka_connect.*` | Connector Metrics |
| `confluent_kafka_schema_registry.*` | Schema Registry Metrics |
| `confluent_kafka_ksql.*` | KSQL Metrics |
| `confluent_flink_*` — `compute_pool_utilization`, `num_records_in`, `num_records_out`, `pending_records`, `statement_status` | Flink Statement + Compute Pool Metrics |

> ⚠️ **Confirm the exact keys in your own tenant before writing alerts against them.** The Dynatrace forms above come from `wiki/concepts/observability-metrics-mapping.md` (confidence: medium), whose Dynatrace column may describe the **push/ingest** path (`/api/v2/metrics/ingest`) rather than the **extension** path this runbook uses. The two can differ in namespace. The discovery query above settles it in ten seconds — run it, then pin your dashboards and alerts to what it actually returns.

### 5.2 Confirm the extension is actually executing

Check the monitoring configuration's status in Dynatrace — it should report the last successful execution and the number of endpoints polled. If it reports errors, the EEC log on the ActiveGate host is where the real message is (typically under the ActiveGate's `log/extensions` directory; exact path varies by ActiveGate version and OS).

### 5.3 Confirm resource coverage

Count distinct `kafka_id` values and compare against your expected cluster inventory. A silently partial selection — three of five clusters — is the most common "it works" outcome that isn't.

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401` from §2.4 | Cluster-scoped API key | Recreate with `--resource cloud` (§2.3) |
| `403` from §2.4 | `MetricsViewer` missing or bound to wrong scope/principal | Rebind (§2.2); confirm the principal is the **service account**, not your user |
| Resource picker empty in Dynatrace | `api.confluent.cloud` blocked | Firewall (§0, host 1) |
| **Resources selectable, config healthy, no data ever** | `api.telemetry.confluent.cloud` blocked | Firewall (§0, host 2) — the classic |
| Data arrives, then stops | Key expired/rotated; ActiveGate down; proxy credential change | Re-run §2.4 from the ActiveGate host |
| **A metric you expect does not exist in Dynatrace** | **Extension version lag** — packaged integrations do not include metrics released after the integration's own last update | Update the extension; if still missing, fall back to the Prometheus `/export` endpoint (§7) |
| Connector *state* (RUNNING/FAILED) missing for fully-managed connectors | Not exposed via CC Metrics API for fully-managed connectors | Poll the Connect REST API separately — see `wiki/concepts/observability-metrics-mapping.md` |
| Gaps / sawtooth in series | Polling interval vs Metrics API rate limits or metric publication delay | Lengthen the interval; ⚠️ confirm current rate limits for your org (not asserted here — see §8) |
| Metrics present but dashboard empty | Dashboard filtered on a dimension you are not populating (e.g. `environment`) | Check dashboard variable bindings against §5.1 output |

---

## 7. Fallback — the Prometheus `/export` endpoint

If the extension lags a metric you need, the Metrics API exposes a Prometheus-format export that carries anything marked exportable:

```
https://api.telemetry.confluent.cloud/v2/metrics/cloud/export
```

Basic auth with the same key/secret. Ingest via a Dynatrace Prometheus scrape or a generic extension. Useful as a stopgap for a newly released metric; **not** a reason to skip the packaged extension, which gives you entity modelling and the prebuilt dashboard the raw export does not.

---

## 8. Known limits and what to confirm yourself

**Validated 2026-08-13 via `confluent-docs`:**
- Metrics API host and endpoints (`descriptors/resources`, `discovery`, `export`) on `api.telemetry.confluent.cloud`
- Resource-scoped-for-resource-management API key required; Kafka-cluster-scoped keys cause an authentication error
- `MetricsViewer` role required, bound to a service account
- Dynatrace extension connects with a resource-scoped key; prebuilt dashboard populates within minutes of resource selection

**Not validated — confirm before relying on:**
- ⚠️ **Metrics API rate limits and per-request cardinality caps** for your org tier. These govern how short your polling interval can safely be.
- ⚠️ **Metric granularity and publication delay.** Confluent Cloud metrics are near-real-time, not real-time; alert thresholds and evaluation windows must accommodate the delay. Measure it in your own tenant rather than assuming.
- ⚠️ **ActiveGate minimum version** for the current extension release — check the Hub listing.
- ⚠️ **Your live tenant.** The `dynatrace` MCP server was not connected when this runbook was written, so no metric key in §5.1 was verified against your environment. The Dynatrace forms come from `wiki/concepts/observability-metrics-mapping.md` (confidence: medium) — and that article's Dynatrace column may describe the push/ingest path rather than the extension path. **Run the discovery query in §5.1 and pin everything to what it returns.**
- ⚠️ **Extension metric-key namespace.** Whether the extension emits under `confluent_kafka_server.*` (matching the mapping article) or its own namespace is the single most likely place this runbook is wrong. It costs one query to find out and it invalidates every dashboard binding if you skip it.

**Structural limits:**
- Fully-managed connector **state** is not in the CC Metrics API — separate Connect REST API polling required.
- Packaged integrations lag the Metrics API. Confluent documents this explicitly for the Grafana integration; the same applies to any vendor-packaged extension, Dynatrace included.

---

## 9. Rollback

1. **Dynatrace** — disable the monitoring configuration (keeps credentials and selection for a fast re-enable). Remove the extension only if you are abandoning the integration.
2. **Confluent Cloud** — delete the API key:
   `confluent api-key delete <KEY>`
3. Remove the role binding:
   `confluent iam rbac role-binding delete --principal User:sa-xxxxxx --role MetricsViewer --organization <ORG_ID>`
4. Delete the service account if the integration is being retired permanently.
5. Leave the firewall rules — they are narrow, read-only-egress, and you will want them again.

Rollback is non-destructive to Confluent Cloud: this integration is read-only throughout. Nothing here can affect cluster operation.

---

## 10. FSI overlay

- **Service account per integration, never shared.** This one holds read access to operational telemetry across the org — it belongs in the same rotation and attestation cycle as any other production credential. Record the owner and rotation date in the service-account description (§2.1 does this inline).
- **`MetricsViewer` is read-only and carries no payload access.** Worth stating explicitly in a control narrative: the Dynatrace integration cannot read message contents, only metrics. This is usually the first question from a reviewer and the answer is clean. See `wiki/patterns/auditor-readonly-rbac-payload-isolation.md`.
- **Prefer per-environment role bindings** where environments map to regulated vs non-regulated workloads, so the blast radius of the credential matches the data classification.
- **API key rotation must be a runbook, not an event.** Storing the secret as a Dynatrace credential (§4) means rotation is a single edit; storing it inline in the monitoring config means rotation is a rediscovery.
- **This is metrics, not audit.** Confluent Cloud audit logs are a separate pipeline with separate retention and separate regulatory weight — do not let a green metrics dashboard imply audit coverage. See `wiki/patterns/audit-log-siem-integration.md`.
- **Alert thresholds must reflect the SLA tier**, not a single global default — see `wiki/concepts/sla-tiers.md`.

---

## Related

- `wiki/concepts/observability-metrics-mapping.md` — CC Metrics API vs JMX across six providers
- `wiki/concepts/consumer-lag-monitoring.md` — lag specifically; alert on the derivative, not the absolute
- `wiki/concepts/schema-registry-observability.md` · `wiki/concepts/ksqldb-observability.md` · `wiki/patterns/cluster-linking-observability.md`
- `wiki/patterns/cfk-observability-baseline.md` — the self-managed/CFK counterpart to this runbook
- `outputs/reports/dynatrace-metrics-customer-wiki-glossary.md` — per-metric glossary with directionality
- `outputs/reports/connect-dynatrace-review-2026-05-19.md` — Connect JMX + DQL validation
