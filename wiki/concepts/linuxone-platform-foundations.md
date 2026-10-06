---
title: LinuxONE Platform Foundations
tags: [linuxone ibm s390x stp ctn cbu smc-r roce uko keys telum spyre crun fsi]
sources:
  - https://www.ibm.com/products/linuxone/ai-processor
  - https://github.com/IBM/zDNN
  - https://github.com/IBM/zDLC
  - https://www.ibm.com/products/ai-toolkit-for-z-and-linuxone
  - https://www.ibm.com/docs/en/linux-on-systems
  - https://www.ibm.com/products/unified-key-orchestrator
related: [concepts/linuxone-kafka-integration, concepts/fsi-compliance, concepts/fsi-data-streaming-platform, patterns/linuxone-validation-suite, patterns/linuxone-kafka-tuning, patterns/linuxone-flink-validation-tuning, patterns/fsi-l1-reference-architecture]
confidence: medium
last_updated: 2026-05-07
last_validated: 2026-05-07
---

# LinuxONE Platform Foundations

## Summary

L1-specific platform concerns that span Kafka, Flink, and the operational data layer: time synchronization, capacity management, cross-frame transport, key lifecycle, on-frame AI accelerators, and container runtime. Pulled out as a single concept doc so the four LinuxONE pattern docs can reference these foundations without each duplicating the prose. None of these are FSI-optional — STP and key lifecycle are regulator's-third-question material; CBU is an SOW economics lever; SMC-R is the difference between sub-millisecond and "sub-50ms is fine" cross-frame replication.

## Detail

### Server Time Protocol (STP)

IBM Z Server Time Protocol provides sub-microsecond clock synchronization across CECs (frames) using a **Coordinated Timing Network (CTN)**. STP is the canonical mechanism for keeping audit-log timestamps and Flink event-time semantics consistent across a dual-frame deployment.

**Why this matters for FSI:**

- Audit log timestamps used for regulatory submissions must be coherent across all sources. If frame 1 and frame 2 disagree by >100 µs, post-incident forensics produce inconsistent event ordering and the audit story falls apart.
- Flink event-time watermarks across operators on different LPARs / frames depend on a shared clock. Drift creates spurious "late" events and watermark stalls.
- This is **the regulator's third question** after "where does the data live" and "who can decrypt it."

**Configuration:**

- Single CTN spanning frame 1 and frame 2 (and the paired DC frames if MRC stretches there).
- Stratum-1 server selected from the CTN; backups configured.
- Validate sync state via z/VM `Q STP` or `chsccfg --query` (Linux side); drift bound is sub-microsecond between CTN members.

**Fallback (PTP/NTP):**

- If STP cannot be deployed (mixed-vendor data center, smaller customer footprint), use **PTP (IEEE 1588)** with hardware timestamping NICs as the next-best option. NTP is too coarse (~1–10 ms) for sub-millisecond pipelines.
- Document measured drift bounds in the validation suite; alert on drift > 100 µs.
- Process for detection: external time auditor every 24 h compares local clocks against an authoritative source.

### Capacity Backup Upgrade (CBU) / On/Off Capacity on Demand

IBM Z's mechanism for activating reserved IFL capacity only during a declared disaster. **The DR economics of LinuxONE depend on CBU** — without it, you would pay full IFL pricing for a passive DR frame.

**Sizing pattern:**

- Frame 1 (primary): `n` IFLs base, sized for steady-state production.
- Frame 2 (DR): `n` IFLs base sized for DR-tier workloads, plus `m` CBU IFLs (typically `m ≈ n × 0.5` to allow primary-equivalent capacity post-failover).
- CBU activates within hours of disaster declaration via IBM-provided tooling; the customer pays only for the activated days.

**Sizing implications:**

- Sizing math should explicitly call out base IFLs vs CBU IFLs, with CBU activation cost modeled as a per-incident variable rather than a recurring one.
- For a partner sizing doc, CBU is a real lever: customers can be sold a smaller DR frame on day one with confidence in the elasticity story.

### Cross-frame Transport: SMC-R over RoCE Express

