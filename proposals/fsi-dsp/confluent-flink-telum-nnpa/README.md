# Confluent Flink + Telum NNPA — Accelerator Proposal

Fraud-scoring pipeline: Confluent Platform (Kafka + Flink via CMF) on OpenShift/s390x,
with model inference offloaded to the Telum on-chip AI accelerator (NNPA).

**Reference sizing — example target:** IBM z16, **32 dedicated IFLs across 4 Telum (gen-1) chips**.
RHEL + OCP assumed pre-installed.

---

## 1. Runbook evaluation

The runbook is technically strong and its core corrections are right. Validated against
`confluent-docs` (CP 8.2/8.3 *System Requirements* + *Linux on IBM Z (s390x) support*)
on 2026-07-06.

### Confirmed correct ✅

| Runbook claim | Verdict |
|---|---|
| CFK **and** Confluent Platform for Apache Flink (CMF) supported on s390x | ✅ Both named explicitly in the s390x support list |
| k8s is mandatory (CMF is k8s-only); no systemd path for this stack | ✅ |
| KRaft, not ZooKeeper | ✅ |
| SMT-2 → 32 IFLs present **64 logical CPUs** | ✅ |
| Telum gen-1 (z16) = **DLFLOAT16, no INT8**; INT8 arrives with Telum II | ✅ |
| zDNN (via zDLC/onnx-mlir), **not** OpenBLAS, is the only path to NNPA | ✅ |
| Silent CPU fallback is the #1 operational risk | ✅ — and there is no accelerator utilization counter, so indirect detection is correct |
| One NNPA per chip, shared by 8 cores; gen-1 has **no cross-chip** accelerator access | ✅ |
| Semeru = OpenJDK libs on OpenJ9 | ✅ |
| Terraform is peripheral (Grafana config-as-code + cloud adjuncts) | ✅ |

### Support-matrix posture

`confluent-docs` ("Linux on IBM Z (s390x) support") lists, under *"not yet supported on
s390x"*: **FIPS mode, IPv6, Unified Stream Manager Agent, connectors that rely on native OS
libraries.** All four are **CP-layer** statements, not platform statements — s390x/RHEL/OCP
support all of these; the claim is about Confluent Platform's s390x build.

Per the runbook's Phase 2/6.5 reasoning — the public matrix lags actual state (confirm with IBM/Confluent
before deployment), and CP is entitled as **IBM Confluent Platform
for Z and LinuxONE** (GA 2026-03-17) — none of these are treated as design-time blockers.
They are **recorded posture items, confirmed with IBM/Confluent before deployment** and captured in the BOM (§9 of the
runbook). The artifacts here reflect that:

| Item | Posture | Where it lands |
|---|---|---|
| **FIPS mode** | **Supported and enabled.** OS FIPS is validated *on z16* (RHEL 9 modules tested on z16 as a certified operational environment). CP FIPS mode is BC-FIPS — pure Java; enabling on Z is configuration + certification sequencing, not architecture. | `ansible/02-fips-mode.yml`, `helm/cfk-operator-values.yaml` (`fipsmode: true`), BCFKS keystore pipeline |
| **IPv6** | Demoted to a **recorded posture item**, not a gate. Same doc scope as the FIPS line. Confirm with IBM/Confluent before deployment; if CP's s390x build lacks IPv6 listener support it surfaces as broker bind failures, not a clean error — so record the cluster network mode either way. | `00-platform-validate.yml` (warn + record) |
| **Native-lib connectors** | A **runtime fact, not a support-matrix fact.** Connectors in scope (Mongo sink, CDC) are pure-Java and run fine. Audit and record per plugin. | `ci/images.txt` + BOM connector audit row |
| **Unified Stream Manager Agent** | Not deployed by this accelerator. Values are USMAgent-ready. | — |
| **Entitlement** | **IBM Confluent Platform for Z and LinuxONE**, entitled through IBM. BOM line item. | `MANIFEST-entry.yaml` |
| **Version floor** | **CP ≥ 8.2.0** — the s390x floor. Pin no lower. | all image pins |

### Gaps the runbook still has ⚠️

Two engineering defects survive the update. Neither is a support-matrix question.

### Sizing: the runbook's CPU budget does not close ⚠️

The runbook proposes *"brokers 16 lCPU, Flink TMs 40 lCPU, system/observability 8"* = 64 lCPU
exactly. That leaves **zero** for KRaft controllers, Schema Registry, CMF, the Flink JobManager,
and OCP node overhead. It is over-subscribed on arrival.

Also worth stating plainly: **Confluent's reference broker is 24 cores / 64 GB.** Three of them
is 72 lCPU — *more than this entire machine*. This box cannot run reference-sized brokers; the
scaled-down figures below are deliberate and must be documented as such.

