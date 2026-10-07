---
title: Event-Driven z17 — CQRS Streaming Reference Architecture (Confluent + MongoDB on LinuxONE)
subtitle: Co-located command/query separation over the z17 frame, with corrected capture mechanisms and honest latency/consistency/cost models
audience: FSI architects, mainframe integration leads, Confluent/streaming platform teams
status: Reference architecture (technical) — derived and corrected from a marketing narrative
validated: 2026-08-06 against local canon (linuxone-kafka-integration [MQ Source Connector bridge], linuxone-platform-foundations [HiperSockets/SMC-D latency, Telum/Spyre], confluent-on-s390x-support-and-ifl-sizing [CP 8.2.0 s390x support]) + Confluent Canon. IBM-product mechanics (Data Gate, zDIH, IIDR CDC, CICS events, RRS 2PC) are from domain knowledge and are OUTSIDE confluent-docs — confirm with IBM before customer commit.
---

# Event-Driven z17 — CQRS Streaming Reference Architecture

**Keep the data gravity. Offload the read volume. Be honest about latency and consistency.**

This reference architecture separates commands (writes, which stay authoritative on z/OS) from
queries (reads, served from a materialized store on Linux on Z), using Confluent as the event
backbone. It co-locates the stream and the read store on the **same z17 frame** as the systems of
record to collapse the network hop to microseconds — not zero — and to shift read-serving load off
general-purpose engines.

> **Corrections applied vs. the source narrative (2026-08-06).** The thesis (CQRS read-offload,
> MQ-outbox capture, data gravity) is sound. Five mechanism/claim errors are fixed here:
> 1. **Db2 → Confluent is NOT Db2 Data Gate.** Data Gate is a Db2-target query-offload sync, not a
>    Kafka pipe. The Db2-z/OS→Kafka feeder is **log-based CDC** (IBM IIDR CDC → Kafka, or Debezium Db2).
> 2. **VSAM → Confluent is NOT zDIH.** zDIH (z *Digital* Integration Hub) is a read-side cache/API
>    layer, not a change-capture tool. VSAM capture is **IIDR CDC for VSAM** or **CICS events**.
> 3. **"Zero-network-latency" → sub-millisecond.** Co-located LPARs traverse HiperSockets (~800µs
>    p99) or SMC-D (<200µs). Low, not zero; not DRAM speed.
> 4. **"Same silicon" → same frame, different engines.** Confluent/MongoDB on **IFLs**; z/OS on **CP
>    engines**; co-located LPARs on one CEC.
> 5. **"Perfectly consistent" → eventually consistent** read model (CQRS async). Strong consistency
>    is on the command side only, within the RRS-coordinated Unit of Work.

---

## 1. Physical substrate

One z17 CEC (frame), multiple LPARs of two engine types:

```
┌───────────────────────────── IBM z17 (single CEC / frame) ─────────────────────────────┐
│                                                                                          │
│  ┌── z/OS LPAR(s) — general-purpose CP engines ──┐   ┌── Linux on Z LPAR(s) — IFLs ────┐ │
│  │  CICS · IMS · Db2 for z/OS · VSAM             │   │  Confluent Platform (CP 8.2.0+) │ │
│  │  IBM MQ (queue manager)                        │   │   brokers · Connect · SR        │ │
│  │  RRS (2PC coordinator)                         │   │  MongoDB (read model)*          │ │
│  └───────────────────┬────────────────────────────┘   └──────────────┬──────────────────┘ │
│                      │        HiperSockets / SMC-D (in-frame, sub-ms) │                    │
│                      └────────────────────────────────────────────────┘                    │
└──────────────────────────────────────────────────────────────────────────────────────────┘
  * MongoDB on s390x/LinuxONE: VERIFY current support (see §7, open items).
```

- **Engines:** Confluent and MongoDB run on **IFLs** (specialty Linux engines — no MLC); z/OS runs on
  **CP** engines. Same frame, separate LPARs, separate OS. This is the source of the cost story (§6),
  not "same silicon."
- **Transport:** in-frame LPAR-to-LPAR over **HiperSockets** (~800µs p99) or **SMC-D** (<200µs p99) —
  no external NIC, so no 5–20ms PrivateLink/physical-network hop. Sub-millisecond, not zero.
- **Confluent on s390x** is supported from **CP 8.2.0** (RPM/Docker/CFK/CMF/CLI/most connectors);
  requires a separate IBM Z software entitlement (IBM Confluent Platform for Z and LinuxONE). z/OS
  itself is **not** a Confluent runtime — Confluent lives on the Linux/IFL side.

