---
title: LinuxONE Kafka Tuning
tags: [kafka linuxone ibm s390x kraft tuning fips fsi]
sources:
  - https://kafka.apache.org/42/configuration/producer-configs/
  - https://kafka.apache.org/42/configuration/consumer-configs/
  - https://kafka.apache.org/42/configuration/broker-configs/
  - https://docs.confluent.io/platform/current/kafka-metadata/kraft.html
  - https://docs.confluent.io/platform/current/kafka/post-deployment.html
  - https://www.ibm.com/docs/en/linux-on-systems
related: [concepts/producer-batching-config, concepts/sla-tiers, concepts/linuxone-kafka-integration, concepts/linuxone-platform-foundations, patterns/linuxone-validation-suite, patterns/aks-kafka-tuning, patterns/fsi-exactly-once]
confidence: medium
last_updated: 2026-10-25
last_validated: 2026-05-07
validated_via: [confluent-docs (producer-configs.html, consumer-configs.html, versions-interoperability.html, tiered-storage.html), context7 (/websites/javadoc_io_doc_org_apache_kafka_kafka-clients_4_2_0)]
changelog:
  - 2026-10-25 (rev 3) — Corrected FIPS: CP FIPS mode is not yet supported on s390x (versions-interoperability, 8.3 docs), so the BCFIPS-on-L1 advice is withdrawn. JDK list now names Eclipse Temurin.
  - 2026-05-07 (rev 2) — Peer-review pass. Replaced fabricated `-Dcom.ibm.crypto.provider.useIBMJCE` and `lscrypt` with real IBM JCE activation mechanism (java.security edit) and `lszcrypt -VV`. Added concrete `smc_run` systemd drop-in. New SMC-R cross-frame subsection. Disambiguated `confluent.tier.feature` vs `confluent.tier.enable`.
---

# LinuxONE Kafka Tuning

## Summary

Validated, FSI-overlaid Kafka tuning guidance for Confluent Platform 8.2 on IBM LinuxONE Emperor 5 (Telum II / s390x). Updates the early-2025 generic tuning notes with current Kafka 4.2 defaults (`linger.ms=5`, `acks=all`, `enable.idempotence=true`), strikes the legacy ZooKeeper guidance (Confluent Platform 8.0 is KRaft-only), and adds an L1-specific overlay for HiperSockets MTU, Crypto Express offload, NUMA pinning across z/VM CPs, transparent huge pages, and SMC-D socket usage. Throughput vs. latency profiles are pinned to FSI SLA tiers — `critical` and `compliance` tiers do **not** trade durability for throughput regardless of what the generic guidance says.

## Pattern

### Default Reset (2026)

Several settings the legacy tuning doc treats as defaults are no longer:

| Property | Legacy "default" | Current default (Kafka 4.2 / CP 8.2) | Note |
|----------|------------------|--------------------------------------|------|
| `linger.ms` (producer) | 0 | **5** | Changed in Kafka 4.0; the 5 ms wait wins more on throughput than it loses on latency for typical workloads |
| `acks` (producer) | 1 | **all** | Default since Kafka 3.0; FSI requires `all` for any durable workload |
| `enable.idempotence` (producer) | false | **true** | Default since 3.0; required for `acks=all` correctness under retries |
| `send.buffer.bytes` (producer) | "OS default" | **131072** (128 KB) | Kafka has its own default; `-1` selects OS default |
| `receive.buffer.bytes` (consumer) | "OS default" | **65536** (64 KB) | Same — `-1` selects OS default. Note: producer-side `receive.buffer.bytes` is **32768** (32 KB) — different from consumer |
| Metadata management | ZooKeeper | **KRaft** | ZooKeeper removed in CP 8.0 |

The "balance throughput vs. latency" framing remains valid, but always layer the **FSI overlay** on top:

| FSI SLA Tier | Durability requirement | What you may tune | What you may not tune |
|--------------|------------------------|-------------------|------------------------|
| `critical` | Hard | `linger.ms`, `batch.size`, compression, fetch sizes | `acks=all`, `min.insync.replicas=2`, `enable.idempotence=true` |
| `compliance` | Hard + RPO=0 | Same as critical | Same as critical, plus retention is regulatory — do not lower |
| `standard` | Soft | Anything | None |
| `best-effort` | None | Anything including `acks=1` if explicitly waived | None |

### Throughput Profile

Producer:

