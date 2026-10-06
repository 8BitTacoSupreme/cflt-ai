---
title: Opt-In Asynchronous Replica Placement for MRC Topics
subtitle: Per-topic "Example 1" placement (all sync replicas in one DC, all observers in the other) for apps that need the latency win and accept the DR tradeoff
audience: Application teams and Confluent operators deciding which topics should opt into async placement on an MRC cluster
validated: 2026-09-23 — MCP-checked against docs.confluent.io/platform/current/multi-dc-deployments/multi-region.md
confidence: high
related-canon: wiki/patterns/dr-multi-region-cluster.md
---

# Opt-In Asynchronous Replica Placement for MRC Topics

**Purpose:** Give specific producer/consumer apps a lower-latency, opt-in placement pattern
on an MRC cluster whose cluster-wide default already stripes sync replicas across both DCs —
without changing the cluster default, and while being explicit about the DR risk this trades in.

## The difference in placement

| | Cluster default (replicas split both DCs) | Async opt-in (all sync replicas in 1 DC) |
|---|---|---|
| Sync (ISR) replicas | Span both DCs | All in one DC only |
| Observers | 1 per DC | All in the *other* DC |
| `acks=all` latency | Pays cross-DC RTT on every write | In-DC only — no cross-DC RTT on the write path |
| Automatic failover on total DC loss | Yes — the other DC's replicas are already in ISR | **No** — observers aren't in ISR by default |

This is Confluent's documented **Example 1** placement pattern, applied per topic — it is the
opposite of a topology where replicas are already split across both DCs. Because it's set via
`--replica-placement` on `kafka-topics --create` (or `kafka-configs --alter --replica-placement`
on an existing topic, followed by a reassignment), it's a **per-topic** setting, not a cluster
default — only apps that explicitly need the performance and accept the tradeoff below should
opt in.

## Placement JSON

```json
{
  "version": 2,
  "replicas": [
    { "count": 3, "constraints": { "rack": "us-west" } }
  ],
  "observers": [
    { "count": 2, "constraints": { "rack": "us-east" } }
  ],
  "observerPromotionPolicy": "under-min-isr"
}
```

- `replicas` = sync, ISR-eligible, all pinned to one DC's `broker.rack`.
- `observers` = async, pinned to the other DC's `broker.rack` — replicate as fast as they can,
  but the leader never waits on them for `acks=all`.
- `observerPromotionPolicy: under-min-isr` auto-promotes observers into the ISR if the sync
  DC has a **partial** failure (ISR drops below `min.insync.replicas`) — this covers losing one
  or two brokers in the sync DC without manual action. It does **not** by itself elect a new
  leader if **every** sync replica goes offline at once (a full DC loss) — that's a leaderless
  partition, covered below.

## Why these topics need `unclean.leader.election.enable=true`

If the entire sync DC goes down, none of the topic's ISR members are reachable. By default
(`unclean.leader.election.enable=false`), Kafka leaves that partition **offline** rather than
elect a non-ISR replica — which for this pattern means the topic stops functioning cluster-wide
during exactly the DR event this async design exists to survive.

Setting `unclean.leader.election.enable=true` as a **topic-level override** on every topic using
this async pattern lets the controller automatically elect a caught-up observer in the surviving
DC as leader without waiting for manual intervention. The manual fallback/verification path is
the same either way:

```bash
# unclean-election.json
{ "version": 1, "partitions": [{ "topic": "<topic>", "partition": 0 }] }

kafka-leader-election --bootstrap-server <bootstrap-servers> \
  --election-type UNCLEAN --path-to-json-file unclean-election.json
```

**The cost:** unclean leader election can truncate the log to whatever offset the observer had
actually caught up to — any producer-acknowledged records beyond that are lost. This is the
explicit trade this pattern makes for lower latency, so:

- Only apply this to topics whose owning app has explicitly accepted possible data loss during
  a full-DC DR event in exchange for the latency win.
- Monitor observer lag continuously (`CaughtUpReplicasCount`, `IsNotCaughtUp`,
  `ObserversInIsrCount` JMX metrics) so the realistic data-loss window is known, not assumed.

## Failback: moving leadership back to the primary DC

**ISR demotion happens automatically; leadership does not.** Once the primary DC's original
sync replicas come back online and fully catch up to whatever is now leading (the promoted
observer), they rejoin the ISR automatically and the observer(s) are automatically demoted back
out of the ISR — no manual step needed for that part. But the **leader stays on the promoted
observer** until you explicitly move it, unless `auto.leader.rebalance.enable=true` is set (it
runs on its own schedule via `leader.imbalance.per.broker.percentage` /
`leader.imbalance.check.interval.seconds`).

To move it back on demand:

```bash
kafka-leader-election --bootstrap-server <bootstrap-servers> \
  --election-type PREFERRED --topic <topic-name>
# or, for every partition of every topic:
kafka-leader-election --bootstrap-server <bootstrap-servers> \
  --election-type PREFERRED --all-topic-partitions
```

**When to run it:** only after confirming the primary DC's replicas are actually back in the
ISR — check `kafka-replica-status --bootstrap-server <bootstrap-servers> --topics <topic> --verbose`
and look for `IsInIsr: true` on the primary-DC replicas. `--election-type PREFERRED` only elects
a replica that's already in-sync; running it before the primary DC has caught back up is a safe
no-op (it won't force anything), so there's no harm in checking status right before running it —
but it also means the command will silently do nothing useful if run too early.

**`unclean.leader.election.enable=true` doesn't affect this step.** That setting only governs
whether the controller may elect a non-ISR replica when there's no ISR member left at all —
`PREFERRED` elections are always "clean" (in-sync-replica-only) regardless of that topic setting,
so leaving it `true` doesn't risk an unclean failback.

## Opt-in scope

Keep a documented list of exactly which topics use this placement + `unclean.leader.election.enable=true`,
separate from the cluster's default (both-DC-synchronous) topics. Nothing about this pattern
should be applied cluster-wide — it's a deliberate, per-topic, per-app exception.

## Caveats

- This guide assumes the cluster already runs MRC with `broker.rack` set correctly on every
  broker and KRaft spans 3+ locations for quorum safety (see Confluent's MRC deployment
  architecture guidance) — it only covers the topic-level opt-in decision.
- Don't conflate `observerPromotionPolicy: under-min-isr` (handles partial failures
  automatically) with `unclean.leader.election.enable=true` (handles total ISR loss) — both are
  needed for this pattern to be genuinely hands-off during a full DC outage.

## Related

- [Multi-Region Deployments](https://docs.confluent.io/platform/current/multi-dc-deployments/multi-region.md) —
  replica placement JSON, automatic observer promotion, and observer failover/unclean election
  mechanics this guide is based on.
