---
title: Exactly-Once Semantics
tags: [kafka fsi exactly-once transactions]
sources:
  - https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/
  - https://docs.confluent.io/kafka/design/delivery-semantics.html
  - https://www.confluent.io/blog/transactions-apache-kafka/
  - https://cwiki.apache.org/confluence/display/KAFKA/KIP-447:+Producer+scalability+for+exactly+once+semantics
  - https://cwiki.apache.org/confluence/display/KAFKA/KIP-679:+Producer+will+enable+the+strongest+delivery+guarantee+by+default
  - https://flink.apache.org/2018/02/28/an-overview-of-end-to-end-exactly-once-processing-in-apache-flink-with-apache-kafka-too/
related: [concepts/consumer-group-rebalancing, concepts/consumer-lag-monitoring, patterns/fsi-exactly-once, concepts/flink-checkpointing, patterns/transactional-outbox, patterns/saga-process-manager, patterns/event-handler-substrate-selection, concepts/queues-for-kafka-share-groups]
confidence: medium
last_updated: 2026-04-11
last_validated: 2026-04-28
---

# Exactly-Once Semantics

## Summary

Exactly-once semantics (EOS) guarantees that each message produced to Kafka is written and processed exactly once, even across producer retries, broker failures, and consumer restarts. Introduced in Apache Kafka 0.11 (KIP-98), EOS is built on two layers: idempotent production (single-partition deduplication via Producer ID and sequence numbers) and transactions (cross-partition atomicity via a two-phase commit protocol coordinated through the `__transaction_state` internal topic). Consumers must set `isolation.level=read_committed` to observe only committed transactional data. Kafka Streams, Flink, and Connect each build on these primitives to provide framework-level EOS guarantees. The scope of EOS is strictly Kafka-internal; end-to-end exactly-once delivery to external systems requires additional patterns such as the outbox pattern, idempotent consumers, or saga orchestration.

## Detail

### Delivery Guarantee Spectrum

| Guarantee | Mechanism | Risk |
|-----------|-----------|------|
| At-most-once | `acks=0` or commit offsets before processing | Data loss |
| At-least-once | `acks=all` with retries, commit after processing | Duplicates |
| Exactly-once | Idempotent producer + transactions + `read_committed` consumer | Highest overhead |

### Idempotent Producer

Idempotent production prevents duplicate writes to a single partition caused by producer retries.

#### How it works

1. On initialization, the broker assigns each producer a unique **Producer ID (PID)**.
2. The producer maintains a **monotonically increasing sequence number** per topic-partition.
3. The broker tracks a high-water mark sequence per `(PID, partition)` pair and rejects any message whose sequence number is not exactly one greater than the last accepted value.
4. On duplicate delivery (same PID + same sequence), the broker silently deduplicates -- the message is not written a second time.
5. Ordering is preserved with up to 5 in-flight requests because the broker uses sequence numbers to detect and reorder out-of-sequence batches.

#### Epoch fencing

When a producer with the same `transactional.id` restarts, the broker bumps the **epoch** for that PID. Any older producer instance with a lower epoch is fenced and will receive a `ProducerFencedException` on its next operation, preventing zombie producers from writing stale data.

#### Configuration

| Property | Required Value | Default | Since |
|----------|---------------|---------|-------|
| `enable.idempotence` | `true` | `true` (KIP-679) | 0.11 (default changed in 3.0) |
| `acks` | `all` (`-1`) | `all` (KIP-679) | 0.11 requirement (default changed in 3.0) |
| `max.in.flight.requests.per.connection` | `<= 5` | `5` | 0.11 requirement |
| `retries` | `> 0` | `2147483647` | 0.11 requirement (default changed in 2.1) |

**KIP-679 bug note**: In Kafka 3.0.0 and 3.1.0, a bug prevented the idempotence default from being applied. Fixed in 3.0.1, 3.1.1, and 3.2.0.

### Transactional Producer

Transactions extend idempotent production to provide atomicity across multiple partitions and topics. Either all messages in a transaction become visible to `read_committed` consumers, or none do.

#### Configuration

