---
title: MRC DR Recovery — Rolling Restart & URP Checks
subtitle: Bringing brokers and dependent components back online safely after an upgrade or a DR event
audience: Confluent Platform operators recovering a Multi-Region Cluster
validated: 2026-09-22 — general Kafka/MRC operational practice, not tied to a specific doc fetch; cross-check against wiki/patterns/dr-multi-region-cluster.md for your organization's DR backend
confidence: high
related-canon: wiki/patterns/dr-multi-region-cluster.md
---

# MRC DR Recovery — Rolling Restart & URP Checks

**Purpose:** High-level steps for bringing MRC components back online after they've gone down —
whether from a planned upgrade or an actual DR event — without turning a recovery into a second
outage.

## Core rule: rolling, never bulk

Every multi-instance component (brokers, Schema Registry, Connect, Control Center) comes back
**one node at a time**, with a health check gate between each one. Bringing several nodes back
simultaneously means you have no fallback if the next one doesn't come up cleanly.

## Recovery order

1. **Brokers/controllers first** — everything else depends on the cluster being healthy.
2. **Schema Registry next** — Connect and client apps depend on it being reachable.
3. **Kafka Connect next.**
4. **Downstream consumers/apps last**, once the tiers they depend on are confirmed stable.

## Bringing a broker back — the URP gate

1. Know your baseline before you start: normal URP count for this cluster is effectively zero
   outside of active recovery — confirm that's actually the state before the event, not just
   assume it.
2. Start the first broker. Wait until its partitions are fully caught up and back in the ISR —
   i.e. URPs return to baseline — before touching the next broker.
3. Don't restart the next node while the previous one is still under-replicated. Doing so
   stacks reduced fault tolerance on reduced fault tolerance — a second issue during that window
   can turn a controlled recovery into real unavailability.
4. **MRC-specific nuance:** a clean URP count only confirms replicas caught up — it doesn't
   confirm leadership is back where you want it. If an observer was promoted during the event,
   check observer/ISR status too, not just URPs, before considering that DC "recovered."

## Bringing Schema Registry / Connect back

- Schema Registry: always keep at least one leader-eligible node up throughout — bring the
  second node back once the first is confirmed serving both reads and writes cleanly.
- Connect: bring workers back gradually rather than all at once, and let each rebalance settle
  (tasks reassigned, none stuck) before adding the next worker — piling up several
  near-simultaneous rebalances makes it hard to tell which restart caused a given task failure.

## DR-specific: failback is a deliberate step, not automatic

Bringing brokers back online restores replicas — it does **not** automatically move partition
leadership back to the primary DC. Treat failback as its own explicit, deliberate action:

- Confirm the recovered DC has been stable and fully caught up for a soak period before
  initiating failback, not the moment it rejoins the ISR.
- Move leadership back deliberately (preferred leader election) rather than letting it happen
  implicitly — avoids flapping if the recovered DC isn't actually stable yet.
- Failback timing is a business decision as much as a technical one — confirm with stakeholders
  before moving production traffic back, not just when the cluster is technically healthy.

## Post-recovery validation

- Partition leaders are back on the intended DC (if failback was performed).
- Consumer lag has drained back to normal across all consumer groups.
- No clients, connectors, or SR configs are still pointed at DR-only endpoints.
- URP count and ISR sizes match pre-event baseline across the whole cluster, not just the nodes
  you touched.

## Caveats

- These are general MRC recovery principles — org-specific DR mechanics (observer promotion
  policy, failover/failback tooling) live in the linked DR pattern; check that for the actual
  automation your organization uses before executing.
- A "clean" URP count during a rolling restart is a necessary gate, not a sufficient one —
  always pair it with an ISR/ observer status check on an MRC before calling a node fully
  recovered.

## Related

- [DR — Multi-Region Cluster](../../wiki/patterns/dr-multi-region-cluster.md) — the 2.5-cluster
  MRC DR pattern (replica placement, observer promotion, failover/failback mechanics) this
  runbook assumes
