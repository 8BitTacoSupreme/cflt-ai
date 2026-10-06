---
title: "Flink in Confluent Cloud: Setup, Private Link, and Event Routing Architecture"
date: 2026-04-13
query: "Flink setup and configuration in a Confluent Cloud environment; whether an existing Private Link to the environment also covers Flink; event-routing best practice for ~50M events with selective extraction (raw topic → Flink → output topic vs. direct to Flink)"
wiki_sources: [concepts/flink-checkpointing, concepts/exactly-once-semantics, concepts/fsi-data-streaming-platform, synthesis/adr-index]
claims_checked: 23
claims_corrected: 0
claims_unverifiable: 1
---

# Flink in Confluent Cloud: Setup, Private Link, and Event Routing Architecture

## TL;DR

Flink in Confluent Cloud maps automatically onto existing CC resources (Environment = catalog, Kafka cluster = database, topic + SR schema = table). Create a compute pool, configure RBAC with both Flink and data-plane roles, and run SQL. Private Link for Flink depends on cluster type: Enterprise clusters reuse the existing PrivateLink Gateway; Dedicated clusters need a separate gateway even if Kafka already has PL. Flink-to-Kafka traffic is always internal. For 50M events with selective extraction, land everything to a raw topic, filter/transform in Flink SQL, and emit to an output topic — this is the canonical and only supported pattern in CC, and it gives you replayability, schema decoupling, and debuggability.

## Analysis

### Part 1: Flink Setup in Confluent Cloud

#### Automatic Catalog Mapping

No manual catalog configuration is needed. The mapping is:

| Flink Concept | Confluent Cloud Resource |
|---|---|
| Catalog | Environment |
| Database | Kafka Cluster |
| Table | Kafka Topic (with Schema Registry schema) |

Topics with registered schemas automatically surface as queryable tables. The `$rowtime` system column maps to the Kafka record timestamp. If a topic has no registered schema subjects (`<topic>-key` / `<topic>-value`), key and value are exposed as raw `BINARY` columns.

#### Step 1: Create a Compute Pool

A default pool (up to 5 CFUs) is auto-provisioned on first use. For production, create a dedicated pool to isolate workloads:

```bash
confluent flink compute-pool create prod-pool \
  --cloud azure --region eastus2 --max-cfu 50 \
  --environment env-xxxxx
```

Key characteristics:
- Pools scale to zero when idle — no cost at rest.
- Max CFUs can be increased later but **cannot be decreased**.
- Maximum 50 CFUs per pool (GA); up to 1,000 CFU in Limited Availability.

> ⚠️ unverified — The UI may restrict CFU selection to discrete values (5, 10, 20, 30, 40, 50); the CLI accepts int32 with no documented restriction to specific increments.

#### Step 2: Configure RBAC

Users need **both** control-plane and data-plane roles:

**Control-plane (Flink roles):**

| Role | Scope | Permissions |
|---|---|---|
| FlinkDeveloper | Environment or Pool | Create/run statements, manage workspaces |
| FlinkAdmin | Environment | FlinkDeveloper + create/manage compute pools |
| FlinkFunctionDeveloper | Environment | Manage UDF artifacts and external connectivity |
| Assigner | Service Account | Delegate statement execution to service accounts |
| Operator | Environment | Metadata access to Flink tables, databases, catalogs |

**Data-plane (Kafka/SR roles):**
- `DeveloperRead` on source topics
- `DeveloperWrite` on sink topics
- `DeveloperRead` and `DeveloperWrite` on `Transactional-Id _confluent-flink_*`

For production: bind statements to **service accounts**, not user accounts. This prevents statement disruption from user status changes.

#### Step 3: Run Flink SQL Statements

Submit via SQL Workspaces (Console), `confluent flink shell`, CLI (`confluent flink statement create`), REST API, or Terraform (`confluent_flink_statement`).

Statement characteristics:
- **Immutable** — SQL query cannot be modified after submission.
- Statement name max: 72 characters; query text max: 4 MB.
- Autopilot handles autoscaling within the pool — no manual parallelism tuning.
- Default watermark: 180ms bounded out-of-orderness per Kafka partition on `$rowtime`.
- Stopped statements have 30-day retention.
- State size limits: 500 GB soft, 1 TB hard per statement.