| Property | Value / Default | Notes |
|----------|----------------|-------|
| `transactional.id` | User-defined static string | Must be unique per logical producer; survives restarts; used to fence zombies |
| `transaction.timeout.ms` | `60000` (60s) | Coordinator aborts the transaction if it exceeds this duration |
| `enable.idempotence` | `true` (forced) | Automatically enabled when `transactional.id` is set |

The broker-side maximum is controlled by `transaction.max.timeout.ms` (default: `900000` / 15 minutes). A producer's `transaction.timeout.ms` cannot exceed this value.

#### API

```java
Properties props = new Properties();
props.put("bootstrap.servers", "broker1:9092,broker2:9092,broker3:9092");
props.put("transactional.id", "payments-processor-1");
// enable.idempotence=true and acks=all are forced by transactional.id

KafkaProducer<String, String> producer = new KafkaProducer<>(props);

producer.initTransactions();  // register transactional.id, fence zombies, bump epoch

try {
    producer.beginTransaction();

    producer.send(new ProducerRecord<>("payments.transaction.completed", key, value));
    producer.send(new ProducerRecord<>("audit.payment.events", key, auditValue));

    // atomically commit consumer offsets with the transaction
    producer.sendOffsetsToTransaction(offsets, consumerGroupMetadata);

    producer.commitTransaction();  // two-phase commit
} catch (KafkaException e) {
    producer.abortTransaction();   // roll back all writes in this transaction
    throw e;
}
```

#### Transaction coordinator and `__transaction_state`

The **transaction coordinator** is a broker-side component that manages the lifecycle of each transaction. It is determined by hashing `transactional.id` to a partition of the `__transaction_state` internal topic.

| Broker Config | Default | Purpose |
|---------------|---------|---------|
| `transaction.state.log.num.partitions` | `50` | Partition count for `__transaction_state` |
| `transaction.state.log.replication.factor` | `3` | Replication factor |
| `transaction.state.log.min.isr` | `2` | Minimum in-sync replicas |

#### Transaction protocol flow

1. **FindCoordinator** -- producer locates its transaction coordinator.
2. **InitProducerId** -- coordinator assigns PID and epoch; fences prior instances with the same `transactional.id`.
3. **AddPartitionsToTxn** -- registers each new partition the producer writes to.
4. **Produce** -- standard produce requests with the transactional bit set.
5. **AddOffsetsToTxn** -- registers the consumer group's `__consumer_offsets` partition.
6. **TxnOffsetCommit** -- writes consumer offsets within the transaction scope.
7. **EndTxn (COMMIT/ABORT)** -- triggers the two-phase commit or abort.
8. **WriteTxnMarkers** -- coordinator writes COMMIT/ABORT markers to all participating data partitions.

### Consumer: `isolation.level`

| Property | Values | Default |
|----------|--------|---------|
| `isolation.level` | `read_uncommitted`, `read_committed` | `read_uncommitted` |

**`read_uncommitted`** (default): The consumer sees all messages as soon as they are written, including messages from in-progress or aborted transactions. Highest throughput, lowest latency, but exposes dirty reads.

**`read_committed`**: The consumer only sees messages with offsets below the **Last Stable Offset (LSO)** -- messages from committed transactions and non-transactional messages. Messages from aborted transactions are filtered out. Messages from in-progress transactions are buffered until the transaction completes.

Key nuance: `read_committed` does **not** filter non-transactional messages. It only gates on transactional message visibility. A `read_committed` consumer reads non-transactional writes unconditionally.

### Kafka Streams EOS

Kafka Streams wraps the consume-process-produce loop in a Kafka transaction, ensuring that reading input, updating state stores, writing output, and committing offsets happen as a single atomic unit.

#### Configuration

| Property | Value | Notes |
|----------|-------|-------|
| `processing.guarantee` | `exactly_once_v2` | Requires broker >= 2.5 |
| `commit.interval.ms` | `100` | Default under EOS (vs `30000` for `at_least_once`) |

#### v1 vs v2

