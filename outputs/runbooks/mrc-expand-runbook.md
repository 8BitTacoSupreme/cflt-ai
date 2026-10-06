---
title: MRC Expand — Non-Stretched Topic to Multi-Region Clusters
subtitle: Reverse `kafka-topics --describe` into JSON, then expand into an MRC replica layout with a topic-count execute throttle
audience: Confluent Platform operators converting existing single-region topics to Multi-Region Clusters
validated: 2026-09-17 end-to-end against a local 3-rack KRaft cluster (Docker, torn down after) — plan-only path, `--execute N` topic-count throttle across two runs, and idempotent re-run all confirmed
confidence: high
related-canon: wiki/patterns/yaml-topic-rbac-admin-tool.md
---

# MRC Expand — Non-Stretched Topic to Multi-Region Clusters

**Purpose:** Given topics that are **not yet stretched** across racks (single-rack replica
placement, or `RF=1`), compute — and optionally apply, a limited number of topics at a
time — a replica expansion plan that spreads them across your target racks per an
MRC-style layout. This is the initial "go from one region to MRC" step;
[`mrc-leader-rebalance.sh`](mrc-leader-rebalance-runbook.md) is the follow-on tool for
correcting leader-rack drift on topics that are *already* stretched.

## Tools

Two bash-only scripts, no jq, no Python, no third-party packages:

1. **`outputs/tools/kafka-describe-to-json.sh`** — converts `kafka-topics --describe`
   output into JSON Lines (one JSON object per partition: `topic`, `partition`, `leader`,
   `replicas`, `isr`, `observers`). Pure bash + awk, no network calls.
2. **`outputs/tools/mrc-expand.sh`** — reads that JSON Lines file plus a broker-range rack
   config, computes an expansion plan, and by default only writes it to disk. Pass
   `--execute N` to actually apply the plan for up to `N` topics against a
   `--bootstrap-server` you provide — the only point either script ever makes a network
   call, and only to the cluster you name.

Both scripts share the same rack-config format and placement algorithm as
`mrc-leader-rebalance.sh`, with one addition: **`broker` lines accept ranges**
(`broker 1-2 rack-a`, or `broker 1-3,5,7-8 rack-a`), not just single IDs — useful when a
rack has many brokers.

## Why a topic-count throttle, not just a dry-run flag

