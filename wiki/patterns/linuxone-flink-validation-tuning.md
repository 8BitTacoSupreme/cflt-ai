---
title: LinuxONE Flink Validation, Tuning & Telum II Inference
tags: [flink linuxone ibm s390x telum nnpa zdnn validation tuning fsi]
sources:
  - https://nightlies.apache.org/flink/flink-docs-master/docs/ops/production_ready/
  - https://docs.confluent.io/cp-flink/current/installation/versions-interoperability.html
  - https://docs.confluent.io/cp-flink/current/jobs/configure/checkpointing.html
  - https://www.ibm.com/products/linuxone/ai-processor
  - https://github.com/IBM/zDNN
  - https://github.com/IBM/zDLC
  - https://ibm.github.io/ai-on-z-101/onnxdlc/
related: [concepts/flink-checkpointing, concepts/exactly-once-semantics, concepts/linuxone-kafka-integration, concepts/linuxone-platform-foundations, patterns/linuxone-validation-suite, patterns/linuxone-kafka-tuning, patterns/fsi-exactly-once]
confidence: medium
last_updated: 2026-05-07
last_validated: 2026-05-07
validated_via: [confluent-docs (versions-interoperability.html), context7 (/websites/nightlies_apache_flink_flink-docs-release-2_2)]
changelog:
  - 2026-05-07 (rev 2) — Peer-review pass. Replaced `TwoPhaseCommitSinkFunction` reference (deprecated in Flink 2.x) with SinkV2 / `SupportsCommitter` framing per FLIP-372/FLIP-453. Replaced fabricated zDLC compile flags with citation to IBM AI Toolkit docs. Added checkpoint write-amplification note and RocksDB localdir guidance. Softened CV-models statement (small CV inference can land on Spyre). L4 cache wording corrected to virtual cluster cache.
---

# LinuxONE Flink Validation, Tuning & Telum II Inference

## Summary

Aggressive validation, tuning, and AI-inference integration plan for **Confluent Manager for Apache Flink (CMF) 2.3.x on Confluent Platform 8.2.x** running IBM LinuxONE Emperor 5. CMF 2.3 (released 2026-04-10) supports **Apache Flink 1.18.x – 2.1.x**. Confluent shipped s390x support for CP for Apache Flink in December 2025; this plan validates that bundle end-to-end and adds the differentiator: Telum II on-chip inference invoked from a Flink user-defined function for **sub-millisecond anomaly detection on the same LPAR as the broker and job**, eliminating the network hop that defeats sub-ms targets on x86. Tuning targets the same FSI tier matrix as Kafka — `critical` and `compliance` are exactly-once, RPO=0, no exceptions.

> Version pairing (per `confluent-docs` versions-interoperability.html, retrieved 2026-05-05):
> - CMF 2.3.x ↔ CP 8.2.x ↔ Apache Flink 1.18.x – 2.1.x ↔ CFK Operator 1.14.x ↔ CC 2.5.0 (CMF release 2026-04-10)
> - CMF 2.2.x ↔ CP 8.1.x ↔ Apache Flink 1.18.x – 2.1.x ↔ CFK Operator 1.13.x (CMF release 2025-12-18)
>
> Default to Apache Flink 2.x for new builds — Flink 2.0 GA shipped 2025; 2.1 is current; 2.2 is upstream nightly.

## Pattern

### 1. Topology

| Topology | Purpose |
|----------|---------|
| **Co-resident** | Kafka brokers + Flink JobManager + Flink TaskManagers all on the same Emperor 5; client traffic via SMC-D / HiperSockets | Sub-ms end-to-end target |
| **Split** | Brokers on L1, Flink on x86 RHEL via OSA | Cost-tier validation; comparison baseline |
| **Hybrid AI** | Brokers on L1, Flink TaskManagers on L1 with NNPA-enabled inference UDFs; off-platform analytics via Confluent Cluster Linking → CC → Databricks | The reference pattern for in-line fraud/AML/anomaly detection |

### 2. Validation Suite