```properties
# Idempotent + durable; tune only batching/compression
acks=all
enable.idempotence=true
batch.size=131072            # 128 KB; up from 16 KB default
linger.ms=20                 # 20 ms; raise to 50–100 for log/metrics ingestion
compression.type=lz4         # zstd if storage-bound; never gzip
buffer.memory=67108864       # 64 MB; raise to 128 MB if many partitions
max.in.flight.requests.per.connection=5
```

Consumer:

```properties
fetch.min.bytes=131072       # 128 KB; reduce broker round-trip count
fetch.max.wait.ms=500        # default; pair with fetch.min.bytes
max.partition.fetch.bytes=4194304   # 4 MB; tune if large records
isolation.level=read_committed     # required when paired with transactional producers
```

### Latency Profile

Producer:

```properties
acks=all                     # do NOT downgrade for FSI durable workloads
enable.idempotence=true
batch.size=16384
linger.ms=0                  # or 1–2 ms; legacy doc was right that small > 0 sometimes wins
compression.type=none        # unless network is the bottleneck
max.in.flight.requests.per.connection=5
```

Consumer:

```properties
fetch.min.bytes=1
fetch.max.wait.ms=10         # was 500; aggressive for latency-sensitive
```

### Balanced (Default Starting Point)

Use [Producer Batching Configuration § Tuning Profiles — Balanced](concepts/producer-batching-config.md). Match consumer fetch sizes proportionally.

### Broker Tuning

| Property | Default | Recommended on L1 | Why |
|----------|---------|-------------------|-----|
| `num.network.threads` | 3 | `min(cores, 16)` | One per allocated z/VM CP up to a point; saturates around 16 |
| `num.io.threads` | 8 | `2 × disks` | NVMe-backed FCP storage on L1 favors parallel I/O |
| `num.replica.fetchers` | 1 | 4–8 | Cross-LPAR replication via HiperSockets is fast — the bottleneck moves to follower-side dispatch |
| `socket.send.buffer.bytes` | 102400 | 1048576 | 1 MB; HiperSockets MTU is large (8 KB) but TCP windows still benefit |
| `socket.receive.buffer.bytes` | 102400 | 1048576 | Same |
| `replica.socket.receive.buffer.bytes` | 65536 | 1048576 | Replication keeps up; remove this as a bottleneck |
| `log.flush.interval.messages` | LONG_MAX | leave default | OS page cache + replication is the durability boundary; do **not** force fsync on every record |
| `log.segment.bytes` | 1 GB | 1 GB | Default is fine; smaller hurts compaction & tier offload |
| `compression.type` (broker) | producer | `producer` | Pass-through; do not recompress |
| `transaction.state.log.replication.factor` | 3 | 3 | Required for EOS |

### KRaft-Specific Tuning

| Property | Default | Recommended | Why |
|----------|---------|-------------|-----|
| `controller.quorum.voters` | (unset) | 3 voters across LPARs/frames | Never co-locate all voters on one frame |
| `metadata.log.max.snapshot.interval.ms` | 3600000 (1 h) | 600000 (10 min) for >5k partitions | Faster controller-restart recovery |
| `metadata.log.max.record.bytes.between.snapshots` | 20 MB | 50 MB | Reduces snapshot write frequency under heavy DDL |
| `controller.quorum.election.timeout.ms` | 1000 | 1000 (default OK) | Tune up to 2000 only if cross-frame voters and OSA latency exceeds 200 ms p99 |
| `process.roles` | (unset) | `controller` (voter LPARs) or `broker` (data LPARs) | **Never run combined mode in production** |

### LinuxONE-Specific Overlay

These are knobs that do not exist on x86 or behave differently enough that defaults are wrong.

#### HiperSockets MTU
Set `mtu 8192` on `hsi0`. Kafka producer/consumer batches > 8 KB (the typical case once `batch.size=128 KB`) traverse multiple frames; HiperSockets handles segmentation in firmware, so the larger MTU reduces interrupt overhead vs. Ethernet's 1500 default.

#### SMC-D (intra-frame, same-CEC)
Enable Shared Memory Communications - Direct on inter-LPAR Kafka traffic on the same frame:

```bash
# On both endpoints
modprobe smc
smc_run java -jar kafka-producer.jar
```

For Confluent Platform brokers, drop in a systemd override so `smc_run` wraps the JVM launcher:

```ini
# /etc/systemd/system/confluent-kafka.service.d/smc.conf
[Service]
ExecStart=
ExecStart=/usr/bin/smc_run /usr/bin/java -jar /opt/kafka/lib/kafka.jar ...
```

