# MRC Conversion — Platform-Level Health Checklist

Pre-flight checks for a cluster that just absorbed a standing active-passive
region into one Multi-Region Cluster (MRC), **before** expanding any topic
replica placement. Confluent's own quorum-node-count check is necessary but
not sufficient — the items below are what a passing quorum check can still
hide.

- [ ] **Cluster identity unified** — every broker's `meta.properties` (or
      `kafka-storage info`) shows the *same* `cluster.id`. Confirms former
      passive-side brokers were actually wiped/reformatted onto the new
      cluster ID, not just network-joined.
- [ ] **Feature/metadata-version consistency** — `kafka-features describe
      --bootstrap-server <host:port>` shows one converged `metadata.version`
      cluster-wide, not drift between the old active-side and old
      passive-side brokers.
- [ ] **`broker.rack` set correctly on every broker** — hard prerequisite for
      replica placement; confirm values match the rack names you intend to
      reference in placement JSON before you write any.
- [ ] **CP version / `inter.broker.protocol.version` consistency** — all
      brokers on the same Confluent Platform version, IBP ≥ 3.3 cluster-wide
      (required if replicas + observers will ever share a rack).
- [ ] **Listener/connectivity plumbing** — `listener.security.protocol.map`
      and `advertised.listeners` correct for the inter-broker/replication
      listener and reachable cross-DC; any controller-only or recently
      broker-only host still has `controller.listener.names` set.
- [ ] **License entitlement** covers the merged cluster (MRC/replica
      placement is a licensed Confluent Server feature) — check brokers that
      came from the original passive side too, not just the active side.
- [ ] **Old DR mechanism fully decommissioned** — Replicator or Cluster
      Linking that ran active→passive is stopped and unregistered; no
      dangling connectors, mirror topics, or ACLs left to collide with
      upcoming reassignment.
- [ ] **Cluster-wide default placement configs decided** —
      `confluent.log.placement.constraints`,
      `confluent.offsets.topic.placement.constraints`,
      `confluent.transaction.state.log.placement.constraints` only apply at
      topic-creation time. Set these at the broker level now if you want
      `__consumer_offsets`/txn-state and new topics to inherit correct
      placement automatically.
- [ ] **Feature-conflict check** — Tiered Storage disabled cluster-wide
      (unsupported with MRC); if Self-Balancing/Auto Data Balancer is in
      use, its rack-awareness config matches the `broker.rack` values above.

## Related

- [DR — Multi-Region Cluster](../../wiki/patterns/dr-multi-region-cluster.md)
- [CP → MRC Live Migration Rehearsal Rig](../../wiki/patterns/cp-mrc-migration-rehearsal-rig.md)