#### 2.1 Install
- **CMF 2.3.x on CP 8.2.x** (Apache Flink 1.18.x – 2.1.x range; pin to 2.1.x for new builds).
- Run on RHEL 9 in FIPS mode; verify `systemd-cryptenroll` and that the JVM uses BCFIPS (preferred for Confluent-supported JDKs) or IBMJCE (only with IBM Semeru, which is not on Confluent's supported JDK list — see [LinuxONE Kafka Tuning § JDK posture](linuxone-kafka-tuning.md)).
- Sanity job: `Datagen → SQL filter → Print` running in a session cluster; should be visible in CMF UI within 60 s.
- KRaft Kafka catalog registered in CMF; Schema Registry catalog reachable; both round-trip a CREATE TABLE within 5 s.

#### 2.2 Functional Tests
- **SQL coverage:** every Flink SQL operator class — windowed aggregates (tumbling, hopping, session), regular joins, interval joins, lookup joins, MATCH_RECOGNIZE, top-N, deduplication. Each produces the expected row count for a known input dataset.
- **Connectors:** Kafka source/sink (UPSERT-Kafka for changelog), JDBC lookup against DB2 z/OS via HiperSockets, Iceberg sink to IBM Cloud Object Storage.
- **UDFs:** scalar, table, aggregate. Validated for both Java and Python (PyFlink). Note: Python UDF performance on s390x lags Java by ~30% — use Java UDFs for hot paths.
- **CDC:** Kafka source with `scan.startup.mode=earliest-offset` for deterministic replay (canon).

#### 2.3 Checkpointing & State
- **Backend:** RocksDB on local NVMe / FCP.
- **Interval:** 30 s for `critical`, 60 s for `standard`. Unaligned checkpoints enabled when backpressure expected.
- **Snapshot target:** IBM Cloud Object Storage via S3-compatible API.
- **Test:** kill a TaskManager mid-run; job must recover from latest checkpoint within 30 s; sink must produce no duplicate output (verify via consumer with `isolation.level=read_committed`).
- **Savepoint:** trigger savepoint, redeploy job from savepoint to a different parallelism — state correctly redistributed.

#### 2.4 Exactly-Once End-to-End
- Source: Kafka `read_committed`.
- Sink: `KafkaSink.builder().setDeliveryGuarantee(EXACTLY_ONCE)` — runs under the **SinkV2 API** (`SupportsCommitter` interface; `CommittingSinkWriter` for pre-commits, `Committer` for final commits per FLIP-372/FLIP-453). Pre-commit happens on each checkpoint barrier; final commit happens on `notifyCheckpointComplete`. The legacy `TwoPhaseCommitSinkFunction` was moved to a legacy package in Flink 2.0 and is `@Deprecated` for removal — do not write new code against it.
- Producer `transactional.id` prefix unique per task slot.
- Producer `transaction.timeout.ms` must exceed `execution.checkpointing.tolerable-failed-checkpoints × execution.checkpointing.interval` plus a safety margin (recommend ×1.5). Otherwise transactions abort during normal checkpoint backpressure and the sink falls back to AT_LEAST_ONCE silently.
- Inject failures: TaskManager kill, JobManager kill, broker kill — verify zero duplicates and zero loss across 10M records.

#### 2.5 Schema Evolution
- Live job consuming from a topic with FULL_TRANSITIVE compatibility. Push a schema v2 with an optional new field; job must process v1 and v2 records concurrently without restart.

#### 2.6 Performance & Scale
- **Throughput:** sustained 1 M events/s with 4 TaskManagers, 16 slots each, on a single LPAR with 32 IFLs.
- **Latency:** windowed aggregation, p99 event-to-output < 50 ms for `critical` tier; with NNPA inference UDF in path, p99 < 5 ms.
- **State size:** validate RocksDB at 100 GB/TM; checkpoint times remain bounded (incremental checkpointing on).

### 3. Tuning

#### 3.1 Cluster
| Property | Default | Recommended on L1 | Why |
|----------|---------|-------------------|-----|
| `parallelism.default` | 1 | match peak Kafka partition count for source-bound jobs | Avoid Flink-side bottleneck |
| `taskmanager.numberOfTaskSlots` | 1 | `cores / 2` | Leaves headroom for GC and JIT |
| `taskmanager.memory.process.size` | varies | 16–32 GiB | Big enough for RocksDB block cache + JVM heap |
| `taskmanager.memory.managed.fraction` | 0.4 | 0.5 | Larger RocksDB block cache pays off on s390x |
| `taskmanager.network.memory.fraction` | 0.1 | 0.15 | More buffers help cross-LPAR network shuffles |

#### 3.2 Checkpointing
| Property | Recommended | Notes |
|----------|-------------|-------|
| `execution.checkpointing.interval` | 30000 ms | Critical tier; tune up for stateful jobs |
| `execution.checkpointing.mode` | EXACTLY_ONCE | Default for FSI |
| `execution.checkpointing.unaligned` | true | Survives backpressure better |
| `execution.checkpointing.tolerable-failed-checkpoints` | 3 | Three strikes before failover |
| `state.backend.type` | `rocksdb` | HashMap only for tiny state. Flink 2.x backend class: `org.apache.flink.state.rocksdb.EmbeddedRocksDBStateBackend` |
| `state.backend.incremental` | true | Required at scale |
| `state.checkpoints.dir` | `s3://<bucket>/flink-checkpoints/` | IBM COS preferred on L1 |
| `execution.checkpointing.dir` | matches above | Flink 2.x preferred property name |
| `state.backend.rocksdb.localdir` | dedicated NVMe / FCP mount | **Must not share volume with Flink logs.** Local SSD-class storage; sized for state × 1.5 to handle in-flight compactions |

> **Checkpoint write amplification budget.** At 100 GB state/TM × 4 TMs × 30 s checkpoint interval, with incremental checkpoints producing typical deltas of 1–5% of state size, expect on the order of **8–40 TB/day** of object-store writes. Specify the COS bucket lifecycle policy (retain N latest, expire older incrementals after savepoint), reserve PUT/GET budget against the COS account quota, and validate your COS bucket TPS ceiling against your TM count.

#### 3.3 LinuxONE Overlay
- **JVM:** `-XX:+UseG1GC`, heap sized so that managed memory + heap < 75% of TM process size; `-XX:+UseTransparentHugePages`.
- **CPU pinning:** identical to broker tuning — pin TaskManager containers to contiguous z/VM CPs to avoid cross-drawer cache misses.
- **Network:** wrap TM startup in `smc_run` to use SMC-D for inter-TM/inter-LPAR shuffle traffic.
- **Crypto:** mTLS to brokers offloads to CEX8S via the JVM's JCE provider chain — see [LinuxONE Kafka Tuning § Crypto Express (CEX8S)](linuxone-kafka-tuning.md). IBM JCE activation is via `java.security` edit or `Security.insertProviderAt`, not a system-property switch.
- **RocksDB on s390x:** require Flink 1.20+ with RocksDB 7.10+ (older versions have s390x JNI bugs). For Flink 2.x, the embedded RocksDB ships in the `flink-statebackend-rocksdb` artifact under the new `org.apache.flink.state.rocksdb` package. Set `state.backend.rocksdb.thread.num=4` to match IFL count.

### MCP Validation Notes

| Claim | Source | Result |
|-------|--------|--------|
| CMF 2.3.x supports Apache Flink 1.18.x – 2.1.x on CP 8.2.x | confluent-docs versions-interoperability.html | Confirmed (release 2026-04-10) |
| s390x supported for CP for Apache Flink | confluent-docs versions-interoperability.html | Confirmed: GA December 2025; arch-specific issues not Confluent-supported |
| `EXACTLY_ONCE` Kafka sink uses Kafka transactions | context7 /websites/.../flink-docs-release-2_2 | Confirmed: KafkaSink supports NONE, AT_LEAST_ONCE, EXACTLY_ONCE; EXACTLY_ONCE uses transactions and commits on checkpoint |
| RocksDB incremental checkpoints | context7 /websites/.../flink-docs-release-2_2 | Confirmed: `EmbeddedRocksDBStateBackend(true)` |
| Flink 2.x state backend type config | context7 /websites/.../flink-docs-release-2_2 | Confirmed: `state.backend.type=rocksdb` and `execution.checkpointing.mode=EXACTLY_ONCE` |
| `TwoPhaseCommitSinkFunction` deprecated in Flink 2.x | context7 /websites/.../flink-docs-release-2_2 | Confirmed: SinkV2 API uses `SupportsCommitter` (`CommittingSinkWriter` + `Committer`); legacy 2PC sink moved to legacy package and `@Deprecated` per FLIP-372/FLIP-453 |

### 4. Telum II Sub-Millisecond Anomaly Detection

This is the differentiator.

#### 4.1 Architecture

```mermaid
flowchart TD
  SRC[("Kafka source — read_committed")]
  PROC["Map/ProcessFunction wrapping anomaly inference"]
  ALERTS[("kafka.fraud.alerts.v1")]
  SCORED[("kafka.events.scored.v1 — audit")]
  SRC --> PROC
  PROC -->|"if score > threshold"| ALERTS
  PROC -->|"always"| SCORED
```

The inference call is **in-process, on-LPAR, on-chip** — there is no network hop, no PCIe round-trip to a GPU, no microservice call. Telum II's NNPA accelerator is invoked via the IBM Z Deep Neural Network library (`zDNN`); models are pre-compiled from ONNX with the IBM Z Deep Learning Compiler (`zDLC`), which emits a JNI-callable JAR.

#### 4.2 Build Pipeline

1. **Train** the anomaly model on Databricks (off-platform, Spark/MLflow).
2. **Export** to ONNX.
3. **Compile** with zDLC to produce a JNI-callable artifact (`model.so` + `model.jar`). Use the canonical compile invocation from the [zDLC release docs](https://github.com/IBM/zDLC) and the [AI Toolkit for IBM Z and LinuxONE](https://www.ibm.com/products/ai-toolkit-for-z-and-linuxone) — do not paste a flag string from secondary sources, since the LLVM target triple and `-march=` value vary by zDLC release and toolchain version (e.g., `-march=z17` works only when the toolchain aliases it; older toolchains use `-march=arch15`).
4. **Sign + register** the JAR in Schema Registry-adjacent artifact store; record SHA-256 in the model registry.
5. **Distribute** to TaskManager classpath via `flink run --classpath model.jar`.

#### 4.3 Flink UDF (Java skeleton)

```java
public class TelumAnomalyScore extends RichMapFunction<Transaction, ScoredTransaction> {
  // model loaded once per TM; thread-safe per zDNN docs
  private transient TelumModel model;

  @Override
  public void open(Configuration cfg) {
    // Loads the JNI library into the on-chip NNPA path; falls back to CPU if unavailable
    this.model = TelumModel.load("/opt/models/anomaly-v3.so");
  }

  @Override
  public ScoredTransaction map(Transaction tx) {
    float[] features = FeatureBuilder.from(tx);
    float score = model.score(features);   // ~150–300 µs on Telum II for typical fraud DLM
    return new ScoredTransaction(tx, score);
  }
}
```

#### 4.4 Latency Budget for Sub-ms

To hit p99 < 1 ms event-to-decision, every hop must be sized:

| Hop | Budget | How |
|-----|--------|-----|
| Kafka source poll | < 100 µs | Co-resident broker via SMC-D; `fetch.min.bytes=1`, `fetch.max.wait.ms=10` |
| Deserialize Avro | < 50 µs | Schema cached in TM |
| Feature build | < 100 µs | Fixed-shape vector; no allocations |
| **NNPA inference** | < 300 µs | Telum II for fraud-class DLM models |
| Branch + serialize | < 100 µs | Pre-allocated output buffers |
| Sink to alerts topic | < 200 µs | `linger.ms=0`, `acks=all`, SMC-D path |
| **Total p99** | **< 1 ms** | Co-resident is the only way |

For comparison: a Flink job on x86 calling out to a GPU inference microservice over a 10 GbE link routinely sits at 5–15 ms p99 — not viable for sub-ms.

#### 4.5 Co-Residency Validation
A test in the [LinuxONE Validation Suite §5.4](linuxone-validation-suite.md) confirms NNPA workloads do not interfere with broker performance on the same LPAR — the accelerator runs on dedicated silicon and shares only the **cluster-level virtual L4 cache / interconnect** (Telum II's "L4" is a virtual aggregation across the chip cluster, not a discrete cache array). L1/L2 and memory bandwidth are not contended. Run in production confidence after that test passes.

#### 4.6 Models that Fit
- **Credit card fraud** (DLM, ~5–20 features, < 1M params) — IBM-published reference shows 5M ops/s at p99 < 1 ms on Emperor 5.
- **Anti-money-laundering pattern detection** (graph-aware, small) — fits if pre-aggregated upstream.
- **Real-time payment risk scoring** — fits.

Models that **do not fit** the on-chip accelerator:
- LLMs and transformers above ~1B params — these go to **IBM Spyre** (separate PCIe accelerator, also on z17/Emperor 5). See [LinuxONE Platform Foundations § Spyre Integration Boundary](../concepts/linuxone-platform-foundations.md) — the on-frame two-tier inference story (NNPA for ~250 µs class; Spyre for larger models at ~500 µs–1 ms over PCIe; decision is at compile time via zDLC vs Spyre toolchain).
- **Large** computer vision models (>500M params) — keep off-platform. **Small** CV inference (signature/check verification, document quality classification, e.g. <50M params) can land on Spyre with sub-ms latency.

### 5. Reporting

Same convention as the validation suite — Markdown report per run committed to `reports/flink-validation/`. Include separate latency histograms for the inference hop alone (NNPA) so we can detect accelerator regressions independently of Flink overhead.

## Related

- [LinuxONE Platform Foundations](../concepts/linuxone-platform-foundations.md) — Spyre integration boundary, Telum II vs Spyre tier decision, IBM benchmark anchors, STP for event-time consistency
- [LinuxONE Validation Suite](linuxone-validation-suite.md) — paired Kafka validation
- [LinuxONE Kafka Tuning](linuxone-kafka-tuning.md) — broker tuning consumed by the Flink pipeline
- [Flink Checkpointing](concepts/flink-checkpointing.md) — barrier mechanics, aligned vs unaligned
- [Exactly-Once Semantics](concepts/exactly-once-semantics.md) — Flink 2PC sink details
- [LinuxONE Kafka Integration](concepts/linuxone-kafka-integration.md) — frame-level architecture context
- [FSI Exactly-Once Pattern](fsi-exactly-once.md) — durability bar applied to Flink jobs