Three transports in the L1 networking stack, each with a specific fit:

| Transport | Scope | Latency floor | Use |
|-----------|-------|---------------|-----|
| **SMC-D** (Shared Memory Communications - Direct) | Inter-LPAR, same CEC | < 200 µs p99 | Intra-frame Kafka producer ↔ broker, broker ↔ broker |
| **HiperSockets** | Inter-LPAR, same CEC | < 800 µs p99 | Intra-frame fallback when SMC-D not available; firmware switch |
| **SMC-R over RoCE Express** | Inter-CEC, same data center | < 100 µs link-layer + cable | **Cross-frame** Kafka replication, MRC quorum, CL on-campus, store-native replication |
| **OSA-Express** | Off-CEC, off-campus | 2–5 ms (TCP overhead + WAN) | Egress to off-campus targets only (CC, Databricks, Snowflake) |

**Why SMC-R for cross-frame:**

SMC-R provides the same TCP-stack-bypass advantage as SMC-D, but works across the RoCE fabric instead of in-frame shared memory. Cross-frame replication that goes through OSA-Express adds 2–5 ms p99 — fine for analytics, fatal for compliance-tier MRC quorum (which needs sub-50 ms RTT for the latency budget to close).

**Configuration:**

- RoCE Express adapters in both frames, connected via the data-center RoCE fabric.
- Linux kernel SMC module loaded: `modprobe smc`.
- Application launched via `smc_run` wrapper (same as SMC-D usage on the intra-frame side); the wrapper auto-selects SMC-D or SMC-R based on peer locality.

### Unified Key Orchestrator (UKO) and Key Lifecycle

The crypto-algorithm story (FIPS 140-3 via CEX8S, BCFIPS provider) covers *how* data is encrypted but says nothing about **where keys live** and **how they rotate**. For an FSI audit, the key lifecycle question is mandatory.

**On-frame:**

- TLS server certificates and private keys stored in **CEX8S in EP11 mode** (FIPS 140-3 hardware keystore, never extractable).
- Master keys for topic-payload encryption (if used) bound to CEX8S.
- Schema Registry signing keys (if SR runs in mTLS+signed mode) similarly HSM-bound.
- OAUTHBEARER signing key (the JWT signer) — same.

**Off-frame federation:**

- **IBM Unified Key Orchestrator (UKO) for IBM Z** is the IBM-bundled path for managing keys across CEX8S, external HSMs, and z/OS DKMS via KMIP. Single pane for FSI key lifecycle: rotation policy, backup, escrow.
- **External HSM via KMIP** (Thales, Entrust, etc.) — alternative for customers with existing HSM standards.

**Compliance-tier topic encryption — choose deliberately:**

- **Option A (most FSI deployments):** TLS-in-flight + at-rest encryption from the storage layer (broker disk, COS bucket). Simpler, audit-friendly, no client-side complexity.
- **Option B (regulator pushes for "encryption keys never leave the customer"):** Client-side payload encryption using keys served by UKO, encryption applied in the producer / Flink UDF before the record hits the broker. More invasive, but defends against any cloud-side compromise.
- The choice has audit implications and **must be stated in the SOW**, not left to the implementer.

### Spyre Integration Boundary for Flink

LinuxONE Emperor 5 ships with two on-frame AI accelerator paths. Choose at compile time per model class:

| Tier | Hardware | Programming surface | Latency class | Model size |
|------|----------|---------------------|---------------|------------|
| **Telum II NNPA** | On-chip accelerator, integrated into the CPU | zDNN library; ONNX → zDLC → JNI | ~150–300 µs | Up to ~1B params (DLM-class fraud / AML / risk scoring) |
| **IBM Spyre** | PCIe accelerator card (Spyre Accelerator), separate from Telum | Spyre runtime; targeted compile path | ~500 µs – 1 ms | Larger models (transformers, larger CV, foundation-model-class) up to multi-billion params |

**Decision flow:**

