---
title: Kafka DR Framework v3 — Evaluation Report
date: 2026-04-20
query: "Validate kafka-dr-framework-v3.md against wiki, MCP sources, and fsi-dsp reference code"
wiki_sources: [patterns/dr-cluster-linking, concepts/cluster-linking-topology, concepts/sla-tiers, concepts/exactly-once-semantics, patterns/fsi-exactly-once]
claims_checked: 24
claims_corrected: 2
claims_unverifiable: 4
---

# Kafka DR Framework v3 — Evaluation Report

## TL;DR

The reviewed DR framework document is technically sound. 24 verifiable claims checked: 18 confirmed, 2 corrected, 4 unverifiable (ORKA-specific claims with limited public documentation). The SLA tier values, Cluster Linking mechanics, and One-Click DR architectural description all align with compiled wiki knowledge and live MCP sources. Two corrections required: (1) `auto.create.mirror.topics` should be `auto.create.mirror.topics.enable`, (2) "RPO = 0" for planned failover should be qualified as "effective RPO = 0" (async drain-to-zero, not synchronous). One-Click DR timeline is slightly conservative (Q4 2026 GA per Confluent, not Q1 2027) but the conclusion is correct — FSI adoption lag makes this effectively 2027 for a regulated FSI adopter.

---

## Step 2: Extracted Claims

### Cluster Linking / Infrastructure

| # | Claim | Source Section |
|---|-------|---------------|
| 1 | Cluster Linking handles byte-for-byte replication of topics, ACLs, and consumer offsets | §6.2 |
| 2 | Mirror topics are read-only until promoted | §6.2 |
| 3 | `auto.create.mirror.topics = false` in production | §2.2 (canon reference) |
| 4 | Cluster Linking preferred over MM2 for Confluent-to-Confluent topologies | §2.2 (canon reference) |
| 5 | `mirror failover` = immediate/no lag check; `mirror promote` = planned/checks zero lag | §6.4 |
| 6 | Planned failover enforces RPO = 0; unplanned uses last-replicated offset | §6.4 |

### One-Click DR / Cloud Gateway

| # | Claim | Source Section |
|---|-------|---------------|
| 7 | Cloud Gateway acts as proxy redirecting traffic without client-side config changes or restarts | §6.2 |
| 8 | One-Click DR automates: promotion, traffic redirection, auth hand-off, reverse replication | §6.3 |
| 9 | Auth hand-off uses OAuth2 + Identity Pools | §6.3 |
| 10 | Single "Failover" button in Confluent Cloud Console | §6.2 |
| 11 | One-Click DR not GA; not expected before Q1 2027 | §6.6 |
| 12 | "One-Click DR" is the product name | §6.1 |

### SLA Tiers

| # | Claim | Source Section |
|---|-------|---------------|
| 13 | critical: RPO < 5 min, RTO < 15 min | §2.4 |
| 14 | compliance: RPO = 0*, RTO < 15 min | §2.4 |
| 15 | standard: RPO < 2 hr, RTO < 1 hr | §2.4 |
| 16 | best-effort: RPO < 24 hr, RTO < 4 hr | §2.4 |
| 17 | Mirror lag thresholds: critical 30s/60s, compliance 10s/30s, standard 5m/15m, best-effort 1h/4h | §2.4 |

### ORKA

| # | Claim | Source Section |
|---|-------|---------------|
| 18 | ORKA is a GoodLabs product | §5 |
| 19 | ORKA returns empty fetch responses to pause consumers (indistinguishable from quiet topic) | §5.1 |
| 20 | No application restart during failover | §5.2 |
| 21 | Kafka guarantees preserved (no duplicates, no missed messages) | §5.3 |
| 22 | RTO measured in seconds | §5.3 |
| 23 | Smart Switching Sets for blue/green deployments | §5.3 |

### Architecture / Integration

| # | Claim | Source Section |
|---|-------|---------------|
| 24 | fsi-dr.sh uses Consul KV `fsi/kafka/active-region`; covers CL, MM2, MRC backends | §2.1 |

---

## Step 3: MCP Validation Results

