---
title: "Flink Center of Excellence — Managed Flink on Confluent Cloud"
subtitle: "Foundations, Optimization, Security, and AWS PrivateLink Reference Architecture"
date: "2026-07-30"
---

*A self-contained enablement guide for standing up Managed Flink on Confluent Cloud (CC) before use cases are selected. Product- and environment-shaped, not use-case-shaped. All Confluent-product claims validated against Confluent documentation on 2026-07-30; items marked (LA) are Limited Availability and (unverified) are noted where a claim could not be confirmed against current docs.*

---

# Part 1 — Overview

## What this is

This guide is the foundation for a Flink Center of Excellence / Center for Enablement (COE/C4E) built on **Managed Flink on Confluent Cloud (CC)** — the serverless Flink SQL / Table API offering. It is intentionally *not* about a specific use case: it establishes the environment, guardrails, and best practices so that when workloads arrive, the platform, security model, networking, and cost controls are already correct.

The single most important thing to internalize: **CC Flink is a governed subset of Apache Flink / Confluent Platform (CP) Flink SQL.** Several statements you would reach for on open-source (OSS) Flink or CP-Flink (managed by Confluent Manager for Apache Flink, "CMF") are unsupported or behave differently on CC — and one of them (`DROP TABLE`) deletes real Kafka data. See "Anticipated blockers" at the end of this part.

## Where CC Managed Flink sits

There are three ways to run Flink against Confluent. The one-line decision:

| Model | Surface | Who owns the engine | Choose it when |
|---|---|---|---|
| **CC Managed Flink** (this COE) | Flink **SQL + Table API** only | Confluent — serverless; no checkpoint / state-backend / parallelism knobs | New SQL/Table workloads on Confluent Cloud; zero engine ops |
| **CMF** (Confluent Manager for Apache Flink) on Kubernetes | **Full Flink** — SQL, Table *and* DataStream API, custom JARs | You — checkpointing, state backend, parallelism, HA | On CP/Kubernetes already; need DataStream/custom code |
| **Self-managed OSS Flink** | Full Flink | You + community support | Genuine open-source freedom / unsupported connectors |

The COE's scope is the first row. If a use case later needs the DataStream API, custom operators, or arbitrary JARs, that is a signal to escalate to CMF — **CC cannot do those.**

## The CC Flink mental model (what differs from OSS/CMF)

CC maps Confluent Cloud objects onto Flink concepts automatically. This is the biggest day-one adjustment for engineers coming from OSS/CMF:

- **Catalog = environment, database = cluster, table = Kafka topic.** Every topic in the cluster is already a queryable table, with its key/value schema mapped from Schema Registry. You rarely write `CREATE TABLE` — use it only to customize a schema, set a non-default serialization format, set changelog mode, or run `CREATE TABLE AS SELECT`. A topic with no registered schema is exposed as raw `BINARY` key/value.
- **Compute pools, sized in CFUs (Confluent Flink Units).** Statements run in a compute pool with a maximum-CFU ceiling. Autoscaling ("Autopilot") scales resources within that ceiling based on statement parallelism. Pools **scale down to zero** when no statement is running (no cost at rest).
- **`'connector' = 'confluent'`** — a single connector covers both append and upsert behavior. On OSS/CMF you would write `'kafka'` or `'upsert-kafka'`; that syntax does not apply on CC.
- **Default watermark strategy + `$rowtime` system column.** CC applies a default watermark (fixed out-of-orderness tolerance ~180 ms) to every table, based on the `$rowtime` column (the Kafka record timestamp). Override it with `ALTER TABLE` only when your out-of-orderness materially exceeds that (for example, batch-loaded historical data). CC is event-time by default.
- **Schema Registry: Avro, JSON Schema (JSON_SR), and Protobuf** are all supported natively (OSS Flink supports only Avro with Schema Registry). `INFORMATION_SCHEMA` exists on CC (it does not in OSS).
- **Configuration options are a remapped subset.** CC exposes only the necessary subset of Flink options, under `sql.*` names. Port OSS configs through this mapping — do not assume the OSS name works:

| Confluent Cloud | Apache Flink (OSS/CP) |
|---|---|
| `sql.state-ttl` | `table.exec.state.ttl` |
| `sql.tables.scan.startup.mode` | `scan.startup.mode` |
| `sql.tables.scan.idle-timeout` | `table.exec.source.idle-timeout` |
| `sql.local-time-zone` | `table.local-time-zone` |

## Environment setup best practices (do these before use cases land)

- **Compute pools per team/environment boundary**, not one shared pool — isolation and billing clarity. Pool exhaustion parks statements in `PENDING`. A default pool (up to 50 CFU) is auto-provisioned on first use; create dedicated pools to isolate production. Suggested starting ceilings: **5–10 dev / 10–20 staging / 20–50 prod.**
- **Service accounts per application, never per person.** Humans get RBAC role bindings; applications get service accounts and API keys. Production statements should run *as a service account* — see Part 3.
- **Naming and governance up front** — topic/table naming `<domain>.<entity>.<event>`; Schema Registry compatibility `BACKWARD` by default, Avro or Protobuf (JSON only for prototype). Carry the environment/team in pool and statement names for cost attribution.
- **Dead-letter handling on source tables** — CC Flink supports a managed DLQ via the source table property `error-handling.mode = 'log'` (with `error-handling.log.target = '<table>'`), which routes records CC cannot deserialize to a DLQ table instead of failing the statement. **Scope caveat:** it catches *source deserialization* errors only — not errors in user-defined functions, serialization, or windowed aggregations.
- **Networking decided before the first statement** — for FSI this is PrivateLink. The client→Flink control-plane path is private; Flink→Kafka traffic stays internal to Confluent Cloud. See Part 4.
- **Baseline defaults that apply to every statement:** bounded watermarks plus an idleness timeout; `sql.state-ttl` on every non-windowed stateful operator; the `confluent` connector for changelog output; tumbling windows preferred over sliding/session; `sql.tables.scan.startup.mode = earliest-offset` for deterministic replay.
- **Canonical topology:** `Producers → raw landing topic → Flink SQL (filter/transform) → output topic`. "Direct to Flink" does not exist on CC — Flink is compute over Kafka only. External data must enter via a connector or producer first.

## Anticipated blockers & FSI gotchas

Flag these now — several surface the moment engineers port OSS/CMF habits:

| Blocker | Why it bites | Mitigation |
|---|---|---|
| **`DROP TABLE` deletes the underlying Kafka topic + all data + Schema Registry subjects** (default `TopicNameStrategy`) | On OSS it is metadata-only. On CC it destroys regulated data in one statement — a genuine incident risk. | RBAC: withhold table-drop from developer roles; change-control any `DROP`. `RecordNameStrategy` / `TopicRecordNameStrategy` preserve subjects but still drop the topic. |
| **Unsupported statements:** `DELETE`, `UPDATE`, `TRUNCATE`, `ANALYZE`, `CALL`, `JAR`, `LOAD`/`UNLOAD`, and catalog/database `CREATE`/`DROP`/`ALTER` | Engineers assume full SQL DML/DDL. CC is append/stream-oriented; no row mutation. | Model as streams/changelogs. Escalate genuinely-needed cases to CMF. |
| **No DataStream API and no custom JARs on CC** | Custom operators / arbitrary Java are impossible on CC. | If a use case needs it → CMF, not CC. Decide the runtime per use case. |
| **No processing-time operations** (`PROCTIME()`, `TUMBLE_PROCTIME`, etc.) | Event-time only. Porting processing-time jobs fails. | Use event-time (`$rowtime`) — better for regulatory determinism anyway. |
| **Limited `ALTER TABLE`** — only change the watermark strategy, add a metadata column, or change a parameter value | Structural alters available on OSS are not on CC. | Evolve schemas through Schema Registry, not `ALTER TABLE`. |
| **Windowing only via Table-Valued-Function syntax** (`TUMBLE`/`HOP`/`SESSION`/`CUMULATE` as TVFs) | Legacy grouped-window syntax is rejected. | Write window TVFs from the start. |
| **State without TTL runs away; CFU cost follows state and throughput** | The #1 CC Flink cost surprise. | `sql.state-ttl` on every unbounded stateful operator (see Part 2). |
| **A Flink statement needs a principal** to run as | Terraform fails with `error creating Flink Statement: one of provider.flink principal id … must be set`. | Set the service-account principal on the provider or the resource (see Part 3). |
| **`SHOW CREATE TABLE` output is not a re-runnable script** | Re-running yields a Schema-Registry subject-mismatch error, easily misread as a schema-incompatibility problem. | Do not use it as a migration script. |