1. Train model off-platform (Databricks, internal MLOps).
2. Export to ONNX.
3. **If model fits NNPA capacity** (parameter count, supported ops): compile with zDLC for NNPA target → JNI JAR → Flink UDF. Runs in-process on the LPAR; ~250 µs class.
4. **If model exceeds NNPA capacity**: compile with Spyre toolchain → Spyre runtime invocation from the Flink UDF. Runs over PCIe to the Spyre card on the same frame; ~500 µs – 1 ms class.

The decision is **at compile time**, not runtime. A given model artifact targets one path. Don't try to runtime-fall-back from NNPA to Spyre — make the deployment choice explicit.

**Two-tier inference is a real differentiator** vs. anything x86/GPU can offer: the small fraud-class model runs in-process on Telum II (network-hop-free), the larger AML / NLP / payment-context model runs on Spyre on the same frame (PCIe-bound but no network hop). x86 + GPU adds a 5–15 ms p99 network hop for either model.

### Container Runtime: crun on s390x

For container density on OpenShift Container Platform on LinuxONE (or any RHEL-9-based container host on s390x):

- **crun** outperforms runc for container start time (~2× faster cold start) and memory footprint (~30% lower per-container overhead) on s390x.
- crun is the upstream default in RHEL 9.
- On OCP, pin via `ContainerRuntimeConfig` resource or the `MachineConfig` for the worker pool.

This matters for the [LinuxONE Validation Suite §5.4](../patterns/linuxone-validation-suite.md) container-density target (30 broker containers per LPAR on z/VM, equivalent on OCP).

### IBM Benchmark Anchors

A single place where the four LinuxONE pattern docs anchor performance claims. Update this section as IBM publishes new reference benchmarks; pattern docs cite back here rather than embedding numbers.

| Claim | Anchor source | Notes |
|-------|---------------|-------|
| Sub-ms in-process inference on Telum II | [IBM Telum II AI processor product page](https://www.ibm.com/products/linuxone/ai-processor) | Reference: 5M ops/s at p99 < 1 ms for credit-card fraud DLM on Emperor 5 |
| Up to 450B inference operations/day with sub-ms response times | IBM Telum II announcement (Hot Chips 2024 / GA 2025) | Anchors §4.4 Latency Budget in [Flink Validation & Tuning](../patterns/linuxone-flink-validation-tuning.md) |
| HiperSockets latency floor (~800 µs p99 for 1 KB) | IBM HiperSockets technical white papers | Cited in [Validation Suite §5.4 HiperSockets Latency Floor](../patterns/linuxone-validation-suite.md) |
| SMC-D / SMC-R latency advantage | IBM SMC technical references | Cited in [Kafka Tuning § LinuxONE Overlay](../patterns/linuxone-kafka-tuning.md) |
| CEX8S throughput sustaining mTLS workloads | IBM Crypto Express 8S product brief | Cited in [Validation Suite §5.4 Crypto Express FIPS Throughput](../patterns/linuxone-validation-suite.md) |

> **Action:** IBM publishes Emperor 5 fraud-detection benchmark results, HiperSockets latency white papers, and CEX8S throughput data — pin specific URLs and document versions here as they become available rather than relying on directional citations.

## Related

- [LinuxONE Kafka Integration](linuxone-kafka-integration.md) — frame-level architectural rationale for the L1 + Kafka bridge pattern
- [FSI Compliance](fsi-compliance.md) — audit trail requirements that STP and key lifecycle satisfy
- [FSI Data Streaming Platform](fsi-data-streaming-platform.md) — platform layer that this concept doc supports
- [LinuxONE Validation Suite](../patterns/linuxone-validation-suite.md) — exercises the foundations defined here
- [LinuxONE Kafka Tuning](../patterns/linuxone-kafka-tuning.md) — references SMC-D/SMC-R, CEX8S, JDK posture
- [LinuxONE Flink Validation & Tuning](../patterns/linuxone-flink-validation-tuning.md) — references Telum II / Spyre boundary
- [FSI L1 Reference Architecture](../patterns/fsi-l1-reference-architecture.md) — references CBU sizing, UKO key lifecycle, MRC stretch transport