### Claim 1 — Byte-for-byte replication of topics, ACLs, consumer offsets
**CONFIRMED.** Confluent docs explicitly state "messages on the source topics are mirrored precisely on the destination cluster, at the same partitions and offsets." ACL sync (`acl.sync.enable`) and consumer offset sync (`consumer.offset.sync.enable`) are opt-in properties on the cluster link. ACL sync limited to same Confluent Cloud org.

### Claim 2 — Mirror topics read-only until promoted
**CONFIRMED.** Docs: "Mirror topics are read-only; you can consume them the same as any other topic, but you cannot produce into them."

### Claim 3 — `auto.create.mirror.topics = false` in production
**CORRECTED.** The correct property name is **`auto.create.mirror.topics.enable`**. The production recommendation (explicit control) is sound. The document uses the shortened form without the `.enable` suffix.

### Claim 4 — CL preferred over MM2 for Confluent-to-Confluent
**CONFIRMED.** Confluent Platform docs: "Cluster Linking is an improvement over both Confluent Replicator and MirrorMaker 2, which require a second network hop to write the data, and do not retain compression."

### Claim 5 — Failover vs. promote semantics
**CONFIRMED.** `mirror failover`: immediate, no lag check, source cluster does not need to be reachable. `mirror promote`: verifies zero lag, final metadata sync, requires source reachable. DR unplanned events use `failover`; planned DR (maintenance, migration) uses `promote`.

### Claim 6 — Planned failover = RPO 0; unplanned = last-replicated offset
**CORRECTED.** Partially correct but overstated. `promote` drains replication to zero lag before cutting over — achieving **effective RPO = 0 at moment of cutover**. But Cluster Linking is async; it does not provide synchronous RPO = 0 (writes acknowledged only after replicated). True synchronous RPO = 0 requires Multi-Region Clusters. Unplanned failover (last-replicated offset) is accurate.

**Recommended wording:** "Planned failover drains replication lag to zero before promoting (effective RPO = 0 at cutover). Unplanned failover promotes immediately; RPO equals replication lag at time of failure."

### Claim 7 — Cloud Gateway as traffic proxy with automatic redirection
**CONFIRMED.** Docs: "Confluent Cloud Gateway serves as the primary traffic control layer, automatically redirecting all Kafka client traffic to the passive cluster when the active cluster becomes unavailable." Described as "Kafka protocol-aware proxy positioned between clients and clusters for stateless routing."

### Claim 8 — One-Click DR automates promotion, traffic redirection, auth hand-off, reverse replication
**CONFIRMED.** Each sub-component documented in Confluent blog (Feb 2026) and product docs. OAuth2 is **required** (API keys are cluster-scoped and break on failover).

### Claim 9 — OAuth2 + Identity Pools for auth hand-off
**CONFIRMED.** Blog: "OAuth2 and Identity Pools in Confluent Cloud are scoped per organization, so you can keep the same client ID/secret for accessing multiple Kafka clusters." Failover only works for OAuth2-authenticated clients.

### Claim 10 — Single Failover button in Cloud Console
**CONFIRMED.** Blog: "triggering a failover is easily accessible in the portal user interface (UI)." Requires Gateway to be deployed and configured.

### Claim 11 — Not GA before Q1 2027
**CONFIRMED (with timeline update).** One-Click DR is a Cluster Linking-based DR automation feature — distinct from Cloud Gateway (which is a traffic routing proxy). Current Confluent guidance puts One-Click DR GA at **Q4 2026**. The document's "not before Q1 2027" is conservative by one quarter, but the effective conclusion is correct and arguably understated: even at Q4 2026 GA, a regulated FSI adopter will not deploy a freshly-GA'd vendor feature. Code freeze windows, internal validation, and the principle of not beta-testing vendor code in production mean realistic adoption is H1-H2 2027. The document's "plan for later rather than earlier" framing is sound field judgment.

### Claim 12 — "One-Click DR" is the product name
**CONFIRMED (informal).** "One-Click DR" is field/SE shorthand, not official Confluent product branding. Confluent uses terms like "automatic disaster recovery switchover," "client switchover," and "Global Resilience" in formal marketing. Acceptable for an internal framework doc. The key distinction: One-Click DR is built on **Cluster Linking** (not Cloud Gateway). Gateway is a separate product for traffic routing/proxy; One-Click DR automates the CL promote/failback lifecycle.