| Config Value | Introduced | Deprecated | Removed | Producer Model |
|-------------|-----------|-----------|---------|----------------|
| `exactly_once` (v1) | 0.11 | 3.0 | 4.0 | One producer per input partition (per task) |
| `exactly_once_beta` | 2.5 | 3.0 (renamed) | 4.0 | One producer per StreamThread |
| `exactly_once_v2` | 3.0 (rename of beta) | -- | -- | One producer per StreamThread |

**v1 problem**: Created a separate transactional producer per input partition. Each producer requires its own memory buffers, thread, and network connections. Resource consumption scales linearly with partition count.

**v2 solution (KIP-447)**: Uses a single producer per `StreamThread`. Leverages the ability to dynamically add partitions to a transaction without requiring a static mapping between `transactional.id` and input partitions. Dramatically reduces resource overhead.

**Broker requirements**: Minimum 3 brokers in production for `transaction.state.log.replication.factor=3` and `transaction.state.log.min.isr=2`. Development environments can relax these.

### Flink EOS with Kafka

Flink achieves end-to-end exactly-once with Kafka by coupling its checkpointing mechanism with Kafka's transactional API through a two-phase commit protocol. See also [Flink Checkpointing](flink-checkpointing.md).

#### Two-phase commit protocol

1. **Pre-commit**: When a checkpoint barrier arrives, the Kafka sink flushes all pending records and pre-commits the Kafka transaction. Records are written but not yet visible to `read_committed` consumers.
2. **Commit**: Once the checkpoint coordinator confirms all operators have successfully checkpointed, Flink commits the Kafka transaction. Records become visible.
3. **Abort on failure**: If the checkpoint fails, the transaction is aborted. Flink restores from the last successful checkpoint.

#### Implementation evolution

- **Flink 1.4.0**: Introduced `TwoPhaseCommitSinkFunction`, the foundational abstract class.
- **Flink 1.14+**: Introduced the unified `KafkaSink` API implementing `TwoPhaseCommittingSink`, replacing the older `FlinkKafkaProducer`.

#### Critical timeout relationship

```
transaction.timeout.ms > checkpoint_interval + max_restart_duration
```

If Flink's checkpoint takes longer than `transaction.timeout.ms`, Kafka aborts the transaction. This causes **silent data loss**: Flink considers the records processed (they were checkpointed), but Kafka discards them because the transaction expired. The broker-side `transaction.max.timeout.ms` defaults to 900,000ms (15 min) and caps the producer-side value.

In Confluent Cloud managed Flink, the platform handles checkpointing, transaction timeouts, and the two-phase commit lifecycle transparently.

### Connect EOS (KIP-618)

Source connectors gained exactly-once support in **Kafka 3.3+** (KIP-618). The framework uses a single transactional producer per connector to atomically write source records and source offset commits. Requirements:

- Broker version >= 3.3
- `exactly.once.source.support=enabled` on the Connect worker
- Connector must implement the `ExactlyOnceSupport` interface

### Performance Impact

| Scenario | Overhead |
|----------|----------|
| Idempotent producer (no transactions) | Negligible -- slight PID/sequence tracking overhead |
| Transactions with short commit interval (~100ms) | 15-30% throughput degradation depending on message size |
| Transactions with long commit interval (~30s) | Minimal for messages >= 1KB |
| Per-transaction fixed cost | Small RPC overhead to coordinator; amortize by batching more messages per transaction |

Key factors:

- Each producer processes transactions **sequentially** -- no pipelining of open transactions on a single producer. Use multiple transactional producers for higher throughput.
- `read_committed` consumers experience added latency because they wait for the LSO to advance (in-progress transactions block downstream visibility).
- KRaft mode (Kafka 4.0+) brings significant performance improvements to transactional processing with faster transaction commits and reduced coordinator overhead.

### Limitations

**Kafka-internal scope only.** EOS applies to the Kafka-to-Kafka path: produce, consume, produce. It does not extend to external systems. For end-to-end exactly-once with databases, APIs, or file systems, use:

- **Outbox pattern**: Write to a database and outbox table in the same DB transaction; CDC publishes outbox events to Kafka. See [Transactional Outbox and CDC Ingress](../patterns/transactional-outbox.md).
- **Idempotent consumers**: Design downstream systems to handle duplicates via idempotency keys or upserts.
- **Saga pattern**: Orchestrate compensating transactions across services. See [Saga / Process Manager](../patterns/saga-process-manager.md).

