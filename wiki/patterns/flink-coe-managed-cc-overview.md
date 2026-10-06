---
title: Flink Center of Excellence — Managed Flink on Confluent Cloud (Overview)
tags: [flink, confluent-cloud, coe, c4e, enablement, fsi, compute-pools, cfu, flink-sql, governance]
sources:
  - https://docs.confluent.io/cloud/current/flink/concepts/comparison-with-apache-flink.html
  - https://docs.confluent.io/cloud/current/flink/concepts/compute-pools.html
related: [patterns/flink-runtime-models, patterns/flink-coe-optimization, patterns/flink-coe-security, patterns/flink-coe-aws-privatelink-refarch, concepts/confluent-cloud-private-networking, patterns/dead-letter-queue-design]
confidence: high
last_updated: 2026-07-30
last_validated: 2026-07-30
---

# Flink Center of Excellence — Managed Flink on Confluent Cloud (Overview)

## Summary

This is the landing page for a Flink Center of Excellence / Center for Enablement (COE/C4E) built on **Managed Flink on Confluent Cloud (CC)** — the serverless Flink SQL / Table API offering, *not* self-managed Flink or Confluent Manager for Apache Flink (CMF). It exists to stand up the environment, guardrails, and best practices **before use cases are chosen**, so that when workloads arrive the platform, security model, networking, and cost controls are already right. The material here is deliberately foundational and product-shaped rather than use-case-shaped. Deeper subjects live on dedicated sub-pages: [Optimization](flink-coe-optimization.md), [Security](flink-coe-security.md), and [VPC / PrivateLink on AWS reference architecture](flink-coe-aws-privatelink-refarch.md). The single most important thing to internalize up front: **CC Flink is a governed subset of Apache Flink / CP-Flink SQL** — several statements you'd reach for on OSS/CMF are unsupported or behave differently, and one of them (`DROP TABLE`) deletes real Kafka data. See "Anticipated blockers" below.

## Pattern

### Where CC Managed Flink sits

Three ways to run Flink against Confluent, covered in depth in [Flink Runtime Models](flink-runtime-models.md). The one-line decision:

| Model | Surface | Who owns the engine | Pick it when |
|---|---|---|---|
| **CC Managed Flink** (this COE) | Flink **SQL + Table API** only | Confluent (serverless; no checkpoints/state-backend/parallelism knobs) | New SQL/Table workloads on Confluent Cloud; want zero engine ops |
| **CMF** (Confluent Manager for Apache Flink) on CFK/K8s | **Full Flink** — SQL, Table *and* DataStream API, custom JARs | You (checkpointing, state backend, parallelism, HA) | On CP/CFK already; need DataStream/custom code; LinuxONE/s390x |
| **Self-managed OSS Flink** | Full Flink | You + community support | Genuine open-source freedom / unsupported connectors |

**The COE's scope is the first row.** If a use case later needs the DataStream API, custom operators, or arbitrary JARs, that is a signal to escalate to CMF — CC cannot do it (see blockers).

### The CC Flink mental model (what's different from OSS/CMF)

CC maps Confluent Cloud objects onto Flink concepts automatically — this is the biggest day-one adjustment for engineers coming from OSS/CMF:

