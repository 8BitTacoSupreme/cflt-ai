---
title: MRC Leader-Rack Rebalance
subtitle: Force all partition leaders onto one rack after (or during) an MRC conversion
audience: Confluent Platform operators converting existing topics to Multi-Region Clusters
validated: 2026-09-17 against docs.confluent.io Multi-Region Clusters (replica placement, kafka-leader-election, kafka-reassign-partitions), and end-to-end against a local 3-rack KRaft cluster (Docker, torn down after)
confidence: high
related-canon: wiki/patterns/yaml-topic-rbac-admin-tool.md
---

# MRC Leader-Rack Rebalance

**Purpose:** After converting existing topics to Multi-Region Clusters (MRC) replica
placement, force every partition's leader onto a broker in one chosen rack (e.g. the
region with the lowest-latency clients), while expanding replicas to span the other
racks — without relying on Self-Balancing Clusters or Auto Data Balancer to do it,
because neither optimizes for "pin all leaders to rack X." That's not a goal either
rebalancer knows about; it's a preferred-replica-ordering problem.

## Why the built-in rebalancers can't do this

- **Self-Balancing Clusters / Auto Data Balancer** optimize for even load and replica
  distribution across brokers/racks. They have no concept of a target leader rack.
- The **preferred leader** for a partition is defined as `replicas[0]` in its assignment.
  `kafka-leader-election --election-type preferred` only elects whichever broker is
  already first in that list — it cannot pick an arbitrary broker.
- So pinning leaders to a rack means rewriting `replicas[0]` for every partition via
  `kafka-reassign-partitions`, then running preferred-leader election to act on it.
  Changing only the order (same broker membership) is a metadata-only operation — no
  data copy — but it still has to go through the reassignment API, not just leader
  election, because that's the only way to change the value election reads.

## Tool