```bash
systemctl daemon-reload && systemctl restart confluent-kafka
```

SMC-D bypasses the TCP stack entirely after handshake — measured at 2–3× lower p99 vs. raw HiperSockets in-house.

#### SMC-R (cross-frame, same data center)
For Kafka traffic that crosses CECs within the same data center — cross-frame replication, MRC quorum traffic, Cluster Linking — use **SMC-R over RoCE Express**, not OSA. SMC-R provides the same TCP-stack-bypass advantage as SMC-D but works across the RoCE fabric instead of in-frame shared memory; sub-100µs link-layer latency. OSA-Express is for off-campus egress only (e.g. CC, Databricks). See [LinuxONE Platform Foundations § Cross-frame Transport](../concepts/linuxone-platform-foundations.md) for the RoCE Express + SMC-R configuration steps.

#### Crypto Express (CEX8S)
- mTLS broker↔broker offloads to CEX8S when the IBM JCE provider is in the JVM provider chain. **There is no system-property switch for this** — activate IBM JCE by either:
  - Editing `$JAVA_HOME/conf/security/java.security` to list `com.ibm.crypto.provider.IBMJCE` (or `IBMJCEPlus` for newer SDKs) above the default JCE provider in the `security.provider.<n>` ordering, or
  - Programmatic `Security.insertProviderAt(new com.ibm.crypto.provider.IBMJCE(), 1)` at startup.
- **CP FIPS mode is not yet supported on s390x, with any JDK or provider** (CP versions-interoperability, re-checked 2026-10-25). Do not plan a FIPS-mode broker on L1; a tier whose policy requires FIPS 140 validated broker crypto runs its brokers on x86/ARM. CEX8S and CPACF still accelerate TLS.
- Watch CEX8S contention via `lszcrypt -VV` — verbose output shows columns CARD.DOM, TYPE, MODE, STATUS, REQUESTS, **PENDING**, HWTYPE, **QDEPTH**, FUNCTIONS, DRIVER. Sample over time; sustained PENDING/QDEPTH > 0.5 indicates saturation. Mitigate by adding a CEX domain or adapter, or reduce TLS handshake frequency via long-lived connections.

> **JDK posture (Confluent support).** CP 8.2 lists Eclipse Temurin, OpenJDK, Zulu OpenJDK, and Oracle JDK as supported (recommended: Java 21). **IBM Semeru / OpenJ9 is not on the Confluent support list** — using it for IBM JCE access is a deliberate L1 trade-off and a candidate workload for the IBM-bundled support contract. With a listed JDK, CEX8S offload still works via the OS crypto policy path, just not via IBMJCE-specific flags.

#### NUMA / z/VM CP Pinning
- Pin each broker container to a contiguous block of z/VM CPs using `taskset` or systemd `CPUAffinity`.
- LinuxONE LPARs span multiple drawer boundaries above ~24 IFLs; cross-drawer cache misses hurt JIT throughput. Validate with `lscpu --extended` and `numactl --hardware`.

#### Transparent Huge Pages
- Leave THP at `madvise` (RHEL 9 default). Do **not** disable globally — JVM benefits from THP for the heap.
- Confirm `/sys/kernel/mm/transparent_hugepage/enabled` shows `always [madvise] never`.

#### Page Cache & Dirty Ratio
- `vm.dirty_ratio=20`, `vm.dirty_background_ratio=10`. Higher than x86 defaults; the FCP-attached SAN behind L1 has deeper queues.
- `vm.swappiness=1`. Never let Kafka swap.

#### Tiered Storage Target
- **Two distinct properties** (both required):
  - `confluent.tier.feature=true` — broker-level enable for the tier fetcher (must be true on every broker for tier reads to work, even after disabling tiering).
  - `confluent.tier.enable=true` — sets the **default for new topics**. Per-topic override via `kafka-topics --alter --config confluent.tier.enable={true|false}`.
- Plus the backend-specific config: `confluent.tier.backend=S3` (works with IBM Cloud Object Storage via S3-compatible API), `confluent.tier.s3.bucket`, `confluent.tier.s3.region`, `confluent.tier.s3.prefix`.
- Prefer **IBM Cloud Object Storage** with an OSA-Express path; no s390x-specific gotchas — uses standard S3 protocol.
- Off-platform AWS S3 works but pays the OSA latency tax for every cold read; only use for non-FSI tiers.

### Kafka Streams (s390x)