---

# Part 2 — Optimization (CFUs, Autopilot, State, Statement Lifecycle)

On Managed Flink you do **not** tune parallelism, checkpoint intervals, or state backends — Autopilot and the serverless runtime own those. What you control is CFU pool sizing, state growth, watermark tolerance, and statement lifecycle. Cost is driven by **throughput rate and state size, not event count.**

## CFU sizing & Autopilot

- **Maximum 50 CFU per compute pool** (both default and user-created). A single statement can scale up to the full pool capacity, so the practical maximum for one statement is 50 CFU. Pools with up to **1,000 CFU are available as Limited Availability (LA)** for large job fleets; even there, a single job's maximum remains 50 CFU, and concurrent jobs cannot collectively exceed the pool ceiling.
- **Pools scale down to zero** when no statement is running — no cost at rest.
- **CFU burn is proportional to throughput rate × state size**, not total event count — e.g. tens of millions of events at hundreds-to-low-thousands events/sec typically settle at ~1–3 CFU via Autopilot.
- **Autopilot** handles autoscaling and parallelism inside the pool — there is no manual parallelism knob. It ramps over several minutes on a backfill; watch the "Messages Behind" metric (it spikes, then converges to zero).
- **Size to realistic peak.** Reducing a pool's maximum CFU after creation is a change to validate against current tooling behavior before relying on it (the CLI/Terraform behavior for lowering the ceiling is version-dependent and was not confirmed against docs here) *(unverified)*. Run larger workloads by distributing statements across multiple pools.
- One pool per team/environment boundary. `OrganizationAdmin` can raise the default 50-CFU platform limit.

## State & watermarks (the cost blow-up)

- **`sql.state-ttl` on every non-windowed stateful operator.** Unbounded regular joins and non-windowed aggregations keep state forever otherwise — the #1 CFU blow-up and out-of-memory cause. Prefer interval, temporal (versioned-table), and lookup joins — they are bounded by construction. Pure filter/projection statements are stateless and need no TTL.
- **Default watermark = ~180 ms** bounded out-of-orderness on `$rowtime`. Retune for batch-loaded/historical data (high out-of-orderness) or windows never fire. Set an idleness timeout (`sql.tables.scan.idle-timeout`) so a quiet partition does not stall the global watermark and silently prevent all window output.

## Statement lifecycle (immutability drives your deploy model)

- **Statements are immutable** — the SQL cannot be edited after submission. To change a statement you stop the old one and create a new one.
- **Statements snapshot their catalog objects at creation** — a later change to a source schema or watermark does **not** propagate to a running statement.
- **Stateless carry-over offsets:** for a stateless (filter/projection) statement, `SET 'sql.tables.initial-offset-from' = '<old-statement-name>';` lets the new statement resume from the old one's offsets. This is **not valid** for aggregations, windows, pattern-matching, or upsert sinks.
- **Checkpoint interval, state backend, and storage are not user-configurable on CC** (they are on CMF). If you must tune them, that is a reason to use CMF, not CC.

## Quick triage

| Symptom | Likely cause | First moves |
|---|---|---|
| Statement stuck `PENDING` | Compute pool out of CFU capacity | Raise the pool maximum, or split work across pools |
| Windows never produce output | Watermark not advancing — idle partition with no idleness timeout, or event-time skew | Set `sql.tables.scan.idle-timeout`; check the source event-time field; loosen the bound |
| Runaway CFUs / state growth | Missing TTL on a regular join or non-windowed aggregation; high-cardinality `GROUP BY`/`COUNT(DISTINCT)` | Add `sql.state-ttl`; switch to interval/temporal/lookup join; reconsider the key |
| Backfill slow to catch up | Autopilot still ramping | Watch "Messages Behind"; it converges — avoid over-provisioning reactively |