`outputs/tools/mrc-leader-rebalance.sh` — bash only (3.2+, so it runs unmodified on
macOS's stock `/bin/bash` as well as any Linux bastion host). **No jq, no Python, no
third-party packages of any kind, no network calls.** It reads two local files you
provide and writes a plan (JSON + text) for you to execute. It never talks to a broker
itself.

End-to-end validated against a disposable local 3-rack KRaft cluster: expand → verify →
preferred election moved every leader onto the target rack's sole broker as planned.

### Inputs

1. Current state, captured by you from your own environment. `--describe` output for a
   single topic works, or for several topics at once — just not `--describe` with no
   `--topic` filter, since some Kafka versions don't support `--exclude-internal-topics`
   and will otherwise include internal topics you don't want reassigned:
   ```bash
   kafka-topics --describe --bootstrap-server <BS> --topic <topic1> \
     [--command-config client.properties] > current-state.txt
   ```
2. A rack config file — plain text, not JSON, so the tool has zero non-bash
   dependencies. See `--print-example-config`:
   ```bash
   ./mrc-leader-rebalance.sh --print-example-config > racks.conf
   ```
   ```
   # broker <broker-id> <rack>       — every broker in the cluster, once each
   # target_leader_rack <rack>       — must be one of the racks used below
   # sync <rack> <count>             — desired sync-replica count in this rack
   # observer <rack> <count>         — desired observer-replica count (optional)

   broker 1 rack-a
   broker 2 rack-a
   broker 3 rack-b
   broker 4 rack-b
   broker 5 rack-c
   broker 6 rack-c

   target_leader_rack rack-a

   sync rack-a 1
   sync rack-b 1
   sync rack-c 1
   ```
   `sync <rack> <count>` lines set the desired sync-replica count per rack (your MRC
   replica-placement shape). `target_leader_rack` must be one of the `sync` racks — a
   rack with zero replica budget can never legally hold a leader.

### Run

```bash
./mrc-leader-rebalance.sh \
  --describe-file current-state.txt \
  --rack-config racks.conf \
  --out-dir plan/ \
  [--topics t1,t2 | --exclude-topics t3,t4] \
  [--batch-size 200] \
  [--prune-excess-replicas]
```

### What it computes, per partition

- **Keeps the current leader if it's already a sync replica in the target rack** —
  minimizes leader churn to only the partitions that actually need it.
- **Preserves existing replica placement** wherever it already satisfies the desired
  per-rack count — no unnecessary data movement.
- **Adds replicas only in under-provisioned racks** (the actual "expand into MRC"
  step), picking the least-loaded broker in that rack so new copies fan out evenly.
- **Leaves over-provisioned racks alone by default.** Pass `--prune-excess-replicas`
  to actually remove extra copies — off by default because removing a replica is a
  data-deletion-adjacent action that shouldn't happen silently.
- Classifies every partition as `none` (already correct), `leader-reorder-only`
  (metadata-only, no data copy), `expand` (real data movement — the case to throttle
  and flag), or `prune` (replica removal — only if you opted in).

### Output (`--out-dir`)

| File | Contents |
|---|---|
| `plan-summary.txt` | Per-partition diff + the exact run order below |
| `reassignment-leader-only.json` | Same broker set, reordered — safe to run at full speed |
| `reassignment-expand[-NN].json` | Adds replicas — real data movement, throttle it, batched if `--batch-size` given |
| `reassignment-prune.json` | Removes replicas — only written with `--prune-excess-replicas` |
| `preferred-election.json` | Every touched partition, for the final election step |

### Execute (from your own authorized environment — never from this session)

```bash
# 1. Cheap: same members, new preferred order
kafka-reassign-partitions --bootstrap-server <BS> \
  --reassignment-json-file reassignment-leader-only.json --execute

# 2. Real data movement — one batch at a time, verify before continuing
kafka-reassign-partitions --bootstrap-server <BS> \
  --reassignment-json-file reassignment-expand-01.json \
  --throttle <bytes/sec> --execute
kafka-reassign-partitions --bootstrap-server <BS> \
  --reassignment-json-file reassignment-expand-01.json --verify

# 3. Only if you opted into pruning
kafka-reassign-partitions --bootstrap-server <BS> \
  --reassignment-json-file reassignment-prune.json \
  --throttle <bytes/sec> --execute

# 4. Once all reassignments report COMPLETED and new replicas are caught up:
kafka-leader-election --bootstrap-server <BS> \
  --election-type preferred --path-to-json-file preferred-election.json
```

## Caveats

- **This script does not itself set `confluent.placement.constraints`.** If a topic's
  replica list includes brokers meant to act as *observers*, the topic must already
  carry a matching `confluent.placement.constraints` (or get one via `kafka-configs
  --alter --replica-placement`) — see [YAML-Driven Topic & RBAC Admin Tooling](../../wiki/patterns/yaml-topic-rbac-admin-tool.md)
  for how that's set on topic creation. Without it, a broker listed under an `observer`
  directive is just a normal sync replica as far as Kafka is concerned.
- **Rack IDs and broker IDs come from you, not from cluster discovery.** The script
  never queries the cluster, so a stale/decommissioned broker ID left in the rack
  config will surface as a hard error rather than silently misplacing replicas.
- **Run the `--describe`/`--execute`/`--verify` steps only against a cluster you're
  authorized to reach**, from your own VPN-connected environment — never point this
  script's inputs at a client's live cluster from an unauthorized session.
- **Validate on one throwaway topic first.** Confirm `kafka-topics --describe` shows
  the expected leader and replica placement before running the full plan.

## Related

- [MRC Expand — Non-Stretched Topic to Multi-Region Clusters](mrc-expand-runbook.md) — the initial expansion step for topics that aren't stretched across racks yet; this runbook handles ongoing leader-rack drift correction once they are
- [YAML-Driven Topic & RBAC Admin Tooling](../../wiki/patterns/yaml-topic-rbac-admin-tool.md) — sets `confluent.placement.constraints` at topic-creation time; this runbook handles the reassignment step for topics that already exist
- [DR — Multi-Region Cluster](../../wiki/patterns/dr-multi-region-cluster.md) — the target topology
