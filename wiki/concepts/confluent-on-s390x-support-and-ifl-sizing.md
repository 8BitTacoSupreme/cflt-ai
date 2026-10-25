---
title: Confluent on s390x — Support Matrix and IFL Sizing
tags: [linuxone ibm s390x confluent-platform cfk flink sizing ifl smt capacity-planning fsi]
sources: [outputs/reports/confluent-on-linuxone-ifl-bill-of-materials.md]
related: [concepts/linuxone-platform-foundations, concepts/linuxone-kafka-integration, patterns/linuxone-on-cfk-reference-architecture, concepts/fips-at-install-ocp-requirement, concepts/s390x-custom-image-build-pipeline, patterns/x86-to-linuxone-cluster-linking-migration]
confidence: high
last_updated: 2026-10-25
last_validated: 2026-10-25
---

# Confluent on s390x — Support Matrix and IFL Sizing

## Summary

Confluent Platform supports **s390x (Linux on IBM Z) from CP 8.2.0**, including Confluent for Kubernetes (CFK) and Confluent Platform for Apache Flink (CMF). Confluent publishes **no LinuxONE-specific sizing** — its hardware guidance is explicitly architecture-agnostic, stating that "the CPU resource requirement is the same for all platforms." Translating that guidance to IFLs is therefore something you do locally, and it turns on one fact: under **SMT-2**, each IFL (a physical Z core) presents **2 logical CPUs** to Linux, and Kubernetes schedules against those logical CPUs. So `physical IFLs = Σ vCPU ÷ 2` for schedulable capacity — with the caveat that SMT-2 yields ~1.4–1.7× throughput, not a true 2×.

> **Validation status (confidence: high).** Support matrix and per-component hardware table validated 2026-07-09 against `confluent-docs` (CP 8.2/8.3 *System Requirements* and *Linux on IBM Z (s390x) support*). The **throughput→IFL bands and per-tier BOM are a GoodLabs field heuristic, not Confluent canon** — clearly marked below. Do not cite them as vendor guidance.

## Detail

### The s390x support matrix (CP 8.2.0+)

| Supported on s390x | Not yet supported on s390x |
|---|---|
| CP install via RPM, Debian, Tarball | FIPS mode |
| CP Docker images | IPv6 |
| **Confluent for Kubernetes (CFK)** | Unified Stream Manager Agent |
| **Confluent Platform for Apache Flink** | Connectors that rely on native OS libraries |
| Confluent CLI | |
| Most connectors | |

Three things that are easy to get wrong:

1. **The version floor is CP 8.2.0.** Earlier CP releases ship no s390x artifacts at all. Pin no lower.
2. **Linux on IBM Z only — z/OS is not supported.** For Kafka Connect against mainframe data sources on z/OS, use the Connect-on-z/OS bridge (see [LinuxONE Kafka Integration](linuxone-kafka-integration.md) for the canonical IBM MQ Source Connector pattern).
3. **Running CP on Z requires a separate IBM Z software entitlement**, purchased through IBM sales. Productized as **IBM Confluent Platform for Z and LinuxONE**.

#### Read the "not yet supported" column carefully

Every item in that column is a **CP-layer statement, not a platform statement.** s390x, RHEL, and OpenShift support IPv6, FIPS, and native libraries perfectly well; the claim is about Confluent Platform's s390x build. Two consequences:

- **Design to the published matrix, and re-check it at kickoff.** The list moves as Confluent adds s390x capabilities. A vendor statement that contradicts the matrix must be in writing and recorded in the BOM before it changes a design; until then the docs page is the source of truth.
- **`FIPS mode` means CP FIPS mode, and it is not yet supported on s390x** (re-checked 2026-10-25 against the 8.3 docs). Until Confluent lists it, a tier whose policy requires FIPS 140 validated crypto on the brokers runs its brokers on x86/ARM. RHEL 9's FIPS modules being validated on z16 does not change that: OS/JDK FIPS modes on s390x are outside Confluent's s390x support statement, so they are neither a substitute for CP FIPS mode nor a configuration this wiki claims works with CP. mTLS, TLS 1.2/1.3 and CPACF acceleration are unaffected. (On x86/ARM OCP, CP FIPS mode additionally needs a FIPS-at-install cluster — [FIPS-at-install OCP Requirement](fips-at-install-ocp-requirement.md).)
- **Native-library connectors are a runtime fact, not a support-matrix fact.** An s390x image manifest is necessary but not sufficient — a connector can ship a valid s390x image and still shell out to an x86-only native lib. Audit each connector in scope. Pure-Java connectors (Mongo, Debezium) are unaffected.

### IFLs vs. vCPUs vs. Pods

These count different things. Conflating them is the usual source of mis-sizing.

