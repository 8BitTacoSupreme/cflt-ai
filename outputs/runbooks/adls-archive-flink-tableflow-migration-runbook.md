---
title: Archive Normalization & Tableflow Migration Runbook
subtitle: Introducing Flink normalization and Tableflow→Iceberg/Delta ahead of Databricks
audience: Platform / C4E, data engineering
validated: 2026-07-17 against confluent-docs (Tableflow storage/formats, CC Flink) + local canon
confidence: high
companion: adls-gen2-parquet-archive-connect-runbook.md
related-canon: concepts/tableflow-iceberg-delta.md, patterns/tableflow-changelog-mode-immutability.md, patterns/cdc-tableflow-flink-decode-required.md
---

# Archive Normalization & Tableflow Migration (Phase 3–4)

**Purpose:** Move the Parquet-on-ADLS archive from a *file layout* to a *governed table
format*, introducing Flink normalization and Tableflow→Iceberg (or Delta) as topics gain
Databricks consumers — without a backfill.

> The Connect Parquet pipeline (companion runbook) stays valid throughout. This is an
> additive path, not a rip-and-replace. The single condition that makes it a *configuration
> change* rather than a *backfill project* is that topics are already schematized —
> Tableflow requires schematized topics, which the Phase 1–2 design already guarantees.

---

## 1. Why files aren't enough (validated)

Parquet-in-a-container is a file layout, not a table: no atomic commits, no snapshot
isolation, no schema-evolution history, no time-travel. Every consumer reconstructs table
semantics independently, and concurrent readers can observe partially-written partitions.
**Confluent Tableflow** materializes Kafka topics into **Apache Iceberg or Delta Lake**
tables with schema evolution tracked as table metadata, on ADLS Gen2 (BYOS). *(Iceberg +
Delta + ADLS Gen2 BYOS all MCP-confirmed this session.)*

**Iceberg vs. Delta — pick per consumer.** The source design assumes Iceberg-read-via-Unity
Catalog. If **Databricks is the primary consumer**, **Tableflow→Delta** is more native
(Databricks reads Delta directly; Iceberg is read via Unity Catalog / UniForm). If the
reader set is heterogeneous (Trino, Spark, Synapse, Flink), Iceberg is the broader-compat
choice. Decide by consumer, not by default. See
[Tableflow: Iceberg & Delta](../../wiki/concepts/tableflow-iceberg-delta.md).

---

## 2. Why Flink — the work that has no home in Connect

Connect SMTs are **stateless and per-record**: an SMT sees one record, with no memory of
the record before and no knowledge of the one after. Several archive requirements are
inherently **cross-record** and therefore cannot be expressed in Connect at all:

- **Deduplication before archive.** Duplicates in a 7-year archive are paid for in storage,
  query cost, and every downstream reconciliation, permanently. Cross-record by definition.
- **Type reconciliation / widening across records.** Widening a field that is `int` in one
  record and `decimal` in another requires seeing both.
- **Schema drift as a stateful event.** Detecting evolution and registering a widened schema
  *before* an incompatible file is written requires state across the stream.

These are the load-bearing justification for Flink. **CC Flink is serverless** — no cluster
to provision or operate, which removes most of what the "Flink is overkill" objection reacts
to. The job is a source → normalize → sink with minimal state.

> **Correction to the source design's late-data argument.** The design claims a late record
> "lands in the wrong partition." With `timestamp.extractor=RecordField` (the Phase-1
> config), the Connect sink partitions by the record's **event_time**, so a late record
> lands in the **correct** event-time partition regardless of arrival time. The real
> Connect limitations are (a) the partition **file may already be committed**, producing
> extra small files, and (b) it has no watermark to reason about *completeness*. So the
> honest Flink justification is **dedup + type widening + drift + completeness/watermarking**
> — not "wrong partition." The architectural conclusion (build the Flink job before
> Databricks onboarding) is unchanged and correct.