A plan-only mode alone doesn't limit blast radius once you decide to apply it — running
the whole reassignment file at once means every touched topic starts moving data
simultaneously. `--execute N` instead applies the plan for only the first `N` touched
topics (alphabetical order) per invocation: reassign → verify → preferred-election for
those, then stop, leaving the rest of the plan on disk for a follow-up run (re-describe,
re-plan, execute the next batch). This is orthogonal to `--batch-size` (which splits a
single topic's many partitions into reassignment batches) — `--execute N` throttles
**how many topics** you touch per run.

## Inputs

1. Current state — same as `mrc-leader-rebalance.sh`, single-topic (or a few explicit
   topics) `--describe` output:
   ```bash
   kafka-topics --describe --bootstrap-server <BS> --topic <topic1> \
     [--command-config client.properties] > current-state.txt
   ```
2. Convert to JSON Lines:
   ```bash
   ./kafka-describe-to-json.sh --describe-file current-state.txt --out state.jsonl
   ```
3. A rack config file — see `--print-example-config`:
   ```bash
   ./mrc-expand.sh --print-example-config > racks.conf
   ```
   ```
   # broker <id-or-range> <rack>     — accepts "3", "1-2", or "1-2,5,7-8"
   # target_leader_rack <rack>       — must be one of the racks used below
   # sync <rack> <count>             — desired sync-replica count in this rack
   # observer <rack> <count>         — desired observer-replica count (optional)

   broker 1-2 rack-a
   broker 3-4 rack-b
   broker 5-6 rack-c

   target_leader_rack rack-a

   sync rack-a 1
   sync rack-b 1
   sync rack-c 1
   ```

## Run — plan only (default, no network calls)

```bash
./mrc-expand.sh \
  --state-file state.jsonl \
  --rack-config racks.conf \
  --out-dir plan/ \
  [--topics t1,t2 | --exclude-topics t3,t4] \
  [--batch-size 200] \
  [--prune-excess-replicas]
```

Writes the same file set as `mrc-leader-rebalance.sh` (`plan-summary.txt`,
`reassignment-leader-only.json`, `reassignment-expand[-NN].json`,
`reassignment-prune.json`, `preferred-election.json`) into `--out-dir`, and exits 0 with
no network calls.

## Run — apply for N topics at a time

```bash
./mrc-expand.sh \
  --state-file state.jsonl \
  --rack-config racks.conf \
  --out-dir plan/ \
  --execute 1 \
  --bootstrap-server <BS> \
  [--command-config client.properties] \
  [--throttle <bytes/sec>] \
  [--verify-interval-seconds 5] \
  [--verify-max-attempts 24]
```

For the first `N` touched topics (sorted alphabetically), this runs, in order:

1. `kafka-reassign-partitions --execute` for that batch's leader-reorder-only file (if any)
2. `kafka-reassign-partitions --execute` (throttled) for the expand file, polling
   `--verify` every `--verify-interval-seconds` until it reports complete or
   `--verify-max-attempts` is exhausted
3. `kafka-reassign-partitions --execute` for the prune file, if `--prune-excess-replicas`
   was set and any prune candidates exist
4. `kafka-leader-election --election-type preferred` for every touched partition in the batch

The remaining touched topics beyond `N` are left completely untouched — confirmed in
testing that an unexecuted topic's replica assignment doesn't change at all. Re-run with
a fresh `--describe` → `kafka-describe-to-json.sh` → `mrc-expand.sh --execute N` cycle to
work through the rest; already-satisfied topics show up as `no-op` and cost nothing to
re-plan.

## Validated end-to-end (local KRaft, 3 racks, one broker per rack)

Two topics created as genuinely non-stretched (`RF=1`, single broker, single rack):
`orders.payments.completed` (3 partitions) and `orders.payments.refunded` (2 partitions).

1. **Plan-only**: both topics correctly classified as `expand`, target replica set
   `[1,2,3]` for every partition, leader unchanged at broker 1 (already in
   `target_leader_rack`).
2. **`--execute 1`**: applied only to `orders.payments.completed` — confirmed via
   `kafka-topics --describe` afterward that it moved to `RF=3` across all three racks,
   while `orders.payments.refunded` was untouched (still `RF=1`, unchanged replicas).
3. **Second `--execute 1` pass** (re-described, re-planned): applied to the now-only
   remaining touched topic, `orders.payments.refunded` — confirmed expanded to `RF=3`
   with zero topics left pending, tool exits `0`.
4. **Idempotent re-run**: re-running the plan against fully-expanded topics classified
   every partition `no-op`, `--execute 1` had nothing new to do, and the script still
   exits `0`.

### Bug found and fixed during this validation

The script's trailing `[[ ${#PENDING_TOPICS[@]} -gt 0 ]] && echo ...` line, when it was
the very last statement executed with zero pending topics, made the script exit `1`
despite every reassignment and election having already succeeded — a plain shell
exit-code artifact (the failed `[[ ]]` test on the false branch of a bare `&&` becomes
the script's own exit status when it's the last command run), not a logic error in the
plan or execution. Fixed by converting both trailing conditional-echo lines to explicit
`if` blocks so the script's own exit code no longer depends on whether anything was left
pending.

## Caveats

- Same caveats as [`mrc-leader-rebalance.sh`](mrc-leader-rebalance-runbook.md): this tool
  doesn't set `confluent.placement.constraints` itself; broker/rack IDs come from your
  config, not cluster discovery; only run `--execute` against a cluster you're authorized
  to reach.
- **`--execute` throttles by topic count, not by data volume.** Use `--throttle` together
  with `--execute N` to also bound the reassignment's network/disk impact per batch.
- Validate on one throwaway topic first, exactly as with `mrc-leader-rebalance.sh`.

## Related

- [MRC Leader-Rack Rebalance](mrc-leader-rebalance-runbook.md) — the follow-on tool for
  topics that are already stretched but need leader-rack pinning
- [YAML-Driven Topic & RBAC Admin Tooling](../../wiki/patterns/yaml-topic-rbac-admin-tool.md)
- [DR — Multi-Region Cluster](../../wiki/patterns/dr-multi-region-cluster.md) — the target topology