| Unit | What it is | Who allocates it |
|---|---|---|
| **Pod** | The smallest deployable unit in OpenShift. One Confluent process each: one broker = one pod. A pod *declares* a CPU request. | Platform team, via CR replica counts |
| **vCPU** (logical CPU) | The unit Kubernetes schedules against. One vCPU = **one hardware thread**. Pod CPU requests/limits are in vCPU. | OpenShift scheduler, from Σ of pod requests |
| **IFL** | A **physical** IBM Z processor core licensed to run Linux. What you actually provision. | The LPAR / PR-SM plan |

```
Pods request vCPU   →   OpenShift sums vCPU   →   Physical IFLs = vCPU ÷ 2

(SMT-2: each IFL exposes 2 hardware threads, so OpenShift sees 2 vCPU per IFL.)
```

You **buy IFLs**, you **schedule vCPU**, you **run pods**. 32 IFLs present **64 logical CPUs**.

**SMT-2 nuance:** two threads per IFL give ~1.4–1.7× the throughput of one, **not 2×**. The `÷2` is correct for *schedulable capacity*; it is not free performance. Size latency-sensitive tiers (brokers, Flink) with headroom, or budget closer to `÷1.5`.

**Dedicated vs. shared IFLs.** On LinuxONE you typically dedicate IFLs to the LPAR. On Linux on Z sharing a machine with other LPARs, IFLs may be shared via PR/SM weights — "2 IFLs" can be a fractional entitlement rather than 2 guaranteed cores. The vCPU count is unchanged; *delivered* capacity is not. Dedicate for FSI latency tiers and for any benchmark whose numbers you intend to publish.

### Confluent's per-component hardware reference

Confluent's own words: *"a good starting point based on the experiences of Confluent with production clusters, but actual requirements depend on your specific workload"* — and, decisively for this article:

> "The CPU resource requirement is the same for all platforms. For example, if 12 CPUs is the requirement for non-Kubernetes environments, the requirement for a Kubernetes environment is also 12 CPU units."

So the number is **platform-independent**; Confluent counts cores ≈ CPU-units 1:1 and never mentions IFLs.

| Component | Nodes | RAM | CPU | Storage |
|---|---:|---|---|---|
| **Kafka broker** | 3 | 64 GB | **24 cores** | 12 × 1 TB; RAID 10 optional; OS disk separate |
| **KRaft controller** | 3–5 | 4 GB | 4 cores | 64 GB SSD |
| **Confluent Manager for Flink (CMF)** | 1 pod | 4 GB | 3 cores | 10 GB PV — *manages 150 Flink apps* |
| **Connect** | 2 | 0.5–4 GB heap | not CPU-bound ("more cores > faster cores") | install-time only |
| **Schema Registry** | 2 | 1 GB heap | not CPU-bound | install-time only |
| **REST Proxy** | 2 | 1 GB + 64 MB/producer + 16 MB/consumer | 16 cores | install-time only |
| **ksqlDB** | 2 | 20 GB | 4 cores | ≥ 100 GB SSD |
| **Control Center** (next-gen) | 1 | ≥ 8 GB | 4+ cores | 200 GB SSD |

**Flink job sizing is not published.** Confluent sizes only **CMF**, the Flink control plane. There is no per-`FlinkApplication` JobManager/TaskManager table — that is generic Flink capacity planning, left to the workload. (Confluent Cloud Flink is serverless/CFU-based with no infra sizing at all.)

### Translating the reference to IFLs

Take the "cores" column as **vCPU / CPU-units — identical on x86, LinuxONE, and Linux on Z.** What changes per platform is how many physical cores those vCPU map to.

| Component | Nodes | vCPU/node | Cluster vCPU | Cluster IFLs @ SMT-2 |
|---|---:|---:|---:|---:|
| Kafka broker | 3 | 24 | 72 | 36 |
| KRaft controller | 3 | 4 | 12 | 6 |
| CMF | 1 | 3 | 3 | 1.5 |
| REST Proxy | 2 | 16 | 32 | 16 |
| ksqlDB | 2 | 4 | 8 | 4 |
| Control Center | 1 | 4 | 4 | 2 |
| Connect | 2 | ~2–4¹ | ~6 | ~3 |
| Schema Registry | 2 | ~1–2¹ | ~3 | ~1.5 |
| **Full reference total** | | | **~140 vCPU** | **~70 IFLs** |

¹ Confluent gives no core count for Connect/SR (workload-driven); estimates.

**This is a ceiling, not a target.** It stacks every component at full load (note REST Proxy alone is 16 cores/node). A single reference-sized broker is **12 IFLs**; three of them (36 IFLs) exceed many LPARs outright.

### Throughput-banded IFL sizing — GoodLabs field heuristic

⚠️ **Not Confluent canon.** Confluent publishes the per-component reference above, *not* a throughput→IFL curve. Do not cite this table as vendor guidance.

**Method.** Split the reference into (a) a **fixed HA overhead** floor set by quorum/replica minimums — KRaft ×3, SR ×2, CMF, C3 — which is flat against throughput, and (b) **throughput-scaling** tiers: brokers (dominant), Flink TaskManagers, Connect. Scale only (b), anchoring the broker at `24 vCPU ≈ 200 MB/s/broker`, then `IFLs = Σ vCPU ÷ 2`.

