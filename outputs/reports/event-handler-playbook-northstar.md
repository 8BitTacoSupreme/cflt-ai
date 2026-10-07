---
title: "Event Handler Design Patterns on Confluent Cloud"
subtitle: "A practice playbook for building, proving, and shipping real-time data services"
type: playbook
version: "1.0"
status: normative
created: 2026-08-11
companion_to: event-handler-patterns-playbook-deck.md
validated_against: [confluent-docs MCP, wiki/patterns, wiki/concepts]
---

# Event Handler Design Patterns on Confluent Cloud

> **What this is.** The reference document behind the deck of the same name. The deck is for a
> room; this is for a Tuesday afternoon when someone is writing a handler and needs to know what
> we do here. It is **normative** — it states defaults, not options. Where a default is wrong for
> your case, override it and write down why.
>
> **What this is not.** A Kafka tutorial, an API reference, or a substitute for Confluent's
> documentation. It assumes you can already write a producer.
>
> **How to use it.** §2 picks your substrate. §3–§6 are the pattern catalog — read the two or
> three that apply. §7–§10 are the lifecycle: build, prove, ship, run. §11 is the reference
> section you'll actually keep open: config baselines, the handler review checklist, and the
> maturity scorecard.

---

## Contents

| § | Section | Read it when |
|---|---|---|
| 1 | [Why this exists](#1-why-this-exists) | Once |
| 2 | [What an event handler is, and where to put it](#2-what-an-event-handler-is-and-where-to-put-it) | Starting any new handler |
| 3 | [Contracts: schema, key, time](#3-contracts-schema-key-time) | Before writing code |
| 4 | [Delivery semantics](#4-delivery-semantics) | Before writing code |
| 5 | [Structural patterns](#5-structural-patterns) | Choosing a shape |
| 6 | [Resilience patterns](#6-resilience-patterns) | Always — §6.1 is not optional |
| 7 | [Development](#7-development) | Setting up a repo |
| 8 | [Testing](#8-testing) | Setting up CI |
| 9 | [Deployment](#9-deployment) | First ship, and every ship after |
| 10 | [Run](#10-run) | Handing to on-call |
| 11 | [Reference](#11-reference) | Constantly |
| 12 | [What this playbook doesn't cover yet](#12-what-this-playbook-doesnt-cover-yet) | Before you trust it blindly |

---

## 1. Why this exists

We keep paying for the same six failures. They are not novel and they are not hard; they are
simply nobody's job until they are everybody's incident.

| # | The failure | Answered in |
|---|---|---|
| 1 | A poison pill takes down a partition at 2am and no one owns the DLQ | §6.1, §6.2 |
| 2 | A handler is "exactly once" in the design doc and at-least-once in production | §4 |
| 3 | A rebalance storm on every deploy, because nobody set static membership | §7.3, §9.3 |
| 4 | A schema change ships fine and breaks a consumer three teams downstream | §3.1, §8.3 |
| 5 | A replay you needed became an incident, because nothing was idempotent | §6.3 |
| 6 | A rolling restart took forty minutes, because nobody sized the state | §5.3, §10.3 |

The broker is a solved problem. Confluent Cloud runs it. What is *not* solved — what this
playbook is about — is the code between two topics.

**The single most useful sentence in this document:** a handler you cannot replay, cannot test
without a cluster, and cannot roll back is not a service. It is an outage with a deployment
pipeline.

---

## 2. What an event handler is, and where to put it

### 2.1 Definition

> **An event handler is the smallest unit of business logic with a topic on either side.**

Consume → decide → produce. That is the whole scope.

**In scope:** the logic that reads an event, makes a decision, and emits a result or effect.

**Out of scope as handlers, in scope as ingress/egress:** connectors. Kafka Connect moves data
across the system boundary. It is not where business decisions live. A Single Message Transform
doing a field rename is fine; an SMT encoding a business rule is a handler in the wrong place.

**Also out of scope:** API gateways, batch jobs, and anything whose trigger is a clock rather
than an event.

### 2.2 The anatomy every handler shares

Nine parts. If yours is missing three of them, that is the finding — not a style preference.

```
   source topic
        │
        ▼
 1  deserialize + validate ──────── schema failure ──────► dlq topic
        │
        ▼
 2  idempotency guard ───────────── already seen ────────► drop and count
        │
        ▼
 3  business logic ◄──────────────► 4  handler state
        │
        ▼
 5  classify outcome
        ├── success ──────► 6  serialize + propagate headers ──► sink topic
        ├── transient ────► 7  retry topic
        ├── semantic reject ──────────────────────────────► rejects topic
        └── poison ───────────────────────────────────────► dlq topic
                                       │
                          8  metrics  9  trace propagation
```

The template repo (§7.1) pre-wires all nine. Deviating from this shape requires an ADR, because
every part that goes missing shows up later as one of the six failures in §1.

**The part that determines everything downstream is #3's side effect.** If the handler's effect
is confined to Kafka, you have options. If it reaches an external system, §4 constrains you and
there is no configuration that changes that.

### 2.3 The five substrates

Confluent Cloud gives you five places to put handler logic. This is a design decision, not a
language preference.

| Substrate | Use it for | Disqualifier |
|---|---|---|
| **Flink SQL / Table API** | Stateless and windowed logic expressible declaratively; serverless, nothing to operate | Logic not expressible in SQL |
| **Kafka Streams** | Stateful JVM logic, exactly-once v2, embedded state stores | Team doesn't want to operate a JVM service |
| **Consumer / producer client** | Full control, non-JVM languages, custom effects | You are reimplementing Kafka Streams badly |
| **Share group worker** (KIP-932) | Competing consumers, per-record acknowledgement, parallelism **above** partition count | Per-key ordering or exactly-once required — neither is available |
| **Connect + SMT** | Ingress and egress only | Any real business decision |

### 2.4 Choosing — five questions

Answer in order. The first disqualifying answer decides it.

1. **Is the effect purely writing to an external system?** → Managed Connect sink. Stop.
2. **Does it need state across events?** No → Flink SQL if expressible; otherwise a client.
3. **Does per-key ordering matter?** Yes → consumer group. **Never a share group.**
4. **Is exactly-once required, and is the effect inside Kafka?** Yes to both → Kafka Streams
   (`exactly_once_v2`) or Flink. Yes to the first and no to the second → see §4; EOS won't help.
5. **Who operates it?** Platform-operated → prefer Flink. App-team-operated → Streams or client.

### 2.5 Share groups, stated properly

Share groups reached general availability in Apache Kafka 4.2.0 (February 2026) and are **GA on
Confluent Cloud**. They are the most significant addition to the substrate menu in years and they
are routinely misapplied, so read this whole subsection before using them.

**What changes.** In a classic consumer group, a partition is owned by at most one consumer, so
parallelism is capped by partition count and one slow record blocks its partition. A share group
moves acknowledgement from offset-based (per partition) to **record-based (per message)**.
Multiple consumers cooperatively read the same partitions, each record is individually
acknowledged, and redelivery and poison-message rejection become native.

**What that buys you.**
- Consumer parallelism decoupled from partition count — you can run more consumers than partitions
- Competing-consumer work distribution without partition affinity
- No head-of-line blocking from a single slow record

**What it costs you — non-negotiable.**
- **At-least-once only.** There is no exactly-once path. Design an idempotent handler (§6.3).
- **No per-key ordering.** Records for the same key can be processed concurrently and out of order.

**Therefore:** share groups are a **work-distribution** substrate, not a state-machine substrate.
Use them for independent units of work — enrichment lookups, notification fan-out, document
processing. Never for ordered state transitions on an entity.

*Backing: `wiki/concepts/queues-for-kafka-share-groups.md` — confidence high, MCP-validated
2026-06-09 against the CP Share Consumers documentation and the Apache Kafka 4.2.0 release.*

---

## 3. Contracts: schema, key, time

Three decisions made before the first line of code, all three of which surface months later as
incidents.

### 3.1 Schema — the contract is the API

**Defaults:**

| Decision | Default | Escalate when |
|---|---|---|
| Format | Avro or Protobuf | JSON Schema for prototype/debug only — never production |
| Subject naming | `TopicNameStrategy` | `RecordNameStrategy` for event-union patterns |
| Compatibility | `BACKWARD` | `FULL` for shared consumer contracts |
| Where declared | In git, per topic | Never set only in the console |
| When checked | CI, on every commit | Never first at deploy time |

**The thing everyone gets wrong.** Compatibility checking is **syntactic**. It verifies that a
schema can be read by a reader of another version. It cannot see meaning. All three of these pass
`BACKWARD` cleanly and all three break downstream consumers:

- A field is reused with a new meaning
- An enum gains a value that consumers `switch` on
- A nullable field that consumers assumed was always populated starts arriving null

If §1's failure #4 keeps happening despite a green compatibility gate, this is why. The fix is
not a stricter compatibility mode — it is **Data Contracts** (rules and migration rules), which
push semantic validation left of the handler, plus consumers declaring the subject *and version*
they read. Treat the compatibility gate as necessary and insufficient.

**Codegen from the schema. Never hand-write the record class.**

### 3.2 Key — the key is the ordering domain

Kafka guarantees ordering within a partition. The key selects the partition. Therefore:

> **Choose the key for the aggregate whose ordering you need to preserve — not for even
> distribution.**

If ordering per customer matters, key by customer. If that produces a hot partition, you have a
capacity problem to solve, not a key to change. Changing the key to smooth the distribution
silently discards the ordering guarantee, and nothing will tell you.

Where no ordering is required at all, say so explicitly in the service manifest, and consider a
share group (§2.5).

### 3.3 Topic naming

```
{domain}.{application}.{version}.{entity}
```

Example: `corebanking.payments.v1.transaction`

| Segment | Regex | Example |
|---|---|---|
| domain | `^[a-z][a-z0-9-]{1,30}$` | `corebanking` |
| application | `^[a-z][a-z0-9-]{1,30}$` | `payments` |
| version | `^v[0-9]+$` | `v1` |
| entity | `^[a-z][a-z0-9-]{1,30}$` | `transaction` |

**Version sits third, before entity, deliberately.** It keeps prefix-based RBAC (`corebanking.*`)
stable across a versioned migration, and it makes dual-version operation discoverable. A breaking
contract change means a new versioned topic (`v2`) running alongside `v1` during migration — the
version segment is what makes that explicit rather than archaeological.

Enforced in Terraform variable validation and a CI pre-check. Not in a wiki page.

Avro namespaces follow `org.fsi.{domain}.{application}.{version}`.

*Backing: `wiki/patterns/topic-naming.md`.*

### 3.4 Time — event time or nothing

> **Processing time is a bug you haven't noticed yet.**

A handler that uses processing time produces different results on replay than it did live, which
means you can never reproduce an incident and never trust a backfill.

**Defaults:**
- Event time, always, sourced from the event, not the broker append time
- Watermarks with `BOUNDED_OUT_OF_ORDERNESS` and a **bounded** delay. Never unbounded.
- Lateness policy declared explicitly per handler
- Window preference by cost: tumbling > hopping > session

**Where late data goes** is a product decision, not a config default. Three legitimate answers:
a side output topic, a correction event, or dropped-and-counted. **Silently dropped is not one of
them** — if you drop, you emit a metric, and someone reviews it.

Flink's watermark strategy and Kafka Streams' grace period are the same concept with different
knobs. Set both deliberately.

---

## 4. Delivery semantics

> **At-least-once plus an idempotent sink beats exactly-once for most handlers, and costs less.**

### 4.1 The boundary that governs everything

Transactional exactly-once in Kafka covers a read–process–write cycle **within one cluster**. It
does not and cannot extend past that.

> **Any effect on an external system is at-least-once. Always. Regardless of what
> `processing.guarantee` is set to.**

A handler that calls a payment API, writes to a database, or sends a notification has an effect
outside the transaction. The transaction can be rolled back; the payment cannot. This is §1's
failure #2 in one sentence, and no configuration fixes it — only an idempotent effect does (§6.3).

### 4.2 Choosing

```
Is the sink idempotent, or does it have a natural dedup key?
├── Yes ──► at-least-once + idempotent write
└── No
     └── Is the effect inside Kafka? (read-process-write, one cluster)
          ├── No — external system ──► at-least-once + explicit dedup store
          │                            EOS cannot cross this boundary
          └── Yes
               └── Handler owns durable state, OR duplicate is visible
                   to a customer or a ledger?
                    ├── Yes ──► transactional EOS (exactly_once_v2)
                    └── No  ──► at-least-once + idempotent write
```

Record the choice **per handler in the service manifest.** A delivery guarantee that lives only
in someone's memory is not a guarantee.

### 4.3 The cost of EOS

Exactly-once is a latency and throughput tax — transaction coordination, more round trips, larger
commit intervals. Pay it where money moves and where a regulator will ask. Don't pay it uniformly
because it sounds safer.

### 4.4 FSI overlay

In regulated contexts, the delivery guarantee is a compliance artifact, not just an engineering
choice:

- State the guarantee per handler in terms the regulator uses — "no duplicate postings to the
  ledger" beats "`exactly_once_v2`"
- Reconciliation-tier flows (async) can almost always take at-least-once with a dedup key, and
  should, because the EOS tax buys nothing there
- Where EOS *is* used, the boundary in §4.1 must be documented, because the external-effect gap
  is precisely what an auditor will probe

*Backing: `wiki/concepts/exactly-once-semantics.md`, `wiki/patterns/fsi-exactly-once.md`.*

---

## 5. Structural patterns

Fourteen patterns on two axes: how much state, how many streams. Operational cost rises along the
diagonal from stateless-single-stream to stateful-joined — see §11.4 for what that costs.

### 5.1 Stateless: transform, filter, route

> If it is stateless and single-stream, it should be Flink SQL and it should be boring.

Covers content-based routing, splitting, normalization, and masking/tokenization at the edge.
Cost is parallelism × throughput and nothing else — the cheapest thing you can run.

**Anti-pattern:** a JVM microservice, with a deployment pipeline and an on-call rotation, doing a
three-line projection.

### 5.2 Raw → derived topology

**Never filter or fan out in the producer.** Land the raw event verbatim; derive views downstream.

```
producer ──► raw.{domain}.{app}.v1.{entity}   (ground truth, wire format unchanged)
                        │
                        ▼
              Flink SQL statement  (filter · project · split · lookup join)
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
      derived...settlement   derived...exposure
              │                   │
              ▼                   ▼
         handler A            handler B
```

Three load-bearing reasons:
1. **Replayability** — derived topics are reproducible by re-running the statement from
   `scan.startup.mode = 'earliest-offset'`
2. **Schema decoupling** — consumers don't share a schema with whatever the producer emits
3. **Debuggability** — the raw topic survives as ground truth after the routing logic changes

The counter-pattern this displaces is producer-side filtering, Connect SMT routing, and Debezium
predicates. Convenient for one consumer; corrosive at three.

*Backing: `wiki/patterns/flink-event-routing.md`.*

### 5.3 Stateful: aggregate and window

> State is the thing you have to migrate, back up, and reason about at 3am.

**Sizing state is a capacity planning exercise you do before you write the SQL**, not a thing you
discover in production.

Three places state can live, three failure modes:

| Where | What you get | What it costs |
|---|---|---|
| Kafka Streams state store | RocksDB + changelog topic, local reads | **Restore time is your real RTO and your real deploy time** |
| Flink managed state | Checkpointed, serverless, no ops | Non-deterministic UDFs break replay determinism |
| External store | Simple to start | Becomes the bottleneck, and you reinvent a changelog |

Retention vs. grace vs. TTL are three different clocks. Set all three explicitly.

**Standby replicas trade cost for restore time.** That is a §11.4 cost decision made in advance,
not an ops decision made during an incident.

### 5.4 Enrichment and joins

Three ways to enrich; only one of them is free.

| Approach | Use when | Watch for |
|---|---|---|
| **Stream–table join** (KTable / Flink lookup on a compacted topic) | Default. The reference data is or can be a Kafka topic | Compaction lag on the table side |
| **Temporal / versioned join** | Point-in-time correctness required — pricing, FX, entitlements | Holds *both* sides in state; costs accordingly |
| **External lookup + bounded cache** | Escape hatch only | **Circuit-break it or it becomes your SLO.** An uncached miss storm will take the handler down |

For anything regulated, temporal joins are usually not optional: "what was the rate *at the time
of the trade*" is a different question from "what is the rate."

### 5.5 Orchestration: saga / process manager

Multi-step business processes need an **explicit state machine**, not a chain of handlers each
knowing a little about the next.

Requirements:
- Every non-terminal state has a **timeout** and a **compensating action**
- Terminal states are enumerated and exhaustive
- The state machine is a first-class artifact in the repo and **gets its own tests**

A saga implemented as an implicit chain of topics is a distributed system with no owner and no
diagram. When it breaks, nobody can say what state anything is in.

### 5.6 Request–reply over Kafka

Legal, occasionally correct, usually the wrong instinct — but codify it so it gets done once,
well, rather than five times badly.

- Correlation ID on the request; reply-to topic in a header
- Consumer-side filtering on the correlation ID
- A **hard client timeout**, always
- Prefer `202 Accepted` + polling, or server-sent completion, over holding an HTTP thread open

If you find yourself building this more than twice, the question is whether the interaction is
actually synchronous and belongs in an API.

---

## 6. Resilience patterns

### 6.1 Error taxonomy — three classes, three destinations

Everything else is guessing. Classify before you route.

| Class | Meaning | Destination | Owner |
|---|---|---|---|
| **Transient** | Will probably succeed later — timeout, throttle, downstream 503 | Tiered retry topics | Platform |
| **Poison / schema** | Will never succeed — malformed, undeserializable, contract violation | DLQ, with original bytes | Platform + producer team |
| **Semantic reject** | Processed correctly; the answer is "no" — failed a business rule | Rejects topic | **Product** |

The third row is the one teams miss. A payment that fails a limit check is not an error. It is an
outcome, and something downstream — a customer notification, a case queue — wants it. Routing it
to the DLQ buries a product event in an ops channel.

**The retry ladder.** Climb only as far as the failure profile demands:

```
1. Simple            source → handler → dlq
2. Retry + DLQ       source → handler (N in-process retries) → dlq
3. Multi-level       source → retry.5s → retry.1m → retry.15m → dlq   (non-blocking)
4. Categorised       classify, then route: retriable → ladder, non-retriable → dlq
```

Attempt count travels in a header. Delay consumers **wait and re-publish to the handler's input
topic** — they do not execute business logic. The handler stays the only place logic runs.

**Know which rungs you get free before building any of it:**
- Managed sink connectors auto-generate a DLQ topic
- Confluent Cloud for Apache Flink routes source deserialization failures to a DLQ table via the
  `error-handling.mode` table property

Build only what those two don't cover.

*Backing: `wiki/patterns/dead-letter-queue-design.md`.*

### 6.2 The DLQ is a product with an owner

> A DLQ you cannot replay from is a landfill.

Non-negotiable, for every DLQ:

- [ ] A **named owner** — a person, not a team alias
- [ ] An **SLO** — how long a message may sit before someone looks
- [ ] A **replay tool** that exists and has been run at least once
- [ ] **Full original bytes** preserved, plus failure context in headers (exception class,
      timestamp, source offset, attempt count)
- [ ] A **depth alert** and a rate alert

Preserving the original bytes matters more than it sounds: if you DLQ the *deserialized* form, a
schema-failure message cannot be written at all, and you lose exactly the messages you most need.

A quarantine topic (held pending human decision) is not a DLQ (failed and needs remediation).
Don't merge them.

### 6.3 Idempotency and dedup

> Design the handler so that replaying the topic is a non-event.

This is the single highest-leverage property a handler can have. It makes replay routine, makes
at-least-once sufficient (§4), and turns a class of incidents into a shrug.

**Dedup key, in preference order:**
1. **Natural business key** — order ID, transaction reference. Best: meaningful, stable, and
   already in the payload.
2. **Synthetic event ID** — assigned by the producer. Works, but only as reliable as the producer.
3. **Hash of the payload** — last resort. Breaks on any non-semantic change (field reorder,
   timestamp precision).

**Size the dedup window to your worst-case replay, not your happy path.** A 5-minute window is
useless when the replay you actually need is 3 days.

Producers: `enable.idempotence=true` always. That solves producer-side retry duplicates only —
it does not make your *handler* idempotent.

### 6.4 Claim check — large payloads

> Kafka is not a file system. Put the pointer on the topic.

- Payload to object storage; the event carries a **reference + checksum + size**
- **The object store's retention policy must outlive the topic's retention.** Get this backwards
  and replay produces dangling pointers.
- Governs blast radius on both throughput and cost

**Open item:** the threshold at which you reach for this is the max message size for your cluster
type. Confirm it for your target tier and record it here — it was not confirmable from the Cloud
quotas documentation during this playbook's drafting.

### 6.5 Outbox and CDC ingress

> Dual writes are the most common correctness bug in event-driven systems.

Writing to your database and then publishing to Kafka is two operations that can partially fail.
There is no retry strategy that fixes this. Two correct patterns:

- **Transactional outbox** — for data your application owns. Write the business row and the
  outbox row in one local transaction; a CDC connector publishes from the outbox.
- **CDC** — for systems you do not own. Capture the change log directly.

Both converge on the same downstream handler contract, which is the point: a downstream handler
should not know or care which one produced its input.

For the CDC path, apply §5.2 — land raw, decode and normalize in Flink, then publish the
canonical event.

**FSI note:** mainframe integration follows the same shape, with IBM MQ Source Connector → Kafka
as the canonical bridge.

---

## 7. Development

### 7.1 The golden path

> A new handler should be running against a real topic in under an hour.

Ship templates, not documents. The template repo carries:

- The nine-part anatomy from §2.2, pre-wired
- Config baselines (§11.1) already set
- Schema Registry registration and codegen
- DLQ, retry, and rejects wiring
- Test harness at all five tiers (§8)
- CI workflow including both schema gates (§8.3)
- Terraform stanza for topics, service account, and RBAC
- A dashboard definition with the four signals (§10.1)

**Teams should delete code to start, not add it.** If the golden path is a wiki page describing
what to build, it is not a golden path.

### 7.2 The inner loop

A handler you cannot run in 30 seconds on a laptop will not get tested.

- **Inner loop:** containerized broker + Schema Registry locally
- **Outer loop:** ephemeral namespaced topics on a shared dev cluster, for anything managed —
  Flink statements, managed connectors, RBAC behaviour
- Confluent's VS Code extension and JetBrains plugin for topic, schema, and Flink inspection

### 7.3 Config, identity, naming

> Nothing about the environment lives in the artifact.

- **Zero bootstrap URLs in code.** Ever.
- **Service accounts per handler**, not per team. RBAC scoped to the topics it actually touches.
- **API keys rotated by pipeline**, not by a human with a console tab open.
- Topic naming per §3.3, enforced in CI.

**Static membership.** This is where §1's failure #3 is answered:

- `group.instance.id` set per instance
- Cooperative-sticky partition assignor
- `session.timeout.ms` tuned to your restart window

A rolling deploy should not trigger a full rebalance. §8.5 proves it; this designs it.

### 7.4 Anti-patterns — grep for these

| Anti-pattern | Why it's wrong |
|---|---|
| `enable.auto.commit=true` in a processing loop | Commits position, not completion. Loses messages on crash. |
| Filtering or routing in the producer / SMT | See §5.2 |
| One consumer group per instance | Defeats the group. Each instance reads everything. |
| Unbounded watermarks | State grows without limit; windows never close |
| `try { ... } catch (Exception e) { log.warn(...) }` | Not an error strategy. See §6.1. |
| Hand-written record classes | Drifts from the schema silently |
| Processing time in a windowed aggregate | See §3.4 |

---

## 8. Testing

> Most streaming teams have an hourglass. We want a pyramid.

### 8.1 The five tiers

| Tier | What | Count / runtime | Runs |
|---|---|---|---|
| 1 · **Unit** | Topology test driver / Flink table tests | Thousands / milliseconds | Every save |
| 2 · **Contract** | Schema compatibility + Data Contract rules | One per subject / seconds | Every commit |
| 3 · **Component** | Containerized broker + SR, one handler, real serialization | Dozens / minutes | Every commit |
| 4 · **Integration** | Ephemeral namespaced topics on a real Confluent Cloud environment | Handful / minutes | Every PR |
| 5 · **Non-functional** | Lag, rebalance, failover, poison pill | A few / hours | Nightly / pre-release |

The contract gate sits second on purpose: it is the cheapest check in the stack, so it runs
earliest and most often.

### 8.2 Unit — make the handler a pure function

Separate deserialize / process / effect so that `process` is a pure function over a decoded
record. Then:

- **No `KafkaConsumer` in a unit test.** If you need one, the seam is in the wrong place.
- Kafka Streams: `TopologyTestDriver`
- Flink: test the SQL as SQL, against fixed input tables

This single structural choice is what makes tiers 1 and 3 cheap. Handlers that mix I/O and logic
end up with all their tests at tier 4, which is the hourglass.

### 8.3 Contract — the highest-ROI gate you can add

One CI step prevents the most common incident in streaming. Two gates, not one:

1. **Compatibility check** against the registry's current version — syntactic
2. **Data Contract rules** — semantic (§3.1)

A breaking change fails the pull request, not the deploy. Consumers declare the subject **and
version** they read, so the blast radius of a change is computable rather than discovered.

### 8.4 Determinism and fixtures

> A flaky streaming test is usually an undeclared time dependency.

- **Pin the clock.** Drive watermarks manually. Seed everything.
- Fixtures from **captured production traffic** — masked, versioned, checked into the repo
- **Golden-file assertions** on output topics. Diff, don't eyeball.

### 8.5 The tests nobody writes

Correctness tests pass. Then you deploy. These five are where the actual incidents come from:

- [ ] **Lag and backpressure at 3× peak** — watch lag's derivative, not its absolute value
- [ ] **Rebalance on rolling restart** — proves §7.3
- [ ] **Broker / AZ failover and reconnect**
- [ ] **Poison pill injection** — prove the DLQ path works before production proves it doesn't
- [ ] **State restore from cold** — this number *is* your RTO (§10.3)

---

## 9. Deployment

### 9.1 Everything as code

> If it isn't in the provider, it isn't a deployment — it's a change someone made.

Terraform (Confluent provider) is the single source of truth for: environments, clusters, topics,
schemas, ACLs and RBAC bindings, connectors, Flink statements, service accounts, and API keys.

Environment topology: separate Confluent Cloud environments per stage. Where production data must
reach a lower stage, Cluster Linking with a masked subset — never a copy job someone runs.

*Backing: `wiki/patterns/terraform-cicd-confluent-private-networking.md`,
`wiki/patterns/fsi-governance-automation.md`.*

### 9.2 The pipeline and the promotion path

```
commit → build + codegen → unit → schema compat (syntactic) → Data Contract rules (semantic)
       → component → provision ephemeral topics → integration → tear down
       → publish immutable artifact → register schema → shadow → canary → promote
```

**The same artifact moves through every stage. Config differs; bytes don't.**

What promotes and what doesn't:

| Artifact | Promotes? | Note |
|---|---|---|
| Application artifact | Yes | Immutable, same bytes |
| Schemas | Yes | With a compatibility re-check per environment |
| Flink statements | Yes | As SQL artifacts |
| Topics | **No** | Per-environment, created by Terraform |
| Secrets / API keys | **Never** | Per-environment, rotated by pipeline |

### 9.3 Deploy strategies — a consumer group is a stateful deployment

| Strategy | When | Watch for |
|---|---|---|
| **Rolling** | Default. Behaviour unchanged | Requires static membership (§7.3) or you get a storm |
| **Blue/green group** | **Any change to handler semantics.** New `group.id`, cut over, keep blue warm | See below |
| **Flink statement swap** | Flink handlers | New statement → new derived topic → verify → repoint consumers |

**Two details decide whether blue/green works:**

1. **Green starts at blue's committed offsets**, not `earliest`. Starting at earliest replays
   history through a handler whose effects may not be idempotent — you just ran a §6.3 test in
   production.
2. **Running both is a double read.** Double consumer-side compute and egress for the whole shadow
   window. Budget it and **time-box it**. "Leave it shadowing for a while" is how this pattern
   gets banned by whoever owns the bill.

Promotion gates: lag SLO, error rate by class, DLQ rate, output diff rate.

**The offset reset policy is decided before deploy, written down, and not improvised at 2am.**

### 9.4 Reprocessing, rollback, and what you can't undo

> Code rolls back. Emitted events and evolved schemas do not.

| Reversible | Irreversible-ish |
|---|---|
| Config | Produced records |
| Code / artifact version | Schema evolution |
| Consumer group offsets | Compacted state (originals gone) |
| Scaling | Downstream side effects |

**Design corrections as events.** You do not un-emit; you emit a correction, and downstream
handlers must be built to accept one.

**Have the replay runbook written before you need it.** It should name: who authorizes a replay,
which offsets, what downstream systems must be paused, and how duplicates will be absorbed
(§6.3).

---

## 10. Run

### 10.1 Four signals, one error budget

> Consumer lag is a symptom. End-to-end event latency is the SLO.

| Signal | Alert on | Not on |
|---|---|---|
| **Consumer lag** | Its **derivative** — is it growing? | Absolute value. 50k and falling is fine; 5k and climbing is an incident. |
| **End-to-end latency p99** | Produce timestamp → effect completed | Broker-internal latency only |
| **Error rate by class** | Each of §6.1's three classes separately | A single blended error rate |
| **DLQ depth and rate** | Both | Depth alone — a flat deep DLQ is a different problem from a growing one |

Combine into one error budget per handler. `traceparent` propagated in headers through every hop,
required by the template. Stream Lineage answers "what breaks if I change this."

*Backing: `wiki/concepts/consumer-lag-monitoring.md`, `wiki/concepts/observability-metrics-mapping.md`.*

### 10.2 SLA tiers (FSI)

Frame handler latency requirements in tiers, and let the tier drive the substrate and the
delivery-semantics choice:

| Tier | Budget | Typical |
|---|---|---|
| Market data | sub-millisecond | Tuned clients, no EOS |
| Risk | < 10 ms | Streams or tuned client |
| Compliance | < 100 ms | Flink or Streams; EOS often required |
| Reconciliation | async | At-least-once + dedup; EOS is waste here |

*Backing: `wiki/concepts/sla-tiers.md`.*

### 10.3 DR — the handler's half of the plan

> Cluster Linking moves the data. Something still has to move the consumers.

- Cluster Linking for CC↔CC. Mirror only what you need;
  `auto.create.mirror.topics.enable = false` in production.
- **Consumer offsets are translated onto the mirror** — verify this works before you need it.
- **Application routing is the part teams forget.** Bootstrap indirection, plus a decision made in
  advance about *who* flips it and *on what signal*.
- **Your RTO is dominated by state restore, not by the link.** A stateless handler fails over in
  seconds. A handler with a large state store fails over in however long the restore takes. That
  is why standby replicas or a warm handler in region B is a cost decision (§11.4) made in
  advance, not an ops decision made during the incident.

Test it. It belongs on §8.5's list.

*Backing: `wiki/patterns/dr-cluster-linking.md`, `wiki/patterns/dr-application-routing.md`.*

---

## 11. Reference

### 11.1 Config baselines

Non-negotiable defaults. Everything else is tuning.

**Producer**

| Setting | Value | Why |
|---|---|---|
| `acks` | `all` | Anything less can lose acknowledged writes |
| `enable.idempotence` | `true` | Removes producer-retry duplicates. Free. |
| `compression.type` | `lz4` | `zstd` when storage-constrained |
| `transactional.id` | set | Only when EOS is chosen per §4.2 |

**Consumer**

| Setting | Value | Why |
|---|---|---|
| `enable.auto.commit` | `false` | Commit after processing, never on a timer |
| `auto.offset.reset` | `earliest` | Document deliberately if using `latest` |
| `group.id` | one per logical application | Not per instance |
| `group.instance.id` | set per instance | Static membership; see §7.3 |
| partition assignor | cooperative-sticky | Avoids stop-the-world rebalance |

**Topic**

| Setting | Value |
|---|---|
| replication factor | 3 |
| `min.insync.replicas` | 2 |
| retention | event-time driven; compaction for entity streams |

**Kafka Streams**

| Setting | Value |
|---|---|
| `processing.guarantee` | `exactly_once_v2` where §4.2 says so |
| `num.standby.replicas` | ≥ 1 where restore time matters |

**Flink SQL**

| Setting | Value |
|---|---|
| `scan.startup.mode` | `earliest-offset` for deterministic replay |
| watermark | `BOUNDED_OUT_OF_ORDERNESS`, bounded delay |
| changelog output | `UPSERT-KAFKA` connector |

*Backing: `wiki/patterns/producer-config-fsi.md`, `wiki/patterns/consumer-config-fsi.md`,
`wiki/concepts/kafka-streams-config-baseline.md`.*

### 11.2 Handler review checklist

Run this before a handler goes to production. Anything unchecked is a finding with an owner.

**Contract**
- [ ] Schema registered, format Avro or Protobuf, compatibility mode declared in git
- [ ] Data Contract rules defined for semantic constraints
- [ ] Consumers declare subject and version
- [ ] Key chosen for the ordering domain, and that choice written down
- [ ] Topic name matches `{domain}.{application}.{version}.{entity}`

**Semantics**
- [ ] Delivery guarantee chosen per §4.2 and recorded in the service manifest
- [ ] If the effect is external, the handler is idempotent (§6.3)
- [ ] Event time, not processing time; lateness policy explicit

**Error path**
- [ ] All three error classes classified and routed separately
- [ ] DLQ has a named owner, an SLO, and a replay tool that has been run
- [ ] Original bytes and failure context preserved on DLQ messages
- [ ] Poison-pill injection test passes

**Ship**
- [ ] Everything in Terraform — topics, schema, service account, RBAC, statement
- [ ] Static membership configured
- [ ] Deploy strategy chosen; offset reset policy written down
- [ ] Rollback path identified, and the irreversible parts named (§9.4)

**Run**
- [ ] Four signals instrumented; alerting on lag derivative
- [ ] `traceparent` propagated
- [ ] State restore time measured, and it is the stated RTO
- [ ] Runbook exists and links to the replay procedure

### 11.3 Maturity model

| Stage | Looks like | The one change that moves you up |
|---|---|---|
| **1 · Ad hoc** | Handlers hand-rolled; DLQs unowned; testing manual | Adopt the template repo for the *next* handler |
| **2 · Templated** | Golden path adopted; schema gate in CI; DLQ owners named | Put all infrastructure in Terraform |
| **3 · Governed** | All infra as code; contracts enforced; SLOs per handler; canary standard | Make the paved road self-serve |
| **4 · Self-service** | Teams ship handlers without platform involvement; platform owns the road only | — |

Score each handler 0–3 on five axes: **contract, error path, test depth, deploy automation,
observability.** The low score is your next sprint.

### 11.4 What things cost

Four levers, and they are the only four. Cost accrues at rest, not at authoring time — a handler
is cheap to write and expensive to hold.

| Lever | Drives |
|---|---|
| **Partition count** | Parallelism floor, rebalance cost |
| **State size** | Compute, restore time, changelog storage, standby replica cost |
| **Retention** | Storage, and how far back you can replay |
| **Egress** | Cross-AZ, cross-region, cross-cluster |

Where patterns land: stateless Flink SQL is parallelism × throughput and nothing else. Windowed
aggregates add state. Temporal joins hold *both* sides in state. Sagas add state plus timers plus
a compensating path you also pay for.

**Price your top three handlers against these four levers before the next planning cycle.**

---

## 12. What this playbook doesn't cover yet

Stated plainly so nobody mistakes silence for a recommendation.

1. **Max message size / claim-check threshold (§6.4).** Not confirmed for a specific cluster type.
   The Confluent Cloud quotas documentation does not carry it. Confirm for your tier and fill in.
2. **Testing has no wiki backing.** §8 is the least source-backed section here; there is no
   `wiki/patterns/event-handler-testing-strategy.md`. Treat §8 as considered practice rather than
   validated canon until that exists.
3. **Share groups in production at scale.** GA and documented (§2.5), but this playbook carries no
   first-hand operational experience of them under load. The stated constraints are reliable; the
   operational characteristics are not yet ours.
4. **Streaming agents / AI-adjacent handlers.** Confluent Cloud now offers streaming agents and a
   real-time context engine. Deliberately out of scope for v1.0 — the patterns here apply, but the
   substrate has not been assessed.
5. **Multi-tenancy inside a handler.** Not addressed. Assumes one handler serves one logical
   tenant boundary.

---

## Appendix A — Monday

Three things, this week. Each one stops you paying for a named failure from §1.

| Do this | Kills |
|---|---|
| **Name a DLQ owner** for your three highest-volume topics | Failure 1 — poison pill at 2am, nobody owns the DLQ |
| **Add the schema compatibility gate** to one named pipeline | Failure 4 — schema change breaks a consumer downstream |
| **Adopt the template repo for the next handler** — not a retrofit | Starts on 3, 5 and 6 — rebalance storms, non-idempotent replay, unsized state |

Two notes on making this stick:

- **Put a name and a date against each one before anyone leaves the room.** Three items with no
  owner is a wish.
- **"The next handler, not a retrofit" is load-bearing.** The standard way this dies is someone
  proposing to migrate the existing forty handlers; it gets estimated, and it gets shelved.
  Greenfield-only is the wedge that survives contact with a roadmap.

---

## Appendix B — Sources

Canon and wiki articles this playbook draws on. Where a claim here and a wiki article disagree,
the wiki article wins and this document is wrong.

**Patterns:** `dead-letter-queue-design` · `flink-event-routing` · `topic-naming` ·
`producer-config-fsi` · `consumer-config-fsi` · `schema-registry-adoption-playbook` ·
`kafka-streams-topology-patterns` · `terraform-cicd-confluent-private-networking` ·
`fsi-governance-automation` · `fsi-exactly-once` · `dr-cluster-linking` ·
`dr-application-routing` · `dr-multi-region-cluster`

**Concepts:** `queues-for-kafka-share-groups` · `exactly-once-semantics` ·
`schema-registry-best-practices` · `schema-evolution-strategies` ·
`consumer-group-rebalancing` · `consumer-lag-monitoring` · `observability-metrics-mapping` ·
`sla-tiers` · `kafka-streams-config-baseline` · `kafka-streams-production-hardening` ·
`flink-checkpointing`

**Live sources:** Confluent documentation via `confluent-docs` MCP, August 2026.

**Companion deck:** `event-handler-patterns-playbook-deck.md` (v1.1, 31 slides) with 16 art
assets in `event-handler-deck-art/`.
