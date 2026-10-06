---
title: Wiki Validation Report — Targeted (ORKA guarantee-preservation claim)
date: 2026-05-18
scope: single queued claim — kafka-dr-framework-v3.md §5.3
operator: /wiki:validate
---

# Wiki Validation — 2026-05-18 (ORKA §5.3)

## Scope

User-supplied scope (from `wiki/_queue.md` "Unverified Claims to Resolve"):

> [ ] kafka-dr-framework-v3.md §5.3: "Kafka guarantees preserved (no duplicates, no missed messages)" — ORKA-specific; Confluent Gateway DR explicitly warns against this for Streams apps

Same posture as the §5.1 resolution (`wiki-validation-2026-05-15.md`):
`kafka-dr-framework-v3.md` is an external DR framework document, not a wiki
article. No wiki article currently authors this claim, so the outcome is a
**queue-resolution decision** with guidance for the queued
`dr-application-routing.md` stub — not a wiki body edit.

## Articles checked

- 0 wiki articles (claim is not authored into the wiki)
- 1 external evaluation cross-checked (`kafka-dr-framework-v3-evaluation-2026-04-20.md`)
- 2 MCP sources consulted (`confluent-docs` for Gateway DR docs; cross-referenced earlier `wiki-validation-2026-05-15.md` Kroxylicious findings)

## Claim decomposition

| # | Sub-claim | Verifiable via public sources? |
|---|-----------|-------------------------------|
| A | A pause-sync-switch proxy can preserve **at-least-once / no-duplicate** delivery for stateless consumers (offset sync via CL, no commit advance during pause) | **Yes** (protocol-derivable) |
| B | The same mechanism preserves correctness for **stateful** apps (Kafka Streams: changelog topics, repartition topics, RocksDB state, in-flight aggregates) | **No** — Confluent's own guidance is explicit it does NOT |
| C | ORKA specifically implements (A) **and** extends to (B) ("Smart Switching Sets" for stateful blue/green) | **No — vendor-internal** |

## Findings

### Sub-claim A — CONFIRMED (protocol-level, for stateless consumers)

The pause-sync-switch primitive is sound for stateless / at-least-once
workloads when all three legs hold:

1. **Pause before promotion** — proxy stops advancing consumer offsets on the
   active cluster (the Kroxylicious `FetchResponseFilter` mechanism verified
   in the 2026-05-15 §5.1 resolution).
