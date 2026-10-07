---
title: Flink on Confluent Cloud — Setup, RBAC, Lifecycle, and Statement Evolution
tags: [flink, confluent-cloud, compute-pools, rbac, autopilot, watermarks, statement-evolution, cfu, udf, flink-artifact]
sources: [https://docs.confluent.io/cloud/current/flink/overview.md, https://docs.confluent.io/cloud/current/flink/concepts/compute-pools.md, https://docs.confluent.io/cloud/current/flink/concepts/statements.md, https://docs.confluent.io/cloud/current/flink/concepts/autopilot.md, https://docs.confluent.io/cloud/current/flink/concepts/schema-statement-evolution.md, https://docs.confluent.io/cloud/current/flink/concepts/timely-stream-processing.md, https://docs.confluent.io/cloud/current/flink/operate-and-deploy/flink-rbac.md, https://docs.confluent.io/cloud/current/flink/how-to-guides/create-udf.md]
related: [patterns/flink-runtime-models, concepts/flink-checkpointing, concepts/schema-evolution-strategies, concepts/schema-registry-best-practices, concepts/exactly-once-semantics, patterns/flink-coe-security]
confidence: high
last_updated: 2026-09-10
last_validated: 2026-09-10
---

# Flink on Confluent Cloud — Setup, RBAC, Lifecycle, and Statement Evolution

## Summary

Confluent Cloud for Apache Flink (CC Flink) is the serverless Flink runtime on Confluent Cloud — SQL + Java/Python Table API (preview), with Kafka topics auto-exposed as queryable tables via a fixed three-part name (`environment.cluster.topic` → `catalog.database.table`). Resources are allocated through region-bound **compute pools** sized in **CFUs**, scaled automatically by **Autopilot**. Permissions split across two distinct planes: **control plane** (Flink RBAC roles — who can submit statements) and **data plane** (Kafka/SR RBAC — what data the statement reads/writes). Statement SQL is immutable, so production change-management uses **materialized tables** (`CREATE OR ALTER MATERIALIZED TABLE`) or manual **carry-over-offsets** evolution. The same immutability governs **UDFs**: a statement pins the artifact version it was submitted against, so updating a function means replacing dependent statements, and the resulting breakage lands on *stopped* statements rather than running ones (§7). Pairs with [Flink Runtime Models](../patterns/flink-runtime-models.md) (CC vs CMF vs self-managed) and [Flink Checkpointing](flink-checkpointing.md).

> **Validation status (confidence: high, revalidated 2026-09-10).** Re-checked against `confluent-docs` after 117 days of decay. **Confirmed unchanged:** all §1 CFU limits (50-CFU default pool max modifiable by `OrganizationAdmin`, 50 CFU per user-created pool, 50 CFU per statement, 1,000-CFU pools still Limited Availability with the single-job cap unchanged, scale-to-zero, region binding); all §4 hard limits (4 MB query text, 72-char statement name, 500 GB soft / 1000 GB hard state, 5-minute foreground idle, 30-day terminal retention, immutable SQL, mutable principal/pool while stopped); all five §3 Flink RBAC roles and the `_confluent-flink_*` Transactional-Id grants. **Corrected:** the 80%-warning threshold (applies to *both* limits, not just soft), the statement-state list (added `Failing`), and `FlinkDeveloper`'s UDF-artifact grant (see §3 note). **Added:** §7 UDF artifacts and function evolution. **Not revalidated this pass:** §5 Autopilot internals (the ~10 GB-per-task-manager target), §6 watermark numeric defaults, and the "Table API (preview)" status in the Summary — no evidence either way was found in the pages fetched, so those carry forward from 2026-05-15 unverified.

## Detail

### 1. Compute pools

A compute pool is a **regional** set of compute resources that runs SQL statements. All statements in a pool share its resources.

| Property | Value |
|---|---|
| Capacity unit | **CFU** (Confluent Flink Unit) |
| Default pool max | **50 CFUs** (modifiable only by `OrganizationAdmin`) |
| User-created pool max | Configurable, **up to 50 CFUs per pool** |
| Max CFUs per single statement | **50 CFUs** (full pool — practical ceiling for one job) |
| Idle scale-down | Pool with no running statements scales to **zero** |
| Region scope | Pool reads/writes Kafka topics **only in the same region** |
| Cross-environment | Pool can query topics in **other environments in the same region** if RBAC allows |
| Move statement between pools | Requires **stop → change pool → resume** |
| Decrease max CFUs after creation | Not supported on user-created pools |

> **Default pools are shared and automatic.** When enabled at the org level (the default), CC Flink creates a default pool on first use in an environment/region; all users in that environment use it unless they specify an explicit pool. `OrganizationAdmin` can disable default pools globally, forcing all users to create explicit pools.

> **Limited Availability:** Pools up to **1,000 CFUs** are available via the LA program. Per-statement cap remains 50 CFUs; the 1,000-CFU pool just lets you run more concurrent 50-CFU jobs in one pool.

**Sizing guidance** — see [Flink Runtime Models — CC compute pool sizing](../patterns/flink-runtime-models.md) for the 5/10–20/20–50 dev/staging/prod starting points. The biggest single sizing variable is **state size**, not throughput.

### 2. Catalog / database / table mapping

CC Flink is a SQL surface on top of Confluent Cloud's existing metadata. Nothing is declared manually for existing topics:

| Kafka object | Flink object | Sync behavior |
|---|---|---|
| Environment | Catalog | One-to-one |
| Kafka cluster | Database | One-to-one |
| Topic + Schema Registry subject | Table | **Bidirectional, automatic.** Creating a table in Flink creates the topic + schema in CC. Creating a topic in CC makes it instantly queryable as a Flink table. |

DDL statements (`CREATE TABLE`, `DROP TABLE`, `ALTER TABLE`) act on **physical** objects, not metadata only — distinct from open-source Flink. Three-part name queries work across environments in the same region:

```sql
SELECT * FROM `myEnvironment`.`myCluster`.`myTopic`;
```

**Cross-region queries are blocked by design** — protects data sovereignty and avoids cross-region transfer charges. Workload isolation across regions requires separate pools per region.

### 3. RBAC — dual control-plane / data-plane model

A user (or service account) needs **permissions on both planes** to run a statement successfully. CC Flink does not support ACLs.

#### Control plane (Flink roles — what you can do in Flink)

| Role | Grants |
|---|---|
| `FlinkDeveloper` | Create/run statements, manage own workspaces. Granted by default to all users at org/env scope, or bind at compute-pool scope to restrict access to specific pools. |
| `FlinkAdmin` | All FlinkDeveloper capabilities + create/delete/modify user-created compute pools. |
| `FlinkFunctionDeveloper` | **The UDF artifact role** — manage user-defined function artifacts and external connectivity. No statement or compute pool access. |
| `Assigner` | Delegate statement execution to a service account (required for OAuth identity-pool integration; user holds Assigner on the SA). |
| `Operator` | Metadata access to Flink tables/databases/catalogs. |

> **Revalidation note (2026-09-10):** the previous version credited `FlinkDeveloper` with UDF-artifact management. The Flink RBAC overview attributes that specifically to **`FlinkFunctionDeveloper`** and describes `FlinkDeveloper` as statements + workspaces only. Corrected above. If you need the per-permission breakdown, the `predefined-rbac-roles` page is authoritative and was not re-read this pass.

**Least-privilege split for UDF release pipelines.** Because artifact management and statement management are separate roles, a CI pipeline should use two identities: `FlinkFunctionDeveloper` for the artifact-upload job (cannot touch running statements) and `FlinkDeveloper` bound at **compute-pool scope** for the function-registration and statement-migration job. `EnvironmentAdmin` is not required for either. See §7 and `outputs/runbooks/cc-flink-udf-release-runbook.md`.

#### Data plane (Kafka + Schema Registry roles — what the statement can touch)

| Layer | Kafka resource | Schema Registry resource |
|---|---|---|
| **Base/required** (every statement) | `DeveloperRead` + `DeveloperWrite` on Transactional-Id `_confluent-flink_*` | — |
| **Read tables** (`SELECT FROM`) | `DeveloperRead` on topic | `DeveloperRead` on subject |
| **Write tables** (`INSERT INTO`) | `DeveloperWrite` on topic | `DeveloperRead` on subject (to validate format) |
| **Create tables** (`CREATE TABLE [AS SELECT]`) | `DeveloperManage` on topic (or prefix) | `DeveloperWrite` on subject (or prefix) |
| **Alter tables** (`ALTER TABLE` — watermarks, columns) | `DeveloperManage` on topic | `DeveloperWrite` on subject |
| **CSFLE / CSPE** (encrypted fields) | — | `DeveloperRead` on KEK (DeveloperWrite required only for first write that generates the DEK) |

**Key behavioral points:**

- **Statements are not principals.** A statement inherits the permissions of the principal (user or service account) running it. Compute pools are **resources, not principals** — Alice and Bob can share a pool, but each statement runs under its submitter's identity.
- **Cross-environment data access** is governed by the principal's RBAC. A statement in env A can read topics in env B if the principal has data-plane perms in B and they're in the same region.
- **Transaction ID structure:** `_confluent-flink_{statement-name}_{statement-uid}_{jobgraph-node-id}_{subtask-index}_{transaction-index}`. The statement UID (UUID) guarantees uniqueness across statements of the same name.

**FSI/production rule:** Long-running statements (`INSERT INTO` pipelines) must run under a **service account**, not a user account, so authorization survives user departures and role changes. Production user grants Assigner on the SA; SA gets the least-privilege layered permissions above. See [FSI Compliance](fsi-compliance.md) and [Audit Log SIEM Integration](../patterns/audit-log-siem-integration.md).

### 4. Statement lifecycle

Submitting a SQL query creates a **statement** resource. Statement SQL and statement properties (e.g., `sql.state-ttl`) are **immutable** — you cannot edit them. To change SQL, you stop the statement and submit a new one. The **principal** and the **compute pool** are mutable, but only while the statement is stopped.

States: **Pending → Running → Completed | Failing → Failed | Degraded**, with `Stopping → Stopped` and `Deleting` as terminal transitions. `Failing` is the distinct transitional state between encountering an error and `Failed`. `Degraded` signals an unhealthy job (no commits for a long time, frequent restarts) but is not yet failed.

| Hard limit | Value |
|---|---|
| Query text size | **4 MB** (entire semicolon-separated string if multi-statement) |
| Statement name length | **72 characters** |
| State size — soft limit | **500 GB per statement** (Autopilot stops statement; resume possible but uptime SLA no longer applies) |
| State size — hard limit | **1000 GB (1 TB) per statement** (statement fails, non-resumable) |
| Foreground statement idle timeout | **5 minutes** with no consumer → STOPPED |
| Terminal-state retention | **30 days** before deletion |

Warnings fire at **80% of either limit** — soft (400 GB) *and* hard (800 GB) — via Cloud Console + Metrics API notifications. State-size limits are absolute global values; they don't scale with pool CFUs.

**Materialized tables vs statements.** For long-running streaming pipelines, prefer **materialized tables** (`CREATE [OR ALTER] MATERIALIZED TABLE`) — they're persistent objects that you evolve in place, and Flink automates the stop/swap/migrate workflow. Use direct statements for ad hoc queries, snapshot/batch work, and interactive SQL.

### 5. Autopilot

Autopilot continuously monitors all statements and scales their CFU usage automatically — there is no manual parallelism configuration on CC.

| Scaling status | Meaning |
|---|---|
| `Fine` | Statement has enough resources at required parallelism. |
| `Pending Scale Up` / `Pending Scale Down` | Autopilot has decided to adjust; allocation is in flight. |
| `Compute Pool Exhausted` (`POOL_EXHAUSTED`) | Pool is at its CFU limit; statement may run at reduced parallelism or stay `PENDING`. Fix: raise pool max, stop other statements, or split across pools. |

**"Messages Behind"** is the CC Flink UI label for consumer lag. Autopilot's goal is to keep Messages Behind near zero. The diagnostic matrix:

| Symptom | Read |
|---|---|
| Messages Behind ↑, status `Pending Scale Up` | Normal — Autopilot is reacting; lag should fall once allocation lands. |
| Messages Behind ↑, status `Fine` | **Something is wrong.** Open a Support case. |
| Messages Behind stable, status `Compute Pool Exhausted` | Pool can keep up but has no room to optimize; raise CFU limit or stop other statements. |

**State as a scaling dimension.** Autopilot uses state size (not just throughput) when deciding parallelism, targeting ~**10 GB per task manager**. Large state forces scale-ups while CFUs are available; when state exceeds the soft limit (500 GB), Autopilot stops the statement.

### 6. Watermarks and time

**Processing time is not supported on CC Flink.** All time-based operations run on event time.

| Mechanism | Default |
|---|---|
| Default watermark strategy | `SOURCE_WATERMARK()` function applied to every table automatically |
| Watermark emission interval | Every **200 ms** |
| Watermark alignment | **Enabled by default**; controlled via `sql.tables.scan.watermark-alignment.max-allowed-drift` (default **5 minutes**, matches default idleness timeout) |
| Idleness timeout | **5 minutes** by default — partitions with no events for this long are marked idle so they don't stall the global watermark |
| Time attribute types | `TIMESTAMP(p)` or `TIMESTAMP_LTZ(p)` with `0 ≤ p ≤ 3` |
| Late data handling | `late-handling.mode = 'pass-through'` (default) or `'filter'` (with `$late` system table for filtered events) |

The Canon default of `BOUNDED_OUT_OF_ORDERNESS` with a bounded delay applies — see [Flink Runtime Models](../patterns/flink-runtime-models.md) for the cross-runtime watermark rules and the "windows never fire" troubleshooting matrix.

**Watermark alignment** pauses reading from streams running ahead, letting laggers catch up — relevant for temporal joins between streams with diverging timestamps. Only increase max-allowed-drift if you also increase the idleness timeout (otherwise alignment kicks in while Flink is still waiting to mark partitions idle, wasting CPU).

### 7. Schema and statement evolution

#### Schema compatibility (Schema Registry side)

CC Flink follows the compatibility mode set on each Schema Registry subject. CC's **default is `BACKWARD`** — but for Flink-driven evolution, Confluent recommends `FULL` or `FULL_TRANSITIVE` because the upgrade order of producers vs consumers doesn't matter under FULL. See [Schema Evolution Strategies](schema-evolution-strategies.md) for tier-based compatibility selection and [Schema Registry Best Practices](schema-registry-best-practices.md) for governance.

For changes that exceed `FULL`'s envelope, use **compatibility groups + migration rules** (Data Contracts).

**A statement snapshots its dependencies.** When you create a statement, it captures the configuration of every catalog object it references (tables, UDFs). Changes to source-table watermark strategy, table options, or UDF implementations **do not propagate to existing statements** — the statement keeps running against the snapshot. The current schema version at the time of statement creation is what the statement reads.

#### UDF artifacts and function evolution

The snapshot rule above has sharper consequences for UDFs than for tables, because a UDF's implementation lives in a separate, independently deletable object.

**The artifact is a first-class resource.** A UDF is two objects, not one: an **artifact** (the compiled JAR for Java, packaged distribution for Python) and a **function** registered against it.

| Property | Behavior |
|---|---|
| Uniqueness | `display_name` unique per **cloud + region + environment** |
| Mutability | **Immutable.** Every upload produces a new artifact with its own ID — there is no in-place replacement |
| Cloud support | **AWS and AZURE only.** No GCP artifact support (note this differs from compute pools) |
| Region | Must match the compute pool that runs the consuming statement |
| Languages | Java 11–21, or Python 3.11 |
| Size | Python artifacts capped at **100 MB**; no Java limit is documented — don't assume parity |

Registration is a statement, not a config field:

```sql
-- Java
CREATE FUNCTION fraud_score
  AS 'com.goodlabs.udf.FraudScoreFunction'
  USING JAR 'confluent-artifact://<artifact_id>';

-- Python adds LANGUAGE PYTHON
CREATE FUNCTION is_smaller
  AS 'example_udf.tshirt_sizing.is_smaller'
  LANGUAGE PYTHON
  USING JAR 'confluent-artifact://<artifact_id>';
```

Add `USING CONNECTIONS ('my_external_service')` where the UDF calls out; manage the endpoint with a `confluent_flink_connection` rather than embedding secrets in statement properties.

**There is no `ALTER FUNCTION`.** UDFs are immutable in the same sense statement SQL is (§4). Updating one means dropping the function and creating it again against a new artifact.

**The pin is to an artifact version, and that inverts the obvious risk.** A statement's compiled plan pins the UDF to the artifact that existed at submission time. So:

- **Currently running statements are unaffected** by `DROP FUNCTION` — they keep executing against the pinned artifact.
- **Stopped and failed statements are the exposure.** Their plans still reference the old artifact. If it has been deleted, they cannot resume — they fail with an artifact-not-found error, discovered only at resume time.

This is the opposite of the intuitive check. Before dropping a function or deleting an artifact, enumerate **non-`RUNNING`** statements, not running ones.

**Migration requires statement replacement.** You cannot swap a UDF underneath a running or stopped statement. Dependent statements must be dropped and recreated so they recompile and bind to the new artifact. Two operational consequences:

- In Terraform this is `terraform apply -replace='<statement_address>'`, never a plain `apply` — `statement` is not an editable attribute (only `stopped`, plus `principal.id` / `compute_pool.id` when resuming).
- **`lifecycle { prevent_destroy = true }` blocks that replacement.** The guard recommended for production statements is precisely what stops a UDF rollout, and Terraform forbids variables in `lifecycle` blocks, so it must be unset by a reviewed config edit and restored afterwards.

**Recovery** for a statement pinned to a deleted artifact: `terraform apply -replace=` forces recompilation against the current function definition. Outside Terraform, drop and recreate the statement. The Terraform symptom is not a clean error — the apply hangs on `Still modifying...` and eventually fails with context-deadline-exceeded.

**Rollout order** — either Confluent's documented same-name procedure (upload new artifact → drop and recreate function under the same name → recreate dependent statements → delete old artifact), or the versioned-name variant (`fraud_score_v2` alongside `fraud_score`) which keeps v1 resolvable throughout and so protects stopped statements during the migration window. The versioned variant is the same shape as the manual query-evolution strategy below, applied to functions. Full procedure: `outputs/runbooks/cc-flink-udf-release-runbook.md`.

#### Query evolution — materialized tables (preferred)

```sql
-- Create
CREATE MATERIALIZED TABLE orders_with_customers AS
SELECT o.order_id, c.name AS customer_name, o.price
FROM examples.marketplace.orders o
JOIN examples.marketplace.customers c ON o.customer_id = c.customer_id;

-- Evolve in place — Flink handles the stop / new query / consumer migration
CREATE OR ALTER MATERIALIZED TABLE orders_with_customers AS
SELECT o.order_id, c.name AS customer_name, c.city AS customer_city, o.price
FROM examples.marketplace.orders o
JOIN examples.marketplace.customers c ON o.customer_id = c.customer_id;
```

#### Query evolution — manual (statements only)

Use this only when materialized tables don't apply (exploratory queries, batch, edge cases).

1. `CREATE TABLE orders_with_customers_v2 AS SELECT ... FROM ...;` — new version writes to a new topic.
2. Wait until **Messages Behind ≈ 0** on the v2 statement.
3. Migrate downstream consumers (find them via **Stream Lineage**) to the new topic.
4. Stop the v1 statement.

Trade-offs of the base strategy:
- Works for any statement type.
- Requires source-table retention to cover the full reprocess window.
- Forces every downstream consumer to switch topics — they read v2 from earliest by default.

#### Carry-over offsets (exactly-once for stateless evolution)

When a statement stops, `status.latestOffsets` records the latest committed offset for every partition of every source:

```yaml
status:
  latestOffsets:
    topic1: partition:0,offset:23;partition:1,offset:65
    topic2: partition:0,offset:53;partition:1,offset:56
  latestOffsetsTimestamp: ...
```

You can feed these offsets into the new statement via **dynamic table option hints** so v2 resumes exactly where v1 left off — yielding **exactly-once semantics across the upgrade**, but **only for stateless statements**: filters, routers, and per-row transforms (including UDFs and `UNNEST`):

```sql
-- Stateless filter — exactly-once carry-over works
INSERT INTO shipped_orders
SELECT * FROM orders WHERE status = 'shipped';

-- Stateless router via STATEMENT SET
EXECUTE STATEMENT SET
BEGIN
  INSERT INTO shipped_orders   SELECT * FROM orders WHERE status = 'shipped';
  INSERT INTO cancelled_orders SELECT * FROM orders WHERE status = 'cancelled';
END;
```

To limit reprocessing instead of carrying over, use `scan.startup.mode` hints to start from a timestamp:

```sql
SELECT ...
FROM orders /*+ OPTIONS('scan.startup.mode' = 'timestamp',
                        'scan.startup.timestamp-millis' = '1717763226336') */
JOIN customers /*+ OPTIONS('scan.startup.mode' = 'timestamp',
                           'scan.startup.timestamp-millis' = '1717763226336') */
ON orders.customer_id = customers.id;
```

If the query is windowed, also add `WHERE event_time > '<aligned-window-start>'` so reprocessing starts on a window boundary.

#### In-place upgrade

Replaces the running query while keeping the **same output topic**. Constraints:

- Output table must have a **primary key** (so the new statement updates rows the old one wrote).
- Only **compatible** changes — both semantically and at the schema level.
- Downstream consumers must tolerate **out-of-order, late, bulk updates to all keys** during catch-up.

Procedure: stop the old statement → submit the new one writing to the same `INSERT INTO` target → consumers see the rewritten state via key-level upserts. This pairs naturally with stateless carry-over offsets.

## Related

- [Flink Runtime Models — CC, CMF, Self-Managed](../patterns/flink-runtime-models.md) — cross-runtime defaults (watermarks, state TTL, `upsert-kafka`) and CC compute-pool sizing
- [Flink Checkpointing](flink-checkpointing.md) — Chandy-Lamport mechanics; on CC these are fully managed and not user-tunable
- [Schema Evolution Strategies](schema-evolution-strategies.md) — tier-based compatibility selection
- [Schema Registry Best Practices](schema-registry-best-practices.md) — TopicNameStrategy and operational surface
- [Exactly-Once Semantics](exactly-once-semantics.md) — Flink two-phase commit foundation
- [FSI Compliance](fsi-compliance.md) — audit-log requirements for production service accounts