**Budget for 32 IFLs / 64 lCPU (SMT-2), 4 chips:**

| Component | Pods | lCPU/pod | lCPU | Memory |
|---|---:|---:|---:|---:|
| OCP/system per node (kubelet, CRI-O, OVN) | 4 nodes | 2 | 8 | 16 GB |
| Kafka brokers | 3 | 4 | 12 | 96 GB |
| KRaft controllers | 3 | 1 | 3 | 12 GB |
| Schema Registry | 2 | 1 | 2 | 8 GB |
| CMF (Flink control plane) | 1 | 3 | 3 | 4 GB |
| Flink JobManager | 1 | 2 | 2 | 4 GB |
| **Flink inference TaskManagers** | **4** | **6** | **24** | 64 GB |
| Observability (Prom/Grafana/AM/KSM) | ~4 | ~1 | 4 | 12 GB |
| **Total** | | | **58 / 64** | **~216 GB** |

Headroom ≈ 6 lCPU (~9%). Provision **≥ 256 GB** system memory (the gap over 216 GB is OS
overhead + Kafka page cache, which is not a pod request but is where broker performance lives).

Figures are CPU **requests** — what the scheduler actually reserves. Guaranteed pods (brokers,
Flink JM/TM) hold their CPUs exclusively; Burstable pods (KRaft, SR, CMF, observability) draw from
the shared pool and may burst to their limits. See the QoS table below before changing any value.

### Chip pinning: the runbook's mechanism doesn't do what it claims ⚠️

> *"CPU-pinned (`static` CPU manager policy in kubelet + Guaranteed QoS on the TM pods) so each
> TM's inference threads hit their local accelerator."*

Static CPU manager + Guaranteed QoS gives a pod **exclusive** CPUs — it does **not** let you choose
*which chip* those CPUs are on. Topology Manager aligns to **NUMA** nodes, and on s390x there is no
guarantee each Telum chip surfaces as a distinct NUMA node.

**Recommended topology instead:** carve **4 OCP worker nodes, each backed by 8 dedicated IFLs =
exactly one Telum chip** (16 lCPU/node under SMT-2; 4 × 16 = 64 ✓). Then chip locality is expressed
as ordinary Kubernetes scheduling:

- `podAntiAffinity` on `kubernetes.io/hostname` → exactly one inference TaskManager per node → one per chip → one NNPA each.
- `cpuManagerPolicy: static` + `cpuManagerPolicyOptions: full-pcpus-only` → the TM gets **whole cores** (both SMT siblings), so inference threads don't contend with a co-tenant on the same core.
- TM `cpu` requests must be **even** (whole cores) for `full-pcpus-only` to admit the pod.

### Broker/TM co-residency — Recommended: Option A

The runbook says *"do not co-schedule brokers and inference-heavy TaskManagers on the same chip
domain if you can avoid it."* With exactly 4 chips and a goal of using all 4 accelerators, **you
cannot avoid it.**

**Recommendation: Option A.** 4 inference TMs, one per chip; brokers co-resident but on **disjoint
exclusive cores**. Rationale: NNPA is a *separate on-chip functional unit* — brokers never issue
NNPA instructions. The contention is for cores and L2/LLC, which whole-core pinning
(`full-pcpus-only`) addresses. Uses all 4 accelerators.

*Rejected:* Option B (platform on chips 0–1, inference on chips 2–3) — cleaner isolation but
**halves inference capacity to 2 accelerators**.

*Falsification condition:* if Phase 7 shows cache contention from broker co-residency is material
at the target p99, revisit. Until then, Option A holds.

#### The QoS consequence — read before editing any `cpu:` value

Option A only works if brokers and inference TMs never share a **physical core**. That comes from
`full-pcpus-only`, which carries a trap: **any Guaranteed pod (requests == limits) whose CPU request
is not a whole physical core is rejected at admission with `SMTAlignmentError`.** Under SMT-2 the
count must be **even**.