---

# Part 3 — Security (RBAC, Service Accounts, Principals)

CC Flink needs **two role planes** — control-plane (Flink) roles to submit and manage statements, *and* data-plane (Kafka / Schema Registry) roles for the topics and subjects a statement touches. Missing either fails at submit time or at first topic access. Production statements must run **as service accounts, not users.**

## Control-plane (Flink) roles

| Role | Grants |
|---|---|
| `FlinkDeveloper` | Create and run statements, manage artifacts and your own workspaces. Can be scoped at the compute-pool level to restrict a user to specific pools. |
| `FlinkAdmin` | All FlinkDeveloper capabilities plus creating and managing compute pools (workload isolation / cost control). |
| `FlinkFunctionDeveloper` | Manage user-defined-function (UDF) artifacts and external connectivity. |
| `Operator` | Metadata access to Flink tables, databases, and catalogs. |
| `Assigner` (granted on the service account) | Delegate statement execution to a service account — required for the OAuth identity-pool → service-account pattern (the identity pool authenticates; the service account executes). |

> Note: **`FlinkEnvironmentAdmin` is not a real role** — confirmed absent from the Confluent role catalog. Some third-party materials mislabel `FlinkDeveloper` as `FlinkEnvironmentAdmin`; use `FlinkDeveloper`.

## Data-plane (Kafka / Schema Registry) roles the statement's principal needs

- `DeveloperRead` on **source** topics; `DeveloperWrite` on **sink** topics.
- **Both `DeveloperRead` and `DeveloperWrite` on Transactional-Id `_confluent-flink_*`** — required for **all** Flink statements (Flink uses Kafka transactions for exactly-once semantics), not just sinks.
- `DeveloperRead` on **source** Schema Registry subjects; `DeveloperWrite` on **sink** subjects. The sink-subject write is required because the Avro/Confluent format defaults to auto-registering schemas — **without it, sink writes fail with a 403** (which, in a self-managed runtime, manifests as a crash-loop).

## Service-account principal model

- **Bind production statements to service accounts, not user accounts** — this prevents disruption when a person's status changes. The `Assigner` role on the service account is what lets a human submit statements that *run as* that service account.
- **In Terraform**, a Flink statement must have a principal: set `flink_principal_id` on the Confluent provider (or the `FLINK_PRINCIPAL_ID` environment variable), or a `principal { id = … }` block on the statement resource. Omitting it fails with `one of provider.flink principal id … must be set`.
- **`DROP TABLE` deletes the underlying topic and data** — withhold table-drop from developer roles and change-control any drop.

## FSI hardening notes (from comparable regulated deployments)

- **Bind roles to identity-provider groups, never to individuals** — revocation flows through group membership, which satisfies SOX/FFIEC access-change logging. Scope Flink roles to the environment (or pool), not organization-wide.
- **Least-privilege binding shape:** separate bindings for (1) source-topic read, (2) sink-topic write + Transactional-Id, (3) source-subject read, (4) sink-subject write — so each is independently auditable and revocable.
- **Flink topic access is auto-audited** — every authorization decision on a Flink topic access is emitted to the audit-log event stream; statement submit/cancel is also captured. This is the enforcement point for proving access controls at audit time.
- **Contrast with CMF (self-managed):** on CMF, the job's Kafka identity is an mTLS certificate whose CN/SAN matches the service account; checkpoint state must be written to encrypted storage (unencrypted checkpoints can contain transaction amounts / account numbers — a PCI-DSS / GLBA finding). Neither applies to CC, where checkpoints are managed and endpoints are reached via API key / OAuth / mTLS to the managed service.

---

# Part 4 — AWS VPC / PrivateLink Reference Architecture

Two network paths matter, and only one is yours to wire.

1. **Flink → Kafka: always internal to Confluent Cloud.** This path never traverses PrivateLink or the public internet and requires no configuration. The compute pool reaches the cluster over Confluent's internal fabric.
2. **Client → Flink: PrivateLink-governed.** SQL Workspaces (Console), the Flink shell/CLI, `confluent_flink_statement` (Terraform), and the REST API all reach the Flink control-plane endpoint — that path is what you make private.