#### Checkpointing

Fully managed in Confluent Cloud — users do not configure checkpoint intervals, state backends, or storage. See [Flink Checkpointing](wiki/concepts/flink-checkpointing.md) for internals. On Confluent Platform (self-managed via CMF), all standard Flink checkpoint properties are user-configurable at pool and statement level.

#### Statement Evolution

Statements snapshot dependent catalog objects at creation time. Schema or watermark changes to source tables do **not** propagate to running statements. To evolve a statement:

1. Stop the old statement.
2. Create a new statement with updated SQL.
3. For stateless operations (filter/projection), use carry-over offsets to avoid reprocessing:

```sql
SET 'sql.tables.initial-offset-from' = '<old-statement-name>';
```

The new statement waits up to 6 hours for the old one to stop. Only works for stateless operations — not usable with aggregations, windows, pattern matching, or upsert sinks.

---

### Part 2: Private Link and Flink

#### Two Distinct Network Paths

1. **Flink-to-Kafka (internal)**: Routed internally within Confluent Cloud infrastructure. Never traverses the public internet regardless of networking configuration. No action needed.
2. **Client-to-Flink (ingress)**: CLI, Console, Terraform, REST API talking to the Flink control plane. This is what Private Link governs.

#### Do You Need a Separate PL for Flink?

| Cluster Type | Flink PL Requirement |
|---|---|
| **Enterprise** | No — reuse the existing PrivateLink Gateway |
| **Dedicated (any connection type: PL, Peering, TGW)** | **Yes** — Flink needs its own PrivateLink Gateway in the same region, even if Kafka already has PL |

#### Azure Private Link Setup

As of February 2026, the PrivateLink Attachment (PLATT) resource has been replaced by the **ingress PrivateLink Gateway**. Existing PLATTs continue to function.

1. Navigate to **Environments** > **Network management** in the Console.
2. Select the **For serverless products** tab.
3. Click **+Add gateway configuration** and choose PrivateLink.
4. Configure: gateway name, Azure, region (must match your Kafka cluster region).
5. Record the **Private Link Service alias** provided by Confluent.
6. In your Azure subscription, create an **Azure Private Endpoint** in your VNet targeting that alias.
7. Configure **Private DNS Zones** for resolution (e.g., `*.az.private.confluent.cloud`).
8. Create an **Access Point** in Confluent Cloud to register the Azure Private Endpoint.

#### Egress Private Link (Niche Case)

If Flink statements need to reach external Azure services (KMS for field-level encryption, etc.), Egress PrivateLink Endpoints provide outbound connectivity. Enterprise clusters only, one gateway per region per environment.

---

### Part 3: Event Routing Architecture — Raw Topic → Flink → Output Topic

#### The Canonical Pattern

Flink in Confluent Cloud reads from Kafka topics and writes to Kafka topics. There is no "send directly to Flink" — Flink is a compute layer over Kafka, not an ingestion endpoint.

```
Producers → raw.events.ingested (landing topic)
                    │
              Flink SQL (filter/transform/enrich)
                    │
              domain.entity.processed (output topic)
```

This is the only supported topology in CC Flink. It is also the right one for selective extraction from 50M events.

#### Why Raw-First

| Benefit | Explanation |
|---|---|
| **Replayability** | Raw topic preserves the full corpus. If filter logic changes, rewind (`scan.startup.mode = 'earliest-offset'`) and reprocess without re-ingesting from source. |
| **Schema decoupling** | Raw schema is the source-of-truth contract. Output schema evolves independently. Statement snapshots freeze schema at creation time. |
| **Debuggability** | When output looks wrong, diff against raw. Without the raw topic, you're blind. |
| **Decoupling** | Producer logic stays simple (serialize and send). All business logic lives in Flink SQL — version-controlled, testable, hot-swappable via carry-over offsets. |

#### Flink SQL Example