| Pod | QoS | cpu | Why |
|---|---|---:|---|
| Kafka broker | **Guaranteed** | 4 | Exclusive whole cores (2 cores) |
| Flink JobManager | **Guaranteed** | 2 | Exclusive whole core |
| Flink inference TaskManager | **Guaranteed** | 6 | Exclusive whole cores (3), one TM per chip |
| KRaft controller | Burstable | 1→2 | Metadata-only; shared pool |
| Schema Registry | Burstable | 1→2 | Not CPU-bound (Confluent's own reference) |
| CMF | Burstable | 2→3 | Control plane; shared pool |
| Prometheus / Grafana / CFK operator | Burstable | — | Shared pool |

Do **not** "tidy" a Burstable control-plane pod into `requests == limits` with an odd `cpu` — it will
fail to schedule, and the failure reads as a capacity problem rather than an alignment one.

### Smaller notes

- *"4 Telum cores"* is read as **4 Telum chips** (8 cores/chip × 4 = 32 IFLs). This means
  all cores on all 4 chips are IFLs, giving exactly **4 NNPA accelerators**.
- On **z16 (Telum gen-1)** chip pinning is a **correctness/latency requirement**, not an optimization —
  a core cannot reach another chip's accelerator.
- CP 8.2.0 pairs with **CMF 2.3.x / Apache Flink 1.20** (`flinkVersion: v1_20`). The Flink Kubernetes
  Operator (FKO) is a CMF prerequisite.

---

## 2. What's in this proposal

```
ansible/    00-platform-validate.yml   fail-fast gate (machine type, NNPA-in-guest, SMT-2,
                                       chip topology, FIPS required, IPv6 recorded)
            01-node-baseline.yml       hugepages, swappiness, XFS, IRQ, chip labelling
            02-fips-mode.yml           FIPS validation chain + BCFKS keystore pipeline
                                       + validation-chain.json (the security-review deliverable)
helm/       cfk-operator-values.yaml   CFK operator, s390x-gated, fipsmode: true
            cmf-values.yaml            Confluent Manager for Apache Flink
            kube-prometheus-stack-values.yaml
manifests/  00-platform-crs.yaml       KRaft + Kafka + SR (budgeted CPU, BC-FIPS/BCFKS,
                                       FIPS-approved ciphers)
            05-kubeletconfig-cpumanager.yaml   static CPU manager + full-pcpus-only
            10-flink-cmf.yaml          CMFRestClass + FlinkEnvironment
            12-flinkapplication-fraud-scoring.yaml   chip-pinned inference TMs
            20-podmonitor-flink.yaml
terraform/  Grafana dashboards + NNPA-fallback alert routing as code
ci/         image-arch-gate.sh         docker manifest inspect → s390x present
            nnpa-coverage-gate.py      zDLC op report → fail on hot-path CPU fallback
            sbom-generate.sh           CycloneDX 1.6 per artifact; s390x-by-digest scans;
                                       model component + coverage attestation; cosign
            sbom-gate.py               4 supply-chain gates + renders BOM.md
observability/ prometheus-rules-nnpa-fallback.yaml
```

**Apply order:** `ansible/00` → `ansible/01` → `ansible/02` → `manifests/05` (reboots nodes) →
`helm/cfk` → `manifests/00` → `helm/cmf` → `manifests/10` → `manifests/12` →
`helm/kube-prometheus-stack` → `manifests/20` → `terraform/`.

**CI:** `image-arch-gate.sh` → `nnpa-coverage-gate.py` → `sbom-generate.sh` → `sbom-gate.py`.
Gate 3 (model coverage attestation) is the supply-chain twin of the Phase 4 fallback gate:
a model reaching production without one has an unattributable latency regime. Publish nothing from it.

## 3. Custom vs OOTB

Matches the runbook's scorecard. The durable IP is the **zDLC op-coverage CI gate**
(`ci/nnpa-coverage-gate.py`), the **NNPA-fallback alert rules**, and the **model-artifact
attestation** in the SBOM pipeline — together they are what make the Telum claim *provable*
rather than asserted, and what an FSI model-risk-management review actually asks for.

FIPS is **not** an exception here: the BCFKS keystore pipeline and `fipsmode: true` are built in
from day one, so flipping CP FIPS mode is a values change rather than a re-architecture.

## 4. Open items before benchmarking

1. **IBM/Confluent confirmation** of CP-on-Z status for: CP FIPS mode, IPv6 listeners, USM Agent.
   Record answers in the BOM — that table, not the public matrix, is the source of truth.
2. **TLS 1.2 EMS (RFC 7627) client-fleet audit.** RHEL 9 FIPS mode enforces Extended Master Secret;
   legacy clients without EMS or TLS 1.3 cannot connect. The first symptom is mystery producer
   connection failures. Audit *before* enabling FIPS mode.
3. Connector native-dep audit result recorded per plugin (expected: all pure-Java, all pass).
4. Confirm each Telum chip maps 1:1 to an OCP worker node (Phase 0 `chip_count` assertion).
5. **DLFLOAT16 accuracy tolerance** on the labelled eval set — this, not latency, is the kill criterion.

Note for the security review: the **AI inference path is outside the FIPS boundary by
construction** — zDLC/zDNN/NNPA perform no cryptographic functions. State it explicitly to preempt
the question.
