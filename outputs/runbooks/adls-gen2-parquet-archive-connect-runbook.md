---
title: Self-Managed Connect → ADLS Gen2 Parquet Archive — Deployment & Operations Runbook
subtitle: Avro + JSON Schema topics → time-partitioned Parquet compliance archive
audience: Platform / C4E (owners), application teams (schema owners)
validated: 2026-07-17 against confluent-docs (ADLS Gen2 Sink connector, Parquet/converter requirements, schema-evolution compatibility) + local canon (topic-naming, schema-registry-best-practices, dead-letter-queue-design)
confidence: high
companion: adls-archive-flink-tableflow-migration-runbook.md
related-canon: patterns/archival-storage-long-retention-topics.md, concepts/schema-registry-best-practices.md, patterns/dead-letter-queue-design.md, patterns/topic-naming.md
---

# Self-Managed Connect → ADLS Gen2 Parquet Archive

**Purpose:** Stand up and operate a self-managed Kafka Connect pipeline that lands
schematized Kafka topics (Avro + JSON Schema) as time-partitioned Parquet on ADLS Gen2,
serving as a long-retention (7-year OFAC/AML) compliance archive.

> **Corrections applied vs. the source design (MCP-validated 2026-07-17).** The design's
> architecture is sound; three config-level items were wrong and are fixed here:
> 1. **Connector class** — the design used the *Azure Blob Storage* Sink
>    (`io.confluent.connect.azure.blob.AzureBlobStorageSinkConnector`) but the target is
>    *ADLS Gen2*. Those are **different connectors**. ADLS Gen2 (hierarchical namespace,
>    `abfss`/dfs endpoint) requires `io.confluent.connect.azure.datalake.gen2.AzureDataLakeGen2SinkConnector`.
> 2. **Format class** — likewise `io.confluent.connect.azure.storage.format.parquet.ParquetFormat`,
>    not the `azure.blob.format...` package.
> 3. **Compatibility** — the archive-readability guarantee turns on **transitivity**, not
>    FULL-vs-BACKWARD. Non-transitive FULL is insufficient. Use **BACKWARD_TRANSITIVE**
>    minimum (see §4).

---

## 0. Prerequisites

- **Self-managed Connect cluster** (managed connectors can't take custom SMT JARs or
  arbitrary converter choices — see [Connect deployment models](../../wiki/concepts/kafka-connect-deployment-models.md)).
- **Every topic in scope carries a registered schema** — Avro natively, JSON via JSON
  Schema. There is **no schemaless-JSON path**: `ParquetFormat` requires a Connect
  `Schema`, and the plain `JsonConverter` (schemaless) throws `NullPointerException` /
  `StackOverflowError`. Only `AvroConverter`, `ProtobufConverter`, or `JsonSchemaConverter`
  work. *(MCP-confirmed.)*
- ADLS Gen2 storage account with **hierarchical namespace enabled**, and a service
  principal / managed identity with write access to the target container.
- Schema Registry reachable from Connect workers.

---

## 1. Two connectors, one container — why

`value.converter` is a **connector-level** property, evaluated **before any SMT runs**. A
single connector cannot deserialize Avro on one topic and JSON Schema on another; no
transform can intervene, because by the time an SMT sees the record, deserialization has
already happened (or already failed). So the pipeline is **two connector configs writing
to the same ADLS container** — which also buys independent scaling, independent DLQs, and
the ability to migrate JSON topics to Avro one at a time without touching the Avro path.
*(Validated — this reasoning is correct.)*

---

## 2. Connector A — Avro topics