## 2. Query side (reads) — CQRS read model

Goal: dashboard hydration, inventory checks, customer profiles **never touch CICS/Db2/VSAM**. Reads
hit a materialized store (MongoDB) kept current by CDC through Confluent.

```
Db2 for z/OS ──[IIDR CDC → Kafka, or Debezium Db2]──┐
                                                     ├─▶ Kafka (Confluent, on IFLs) ─▶ MongoDB Kafka
VSAM ──────────[IIDR CDC for VSAM, or CICS events]──┘        (Avro/SR)          Sink Connector ─▶ MongoDB
                                                                                              ▲
                                                                        read APIs query MongoDB (sub-ms)
```

**Corrected feeders:**

| Source | ❌ Narrative said | ✅ Correct capture into Kafka |
|---|---|---|
| **Db2 for z/OS** | Db2 Data Gate | **Log-based CDC** — IBM Data Replication (IIDR) CDC with a **Kafka target**, or the **Debezium Db2** connector on Kafka Connect. Log-based ⇒ no polling, low source overhead. Data Gate is a *different* tool (query-offload to a Db2 target); use it only if a Db2 read replica is the read store — it does not feed Kafka. |
| **VSAM** | zDIH | **IIDR CDC for VSAM** (via CICS VR / logstream) or **CICS events** on the VSAM update path. VSAM has no general transaction log outside CICS/RLS, so capture is constrained — scope per dataset. **zDIH** is an alternative *read store / API-offload cache*, not a capture pipe; it can complement or replace the Mongo read model, not feed it. |

- **Materialization:** the **MongoDB Kafka Sink connector** (MongoDB-provided, pure-Java) consumes the
  Avro/SR topics and upserts documents into the read model. Model documents for the query shape
  (denormalized per read use case), not per source table.
- **Consistency:** **eventually consistent.** The read model lags the SoR by the CDC + sink pipeline
  latency (typically sub-second in-frame, but non-zero). Design read APIs to tolerate bounded lag;
  where a read must be strongly consistent, route it to the SoR (the exception, not the rule).

## 3. Command side (writes) — event capture

Two capture patterns sink natively into Confluent via IBM MQ. Both use the canonical bridge:
**z/OS app → IBM MQ queue → IBM MQ Source Connector (Kafka Connect on IFLs) → Kafka topic.**

### 3.1 Domain-event capture — CICS event bindings (zero-code)

- CICS **event processing** emits a business event at a defined capture point (e.g. claim approval),
  via an external **event binding** — no COBOL/PL/I change. The **EP adapter** routes it to **WMQ**
  (or HTTP/custom), from where the MQ Source Connector lifts it into Kafka.
- **Caveats:** capture points and available data are constrained (commarea/container fields at the
  capture point); per-event overhead on the CICS region; IBM investment in CICS EP has waned — validate
  the capture set and performance envelope. "Zero-code" is real; "perfect real-time domain context" is
  aspirational.

### 3.2 Guaranteed-state capture — transactional outbox in one UOW (the strong pattern)

- The application writes the **event payload to a local MQ queue within the same Unit of Work** as the
  SoR update. On z/OS, **RRS coordinates two-phase commit** across Db2/CICS and MQ, so the event is
  enqueued **iff** the transaction commits, and rolls back with it. This eliminates dual-write drift at
  the source. ✅ This is the soundest mechanism in the design.
- **The honest caveat:** the **MQ → Kafka** hop (MQ Source Connector) is **at-least-once**. So the
  *capture* is atomic, but *end-to-end delivery* into Kafka is at-least-once — **dedupe downstream** on
  a business/idempotency key (or the SoR commit LSN). "Mathematically guaranteed alignment" holds for
  the outbox enqueue, not for exactly-once delivery to consumers.

## 4. Consistency model (stated plainly)

| Plane | Guarantee | Where |
|---|---|---|
| Command (write) | **Strong / atomic** | Within the z/OS UOW (RRS 2PC: Db2/CICS + MQ) |
| Event backbone | At-least-once (EOS available within Kafka/Flink, not across the MQ hop) | Confluent on IFLs |
| Query (read) | **Eventually consistent** | MongoDB read model, lagging by pipeline latency |

CQRS buys read scalability and z/OS offload at the cost of read-model lag. Do not sell it as "perfectly
consistent" — sell it as *strongly consistent writes + bounded-lag reads*, which is what regulators and
architects actually expect.

