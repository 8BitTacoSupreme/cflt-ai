# Review: OIC → Confluent Cloud: Acks=All Timeout Triage

**Date:** 2026-04-29
**Source files:** `oic_cc_acks_all_timeouts.md` (external triage doc)
**Scope:** Kafka producer configuration, Confluent Cloud cluster settings, cross-cloud networking (OCI→Azure), FSI data integrity, acks=all timeout troubleshooting
**Claims extracted:** 26

## Summary

Strong operational triage document with accurate producer configuration defaults and sound architectural guidance on alerting ownership. Two corrections: the `delivery.timeout.ms` constraint is misstated (actual: `≥ linger.ms + request.timeout.ms`, not `≥ 2× request.timeout.ms`), and the compression claim is ambiguous about whose "default" GZIP is. Canon compliance is high — the document correctly prescribes `acks=all`, idempotence, RF=3, `min.insync.replicas=2`. The `connections.max.idle.ms=180000` recommendation aligns with wiki guidance for Azure ILB idle timeout mitigation.

## Claim Validation

### Alerting Strategy

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| oic-1 | Topic-level alerts (zero msgs in 5 min, 70% drop-off) do not detect acks=all timeout failures | — | — | Confirmed |
| oic-2 | Idempotent retries on acks=all timeouts often succeed on next attempt — result is latency spikes and duplicates, not traffic gaps | concepts/exactly-once-semantics | — | Confirmed |
| oic-3 | The producer is the only authoritative source for delivery success | concepts/producer-batching-config | — | Confirmed |

**Notes:**
- Claim oic-1: Correct reasoning — idempotent retry success masks the failure from topic-level volume metrics. The failure presents as latency, not data loss.
- Claim oic-2: Wiki confirms idempotent producer deduplicates at the broker via PID + sequence numbers, so retries don't create broker-side duplicates. However, the document says retries produce "duplicates" — this is slightly imprecise. With `enable.idempotence=true` (which the document prescribes), broker-side duplicates are prevented. The duplicates risk is only if idempotence is disabled or if the producer epoch rolls over.

### Section 1: OIC Adapter — Producer Properties

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| oic-4 | acks=all — strict requirement for FSI data integrity | concepts/exactly-once-semantics, patterns/fsi-exactly-once | canon: producer.acks=all | Confirmed |
| oic-5 | enable.idempotence=true — required with acks=all | concepts/exactly-once-semantics | — | Confirmed |
| oic-6 | max.in.flight.requests.per.connection=5 — required ≤ 5 when idempotence on; preserves ordering | concepts/exactly-once-semantics, concepts/producer-batching-config | — | Confirmed |
| oic-7 | request.timeout.ms=60000 — extends wait for broker ACKs to absorb cross-cloud RTT | concepts/producer-batching-config | — | Confirmed |
| oic-8 | delivery.timeout.ms=120000 — must be ≥ 2× request.timeout.ms | concepts/producer-batching-config | — | Corrected |
| oic-9 | retry.backoff.ms=1000 — 1s between retries prevents hammering during ISR shrinks | — | — | Confirmed |
| oic-10 | linger.ms=50 — batches small FSI messages for throughput on high-latency links | concepts/producer-batching-config | — | Confirmed |
| oic-11 | batch.size=65536 — 64KB batch ceiling | concepts/producer-batching-config | — | Confirmed |
| oic-12 | connections.max.idle.ms=180000 — 3 min, under Azure's 4-min LB idle timeout | patterns/aks-kafka-tuning | — | Confirmed |
| oic-13 | max.block.ms=60000 — prevents hanging on full producer buffer | concepts/producer-batching-config | — | Confirmed |

**Corrections:**
- **Claim oic-8:** The document states `delivery.timeout.ms` "Must be ≥ 2× request.timeout.ms." The actual Kafka constraint is `delivery.timeout.ms >= linger.ms + request.timeout.ms` (see producer-batching-config wiki article). With the document's own values (linger.ms=50, request.timeout.ms=60000), the minimum is 60,050ms — not 120,000ms. The value of 120,000ms is fine (it's the Kafka default), but the stated "2×" rule is incorrect and could mislead tuning in other scenarios. Source: [Apache Kafka 4.1 Producer Configs](https://kafka.apache.org/41/configuration/producer-configs/).

### Implementation Tips

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| oic-14 | OIC adapter only supports GZIP; zstd not supported and will break the connection | — | — | Unverifiable |
| oic-15 | "GZIP (the default)" | concepts/producer-batching-config | — | Corrected |
| oic-16 | Shared or regenerated transactional IDs cause ProducerFenced errors | patterns/fsi-exactly-once, concepts/exactly-once-semantics | — | Confirmed |
| oic-17 | Producer exception class is the single most valuable triage signal | — | — | Confirmed |

**Corrections:**
- **Claim oic-15:** The document says "the OIC adapter only supports GZIP (the default)." If "the default" refers to Kafka's `compression.type`, this is incorrect — Kafka's default is `none`, not `gzip` (see producer-batching-config wiki: `compression.type: none`). If it refers to OIC's default, this cannot be verified against our knowledge base. Recommend clarifying: "GZIP (OIC's default)" or removing the parenthetical.

- **Claim oic-14:** The OIC adapter's compression constraints are OCI-platform-specific. Our wiki has no coverage of Oracle Integration Cloud. Canon default is `lz4` for throughput. The document correctly advises against setting compression.type when the platform constrains it, but this claim cannot be verified.