```sql
-- Create output table (auto-creates topic + registers schema)
CREATE TABLE domain.entity.processed (
  event_id STRING,
  customer_id STRING,
  event_type STRING,
  payload STRING,
  event_time TIMESTAMP_LTZ(3),
  PRIMARY KEY (event_id) NOT ENFORCED
) WITH (
  'changelog.mode' = 'upsert',
  'kafka.retention.time' = '0'    -- infinite retention with compaction
);

-- Continuous selective extraction from raw → processed
INSERT INTO domain.entity.processed
SELECT
  raw.event_id,
  raw.customer_id,
  raw.event_type,
  raw.payload,
  raw.`$rowtime` AS event_time
FROM raw.events.ingested /*+ OPTIONS('scan.startup.mode'='earliest-offset') */ AS raw
WHERE raw.event_type IN ('order.placed', 'payment.completed', 'risk.flagged');
```

#### Sizing and State

- Pure filter/projection is **stateless** — no state TTL configuration needed, no state size accumulation. The Confluent docs explicitly state: "Queries such as `SELECT ... FROM ... WHERE` which consist only of field projections or filters are usually stateless pipelines."
- CFU consumption is driven by **throughput rate**, not total event count. 50M events at typical throughput rates (hundreds to low thousands of events/sec) will settle at 1-3 CFUs via Autopilot.
- Monitor "Messages Behind" metric — for initial backfill, expect elevated values that converge to zero.
- If you add joins or aggregations later, configure `sql.state-ttl` or use `STATE_TTL` hints per operator to prevent unbounded state growth.

#### Anti-Pattern

Do not pre-filter in the producer to skip the raw topic. This bakes business logic into your ingestion pipeline, eliminates replayability, and creates tight coupling that breaks when filtering requirements change.

## Comparison

| Approach | Replayability | Schema Decoupling | Debuggability | Complexity | Storage Cost |
|---|---|---|---|---|---|
| **Raw → Flink → Output** (recommended) | Full replay from raw | Independent evolution | Diff raw vs. output | Low (stateless Flink SQL) | Raw topic retention cost (negligible at 50M events) |
| **Pre-filter before Kafka** | No replay without re-ingestion | Coupled | Blind spot on filtered-out events | Higher (logic in producer) | Lower (only filtered events stored) |
| **Direct to Flink** | N/A — not supported in CC | N/A | N/A | N/A | N/A |

## Decision Framework

- **If on Enterprise clusters with existing PL** → No additional Private Link work for Flink. Reuse the existing gateway.
- **If on Dedicated clusters with existing PL** → Create a separate PrivateLink Gateway for Flink in the same Azure region.
- **If doing selective extraction from a large event corpus** → Raw topic → Flink filter/projection → output topic. Always.
- **If filter logic may change** → Set raw topic retention to cover your replay window (7-30 days, or infinite with compaction for entity state).
- **If adding joins or aggregations later** → Add `sql.state-ttl` configuration. Use `STATE_TTL` hints for per-operator granularity. Monitor state size via Query Profiler.

## Caveats

- **Discrete CFU values**: The UI may constrain compute pool sizes to specific increments; the CLI and API accept arbitrary integers. Plan for the GA max of 50 CFUs per pool.
- **Statement immutability**: You cannot modify a running statement. Evolution requires stop → create new → (optionally) carry-over offsets. Carry-over offsets only work for stateless operations.
- **Schema snapshot at creation**: Running statements do not pick up source table schema changes. You must stop and recreate the statement.
- **Watermark sensitivity**: The default 180ms out-of-orderness tolerance works for most workloads. If your data has higher out-of-orderness (common with batch-uploaded historical data), define a custom watermark strategy before deploying.
- **Autopilot lag**: During initial backfill of 50M events, Autopilot will ramp up parallelism over several minutes. Expect "Messages Behind" to be elevated initially.
- **"Direct to Flink" is not a thing in CC**: Flink reads from Kafka topics only. External data must flow through Kafka Connect (or a producer) into a topic first.

---

*Validated against Confluent docs via MCP (2026-04-13). 23 claims checked, 0 corrected, 1 unverifiable.*