## 5. Latency budget

| Hop | Latency | Note |
|---|---|---|
| z/OS LPAR ↔ IFL LPAR (SMC-D) | < 200 µs p99 | In-frame shared memory |
| z/OS LPAR ↔ IFL LPAR (HiperSockets) | ~800 µs p99 (1 KB) | In-frame firmware channel |
| External NIC / PrivateLink (avoided) | 5–20 ms | The hop co-location eliminates |
| CDC + sink to read-model visibility | sub-second (in-frame), non-zero | The eventual-consistency window |

Co-location makes this viable for the sub-ms and <10 ms SLA tiers where the source is z/OS. It is **not
zero-latency** and not memory-speed; it is *sub-millisecond in-frame transport*.

## 6. Cost model (honest MLC)

- **Real win:** read-serving and stream processing run on **IFLs**, which carry **no MLC** and don't
  consume general-purpose CP capacity. Moving read volume off z/OS lowers the rolling-4-hour-average
  that drives MLC.
- **The offset:** capture is not free — **CDC (IIDR), CICS events, and MQ** all consume **z/OS CP
  cycles** on the write path; and you add **IFL, Confluent (IBM CP-for-Z entitlement), and MongoDB
  licensing**. Net effect is a **reduction** in GP consumption/MLC for read-heavy estates, **not
  elimination**. Model both sides in the business case.

## 7. Canon, security, and open items

**Confluent Canon defaults (apply on the IFL side):**
- Topics: RF 3, `min.insync.replicas=2`; naming `<domain>.<entity>.<event>`.
- Schema Registry: Avro (or Protobuf), `BACKWARD` compatibility; SR governs the CDC + event topics.
- Producers/connectors: `acks=all`, `enable.idempotence=true`, `lz4`.
- Security: **mTLS + RBAC**, service accounts per application; audit log enabled.

**FIPS / crypto (FSI):**
- FIPS 140-3 via **CEX8S + BC-FIPS** provider. **Caveat:** CP **FIPS mode is not yet supported on
  s390x** per the current support matrix — treat FIPS enablement as scoped sequencing, not a checkbox.
- **Secure Execution** (confidential computing) for LPAR isolation; **UKO/CEX8S** for key lifecycle.
- **STP/CTN** keeps audit timestamps and Flink event-time coherent across LPARs/frames.

**Open validation items (confirm before customer commit):**
1. **MongoDB on s390x/LinuxONE** — current build availability and MongoDB's support policy on Z
   (has been limited/deprecated across versions). If unsupported, the read store is a Db2 read replica
   (via Data Gate — its actual use), PostgreSQL on Z, or an off-frame store (losing the co-location win).
2. **IIDR CDC Kafka-target** licensing and z/OS source-agent footprint (Db2 and VSAM capture agents).
3. **VSAM capture feasibility per dataset** — CICS-managed vs non-CICS access determines whether
   log-based capture is even possible.
4. IBM-product mechanics here (Data Gate, zDIH, IIDR, CICS EP, RRS) are **outside confluent-docs** —
   validate against current IBM documentation with the mainframe team.

## 8. Component → tool map (corrected)

| Function | Tool | Runs on |
|---|---|---|
| Event backbone | Confluent Platform (CP 8.2.0+) | IFLs |
| Db2-z/OS change capture → Kafka | **IIDR CDC (Kafka target)** or Debezium Db2 | Connect on IFLs; capture agent on z/OS |
| VSAM change capture → Kafka | **IIDR CDC for VSAM** or **CICS events → MQ** | z/OS capture; Connect on IFLs |
| Domain-event capture (zero-code) | **CICS event bindings → WMQ → MQ Source Connector** | z/OS + Connect on IFLs |
| Guaranteed write capture | **Outbox in RRS 2PC UOW → MQ → MQ Source Connector** | z/OS + Connect on IFLs |
| Read model materialization | **MongoDB Kafka Sink connector** | Connect on IFLs |
| Read serving | MongoDB (verify Z support) — or Db2 read replica via Data Gate | IFLs |
| In-frame transport | HiperSockets / SMC-D | firmware |

---

*Derived from a marketing narrative and corrected against local FSI/LinuxONE canon + Confluent Canon on 2026-08-06. Confluent-side facts are canon-validated; IBM-product mechanisms are domain-knowledge and must be confirmed with IBM.*