### Section 2: CC Cluster Settings

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| oic-18 | min.insync.replicas = RF − 1 (2 for RF=3) | concepts/sla-tiers | canon: min_insync_replicas=2 | Confirmed |
| oic-19 | If min.insync.replicas = RF, any single broker maintenance blocks all acks=all writes | concepts/exactly-once-semantics | — | Confirmed |
| oic-20 | replication.factor = 3 on prod topics | concepts/sla-tiers | canon: replication_factor=3 | Confirmed |
| oic-21 | compression.type = producer on the topic prevents broker recompression | concepts/producer-batching-config | — | Confirmed |
| oic-22 | No single partition should carry >5–10 MB/s | — | — | Confirmed |
| oic-23 | Basic/Standard CC clusters can throttle bursty OIC — Dedicated/Enterprise for production FSI | — | — | Confirmed |

### Section 3: Triage Data

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| oic-24 | Three triage layers required: producer, cluster, network | — | — | Confirmed |
| oic-25 | Azure ILB 4-min default idle timeout is a classic offender | patterns/aks-kafka-tuning | — | Confirmed |
| oic-26 | TCP retransmit rate >0.5% sustained = the cause | — | — | Unverifiable |

## Premise Challenge

| # | Premise | Assumption | Challenge | Severity |
|---|---------|------------|-----------|----------|
| 1 | The intermittent failures are caused by idle connection timeouts | Azure ILB or a middlebox silently kills idle TCP connections at ≤4 min | The document labels `connections.max.idle.ms=180000` as "most likely root cause" without confirming via `connection-close-rate` JMX metric. If the OIC adapter produces continuously (no idle gaps), this fix has no effect. The actual root cause could be ISR shrinks, DNS staleness, or Private Link endpoint health — all listed in Section 3 but not prioritized. | Moderate |
| 2 | OIC exposes all listed Kafka producer properties | The "Additional Properties" table in OIC Connection UI accepts arbitrary `key=value` pairs that pass through to the underlying Kafka producer | Some managed integration platforms restrict or ignore producer properties. If OIC's adapter overrides or ignores `connections.max.idle.ms` or `request.timeout.ms`, the tuning is ineffective. The document should confirm which properties OIC honors vs. ignores. | Critical |
| 3 | The Connectivity Agent JVM is instrumentable with JMX | Adding `-Dcom.sun.management.jmxremote.*` flags to the agent startup script is operationally feasible | The Connectivity Agent may be a managed/containerized process with restricted JVM flag injection. The security posture (`authenticate=false`) is flagged in the document but may be unacceptable in FSI environments without mTLS or localhost binding. | Moderate |
| 4 | Cross-cloud RTT justifies 60s request timeout | OCI→Azure interconnect latency is high enough that the default 30s request.timeout.ms is insufficient | Without measured RTT data, the timeout values are guesses. If actual RTT is <50ms, the 60s timeout masks real failures (slow ISR, broker overload) by waiting too long before surfacing errors. | Minor |

## Canon Compliance

| Area | Status | Notes |
|------|--------|-------|
| Producer: acks | Compliant | `acks=all` matches canon |
| Producer: idempotence | Compliant | `enable.idempotence=true` matches canon |
| Producer: compression | Deviates (justified) | Canon default is `lz4`; document advises not setting compression due to OIC GZIP-only constraint. Valid platform limitation. |
| Topic: replication.factor | Compliant | RF=3 matches canon |
| Topic: min.insync.replicas | Compliant | 2 matches canon |
| Security | Not covered | Document does not address auth mechanism. Canon requires mTLS + RBAC for FSI. Out of scope for this triage doc. |
| Schema Registry | Not covered | No schema governance discussion. Out of scope. |
| Topic naming | Not covered | No naming convention discussion. Out of scope. |

## Gaps

| # | Claim | Topic | Notes |
|---|-------|-------|-------|
| oic-14 | OIC adapter only supports GZIP | OCI Integration Cloud Kafka constraints | No wiki coverage of OIC/Oracle integration patterns |
| oic-26 | TCP retransmit rate >0.5% sustained | Network-level triage thresholds | No wiki coverage of network retransmit thresholds for Kafka |

## Recommendations

1. **Fix the `delivery.timeout.ms` constraint statement.** Change "Must be ≥ 2× request.timeout.ms" to "Must be ≥ linger.ms + request.timeout.ms" — the actual Kafka constraint. The chosen value (120000) is correct; the stated rule is not.

2. **Clarify the GZIP default attribution.** Change "GZIP (the default)" to "GZIP (OIC's default)" to avoid confusion with Kafka's `compression.type` default of `none`.

3. **Validate OIC property passthrough.** Before deploying the properties table, confirm with the OIC team which properties the adapter actually honors vs. silently ignores. This is the highest-risk premise in the document.

4. **Add measured RTT baseline.** Include an `iperf3` or `ping` measurement between the Connectivity Agent and the CC Private Link endpoint. Without baseline RTT, the timeout tuning is directional but ungrounded.

5. **Address the idempotency/duplicates language.** The alerting section says retries produce "duplicates" — but with `enable.idempotence=true` (prescribed in the same document), broker-side duplicates are prevented. Clarify that the duplicate risk is at the application layer if the producer epoch rolls over, not at the broker layer under normal retry.

---

Canon stack: base + industry/fsi | Hash: b6a3cf22b1438242 | MANIFEST: 1.0.0 | Floor: claude-opus-4-6 | Generated: 2026-04-29T18:00:00Z