```properties
name                                = adls-archive-avro
# CORRECTED: ADLS Gen2 Sink, not the Azure Blob Storage Sink.
connector.class                     = io.confluent.connect.azure.datalake.gen2.AzureDataLakeGen2SinkConnector
tasks.max                           = 4

# Route by an explicit topic list in GitOps, NOT by a format token in the topic name.
# (Canon topic naming is {domain}.{application}.{version}.{entity} — there is no
#  serialization-format segment. Encoding `.avro.` in the name breaks prefix-RBAC and
#  fossilizes the wire format into the topic identity. See §7.)
topics                              = payments.fraud.v1.alerts,corebanking.txn.v1.postings

key.converter                       = org.apache.kafka.connect.storage.StringConverter
value.converter                     = io.confluent.connect.avro.AvroConverter
value.converter.schema.registry.url = https://<schema-registry>
value.converter.auto.register.schemas = false     # prod: never auto-register from a client

# CORRECTED format package.
format.class                        = io.confluent.connect.azure.storage.format.parquet.ParquetFormat
parquet.codec                       = snappy

# In-file schema handling — DISTINCT from Schema Registry subject compatibility (§4).
# Controls how the connector projects records to a common file schema and when it rotates
# a file on a schema change. Leaving this at the NONE default rotates a new file on every
# schema variation and can fail to unify records. BACKWARD lets the writer project older
# records forward into the current file schema.
schema.compatibility                = BACKWARD

partitioner.class                   = io.confluent.connect.storage.partitioner.TimeBasedPartitioner
path.format                         = 'yyyy'=YYYY/'MM'=MM/'dd'=dd/'HH'=HH
partition.duration.ms               = 3600000
timestamp.extractor                 = RecordField
timestamp.field                     = event_time      # SEE §5 — single point of silent loss
locale                              = en-US
timezone                            = UTC

flush.size                          = 100000
rotate.interval.ms                  = 3600000          # event-time driven
# ADDED: wall-clock safety. Without this, a low-volume topic whose event-time clock
# never advances leaves a partially-filled file OPEN indefinitely — data sits in the
# connector, not the archive, and nothing errors. This closes files on wall-clock time.
rotate.schedule.interval.ms         = 3600000

# See §6 before accepting errors.tolerance=all on a compliance archive.
errors.tolerance                    = all
errors.deadletterqueue.topic.name   = dlq.adls-archive-avro
errors.deadletterqueue.context.headers.enable = true
errors.deadletterqueue.topic.replication.factor = 3
```

## 3. Connector B — JSON Schema topics

Identical except the converter (and the topic list). The Parquet writer consumes a
Connect `Schema` and neither knows nor cares which converter produced it.

```properties
name                                = adls-archive-json
connector.class                     = io.confluent.connect.azure.datalake.gen2.AzureDataLakeGen2SinkConnector
topics                              = channels.web.v1.events,partner.api.v1.requests
value.converter                     = io.confluent.connect.json.JsonSchemaConverter   # NOT org.apache.kafka.connect.json.JsonConverter
value.converter.schema.registry.url = https://<schema-registry>
# format.class, schema.compatibility, partitioner, flush/rotate, and DLQ identical to Connector A.
```

**Type-fidelity gate (compliance-critical).** JSON Schema has a narrower type system than
Avro. `decimal` and `timestamp-micros` survive Avro cleanly but can arrive as **string or
double** from JSON Schema. A decimal silently landing as a double is a compliance defect
that surfaces years later. **Pin these in the JSON Schema definitions and validate the
resulting Parquet column types before go-live** (§8 step 4).

---

## 4. Schema Registry governance

**Compatibility — the essential property is _TRANSITIVE, not FULL.** A current reader must
read data written by *every* historical schema. That is guaranteed by transitivity:

- **`BACKWARD_TRANSITIVE` — the minimum.** New schema can read data from **all** prior
  versions. *(MCP-confirmed: non-transitive BACKWARD checks only the immediately previous
  version, so a chain of individually-BACKWARD changes can drift until the current schema
  cannot read a very old one.)*
- **Non-transitive `FULL` is NOT sufficient** — it too checks only the previous version.
  The source design's "FULL or FULL_TRANSITIVE" is wrong to offer plain FULL.
- **`FULL_TRANSITIVE`** — stricter superset (adds forward-transitive). Use it if
  heterogeneous readers (Spark, Trino, Databricks) each pin different schema versions;
  otherwise `BACKWARD_TRANSITIVE` is enough and less restrictive on producer evolution.

Set it per subject: `confluent schema-registry compatibility update --level BACKWARD_TRANSITIVE --subject <topic>-value`.
(Canon: BACKWARD default, escalate to FULL for shared contracts, **_TRANSITIVE for
long-lived/widely-shared** — an archive is exactly that. See
[Schema Registry Best Practices](../../wiki/concepts/schema-registry-best-practices.md).)

- **No forward-only evolution.** FORWARD alone (old reader reads new data) does not
  guarantee a new reader reads old data — wrong direction for an archive. Correct.
- **`auto.register.schemas=false` in prod.** Register in CI; fail the build on
  incompatibility.
- **Subject naming:** `TopicNameStrategy` default; `TopicRecordNameStrategy` when multiple
  event types share a topic.

---

## 5. The `timestamp.field=event_time` risk

`timestamp.extractor=RecordField` reads the partition timestamp from `event_time` on every
record. If a subject's schema lacks `event_time`, or a record's `event_time` is null, the
record **fails extraction → routes to the DLQ → and under `errors.tolerance=all` is
silently absent from the archive.** For a system-of-record this is silent data loss.

**Mitigations:**
1. Make `event_time` a **required, non-null** field in every archived subject's schema
   (enforce in the CI compatibility check).
2. Reconcile the DLQ (§6) — a spike of extraction failures there is your only signal.
3. Note the design's later Flink phase (companion runbook) is where event-time correctness
   is *properly* enforced with watermarking.

---

## 6. DLQ reconciliation — `errors.tolerance=all` on an archive