**The sequencing argument is decisive.** The Tableflow/Databricks path depends on
normalized, deduplicated, correctly-partitioned streams, so the Flink job gets built
regardless. Building it *now* costs a small deployment. Building it *after* 18 months of
un-normalized Parquet accumulates costs a **backfill across the entire archive** — rewriting
history in a store whose value is immutability. The choice is *Flink now* or *Flink plus a
migration*.

---

## 3. Phase 3 — the Flink normalization job

Introduce **ahead of** the first Databricks onboarding, not after.

**Job shape (CC Flink, Table API — canon default):**
1. **Source:** the raw schematized topic(s), `scan.startup.mode = earliest-offset` for
   deterministic replay.
2. **Watermark:** `BOUNDED_OUT_OF_ORDERNESS` with a bounded lateness matched to the topic's
   observed skew (never unbounded — canon). This is what gives *completeness* semantics the
   Connect sink lacks.
3. **Deduplicate:** on the business key + event_time (e.g. Flink `ROW_NUMBER()` dedup or a
   keyed state TTL), so duplicates never reach the archive.
4. **Type-normalize / widen:** project to the unified, widened schema; register the widened
   schema in SR under `BACKWARD_TRANSITIVE` *before* emitting.
5. **Sink:** to a normalized topic (`<domain>.<app>.v1.<entity>.normalized`) that the
   archive/Tableflow consumes — or directly via `UPSERT-KAFKA` for changelog entities.

**Verify before cutover:** dedup rate > 0 as expected, no widening errors, and the
normalized topic's SR subject is `BACKWARD_TRANSITIVE`.

---

## 4. Phase 4 — enable Tableflow

Per topic, as it gains a Databricks (or other table-format) consumer:

1. Confirm the topic is schematized and normalized (Phase 3 output).
2. Choose the table format by consumer (§1): **Delta** for Databricks-native, **Iceberg**
   for heterogeneous readers.
3. Enable Tableflow on the topic, targeting the **same ADLS Gen2 account** (BYOS) as the
   Parquet archive.
4. Point the consumer at the catalog (Unity Catalog for Databricks; REST catalog for
   Iceberg readers).
5. **Leave the Parquet archive in place** for topics that do not need table semantics — the
   two coexist in the same container.

> Do **not** lifecycle-age Tableflow/Iceberg table files to the Archive access tier — that
> breaks query access to historical partitions. Scope any Archive-tier lifecycle policy to
> raw connector-landed Parquet only (consistent with
> [Archival Storage for Long-Retention Topics](../../wiki/patterns/archival-storage-long-retention-topics.md)).

---

## 5. Migration triggers (when to move a topic)

| Trigger | Action |
|---|---|
| A topic gains its first Databricks/table-format consumer | Phase 3 (if not already normalized) → Phase 4 for that topic |
| Duplicates observed in the Parquet archive | Bring Phase 3 forward — dedup is cross-record, Connect can't do it |
| Query engines disagree on the archive's schema | Phase 4 — table metadata becomes the single schema authority |
| Late/out-of-order data causing completeness disputes in audits | Phase 3 watermarking |
| Topic has no table-format consumer and no dedup/drift issues | Stay on Parquet — do not migrate speculatively |

---

## 6. Sequence summary

- **Phase 1–2 (companion runbook):** Connect → Parquet on ADLS Gen2, corrected connectors,
  `BACKWARD_TRANSITIVE`, ingest lineage, DLQ reconciliation, sink-lag alerting.
- **Phase 3 (here):** Flink normalization (watermark, dedup, type widening, drift) ahead of
  Databricks onboarding.
- **Phase 4 (here):** Tableflow→Iceberg/Delta per topic as table consumers appear; Parquet
  stays for the rest.

---

*Validated 2026-07-17 against `confluent-docs` (Tableflow storage & formats — Iceberg + Delta on
ADLS Gen2 BYOS; CC Flink serverless) and local canon (Flink SQL watermark/UPSERT-KAFKA defaults,
Tableflow articles). Companion: `adls-gen2-parquet-archive-connect-runbook.md`.*
