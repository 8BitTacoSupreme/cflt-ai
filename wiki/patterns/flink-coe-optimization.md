---
title: Flink COE — Optimization (CFUs, Autopilot, State, Statement Lifecycle)
tags: [flink, confluent-cloud, coe, optimization, cfu, autopilot, state-ttl, watermarks, stub]
sources:
  - https://docs.confluent.io/cloud/current/flink/concepts/compute-pools.html
  - https://docs.confluent.io/cloud/current/flink/concepts/autopilot.html
  - outputs/reports/flink-confluent-cloud-setup-privatelink-architecture.md
related: [patterns/flink-coe-managed-cc-overview, patterns/flink-runtime-models, concepts/flink-checkpointing]
confidence: low
last_updated: 2026-07-30
last_validated: 2026-07-30
---

# Flink COE — Optimization (CFUs, Autopilot, State, Statement Lifecycle)

> ⚠️ Stub — seeded with validated facts; expand per use case once chosen. Deep tuning + triage already lives in [Flink Runtime Models](flink-runtime-models.md); this page is the CC-specific cost/scale layer.

## Summary

<!-- Used verbatim in _index.md -->
Optimization sub-page for the [Flink COE](flink-coe-managed-cc-overview.md). On Managed Flink CC you don't tune parallelism, checkpoints, or state backends — Autopilot and the serverless runtime own those. What you *do* control: CFU pool sizing, state growth (TTL), watermark tolerance, and statement lifecycle. Cost is driven by **throughput rate and state size**, not event count.

## Pattern

### CFU sizing & Autopilot (seed — validate before production commit)

- **`max_cfu` can be increased but never decreased.** GA ceiling **50 CFU/pool** (1,000 in Limited Availability). Size to realistic peak. Pools **scale to zero when idle** — no cost at rest.
- **CFU burn ∝ throughput rate × state size**, not total event count — e.g. 50M events at hundreds–low-thousands ev/s settle at ~1–3 CFU via Autopilot.
- **Autopilot** handles autoscaling/parallelism inside the pool — no manual parallelism knob. It ramps over several minutes on backfill; watch the **"Messages Behind"** metric (spikes, then converges to 0).
- Sizing defaults: **5–10 dev / 10–20 staging / 20–50 prod** (`fsi-dsp:modules/flink` hard-validates `max_cfu ∈ {5,10,20,30,40,50}`). Pool exhaustion → statements stuck `PENDING`. One pool per team/env boundary.

### State & watermarks (the cost blow-up)

- **`sql.state-ttl` on every non-windowed stateful op** — unbounded regular joins and non-windowed aggregations keep state forever otherwise (#1 CFU blow-up + OOM). Prefer interval / temporal / lookup joins (bounded by construction). Pure filter/projection is stateless — no TTL needed.
- State limits per statement: **500 GB soft / 1 TB hard**.
- Default watermark = **180 ms** bounded out-of-orderness on `$rowtime`. **Retune for batch-loaded/historical data** (high out-of-orderness) or windows never fire. Set idleness timeout (`sql.tables.scan.idle-timeout`) so a quiet partition doesn't stall the global watermark.

### Statement lifecycle (immutability drives your deploy model)

- **Statements are immutable** — SQL can't be edited after submit. Name ≤ 72 chars, query ≤ 4 MB. Stopped statements retained 30 days.
- **Statements snapshot their catalog objects at creation** — source schema/watermark changes do **not** propagate to a running statement. To evolve: **stop old → create new.**
- **Stateless carry-over offsets:** `SET 'sql.tables.initial-offset-from' = '<old-statement-name>';` lets a new stateless (filter/projection) statement resume from the old one's offsets (waits up to 6h for the old to stop). **Not valid** for aggregations/windows/pattern-match/upsert sinks.
- **OSS→CC config name mapping** (subset): `sql.state-ttl` = `table.exec.state.ttl`; `sql.tables.scan.startup.mode` = `scan.startup.mode`; `sql.tables.scan.idle-timeout` = `table.exec.source.idle-timeout`. Don't assume OSS option names work.

## Caveats

- Checkpoint interval / state backend / storage are **not user-configurable** on CC (they are on CMF). If you need to tune them → CMF, not CC.
- <!-- TODO: add per-use-case tuning (CDC, aggregation, fraud scoring) once the adopting team picks workloads -->

## Related

- [Flink COE — Overview](flink-coe-managed-cc-overview.md)
- [Flink Runtime Models](flink-runtime-models.md) — the full optimization + triage table (backpressure, windows-never-fire, Kryo, PENDING)
- [Flink Checkpointing](../concepts/flink-checkpointing.md) — mechanics (mostly relevant to CMF)