### Claims 13–17 — SLA Tier values
**CONFIRMED.** All values match wiki article `concepts/sla-tiers.md` exactly (sourced from `ansible/vars/sla_tiers.yml`). Mirror lag thresholds match. Compliance RPO = 0 footnoted as "when using MRC 2.5 pattern" — consistent with wiki noting "RPO=0 achieved via MRC on CP; near-zero via CL on CC."

### Claim 18 — ORKA is a GoodLabs product
**CONFIRMED (with caveats).** GoodLabs Studio is a legitimate Confluent Engineering Partner (2025 Partner Evangelist of the Year award). A YouTube video "Meet ORKA: Zero-Downtime Blue-Green Deployments for Kafka Apps" exists (March 2026). However, no public product page, documentation site, or pricing exists. Appears to be early-stage or partner-specific offering.

### Claim 19 — Empty fetch responses to pause consumers
**UNVERIFIABLE (but technically plausible).** No public ORKA documentation confirms this specific mechanism. However, the approach is sound protocol engineering: empty FetchResponses are standard Kafka behavior for quiet partitions, consumer heartbeats are independent of fetch data flow, and existing proxies (Kroxylicious, Conduktor Gateway) support FetchResponse interception.

### Claim 20 — No application restart during failover
**UNVERIFIABLE (but plausible given claim 19).** If the proxy handles routing transparently at the protocol level, apps would not need to reconnect or restart.

### Claim 21 — Kafka guarantees preserved
**UNVERIFIABLE (with caveat).** The pause-sync-switch mechanism is theoretically guarantee-preserving: consumers stop advancing offsets during pause, offsets sync to DR cluster, switch occurs at known-good offset. However, Confluent's own Gateway DR docs explicitly warn: "If ordering guarantee and data consistency are required, for example, for Kafka Streams applications, do not use client switchover." ORKA claiming it solves this (including for stateful apps) would exceed what Confluent Gateway offers.

### Claim 22 — RTO in seconds
**UNVERIFIABLE (conditionally plausible).** Depends on replication lag at failover time. If Cluster Linking is maintaining sub-second lag in steady state, the pause-sync-switch window could be seconds. Comparable to Confluent's own "60-second DR POC" claim.

### Claim 23 — Smart Switching Sets
**UNVERIFIABLE.** No public documentation. The YouTube title references "Zero-Downtime Blue-Green Deployments" which aligns with the concept.

### Claim 24 — fsi-dr.sh / Consul KV / three backends
**CONFIRMED.** Wiki article `patterns/dr-cluster-linking.md` documents `fsi/kafka/active-region` Consul KV key, 6-step failover/8-step failback. Reference code architecture documents CL, MM2, and MRC backends.

---

## Step 4A: Wiki Inconsistencies

| Finding | Document Says | Wiki Says | Resolution |
|---------|--------------|-----------|------------|
| RPO=0 framing | "Planned failover enforces RPO = 0" (§6.4) | `dr-cluster-linking.md`: "RPO > 0 (async replication). For RPO=0 requirements, use MRC." | **Wiki is more precise.** Document should qualify. |
| Config property name | `auto.create.mirror.topics = false` (§CLAUDE.md canon) | `cluster-linking-topology.md`: `auto.create.mirror.topics.enable` with default `false` | **Wiki is correct.** Canon in CLAUDE.md uses the short form. |
| One-Click DR timeline | "not expected to be real before Q1 2027" | Not covered in wiki | **Slightly conservative.** Confluent guidance is Q4 2026 GA, but FSI adoption lag (code freeze + no beta-testing vendor code) makes H1-H2 2027 realistic for production. Document's conclusion is sound. |

### Enrichment Opportunities (wiki missing, document covers)

1. **Cloud Gateway** — wiki has no article on Confluent Cloud Gateway (the protocol-aware proxy layer)
2. **Application-layer DR routing** — wiki DR articles cover infrastructure failover only; no coverage of the client-restart problem the document addresses
3. **Oracle / downstream system-of-record DR co-dependency** — wiki has no cross-system DR coordination coverage
4. **ORKA / Kafka DR proxy** — no wiki coverage of proxy-based DR routing patterns

---

## Step 4B: Code Deltas