## Do you need a separate PrivateLink for Flink?

| Cluster type | Separate Flink gateway? | Shape |
|---|---|---|
| **Enterprise** | **No** — reuse the one ingress PrivateLink Gateway | One Private Endpoint / one PrivateLink Service covers Kafka + Flink + Schema Registry + Connect |
| **Dedicated** (PrivateLink, Peering, or Transit Gateway for Kafka) | **Yes** — Flink needs its own gateway in the **same region** | Two Private Endpoints, each targeting a different Confluent PrivateLink Service alias, sharing one Private DNS zone |

- **Gateway model:** the older PrivateLink Attachment (PLATT) was superseded by the **ingress PrivateLink Gateway** (AWS cutover 2026-02-12); existing PLATTs continue to function but new ones should use the gateway model.
- **Egress PrivateLink** (niche): for Flink statements reaching *out* to an external service — for example AWS KMS for field-level encryption — available on Enterprise clusters, one gateway per region per environment.

## AWS wiring

- **VPC interface endpoint** targeting the Confluent **PrivateLink Service alias** (recorded from Network Management → "For serverless products" → PrivateLink).
- **Route 53 private hosted zone** with a wildcard record mapping the Flink access-point domain (`*.<region>.aws.private.confluent.cloud`) to the endpoint. Resolution is a two-step CNAME: Confluent's global resolver returns the access-point name and your private resolver maps it to the endpoint. **Wildcard the zone; never hardcode broker/endpoint names** (they are not static).
- **Access Point** registers the endpoint back to the gateway.

## Deployment flow (the FSI pattern)

- **Developers get no direct CLI/Console access to production.** All Flink SQL is version-controlled and deployed by a **self-hosted CI/CD runner inside your VPC** (required for PrivateLink reachability), which calls `confluent_flink_statement` (preferred, infrastructure-as-code) or the REST API over the Private Endpoint.
- Because the Flink control-plane endpoint (`flink.<region>.aws.private.confluent.cloud`) is a private target, the runner must be able to **resolve it** (private hosted zone attached to the runner's network) and **reach it** (the endpoint's security group allows TCP/443 from the runner's CIDR, and the runner's node pool spans the availability zones that have an endpoint — PrivateLink endpoints are per-AZ). These are the same requirements as any private data-plane Terraform apply.

## Two common failure modes on this path

- **`dial tcp <private-IP>:443: i/o timeout`** — DNS resolved to a private address but the connection timed out. This is reachability, not DNS: the endpoint security group does not allow 443 from the runner, or the runner landed in an availability zone with no endpoint. Confirm with `nc -vz <private-IP> 443`.
- **`no such host`** for the Flink or Schema Registry hostname — the private hosted zone is not resolvable from the runner. Attach/forward the Confluent private hosted zone to the runner's network.

---

# Appendix — Validation & Status

- **Validated against Confluent documentation on 2026-07-30:** the CC-vs-OSS/CP subset (unsupported statements, `DROP TABLE` topic deletion, `'connector'='confluent'`, default 180 ms watermark, config-name mapping); compute-pool limits (50 CFU/pool, scale-to-zero, 1,000 CFU LA); Flink RBAC role catalog (`FlinkDeveloper`, `FlinkAdmin`, `FlinkFunctionDeveloper`, `Operator`, `Assigner`; `FlinkEnvironmentAdmin` confirmed *not* a role); Transactional-Id `_confluent-flink_*` requirement; the managed DLQ (`error-handling.mode`); and the PrivateLink gateway model.
- **(LA) Limited Availability:** 1,000-CFU compute pools.
- **(unverified):** the exact behavior of *decreasing* a pool's maximum CFU after creation — size to peak and validate against current tooling before relying on shrink behavior.
- **Scope:** this guide is product/environment-shaped. Use-case-specific tuning (fraud scoring, reconciliation, CDC pipelines) and full AWS reference diagrams/Terraform should be added once workloads are selected. CC Flink capability evolves quickly — re-confirm any specific capability before committing to a design.