`errors.tolerance=all` means conversion/transform failures are routed to the DLQ and the
task keeps running — the record is **not** in the archive and **nothing errors**. On a
compliance archive, an **unreconciled DLQ is a silent gap in the system of record.**

**Decide explicitly:**
- **`errors.tolerance=all` + mandatory DLQ reconciliation** (this runbook's default):
  every DLQ record must be triaged and replayed or formally written off. Alert on DLQ
  ingress rate > 0. See [Dead Letter Queue Design](../../wiki/patterns/dead-letter-queue-design.md).
- **`errors.tolerance=none`** — fail the task loudly on the first bad record. Appropriate
  for the strictest archives where a gap is unacceptable and a paused connector is
  preferable to silent loss. Trade-off: one poison record halts the pipeline.

**DLQ monitoring (mandatory either way):**
```
# Alert if anything lands in either DLQ — on an archive, DLQ ingress > 0 is an incident.
kafka-run-class kafka.tools.GetOffsetShell --broker-list <b> --topic dlq.adls-archive-avro
```
Reconcile: read the DLQ, inspect `errors.deadletterqueue.context.headers` (original topic,
partition, offset, exception), fix the schema/record, and replay into the source topic (or
a dedicated replay topic) so it lands in the archive.

---

## 7. Topic routing (canon)

The source design routes with `topics.regex = .*\.avro\..*` / `.*\.json\..*`, which
assumes a serialization-format token in the topic name. **Canon topic naming is
`{domain}.{application}.{version}.{entity}` — no format segment** (see
[Topic Naming](../../wiki/patterns/topic-naming.md)). Encoding `.avro.`/`.json.`:
- breaks **prefix-RBAC** (`payments.fraud.*` no longer groups a domain), and
- fossilizes the wire format into the topic identity, so migrating a topic Avro→JSON (or
  the reverse) requires renaming the topic.

**Use explicit `topics` lists per connector, maintained in GitOps.** The converter, not the
name, determines the deserialization path; keep that mapping in the connector config, not
in the topic name.

---

## 8. Deploy & validate (Phase 1–2)

1. **Register schemas** for all in-scope subjects in CI; set `BACKWARD_TRANSITIVE`.
2. **Deploy Connector A and B** with the corrected classes, explicit topic lists, DLQ, and
   `rotate.schedule.interval.ms`.
3. **Confirm files land** under `.../yyyy=/MM=/dd=/HH=/` and that partition paths match
   **event time**, not ingest time.
4. **Validate Parquet column types against source schemas** — pull a sample with
   `parquet-tools schema <file>` and confirm decimals are `decimal`/`fixed_len_byte_array`,
   not `double`, and timestamps are `timestamp` logical types. This is the JSON-Schema
   fidelity gate; do not declare production-ready until it passes.
5. **Turn on monitoring:** sink-lag per connector, DLQ ingress rate, task state.
6. **Add ingest-lineage SMT** on day one (§9) — retrofitting provenance means rewriting an
   immutable archive.

---

## 9. Transform chain (thin, stock — no custom SMT needed)

Because converters recover the schema, the SMT chain is routing/metadata/hygiene only:

| Transform | Purpose |
|---|---|
| `SetSchemaMetadata` | Stable schema name → consistent Parquet/Iceberg identity across topics |
| `InsertField` | Ingest lineage: Kafka topic, partition, offset, ingest timestamp (audit trail) |
| `MaskField` | Redact restricted fields **before** write — the archive is immutable once landed |
| `TimestampConverter` | Normalize time representations, only if they differ across topics |

Add ingest-lineage fields **on day one**: once Parquet is in the compliance archive,
adding provenance later means rewriting history — the one thing an immutable archive
forbids.

---

## 10. Monitoring & operations

- **Sink lag.** A stalled connector breaks the archive **silently** — nothing errors, data
  just stops arriving. Alert on per-connector consumer lag and on task state != RUNNING.
- **DLQ ingress > 0** — incident on an archive (§6).
- **File-close latency.** With `rotate.schedule.interval.ms` set, files close on wall clock;
  alert if the newest object in a partition is older than ~2× the rotate interval.
- **Parquet type drift.** Periodically re-run step 8.4 against fresh files — a producer
  schema change can flip a column type between deploys.

---

*Validated 2026-07-17 against `confluent-docs` (Azure Data Lake Storage Gen2 Sink connector
overview/config, ParquetFormat converter requirements, schema-evolution compatibility) and local
canon. Connector property names follow the ADLS Gen2 Sink; verify against your deployed connector
version before applying. Managed-service complement: [Archival Storage for Long-Retention Topics](../../wiki/patterns/archival-storage-long-retention-topics.md).
Forward path: `adls-archive-flink-tableflow-migration-runbook.md`.*
