---
title: MRC Client Migration Guide — Producer & Consumer Properties
subtitle: What to review on the client side after a live, in-place stretch of existing topics into a Multi-Region Cluster
audience: Application teams whose producers/consumers were already pointed at a cluster that got converted to MRC underneath them
validated: 2026-09-22 — MCP-checked against docs.confluent.io/platform/current/multi-dc-deployments/multi-region.md
confidence: high
related-canon: wiki/patterns/dr-multi-region-cluster.md
---

# MRC Client Migration Guide — Producer & Consumer Properties

**Scenario this covers:** clients were already pointed at the (formerly single-region) primary
cluster. The cluster itself was converted to MRC in place, and all topics were stretched across
DCs with no topic-level cutover — from the client's perspective, the bootstrap servers didn't
change, but the replica topology underneath every topic did. Nothing here is about *how* the
cluster conversion happened — it's the client-side config review that should follow it.

**Why this matters:** before the conversion, `acks=all` and consumer fetches were effectively
same-DC operations. After the conversion, if sync replicas span both DCs (as they do in a
topology with cross-DC ISR members), every `acks=all` produce and every leader-routed consumer
fetch can now cross the WAN by default — client configs tuned for LAN-class latency don't
automatically know that changed.

## Producer properties to review

- **`acks` / `enable.idempotence`** — if already `acks=all` / `enable.idempotence=true`, no
  change needed, but confirm this is still the intended tradeoff: it now means every produce
  synchronously pays cross-DC RTT if sync replicas span both DCs, not just in-DC RTT as before.
- **`request.timeout.ms` vs. broker `replica.lag.time.max.ms`** — Confluent's own producer-config
  guidance says the former should be larger than the latter. Both default to 30000ms out of the
  box, so there's zero built-in margin — worth confirming explicitly rather than assuming, and
  more pressing post-MRC since the produce path now has a cross-DC floor added to it.
- **`delivery.timeout.ms`** — the overall retry ceiling. Make sure it comfortably covers
  retries + backoff at the new latency floor, not just the old in-DC one.
- **`retries` / `retry.backoff.ms`** — WAN-class transient issues (packet loss, brief cross-DC
  blips) look different from same-rack blips; backoff tuned for LAN can retry too aggressively
  against a WAN hiccup.
- **`linger.ms` / `batch.size`** — since each round trip now costs more, larger batches amortize
  the added RTT better. Worth revisiting throughput tuning now that the latency floor moved up,
  even if nothing else changed.
- **`compression.type`** — if the cluster was previously fed via Replicator (which can force a
  specific `compression.type` on produce into the DR site), that constraint doesn't apply to
  producers writing natively into the now-stretched topics — don't assume the old Replicator-era
  setting is still required.
- **`transactional.id` / `transaction.timeout.ms`** — if any producers use transactions, the
  `__transaction_state` coordinator partition can now be led from either DC. Size
  `transaction.timeout.ms` with the same cross-DC-RTT-floor reasoning as `request.timeout.ms`.
- **`bootstrap.servers`** — sanity-check this actually lists brokers across both DCs, not a
  stale DC-scoped subset left over from before the stretch. Since this was a live, in-place
  conversion, nothing forced this list to get updated automatically.
- **Common misconception — producers do not get rack-aware routing.** `client.rack` (below) only
  affects consumer fetch routing. Producers always write to the partition leader regardless of
  which DC they're in; there's no producer-side equivalent of follower fetching.

## Consumer properties to review

- **`client.rack` — the single most impactful change.** MRC's follower-fetching feature
  (`replica.selector.class=RackAwareReplicaSelector` + `broker.rack` on the broker side) only
  activates for a given consumer if that consumer sets `client.rack` to a value matching one of
  the cluster's `broker.rack` groups. Without it, every consumer fetch still goes to the leader
  regardless of DC — meaning MRC's main consumer-side latency/cross-DC-traffic win is opt-in per
  client, not automatic just because the cluster is now MRC. This is the first thing to check for
  every consumer app post-migration.
  - Gotcha: `client.rack` must exactly match the `rack` strings used in the topic's replica
    placement JSON. A mismatch fails silently — the consumer just falls back to leader-only
    fetching with no error, so verify actual fetch-from-follower behavior after setting it, not
    just that the config is present.
- **`session.timeout.ms` / `heartbeat.interval.ms`** — the consumer group coordinator (a
  `__consumer_offsets` partition leader) can now live in either DC, so heartbeat/rebalance
  traffic for some members may cross the WAN. Consider modestly widening these versus
  single-DC-era values to avoid false-positive member expiry from transient cross-DC blips.
- **`group.instance.id` (static membership)** — reduces unnecessary full rebalances if a
  consumer briefly can't reach a coordinator that's now potentially in the other DC, rather than
  triggering a rebalance for what's really just a short network blip.
- **`isolation.level`** — only relevant if transactional producers are in play; same
  coordinator-locality reasoning as above applies to transaction visibility timing.
- **`fetch.max.wait.ms` / `fetch.min.bytes`** — worth re-validating if consumers are now being
  routed to a follower/observer via `client.rack` — that replica has its own propagation delay
  from the leader, which is a different latency profile than fetching directly from the leader.
- **`auto.offset.reset`** — unaffected by the MRC conversion itself, but worth re-confirming and
  documenting explicitly now, as part of general due diligence on a topology that changed
  underneath the topic.

## Post-migration verification checklist

- [ ] Every producer/consumer `bootstrap.servers` list actually spans both DCs' brokers.
- [ ] `client.rack` is set on consumers that are meant to benefit from follower fetching, and its
      value is confirmed to match an actual `broker.rack` group used in replica placement — not
      just present in config.
- [ ] Confirm via `kafka-consumer-groups --describe` that group coordinators and members aren't
      unexpectedly all pinned to a single DC now that topics span both.
- [ ] Confirm `request.timeout.ms` > `replica.lag.time.max.ms` with real margin, not just past
      the default-vs-default collision.
- [ ] Tie ongoing latency validation into existing cross-DC `RemoteTimeMs` / ISR-stability
      monitoring, rather than treating client config as a one-time check.

## Caveats

- This is a client-config checklist, not a replica-placement or broker-config guide — it assumes
  the MRC topology (sync replica placement, observer policy) is already settled and stable.
- Exact numeric values (timeouts, batch sizes) depend on the measured cross-DC RTT and
  latency SLA tier — deliberately not hardcoded here; baseline against real measurements before
  locking any in.

## Related

- [Multi-Region Deployments](https://docs.confluent.io/platform/current/multi-dc-deployments/multi-region.md) —
  Confluent's follower-fetching, observer, and replica-placement reference this guide is based on.
- [Producer Configuration Reference](https://docs.confluent.io/platform/current/installation/configuration/producer-configs.md) —
  full definitions/defaults for every producer property referenced above (`acks`, `enable.idempotence`,
  `request.timeout.ms`, `delivery.timeout.ms`, `retries`, `retry.backoff.ms`, `linger.ms`, `batch.size`,
  `compression.type`, `transactional.id`, `transaction.timeout.ms`, `bootstrap.servers`).
- [Consumer Configuration Reference](https://docs.confluent.io/platform/current/installation/configuration/consumer-configs.md) —
  full definitions/defaults for every consumer property referenced above (`client.rack`, `session.timeout.ms`,
  `heartbeat.interval.ms`, `group.instance.id`, `isolation.level`, `fetch.max.wait.ms`, `fetch.min.bytes`,
  `auto.offset.reset`).