2. **Offset sync via Cluster Linking** — `consumer.offset.sync.enable=true`
   on the cluster link replicates the consumer-group offsets to the DR
   cluster. CL replicates messages "at the same partitions and offsets" (per
   the 2026-04-20 evaluation, claim #1, CONFIRMED), so a paused consumer's
   last-committed offset on the DR cluster matches the last-committed offset
   on the active cluster.
3. **Resume on the promoted cluster at the same offset** — `mirror failover`
   promotes the topics; the consumer reconnects (or is transparently
   re-routed) and resumes from the synced offset.

Failure modes that would break (A):
- CL offset sync lag > 0 at moment of failover (offsets behind data → possible
  duplicates on resume; standard async-DR risk, not ORKA-specific).
- `mirror failover` (vs `promote`) used in an unplanned failover: no
  zero-lag guarantee → possible **missed messages** equal to replication lag.

The claim "no duplicates, no missed messages" is therefore **only true under
planned `promote` semantics** (drain-to-zero-lag before cutover) — and even
then only effectively, not synchronously (per the same evaluation, claim #6
correction). For unplanned failover, the claim is overstated regardless of
proxy mechanism.

### Sub-claim B — REFUTED for stateful apps (Confluent's own published guidance)

The April 20 evaluation cited Confluent Gateway DR docs verbatim:

> "If ordering guarantee and data consistency are required, for example, for
> Kafka Streams applications, do not use client switchover."

**MCP re-fetch attempted 2026-05-18:** The specific Cloud Gateway DR pages
(`/cloud/current/networking/gateway/disaster-recovery.html`,
`/cloud/current/clusters/cluster-linking/configure/cluster-link-failover.html`)
all return `302 → /index.html` against `confluent-docs` MCP as of this
validation. The content has likely been repackaged into the One-Click DR
launch material (Q4 2026 GA per the same evaluation). The warning text was
authoritative at the time of the April 20 capture and the underlying
technical reason has not changed:

- **Changelog topics**: A Kafka Streams app maintains state via changelog
  topics. If the proxy pauses *consumer* fetches but the application is
  mid-aggregation (records read, state mutated, changelog write pending),
  state and changelog can diverge across the cutover.
- **Repartition topics**: Streams writes intermediate keyed records to
  repartition topics and re-reads them. A cutover between write and
  re-read can either lose or duplicate records depending on which side of
  the boundary the pause lands.
- **EOS v2 transactions**: A Streams transaction spans consumer offset
  commit + state-store write + downstream produce. Cluster Linking does
  not replicate transaction state; on cutover, in-flight transactions
  abort and may either be retried (duplicate) or lost (missed) depending
  on the producer's transactional-id continuity across clusters.
- **Interactive Queries / RocksDB**: Local state stores are not replicated
  by CL at all. A Streams app coming up on the DR cluster either
  re-bootstraps state from changelog (long RTO; the opposite of "RTO in
  seconds") or starts cold.

The Confluent warning is grounded in these mechanics, not in the proxy
implementation. **No protocol-level proxy can fully preserve Streams app
correctness across a Cluster-Linking-mediated cutover**, because the
correctness boundary is broader than what CL replicates.

### Sub-claim C — UNVERIFIABLE (vendor-internal)

ORKA's §5.3 framing — "Smart Switching Sets for blue/green deployments" with
preserved Kafka guarantees — extends beyond what Confluent's own published
mechanism claims. The candidate ways ORKA could close the gap:

1. **Application-state checkpointing outside Kafka** — e.g., snapshot
   RocksDB state stores out-of-band and restore on the DR side. Plausible
   for blue/green within a single region but doesn't scale to true DR
   across CL boundaries.
2. **Producer transaction-coordinator coordination** — fence in-flight
   transactions on the active side and replay on the DR side. Would
   require coordination with the broker-side transaction coordinator, which
   is not a documented extension point.
3. **Narrower scope than advertised** — "Kafka guarantees preserved" applies
   to the stateless consumer subset only, and "blue/green for stateful
   apps" applies to in-region deployments, not cross-region DR. This is
   the most likely reading and would reconcile the claim with the
   Confluent warning.

Verifying which of (1)–(3) ORKA actually implements requires the same
disclosure path as the §5.1 resolution: vendor technical docs, an
engineering walkthrough, or empirical capture. Public MCP
scope cannot resolve.

## Resolution

**Reclassify the queue entry as "scope-limited — stateless subset
confirmed under planned-failover semantics; stateful subset refuted by
Confluent's own guidance; ORKA-specific extension requires vendor
disclosure."**

- Sub-claim A: **confirmed** for stateless / at-least-once consumers under
  planned `promote` semantics with CL offset sync enabled. Caveat:
  unplanned `failover` retains the standard async-DR risk window.
- Sub-claim B: **refuted as a general claim** for stateful apps. Confluent's
  own client-switchover guidance is the authoritative counter-cite.
- Sub-claim C: **out of public-MCP scope** — requires vendor
  confirmation. Do not author the
  guarantee-preservation claim into the wiki without either (a) a vendor
  citation, or (b) explicit scoping to stateless workloads under planned
  failover.

## Recommendation for the wiki

When the queued stub `wiki/patterns/dr-application-routing.md` is written,
the proxy-pause section should distinguish workload classes explicitly:

- **Safe to assert**: "For stateless consumers under planned, lag-drained
  failover (`mirror promote` + CL `consumer.offset.sync.enable=true`), a
  pause-sync-switch proxy can preserve at-least-once delivery with no
  duplicates and no missed messages. Unplanned failover (`mirror
  failover`) retains the standard async-replication RPO window regardless
  of proxy."
- **Required caveat**: "For stateful applications (Kafka Streams, ksqlDB,
  Flink with Kafka-backed state), Confluent's own guidance explicitly
  cautions against client switchover for correctness-sensitive workloads:
  changelog topics, repartition topics, in-flight EOS transactions, and
  local RocksDB state stores are outside the Cluster Linking replication
  boundary. No protocol-level proxy fully closes this gap."
- **Not safe to attribute to ORKA**: Specific extension claims (Smart
  Switching Sets, stateful preservation) without a GoodLabs citation.
  Phrasing must be "ORKA is reported to extend the proxy-pause pattern to
  stateful blue/green; specific mechanism is vendor-internal and outside
  public verification scope."

## Counts

- Claims validated: 3 sub-claims (1 confirmed-with-scope, 1 refuted, 1 vendor-internal)
- Drift instances found: 0 (no wiki article currently asserts the claim)
- Stubs with expansion potential: 0 new (existing `dr-application-routing.md`
  queue item already covers this territory; this report adds the
  workload-class distinction to its acceptance criteria)

## Health assessment

Wiki has no ORKA-specific drift risk because no wiki article authors the
claim. The queued item is now resolved within public-MCP scope. The
stateful-app caveat is the load-bearing piece of new information from this
pass — when the `dr-application-routing` stub is authored, it must be the
discriminator between proxy-pause patterns and a real claim of "Kafka
guarantees preserved."