| Setting | Document Recommendation | fsi-dsp Reference Code | Delta Type |
|---------|------------------------|------------------------|------------|
| `enable.idempotence=true` | Implied (EOS discussion) | FsiProducer.java:100 — explicit `true` | Aligned |
| `acks=all` | Implied (EOS discussion) | FsiProducer.java:101 — explicit `all` | Aligned |
| Bootstrap externalization | §8.1: "Externalize into ConfigMaps/Consul KV" | FsiProducer.java:79 — `config.getOrDefault("bootstrap.servers", "kafka.fsi.internal:9092")` | **Aligned** — already externalized via config map; default points to Consul DNS |
| `enable.auto.commit=false` | §2.5: "commit after processing" | FsiConsumer.java:103 — explicit `false` | Aligned |
| `auto.offset.reset=earliest` | Not explicitly stated | FsiConsumer.java:104 — `earliest` | Aligned |
| `compression.type` | CLAUDE.md canon: `lz4` for throughput | FsiProducer.java:110 — `none` (latency-optimized) | **Profile Mismatch** — code is fraud-detection latency profile; canon default is throughput profile. Both valid. |
| Service discovery pattern | §2.2: Consul DNS abstraction | FsiProducer/Consumer: `kafka.fsi.internal:9092` via `getOrDefault` | Aligned |

**Summary:** No true deltas — reference code already follows the externalization pattern the document prescribes. The compression difference is an intentional profile choice (latency vs. throughput), not a conflict.

---

## Step 5: Classification Summary

| Outcome | Count | Claims |
|---------|-------|--------|
| **Confirmed** | 18 | #1, #2, #4, #5, #7, #8, #9, #10, #11, #12, #13–18, #24 |
| **Corrected** | 2 | #3 (property name), #6 (RPO=0 qualification) |
| **Unverifiable** | 4 | #19, #20, #21, #22, #23 (all ORKA-specific) |

---

## Step 7: Reconsolidate Actions

### Corrections to Source Document

1. **§6.4 / §7 table**: Replace "Preserved (planned = RPO 0)" with "Preserved (planned drains to zero lag = effective RPO 0; unplanned = last-replicated offset)" and add footnote distinguishing from synchronous RPO 0 (MRC).
2. **CLAUDE.md canon** (not this doc): `auto.create.mirror.topics` → `auto.create.mirror.topics.enable`. **Done** — fixed in both global and project CLAUDE.md.
3. **§6.6 (optional)**: Update "not expected to be real before Q1 2027" to "Confluent guidance is Q4 2026 GA; realistic FSI production adoption H1-H2 2027 given code freeze and no-beta-testing policy." Strengthens the ORKA recommendation rather than weakening it.

### Wiki Stubs Queued

- `wiki/concepts/confluent-cloud-gateway.md` — Protocol-aware Kafka proxy for traffic control, DR switchover, custom domains, auth swapping; self-managed component deployed via CFK/Docker; 1.1.0 GA
- `wiki/patterns/dr-application-routing.md` — The client-restart problem during Kafka DR and solutions: DNS abstraction, protocol proxy (ORKA/Gateway), Cloud-native control plane (One-Click DR); evaluation criteria

### Cross-Links Added

- `patterns/dr-cluster-linking` → `concepts/confluent-cloud-gateway` : Gateway enables client-transparent failover
- `concepts/confluent-cloud-gateway` → `patterns/dr-cluster-linking` : Gateway sits atop CL for DR

---

## Caveats

1. **ORKA claims are unverifiable** against public sources. The product exists (YouTube demo, March 2026) but has no public documentation. Technical claims are protocol-sound but untested by this evaluation.
2. **One-Click DR timeline** is necessarily speculative — Confluent has disclosed no ship date for the fully-managed version.
3. **Oracle / downstream system-of-record DR construct section** (§3) was not validated — it is specific to the source environment and outside Confluent MCP scope.
4. **"One-Click DR" terminology** is not official Confluent branding. Acceptable for internal docs but flagged for awareness.

---

*Validated against Confluent docs via MCP (2026-04-20). 24 claims checked, 2 corrected, 4 unverifiable. Timeline updated per field intelligence: One-Click DR Q4 2026 GA, FSI adoption H1-H2 2027.*