> **Say it out loud when designing:** *any effect on an external system is at-least-once, always, regardless of what `processing.guarantee` is set to.* A handler that calls a payment API, writes to a database, or sends a notification has an effect outside the transaction. The transaction can be aborted; the payment cannot. This is the single most common EOS misconception, and no configuration change addresses it — only an idempotent effect does.

### Choosing a delivery guarantee

At-least-once plus an idempotent sink beats EOS for most handlers, and costs less. EOS is a latency and throughput tax (transaction coordination, extra round trips, `read_committed` LSO waits) — pay it where money moves, not uniformly.

```mermaid
flowchart TD
  A[New handler] --> B{Sink idempotent<br/>or has natural dedup key?}
  B -->|Yes| C[At-least-once<br/>+ idempotent write]
  B -->|No| S{Is the effect inside Kafka?<br/><i>read-process-write, one cluster</i>}
  S -->|"No — external system"| H["At-least-once<br/>+ explicit dedup store<br/><b>EOS cannot cross this boundary</b>"]
  S -->|Yes| D{Handler owns durable state<br/><i>or</i> duplicate visible to<br/>a customer or ledger?}
  D -->|Yes| F["Transactional EOS<br/>processing.guarantee = exactly_once_v2"]
  D -->|No| C
  C --> Z[Record the choice in<br/>the service manifest]
  F --> Z
  H --> Z
  style H fill:#FDF3DC,stroke:#F2A900,color:#173A6C
```

**Record the choice per handler in the service manifest.** A delivery guarantee that lives only in someone's memory is not a guarantee — and in regulated contexts it is an audit finding. State it in the terms a reviewer uses ("no duplicate postings to the ledger"), not only as a config value. See [FSI Exactly-Once](../patterns/fsi-exactly-once.md).

**Share groups have no EOS path at all** — acknowledgement is per record and at-least-once only. Where a share group is the substrate, an idempotent handler is a precondition, not an optimisation. See [Queues for Kafka (Share Groups)](queues-for-kafka-share-groups.md) and [Event Handler Substrate Selection](../patterns/event-handler-substrate-selection.md).

**Transaction timeout edge cases:**

- Long-running processing that exceeds `transaction.timeout.ms` causes the coordinator to proactively abort. The producer receives `InvalidTxnStateException` or `ProducerFencedException`.
- Consumer group rebalances during transactions: v1 (`exactly_once`) caused frequent transaction aborts and reprocessing. v2 (`exactly_once_v2`) handles this more gracefully with the per-thread producer model.

**Broker resource consumption:**

- Each active `transactional.id` consumes memory on the transaction coordinator.
- `__transaction_state` with 50 partitions and RF=3 adds storage and replication overhead.
- Flink's `KafkaSink` can create new `transactional.id` values per checkpoint, which may cause broker-side memory pressure if not managed (tracked in FLINK-34554).

**Cross-cluster:** Kafka transactions do not span multiple Kafka clusters. Cluster Linking mirrors data but does not propagate transaction boundaries.

## Related

- [Consumer Group Rebalancing](consumer-group-rebalancing.md) -- rebalance behavior during transactions, v1 vs v2 implications
- [Consumer Lag Monitoring](consumer-lag-monitoring.md) -- LSO-based lag under `read_committed`
- [FSI Exactly-Once Pattern](../patterns/fsi-exactly-once.md) -- regulatory reporting and audit requirements for EOS in financial services
- [Transactional Outbox and CDC Ingress](../patterns/transactional-outbox.md) -- the outbox as the answer to the external-effect boundary
- [Saga / Process Manager](../patterns/saga-process-manager.md) -- compensating transactions where the effects span services
- [Event Handler Substrate Selection](../patterns/event-handler-substrate-selection.md) -- effect location constrains which substrates can offer EOS at all
- [Flink Checkpointing](flink-checkpointing.md) -- checkpoint mechanics underlying Flink's two-phase commit with Kafka
- [Producer Batching Config](producer-batching-config.md) -- batching and `max.in.flight.requests.per.connection` interaction with idempotence
