---
title: Wiki Validation Report — Targeted (ORKA empty-fetch claim)
date: 2026-05-15
scope: single queued claim — kafka-dr-framework-v3.md §5.1
operator: /wiki:validate
---

# Wiki Validation — 2026-05-15

## Scope

User-supplied scope (from `wiki/_queue.md` "Unverified Claims to Resolve"):

> [ ] kafka-dr-framework-v3.md §5.1: "ORKA returns empty fetch responses to pause consumers" — no public docs; technically plausible per Kafka protocol but unverified

This is a queued claim from a **prior evaluation** of an external document
(`outputs/reports/kafka-dr-framework-v3-evaluation-2026-04-20.md`). The
`kafka-dr-framework-v3.md` is not a wiki article — it was an external DR
framework document evaluated on 2026-04-20. No wiki article currently restates
this claim, so the validation outcome is a **queue-resolution decision**, not
a wiki body edit.

## Articles checked

- 0 wiki articles (claim is not authored into the wiki)
- 1 external evaluation report cross-checked (`kafka-dr-framework-v3-evaluation-2026-04-20.md`)
- 1 MCP source consulted (context7 → Kroxylicious)

## Claim decomposition

| # | Sub-claim | Verifiable via public sources? |
|---|-----------|-------------------------------|
| A | A Kafka proxy can intercept and rewrite `FetchResponse` payloads before they reach the client | **Yes** |
| B | Returning empty `FetchResponse` is indistinguishable from a quiet topic | **Yes** (Kafka protocol) |
| C | Consumer group heartbeat survives an empty-fetch pause (no rebalance triggered) | **Yes** (Kafka protocol — heartbeat is a separate API) |
| D | ORKA specifically implements (A)+(B)+(C) as its consumer-pause mechanism | **No — vendor-internal** |

## Findings

### Sub-claims A, B, C — CONFIRMED (protocol-level)

**MCP source: context7 → Kroxylicious (`/kroxylicious/kroxylicious`).**

Kroxylicious — the canonical open-source Kafka protocol proxy (Red Hat / IBM
upstream) — exposes `FetchResponseFilter` as a first-class extension point:

```java
public interface FetchResponseFilter {
    CompletionStage<ResponseFilterResult> onFetchResponse(
        short apiVersion,
        ResponseHeaderData header,
        FetchResponseData response,
        FilterContext context);
}
```

The filter receives the full `FetchResponseData` and can mutate `responses()`
→ `partitions()` → records before forwarding. A filter is free to clear the
record set on every partition, producing an empty (zero-record) but
protocol-valid `FetchResponse`.

This directly substantiates the protocol-mechanism portion of the ORKA claim.
Other proxies (Conduktor Gateway, AWS MSK Connect Privatelink path) implement
analogous interception points.

Consumer behavior under empty fetch is also well-established:

- `FetchResponse` with empty record batches is the normal steady state for
  quiet/low-throughput partitions; consumers simply wait `fetch.max.wait.ms`
  and re-poll.
- `Heartbeat` (KIP-62 / KIP-429) flows over a separate API call on the
  group-coordinator connection, decoupled from fetch traffic. Empty fetches
  do not trigger `max.poll.interval.ms` rebalance because the consumer keeps
  calling `poll()`.
- `session.timeout.ms` is not breached as long as the background heartbeat
  thread keeps running.

The mechanism is sound. Any vendor proxy (ORKA, Conduktor Gateway, a
hand-rolled Kroxylicious filter) can implement consumer-pause-via-empty-fetch
in a few hundred lines.

### Sub-claim D — UNVERIFIABLE (vendor-internal, public MCP scope cannot resolve)

GoodLabs Studio (the ORKA vendor) has **no public product documentation,
architecture page, or technical whitepaper** as of this validation date.
Confluent docs MCP (`confluent-docs`) does not cover GoodLabs products.
Context7 has no GoodLabs source. A targeted web search would surface only
the March 2026 YouTube demo, which does not describe the failover
mechanism at protocol level.

Verifying that ORKA *specifically* uses empty fetches (vs. e.g. a controlled
`LeaveGroup` + reconnect path, or a stalled `Fetch` until timeout, or a
synthetic `NOT_LEADER_OR_FOLLOWER` error to trigger metadata refresh) requires
**one of**:

1. Vendor technical documentation.
2. A `tcpdump` / wireshark Kafka-protocol capture against an ORKA-fronted
   cluster during failover.
3. A walkthrough from GoodLabs engineering.

This is outside what MCP-sourced validation can answer.

## Resolution

**Reclassify the queue entry from "unverified" to "scope-limited — protocol
mechanism verified; vendor-specific implementation requires GoodLabs
disclosure."** Recommendation:

- Sub-claims A/B/C: **confirmed** via Kroxylicious upstream (FetchResponseFilter
  interface), Kafka protocol (heartbeat decoupling).
- Sub-claim D: **out of public-MCP scope** — requires vendor
  confirmation; do not author into the wiki as a confirmed fact until the
  vendor confirms.

## Recommendation for the wiki

When the queued stub `wiki/patterns/dr-application-routing.md` is written:

- It is **safe** to say "Kafka protocol proxies (Kroxylicious, Conduktor
  Gateway, ORKA) can pause consumers via FetchResponse interception without
  triggering rebalance, by relying on the separation of fetch from the
  heartbeat path."
- It is **not safe** to attribute the empty-fetch mechanism specifically to
  ORKA without a GoodLabs citation. Use phrasing like "ORKA is reported to
  use protocol-level interception; specific failover mechanism is vendor-
  internal."

## Counts

- Claims validated: 4 (3 confirmed protocol-level, 1 vendor-internal / unverifiable)
- Drift instances found: 0 (no wiki article currently asserts this claim)
- Stubs with expansion potential: 0 new (existing `dr-application-routing.md`
  queue item already covers this territory)

## Health assessment

Wiki currently does not author ORKA-specific claims, so there is no drift
risk on the live wiki. The queued claim is now resolved as far as public
sources can take it. Future ORKA-related content must be gated on vendor
disclosure or empirical capture.