- `topology.optimization=all` (was `OPTIMIZE`; `all` is the modern equivalent). When migrating from a prior version that had `exactly_once` (v1), follow the documented `processing.guarantee` upgrade dance: rolling-restart through the `at_least_once → exactly_once_v2` transition (you cannot directly hot-switch v1 ↔ v2 without a planned cutover).
- `processing.guarantee=exactly_once_v2` for any FSI flow that crosses a state-store boundary.
- Embedded clients: prefix with `producer.` / `consumer.` and apply the profiles above.
- RocksDB on s390x: build is supported as of RocksDB 7.x; pin Streams to 7.10+ to avoid older s390x JNI issues.

### MCP Validation Notes

| Claim | Source | Result |
|-------|--------|--------|
| `linger.ms` default = 5 (Kafka 4.0+) | confluent-docs producer-configs.html | Confirmed: "default changed from 0 to 5 in Apache Kafka 4.0" |
| `acks` default = all | confluent-docs producer-configs.html | Confirmed: Default `all`; idempotence requires this |
| `enable.idempotence` default = true | context7 /websites/.../kafka-clients/4_2_0 | Confirmed: default since Kafka 3.0; `retries` defaults to `Integer.MAX_VALUE` |
| `send.buffer.bytes` default = 128 KB | confluent-docs producer-configs.html | Confirmed: 131072 |
| `receive.buffer.bytes` consumer default = 64 KB | confluent-docs consumer-configs.html | Confirmed: 65536 |
| `receive.buffer.bytes` producer default | confluent-docs producer-configs.html | Documented: 32768 (32 KB) — different from consumer |
| ZooKeeper removed in CP 8.0 (KRaft only) | confluent-docs versions-interoperability.html | Confirmed |
| s390x architecture support posture | confluent-docs versions-interoperability.html | Confirmed: GA Dec 2025; "Confluent does not provide support for any issues specific to this architecture" |
| Java 21 recommended for CP 8.2 | confluent-docs versions-interoperability.html | Confirmed: 21 recommended, 17 supported |
| `confluent.tier.feature` (broker) vs `confluent.tier.enable` (per-topic default) | confluent-docs tiered-storage.html | Confirmed: distinct properties; both required for full Tiered Storage on a topic |
| `lszcrypt -VV` is the correct s390-tools command | s390-tools manpage / IBM s390-tools repo | Confirmed; `lscrypt` does not exist on RHEL/Debian/Ubuntu |
| IBM JCE provider activation mechanism | IBM Semeru documentation, Java Security API | Confirmed: java.security edit OR `Security.insertProviderAt`; **no system-property switch** like `-Dcom.ibm.crypto.provider.useIBMJCE` exists |

### What Was Wrong in the Source Doc

| Source claim | Correction |
|--------------|------------|
| "send.buffer.bytes default is OS default, often 128KB" | Kafka default is **128 KB** (the property has its own default); `-1` selects OS default |
| "receive.buffer.bytes default is OS default, often 64KB" | Kafka default is **64 KB**; same `-1` semantics |
| "linger.ms default 0 ms" | Default is **5 ms** since Kafka 4.0 |
| "acks default 1" | Default is **all** since Kafka 3.0 |
| "acks=0 could be used for pure throughput" | **Never** in FSI durable workloads. `acks=0` defeats idempotence and silently loses records on broker failure. Permitted only for explicitly waived `best-effort` tier |
| "ZooKeeper" mentioned in upgrade ordering | Removed in CP 8.0; KRaft only |
| "Tiered Storage if using AWS MSK Tiered Storage" | Confluent Tiered Storage (KIP-405) is the canon target; MSK alternative is irrelevant on L1 |

## Related

- [Producer Batching Configuration](concepts/producer-batching-config.md) — internals; this article applies them to L1
- [LinuxONE Platform Foundations](../concepts/linuxone-platform-foundations.md) — SMC-R cross-frame transport details, UKO key lifecycle, JDK / IBM JCE provider rationale
- [LinuxONE Validation Suite](linuxone-validation-suite.md) — the test plan that exercises these knobs
- [LinuxONE Flink Validation & Tuning](linuxone-flink-validation-tuning.md) — paired Flink overlay
- [SLA Tiers](concepts/sla-tiers.md) — what you may and may not tune per tier
- [AKS Kafka Tuning](aks-kafka-tuning.md) — x86/Azure equivalent for cross-platform comparison
- [FSI Exactly-Once Pattern](fsi-exactly-once.md) — the durability bar tuning may not violate