- **Catalog = environment, database = cluster, table = Kafka topic.** Every topic in the cluster is already a queryable table with its key/value schema mapped from Schema Registry. You rarely write `CREATE TABLE` — use it only to customize schema, set a non-default format, set changelog mode, or do `CREATE TABLE AS SELECT`.
- **Compute pools, sized in CFUs.** Statements run in a compute pool with a `max_cfu` ceiling. **Autopilot** autoscales within that ceiling based on statement parallelism. `max_cfu` **cannot be decreased** after creation — size to realistic peak.
- **`'connector' = 'confluent'`** — a single connector covers both append and upsert behavior. On OSS/CMF you'd write `'kafka'` or `'upsert-kafka'`; that syntax does not apply on CC.
- **Default watermark strategy + `$rowtime` system column.** CC applies a default watermark (fixed out-of-orderness tolerance ~180 ms) to every table off the `$rowtime` column (the Kafka record timestamp). Override with `ALTER TABLE` only when your out-of-orderness materially exceeds that.
- **Schema Registry: Avro, JSON_SR, Protobuf** all supported natively (OSS Flink supports only Avro with SR). `INFORMATION_SCHEMA` exists on CC (it doesn't in OSS).
- **Config option names are remapped and subset.** CC exposes only the necessary subset of Flink options, under `sql.*` names — e.g. `sql.state-ttl` (= OSS `table.exec.state.ttl`), `sql.tables.scan.startup.mode` (= `scan.startup.mode`), `sql.tables.scan.idle-timeout` (= `table.exec.source.idle-timeout`). Port OSS configs through the mapping table, don't assume the OSS name works.

### Environment setup best practices (do these before use cases land)

- **Compute pools per team/environment boundary**, not one shared pool — isolation + billing clarity. Pool exhaustion parks statements in `PENDING`. Start `max_cfu` at ~**5 dev / 10–20 staging / 20–50 prod** and size the ceiling to peak (can't shrink later).
- **Service accounts per application, never per person**; humans get RBAC role bindings, apps get service accounts + API keys. Statements run *as* a principal — set it explicitly (see the Flink-principal blocker below). Details on the [Security](flink-coe-security.md) sub-page.
- **Naming & governance up front** — topic/table naming `<domain>.<entity>.<event>` (see [Topic Naming](topic-naming.md)); Schema Registry compatibility `BACKWARD` default, Avro/Protobuf (JSON only for prototype). Statements and pools carry the environment/team in their names for cost attribution.
- **DLQ on source tables** — set `error-handling.mode='log'` so source deserialization errors route to a DLQ table rather than failing the statement (see [Dead Letter Queue Design](dead-letter-queue-design.md)). Scope caveat: it catches *source deserialization* errors only, not UDF/serialization/window errors.
- **Networking decided before first statement** — for FSI this is PrivateLink; the client-→Flink path is private and the [AWS PrivateLink reference architecture](flink-coe-aws-privatelink-refarch.md) sub-page covers the wiring. Flink→Kafka traffic stays internal to Confluent Cloud.
- **Baseline defaults that apply everywhere** (from [Flink Runtime Models](flink-runtime-models.md)): bounded watermarks + idleness timeout, `sql.state-ttl` on every non-windowed stateful op, `upsert-kafka`/`confluent` for changelog output, tumbling > sliding > session windows, `scan.startup.mode=earliest-offset` for deterministic replay.

### Anticipated blockers & FSI gotchas

Flag these to the adopting team now — several will surface the moment engineers port OSS/CMF habits:

| Blocker | Why it bites | Mitigation |
|---|---|---|
| **`DROP TABLE` deletes the underlying Kafka topic + all data + SR subjects** (default `TopicNameStrategy`) | On OSS it's metadata-only. On CC it destroys regulated data in one statement. A genuine FSI incident risk. | RBAC: withhold table-drop from developers; change-control any `DROP`. `RecordNameStrategy`/`TopicRecordNameStrategy` preserve subjects but still drop the topic. |
| **Unsupported statements**: `DELETE`, `UPDATE`, `TRUNCATE`, `ANALYZE`, `CALL`, `JAR`, `LOAD`/`UNLOAD`, catalog/database `CREATE`/`DROP`/`ALTER` | Engineers assume full SQL DML/DDL. CC is append/stream-oriented; no row mutation. | Model as streams/changelogs; no in-place mutation. Escalate genuinely-needed cases to CMF. |
| **No DataStream API, no custom JARs on CC** | Custom operators / arbitrary Java are impossible on CC. | If a use case needs it → CMF, not CC. Decide the runtime per use case. |
| **No processing-time operations** (`PROCTIME()`, `*_PROCTIME`) | Event-time only. Porting proctime jobs fails. | Use event-time (`$rowtime`) — better for regulatory determinism anyway. |
| **Limited `ALTER TABLE`** — only change watermark, add a metadata column, or change a param value | Schema/structural alters you'd do on OSS aren't available. | Plan schema evolution through Schema Registry, not `ALTER TABLE`. |
| **Windowing only via TVF syntax** (`TUMBLE`/`HOP`/`SESSION`/`CUMULATE` as table-valued functions) | Legacy grouped-window syntax is rejected. | Write window TVFs from the start. |
| **`max_cfu` can't be decreased**; **state without TTL runs away** | Cost/CFU blow-ups; the #1 CC Flink surprise. | Size to peak; `sql.state-ttl` on every unbounded stateful op. See [Optimization](flink-coe-optimization.md). |
| **Flink statement needs a principal** (`flink_principal_id` / `principal {}`), else Terraform fails | `error creating Flink Statement: one of provider.flink principal id … must be set`. | Set the SA principal on the provider or resource. See [Security](flink-coe-security.md). |
| **`SHOW CREATE TABLE` output isn't re-runnable** | Re-running yields an SR subject-mismatch error, misread as schema incompatibility. | Don't use it as a migration script. |

## When to Use

- Standing up a Flink practice on Confluent Cloud where **use cases aren't chosen yet** and your organization wants environment + guardrails first.
- Establishing the CC-vs-CMF decision boundary so teams don't start a DataStream/custom-JAR workload on CC and hit a wall.
- FSI enablement where the governance, security, and PrivateLink posture must be defined before any regulated data flows through Flink.

## Caveats

- CC Flink capability moves fast — the unsupported-statement list and default watermark tolerance were validated against `confluent-docs` on 2026-07-30; re-check before committing to a specific capability.
- This overview is product/environment shaped. Use-case-specific tuning (fraud scoring, reconciliation, CDC) will need its own pages once the adopting team selects workloads.
- The comparison here is CC vs OSS/CMF. CMF ≈ full Apache Flink; the "subset" caveats are about **CC**, not CMF.

## Related

- [Flink Runtime Models — CC Managed, CMF, and Self-Managed](flink-runtime-models.md) — the runtime decision, state-TTL, CFU sizing, and a full triage table
- [Flink COE — Optimization](flink-coe-optimization.md) — CFU/state/watermark tuning (sub-page)
- [Flink COE — Security](flink-coe-security.md) — RBAC, service accounts, principals, mTLS (sub-page)
- [Flink COE — AWS PrivateLink Reference Architecture](flink-coe-aws-privatelink-refarch.md) — VPC/PL wiring on AWS (sub-page)
- [Private Networking](../concepts/confluent-cloud-private-networking.md) — PrivateLink Gateway mechanics that the AWS ref arch builds on
- [Dead Letter Queue Design](dead-letter-queue-design.md) — CC Flink managed DLQ (`error-handling.mode`)