| Deployment | Aggregate ingest | Brokers (IFL) | Flink (IFL) | Connect (IFL) | Fixed HA overhead (IFL) | **Total IFLs** |
|---|---|---:|---:|---:|---:|---:|
| Dev / PoC (collapsed, non-HA) | < 10 MB/s | ~1 | ~1 | — | ~1 | **~2–4** |
| Small (HA) | ~25 MB/s | 3 | 1.5 | 1 | 11 | **~17** |
| Medium | 100 MB/s | 6 | 3 | 1 | 11 | **~21** |
| Large | 250 MB/s | 15 | 8 | 2 | 11 | **~36** |
| Enterprise | 500+ MB/s | 30 | 16 | 8 | 11 | **~65** |

Enterprise (~65 IFL) lands at the full reference (~70), confirming the model.

Two things this makes visible:

- **A 3-node HA cluster has an ~11-IFL floor before a single byte of throughput.** "PoC = 2–3 IFLs" only works by *collapsing* the topology (single-node, combined KRaft, no C3/SR HA). The jump from PoC to Small is HA, not throughput.
- **Any given throughput is a range, not a point.** At 100 MB/s: ~6–8 IFLs (optimistic band), ~11 (lean bottom-up BOM), ~21 (reference-faithful). The spread is driven by the **broker anchor** (MB/s per broker), **overhead tuning** (KRaft 6→~2 IFL trims the floor), and **SMT treatment** (÷2 vs ÷1.5). Plan a range and load-test to land it.

Brokers are the tuning knob and scale with partition count and peak MB/s (canon: `6 × peak MB/s` partitions).

### Scheduling gotcha: `full-pcpus-only` and SMTAlignmentError

If you pin CPUs — required when latency-sensitive pods (e.g. Flink inference) must not share a physical core with a broker — you enable kubelet's static CPU manager with `cpuManagerPolicyOptions: full-pcpus-only`. That allocates **whole physical cores**, and under SMT-2 a core is 2 logical CPUs. The rule is narrower than "Guaranteed pods need even cpu":

| Pod QoS + CPU | Reaches static CPU manager? | SMT constraint |
|---|---|---|
| **Guaranteed + integer cpu** | Yes — exclusive cores | **Must be a multiple of threads-per-core (even at SMT-2)** |
| Guaranteed + fractional (`500m`) | No — shared pool | None |
| Burstable (`requests != limits`) | No — shared pool | None |

A Guaranteed pod with an odd integer CPU request is **rejected at admission with `SMTAlignmentError`**. The failure reads like a capacity problem, so it gets "fixed" by adding IFLs rather than by fixing the config. Give exclusive whole cores only to pods that need them (brokers, Flink JobManager/TaskManager); leave control-plane pods (KRaft, Schema Registry, CMF) **Burstable** in the shared pool.

Note also that **Topology Manager aligns to NUMA nodes, not to chips.** On s390x there is no guarantee each processor chip surfaces as a distinct NUMA node, so `static` + Guaranteed QoS gives you *exclusive* CPUs, not CPUs *on a chosen chip*. Chip locality is a topology problem: one chip per worker node, then `podAntiAffinity` on `kubernetes.io/hostname`.

## Caveats

- **Confluent publishes no s390x-specific sizing.** Every IFL number here is a local translation of architecture-agnostic guidance, or a field heuristic. Neither is vendor guidance.
- **The `÷2` is scheduling capacity, not throughput.** SMT-2 buys ~1.4–1.7×.
- **Confirm SMT state on the target LPAR** (`lscpu`, threads-per-core). With SMT disabled, `IFLs = Σ vCPU` (no divisor).
- **The "not yet supported" list moves.** Re-validate against `confluent-docs` and the vendor before treating any row as a design constraint.
- **Storage is retention-driven, not throughput-driven** — size broker volumes from the retention window, not from MB/s.
- Figures exclude OCP control-plane/infra nodes, which may sit on a separate IFL pool or on x86.

## Related

- [LinuxONE Platform Foundations](linuxone-platform-foundations.md) — SMT, CBU, Telum cache fabric, and the L1-specific substrate this sizing sits on
- [LinuxONE Kafka Integration](linuxone-kafka-integration.md) — the z/OS offload bridge pattern (Connect on z/OS, IBM MQ Source Connector)
- [LinuxONE on CFK Reference Architecture](../patterns/linuxone-on-cfk-reference-architecture.md) — the deployable CFK layering this sizing provisions for
- [FIPS-at-install OCP Requirement](fips-at-install-ocp-requirement.md) — OCP FIPS-at-install (x86/ARM), and why the LinuxONE accelerator does not set CP FIPS mode on s390x
- [s390x Custom Image Build Pipeline](s390x-custom-image-build-pipeline.md) — every image needs an s390x manifest; the CI gate that enforces it
- [x86 → LinuxONE Cluster Linking Migration](../patterns/x86-to-linuxone-cluster-linking-migration.md) — moving an existing cluster onto Z
