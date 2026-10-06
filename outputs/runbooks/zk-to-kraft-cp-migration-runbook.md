---
title: ZooKeeper → KRaft Migration on Confluent Platform
subtitle: Phase-by-phase property changes for `controller.properties` and `server.properties`, applied either by hand or through cp-ansible
audience: Confluent Platform operators on CP 7.5–7.9 who must reach KRaft before upgrading to CP 8.x
validated: 2026-09-28 against live Confluent docs via the `confluent-docs` MCP server — `platform/current/installation/migrate-zk-kraft`, `platform/7.9/installation/migrate-zk-kraft`, `platform/current/tools/kraft-migration-tool`, `platform/7.9/kafka-metadata/kraft` (limitations), `platform/7.9/kafka-metadata/config-kraft`, and `ansible/current/ansible-migrate-kraft` (last published 2026-09-16). Doc-verified only; not executed against a cluster.
confidence: high
related-canon: wiki/patterns/cp-mrc-migration-rehearsal-rig.md
---

# ZooKeeper → KRaft Migration on Confluent Platform

**Purpose:** get an existing ZooKeeper-backed CP cluster to pure KRaft with zero downtime,
with every properties-file edit spelled out per phase, and with the cp-ansible equivalent
of each step alongside it. ZooKeeper is gone in CP 8.0, so this migration is a hard
prerequisite for any 8.x upgrade.

---

## 1. Version gate — read this before anything else

| Constraint | Value |
|---|---|
| Migration supported on | CP **7.5 – 7.9** only |
| Production-GA from | CP **7.6.1** |
| Confluent's recommendation | CP **7.7.0 or later**; the 7.9 doc says upgrade to **7.9.10** (latest 7.9 patch) first |
| cp-ansible migration support | same-version migration on CP **7.6+** (7.6.0 not recommended for production) |
| `kafka-migration-check` ships in | CP **7.7.5+, 7.8.5+, 7.9.2+** |
| Dynamic controller quorum (KIP-853) | CP **7.9+** only |
| ZooKeeper removed in | CP **8.0** |

**Ordering is non-negotiable:** upgrade to the latest 7.9.x → migrate to KRaft → upgrade to
8.x. You cannot combine a version upgrade with the migration, and cp-ansible explicitly
refuses to do both at once.

Two more hard rules:

- **Every node must run the exact same CP version** — existing ZK brokers, new KRaft
  controllers, all of it. A controller older than the brokers makes the brokers fail to
  start in KRaft mode.
- **Combined mode is not supported on Confluent Platform.** You need dedicated controller
  nodes with `process.roles=controller`. Three or five, minimum three.

### Blockers — do not start if any of these apply

- You use the **Schema Registry Topic ACL Authorizer** (`topicacl_authorizer`). Not
  supported in KRaft. Move to the Schema Registry ACL Authorizer (`sracl_authorizer`) or
  Schema Registry RBAC first.
- You have **source-initiated cluster links** from a source cluster on CP 7.0.x or
  earlier. Upgrade the source to 7.1.0+ or convert to a default link.
- Any broker has a **failed log directory** under a multi-`log.dirs` config. During
  migration a single directory failure shuts the broker down, and a broker with a broken
  log dir cannot migrate (KAFKA-16431). Repair first.

Known cosmetic issue: Health+ reports KRaft controllers as brokers, so controller alerts
may misfire during and after the migration.

---

## 2. The five phases at a glance

| Phase | What happens | `kafka-migration-check status` | Rollback? |
|---|---|---|---|
| 1 | ZK mode, pre-flight and validation | `PREMIGRATION` | n/a |
| 2 | Provision + start KRaft controllers in migration mode | `PREMIGRATION` | Trivial — delete the controllers |
| 3 | Roll brokers into hybrid mode; metadata copies ZK → KRaft | `HYBRID_DUAL_WRITE` | Yes, single broker roll |
| 4 | Roll brokers to real KRaft brokers; controller still dual-writes to ZK | `PURE_DUAL_WRITE` | Yes, **two** broker rolls |
| 5 | Take controllers out of migration mode | `FINALIZED` | **No. Permanent.** |

Confluent recommends soaking in `PURE_DUAL_WRITE` for **1–2 weeks** before finalizing.
That is the last point where ZooKeeper still holds a consistent copy of your metadata.

---

## 3. Property change matrix

The whole migration is this table. Everything else is sequencing and verification.

### `controller.properties` (new KRaft controller nodes)

| Property | Phase 2 (set) | Phase 5 (finalize) |
|---|---|---|
| `process.roles` | `controller` | keep |
| `node.id` | unique, **must not collide with any `broker.id`** | keep |
| `controller.quorum.bootstrap.servers` | `h1:9093,h2:9093,h3:9093` (dynamic, 7.9+) | keep |
| `controller.quorum.voters` | `3000@h1:9093,...` (static, alternative) | keep |
| `controller.listener.names` | `CONTROLLER` | keep |
| `listeners` | `CONTROLLER://:9093` | keep |
| `listener.security.protocol.map` | include `CONTROLLER:<proto>` | keep |
| `log.dirs` / `metadata.log.dir` | controller metadata log path | keep |
| `zookeeper.metadata.migration.enable` | `true` | **remove** |
| `zookeeper.connect` | ZK connect string | **remove** |
| `confluent.cluster.link.metadata.topic.enable` | `true` | **remove** |
| `password.encoder.secret` | required if Cluster Linking is configured | **remove** |
| `authorizer.class.name` | `io.confluent.kafka.security.authorizer.ConfluentServerAuthorizer` if RBAC | keep |
| "other properties" (see §7.4) | copy from brokers | keep |

### `server.properties` (existing brokers)

| Property | Phase 3 (hybrid) | Phase 4 (KRaft broker) |
|---|---|---|
| `broker.id` | keep as-is | **remove** — replaced by `node.id` |
| `node.id` | — | set to the **same numeric value** as the old `broker.id` |
| `process.roles` | — | `broker` |
| `inter.broker.protocol.version` | set to your CP line's IBP (`3.9` on CP 7.9) | **remove** |
| `zookeeper.connect` | keep (already present) | **remove** |
| `zookeeper.metadata.migration.enable` | `true` | **remove** |
| `controller.quorum.bootstrap.servers` *or* `controller.quorum.voters` | same value as the controllers | **unchanged** |
| `controller.listener.names` | `CONTROLLER` | **unchanged** |
| `listener.security.protocol.map` | add `CONTROLLER:<proto>` | **unchanged** |
| `confluent.cluster.link.metadata.topic.enable` | `true` | **remove** |
| CONTROLLER-listener security (`sasl.mechanism.controller.protocol`, `listener.name.controller.*`) | set as needed | **keep** |
| `authorizer.class.name` (plain ACLs) | leave at `kafka.security.authorizer.AclAuthorizer` | → `org.apache.kafka.metadata.authorizer.StandardAuthorizer` |
| `confluent.authorizer.access.rule.providers` (RBAC) | leave `CONFLUENT,ZK_ACL` | → `CONFLUENT,KRAFT_ACL` |

> **`ZK_ACL` left in place after Phase 4 means the broker will not start.** This is the
> single most common self-inflicted outage in this migration.

---

## 4. Phase 1 — pre-flight

### 4.1 Snapshot everything

For a hand-built install with no IaC, treat this as the real safety net:

```bash
# On every broker, controller-to-be, and ZK node
TS=$(date +%Y%m%d-%H%M)
sudo tar czf /var/backups/cp-config-$(hostname)-$TS.tar.gz \
  /etc/kafka /etc/kafka-rest /etc/schema-registry /etc/ksqldb /etc/kafka-connect 2>/dev/null

# Diff brokers against each other to surface config drift before it bites you
for h in broker1 broker2 broker3; do
  ssh "$h" 'sudo cat /etc/kafka/server.properties' | grep -v '^#' | grep -v '^$' | sort > /tmp/$h.props
done
diff /tmp/broker1.props /tmp/broker2.props
```

Back up ZooKeeper's data directory (a cold copy of `dataDir` plus `dataLogDir` from a
stopped follower, or a `snapshot.*` + `log.*` copy) before you touch anything.

Inventory every ZK-dependent thing you own: `--zookeeper` flags in operator scripts,
`kafkastore.connection.url` in Schema Registry, monitoring that scrapes ZK JMX, cron jobs,
runbooks. All of it breaks at Phase 5.

### 4.2 Validate ZooKeeper ACLs — manually

The migration tooling assumes all ZK ACLs are valid and migrates malformed ones straight
into KRaft, where they can crash the controller on startup.

- **Every principal must carry a `User:` or `Group:` prefix.** Older Kafka did not enforce
  this. Missing prefixes make the migration **fail**.
- **No `patternType=PREFIXED` ACL may contain a wildcard in `name`.** Invalid syntax; it
  matches nothing. Not fatal to the migration, but fix it.

```bash
kafka-acls --bootstrap-server broker1:9092 --command-config /etc/kafka/admin.properties \
  --list > /tmp/acls-before.txt
grep -vE 'principal=(User|Group):' /tmp/acls-before.txt   # must return nothing
```

Keep `/tmp/acls-before.txt` — it is your post-migration diff baseline.

### 4.3 The `zookeeper.set.acl` trap

If your brokers were **ever** configured with `zookeeper.set.acl=true` — even if it is
`false` today — ZooKeeper ACLs may still be present on the znodes. If they are, the new
KRaft controllers must have the **same ZooKeeper permissions as the brokers**: the
`Client` section of the controllers' `jaas.conf` must match the brokers' `jaas.conf`, or
**Phase 2 fails**.

Alternative: disable ZK security for the duration. Add `skipACL=yes` to
`zookeeper.properties` on every ZK node and rolling-restart the ensemble.

### 4.4 Enable migration trace logging

Add to `$CONFLUENT_HOME/etc/kafka/log4j.properties` on brokers and controllers:

```properties
log4j.logger.org.apache.kafka.metadata.migration=TRACE
```

### 4.5 Run the pre-flight check

Only meaningful **before** any migration attempt. Running it mid-migration tells you
nothing — use `status` for that.

```bash
kafka-migration-check preflight-check \
  --controller-config /etc/kafka/kraft/controller.properties
```

It validates: controller config present with `zookeeper.metadata.migration.enable=true`;
ZK znodes and auth data reachable; no stale `/migration` znode or prior KRaft controller;
all expected brokers reachable and healthy; brokers and cluster links migration-ready
(each broker answers `ApiVersions` as a ZK broker with migration enabled); no orphaned
cluster-link metadata in ZK.

Success looks like:

```text
======================================================================
Running preflight migration check.
controllerConfigPath = ../etc/kafka/kraft/controller.properties
======================================================================
Checking controller config...
Loading zookeeper znodes..
Checking zookeeper znodes...
Testing outbound connections to brokers...
All preflight checks passed.
```

Fix every finding before proceeding.

### 4.6 Record the current IBP

```bash
kafka-configs --bootstrap-server broker1:9092 --command-config /etc/kafka/admin.properties \
  --entity-type brokers --entity-default --describe | grep inter.broker.protocol
grep inter.broker.protocol.version /etc/kafka/server.properties
```

You need this exact value for a Phase 3/4 rollback.

---

## 5. Phase 2 — provision and start KRaft controllers

### 5.1 Get the existing cluster ID

The controllers must be formatted with the **existing** cluster's ID, not a fresh one.

```bash
./bin/zookeeper-shell localhost:2181
# then:
get /cluster/id
# {"version":"1","id":"WZEKwK-bS62oT3ZOSU0dgw"}
```

### 5.2 Write `controller.properties`

Dynamic quorum (**recommended on CP 7.9.x** — lets you add/replace controllers later
without reconfiguring the cluster, and is what CP 8.x expects):

```properties
# /etc/kafka/kraft/controller.properties — controller 3000
process.roles=controller
node.id=3000

# Dynamic quorum (KIP-853). Prefer this over controller.quorum.voters on 7.9+.
controller.quorum.bootstrap.servers=controller1:9093,controller2:9093,controller3:9093
controller.listener.names=CONTROLLER
listeners=CONTROLLER://:9093
listener.security.protocol.map=CONTROLLER:PLAINTEXT

# Controller metadata log. Keep it off the broker log volumes.
log.dirs=/var/lib/kafka/kraft-controller-logs

# --- Migration-only block: every line here is removed again in Phase 5 ---
zookeeper.metadata.migration.enable=true
zookeeper.connect=zk1:2181,zk2:2181,zk3:2181
# Required for Cluster Linking to survive the migration:
confluent.cluster.link.metadata.topic.enable=true
# Required if Cluster Linking is configured, otherwise links break:
# password.encoder.secret=<same secret the brokers use>
# --- end migration-only block ---

# If the cluster uses RBAC:
# authorizer.class.name=io.confluent.kafka.security.authorizer.ConfluentServerAuthorizer

# Plus the "other properties" copied from your brokers — see section 7.4.
```

Static quorum, if you have a specific reason (pre-7.9, or a pinned voter set):

```properties
controller.quorum.voters=3000@controller1:9093,3001@controller2:9093,3002@controller3:9093
```

**`node.id` must not collide with any existing `broker.id`.** In KRaft, brokers and
controllers share one node-ID namespace. Convention: brokers stay at 0–999, controllers
start at 3000.

### 5.3 Generate directory UUIDs (dynamic quorum only)

```bash
./bin/kafka-storage random-uuid
# JEXY6aqzQY-32P5TStzaFg
```

One per controller. Record them next to node ID, host, and port:

```text
3000@controller1:9093:JEXY6aqzQY-32P5TStzaFg
3001@controller2:9093:MvDxzVmcRsaTz33bUuRU6A
3002@controller3:9093:07R5amHmR32VDA6jHkGbTA
```

### 5.4 Format storage on every controller

Dynamic quorum — the `--initial-controllers` string must be **byte-identical on all three
nodes**:

```bash
./bin/kafka-storage format \
  --config /etc/kafka/kraft/controller.properties \
  --cluster-id=WZEKwK-bS62oT3ZOSU0dgw \
  --initial-controllers "3000@controller1:9093:JEXY6aqzQY-32P5TStzaFg,3001@controller2:9093:MvDxzVmcRsaTz33bUuRU6A,3002@controller3:9093:07R5amHmR32VDA6jHkGbTA"
```

Alternative: format the first controller `--standalone` and the rest
`--no-initial-controllers`, then add them with `kafka-metadata-quorum add-controller` once
the standalone node is active. Using `--initial-controllers` avoids those extra steps
mid-migration.

Static quorum:

```bash
./bin/kafka-storage format \
  --config /etc/kafka/kraft/controller.properties \
  --cluster-id=WZEKwK-bS62oT3ZOSU0dgw
```

Expected output on CP 7.9:

```text
Formatting /var/lib/kafka/kraft-controller-logs with metadata version 3.9
```

### 5.5 Start the controllers

```bash
# Confluent packages ship this WITHOUT the .sh suffix; the doc example shows .sh
./bin/kafka-server-start /etc/kafka/kraft/controller.properties
# or, package install:
sudo systemctl start confluent-kcontroller
```

### 5.6 Verify

```bash
./bin/kafka-metadata-quorum --bootstrap-controller controller1:9093 describe --status
```

```text
ClusterId:              WZEKwK-bS62oT3ZOSU0dgw
LeaderId:               3000
LeaderEpoch:            1
HighWatermark:          276
MaxFollowerLag:         0
CurrentVoters:          [{"id": 3000, ...}, {"id": 3001, ...}, {"id": 3002, ...}]
CurrentObservers:       []
```

Confirm the `ClusterId` matches the value from `get /cluster/id`. Then:

```bash
kafka-migration-check status --controller-config /etc/kafka/kraft/controller.properties
# Apparent mode: PREMIGRATION
```

`PREMIGRATION` here is correct — controllers are up, ZooKeeper still owns `/controller`.

---

## 6. Phase 3 — roll brokers into hybrid mode

Metadata migration starts **automatically** once the last broker has restarted with the
migration properties. Roll one broker at a time and wait for each to rejoin.

### 6.1 Edit `server.properties` on each broker

```properties
# Existing ZK broker, listening on 9092
broker.id=0
listeners=PLAINTEXT://:9092
advertised.listeners=PLAINTEXT://broker1:9092
listener.security.protocol.map=PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT

# Pin the IBP to your CP line's version. CP 7.9 = Kafka 3.9 = 3.9.
inter.broker.protocol.version=3.9

# Enable migration
zookeeper.metadata.migration.enable=true

# Cluster Linking metadata topic
confluent.cluster.link.metadata.topic.enable=true

# Already present — leave it
zookeeper.connect=zk1:2181,zk2:2181,zk3:2181

# Point at the controllers. Use the SAME property you used in Phase 2.
controller.quorum.bootstrap.servers=controller1:9093,controller2:9093,controller3:9093
controller.listener.names=CONTROLLER
```

**Do not change the IBP as part of this migration.** Set it to the version you are already
running. Changing metadata version during a ZK→KRaft migration is not supported.

If the `CONTROLLER` listener is not `PLAINTEXT`, add the control-plane client config — see
§7.2.

### 6.2 Rolling restart

```bash
for b in broker1 broker2 broker3; do
  ssh "$b" 'sudo systemctl restart confluent-server'
  # wait for zero under-replicated partitions before moving on
  until [ "$(kafka-topics --bootstrap-server broker1:9092 \
        --command-config /etc/kafka/admin.properties \
        --describe --under-replicated-partitions | wc -l)" -eq 0 ]; do sleep 10; done
done
```

If a broker refuses to start, the migration properties are wrong — the broker deliberately
refuses to boot on a bad migration config. Read `server.log`.

### 6.3 Verify

Active controller log at `INFO`:

```text
Completed migration of metadata from ZooKeeper to KRaft.
```

Optionally check broker logs for a `znode_type` entry on `/controller` showing
`kraftControllerEpoch`. Then:

```bash
kafka-migration-check status --controller-config /etc/kafka/kraft/controller.properties
# Apparent mode: HYBRID_DUAL_WRITE
```

SCRAM credentials migrate from ZooKeeper to the controllers automatically in this phase;
existing clients are unaffected.

---

## 7. Phase 4 — brokers become KRaft brokers

Metadata is migrated but brokers are still ZK-mode, receiving `UpdateMetadata` and
`LeaderAndIsr` RPCs from the KRaft controller. This phase converts them.

### 7.1 Edit `server.properties` on each broker

```properties
process.roles=broker
node.id=0                      # SAME number as the old broker.id

listeners=PLAINTEXT://:9092
advertised.listeners=PLAINTEXT://broker1:9092
listener.security.protocol.map=PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT

# --- Removed / commented out ---
# broker.id=0
# inter.broker.protocol.version=3.9
# zookeeper.metadata.migration.enable=true
# zookeeper.connect=zk1:2181,zk2:2181,zk3:2181
# confluent.cluster.link.metadata.topic.enable=true

# --- Unchanged from Phase 3 ---
controller.quorum.bootstrap.servers=controller1:9093,controller2:9093,controller3:9093
controller.listener.names=CONTROLLER

# Plain ACLs: AclAuthorizer -> StandardAuthorizer
authorizer.class.name=org.apache.kafka.metadata.authorizer.StandardAuthorizer

# RBAC: ZK_ACL -> KRAFT_ACL (broker will NOT start if ZK_ACL remains)
# confluent.authorizer.access.rule.providers=CONFLUENT,KRAFT_ACL
```

Keep any CONTROLLER-listener security properties from Phase 3
(`sasl.mechanism.controller.protocol`, `listener.name.controller.<mechanism>.*`).

### 7.2 Secured CONTROLLER listener

mTLS:

```properties
listener.security.protocol.map=SSL:SSL,CONTROLLER:SSL
listener.name.controller.ssl.keystore.location=/var/ssl/private/controller.keystore.jks
listener.name.controller.ssl.keystore.password=${file:/var/ssl/creds:keystore}
listener.name.controller.ssl.truststore.location=/var/ssl/private/truststore.jks
listener.name.controller.ssl.truststore.password=${file:/var/ssl/creds:truststore}
# Mutual auth on the control plane
listener.name.controller.ssl.client.auth=required
```

SASL on the control plane:

```properties
listener.security.protocol.map=PLAINTEXT:PLAINTEXT,CONTROLLER:SASL_PLAINTEXT
sasl.mechanism.controller.protocol=PLAIN
listener.name.controller.plain.sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required \
    username="<controller-username>" \
    password="<controller-password>";
```

On the controller itself, the keystore lives on the `CONTROLLER` listener and the
inter-broker listener only needs a truststore — the controller is a client there, not a
server:

```properties
listener.security.protocol.map=CONTROLLER:SSL,BROKER:SSL
inter.broker.listener.name=BROKER
listener.name.controller.ssl.keystore.location=/var/ssl/private/controller.keystore.jks
listener.name.controller.ssl.truststore.location=/var/ssl/private/truststore.jks
listener.name.broker.ssl.truststore.location=/var/ssl/private/truststore.jks
```

### 7.3 Rolling restart and verify

Same one-at-a-time roll as Phase 3.

```bash
kafka-migration-check status --controller-config /etc/kafka/kraft/controller.properties
# Apparent mode: PURE_DUAL_WRITE
```

**Soak here for 1–2 weeks.** All brokers run KRaft, the controller still dual-writes to
ZooKeeper, and rollback is still on the table. Exercise a controller failover, verify
consumer group rebalances, and — if you rely on exactly-once — confirm transactional
producers survive a controller leader change before you move on.

### 7.4 "Other properties" to mirror onto the controllers

If a property is set on your brokers, it generally must also be set on the KRaft
controllers. Not exhaustive, but the documented list:

```text
auto.create.topics.enable                    metrics.reporters
compression.type                             min.insync.replicas
confluent.metrics.reporter.bootstrap.servers num.partitions
confluent.license.topic.replication.factor   offsets.retention.minutes
confluent.metadata.topic.replication.factor  offsets.topic.replication.factor
default.replication.factor                   transaction.state.log.replication.factor
delete.topic.enable                          transaction.state.log.min.isr
message.max.bytes                            unclean.leader.election.enable
```

Plus all security properties — truststore locations in particular.

For Control Center to work in KRaft mode you must enable Confluent Metrics Reporter on
**both brokers and KRaft controllers** (it is off by default):

```properties
metric.reporters=io.confluent.metrics.reporter.ConfluentMetricsReporter
confluent.metrics.reporter.bootstrap.servers=broker1:9092
```

---

## 8. Phase 5 — finalize (point of no return)

### 8.1 Edit `controller.properties` on each controller

```properties
process.roles=controller
node.id=3000
controller.quorum.bootstrap.servers=controller1:9093,controller2:9093,controller3:9093
controller.listener.names=CONTROLLER
listeners=CONTROLLER://:9093

# --- Removed ---
# zookeeper.metadata.migration.enable=true
# zookeeper.connect=zk1:2181,zk2:2181,zk3:2181
# confluent.cluster.link.metadata.topic.enable=true
# password.encoder.secret=...
```

### 8.2 Rolling restart controllers, one at a time

Wait for each to rejoin the quorum (`kafka-metadata-quorum describe --status`) before
restarting the next.

```bash
kafka-migration-check status --controller-config /etc/kafka/kraft/controller.properties
# Apparent mode: FINALIZED
```

### 8.3 Decommission ZooKeeper

Only after `FINALIZED`, and only if ZK is not managing another Kafka cluster:

```bash
sudo systemctl stop confluent-zookeeper
sudo systemctl disable confluent-zookeeper
```

### 8.4 Sweep the rest of the stack

| Component | ZooKeeper form | KRaft form |
|---|---|---|
| Schema Registry | `kafkastore.connection.url=zk:2181` | `kafkastore.bootstrap.servers=broker:9092` |
| Clients / services | `zookeeper.connect=zk:2181` | `bootstrap.servers=broker:9092` |
| Admin tooling | `kafka-topics --zookeeper zk:2181` | `kafka-topics --bootstrap-server broker:9092 --command-config <props>` |
| Cluster ID lookup | `zookeeper-shell zk:2181 get /cluster/id` | `kafka-metadata-quorum ... describe --status` |

Also remove ZK JMX scrapes from monitoring and delete the ZK-era alert rules.

---

## 9. cp-ansible path

Same five phases, driven by `confluent.platform.ZKtoKraftMigration.yml`. Confluent Ansible
does host-by-host rolling restarts with a health check between each.

### 9.1 What cp-ansible will and will not do

- Same-CP-version migration only, CP 7.6+. **Upgrade first, migrate second** — never both
  in one run.
- Isolated mode only (`process.roles=controller` / `process.roles=broker`). Combined mode
  is not a migration target.
- Co-located ZK and broker on one node is fine. ZK → KRaft on the same node is fine, but
  **watch for port collisions** — override `kafka_controller_jolokia_port` and
  `kafka_controller_jmxexporter_port`.
- ACLs are migrated.
- One-to-many and many-to-one ZK→controller node counts are supported.
- Same cluster config on both sides — differing security protocols between the ZK cluster
  and the KRaft cluster is not recommended.

### 9.2 Inventory changes

Start from the **same inventory file** you used for the ZooKeeper deployment.

```yaml
all:
  vars:
    kraft_migration: true

kafka_controller:
  hosts:
    controller1.example.com:
    controller2.example.com:
    controller3.example.com:

zookeeper:
  hosts:
    zk1.example.com:
    zk2.example.com:
    zk3.example.com:

kafka_broker:
  hosts:
    broker1.example.com:
    broker2.example.com:
    broker3.example.com:
```

Co-located ZK and controller — avoid the port clash:

```yaml
kafka_controller:
  vars:
    kafka_controller_jolokia_port: 7777
    kafka_controller_jmxexporter_port: 8081
```

SASL/SCRAM clusters — set the controller-to-controller auth method:

```yaml
all:
  vars:
    sasl_protocol: scram

kafka_controller:
  vars:
    kafka_controller_sasl_protocol: plain,scram
```

Cluster Linking — **mandatory**, or links stop working and must be recreated after
migration:

```yaml
all:
  vars:
    kafka_controller_custom_properties:
      password.encoder.secret=<encoder-secret>
      password.encoder.old.secret=<encoder-old-secret>
```

Use the same values Kafka already uses. Remove them after migration.

### 9.3 Run it — two-step, with a validation gate

This is the recommended shape, because rollback is only possible while the cluster is in
dual write.

```bash
# Phase 1: up to Dual Write mode (equivalent to manual Phases 2-4)
ansible-playbook -i inventory/hosts.yml confluent.platform.ZKtoKraftMigration.yml \
  --tags migrate_to_dual_write
```

Validation gate — verify data migrated with no loss, then switch the authorizer on
**both** controller and broker:

```yaml
kafka_broker_custom_properties:
  authorizer.class.name: org.apache.kafka.metadata.authorizer.StandardAuthorizer

kafka_controller_custom_properties:
  authorizer.class.name: org.apache.kafka.metadata.authorizer.StandardAuthorizer
```

> The `migrate_to_kraft` tag **does not apply custom-property changes**. You must push the
> authorizer change with the `all` playbook before Phase 2:

```bash
ansible-playbook -i inventory/hosts.yml confluent.platform.all \
  --tags kafka_controller,kafka_broker --skip-tags package
```

Then finalize:

```bash
# Phase 2: complete the migration (equivalent to manual Phase 5)
ansible-playbook -i inventory/hosts.yml confluent.platform.ZKtoKraftMigration.yml \
  --tags migrate_to_kraft
```

One-step (no pause at dual write — not recommended for production):

```bash
ansible-playbook -i inventory/hosts.yml confluent.platform.ZKtoKraftMigration.yml
```

### 9.4 Post-migration cleanup — required before any other playbook

- Remove `kraft_migration: true` (or set it `false`).
- Delete the entire `zookeeper:` section from the inventory.
- Remove `password.encoder.secret` / `password.encoder.old.secret` from
  `kafka_controller_custom_properties`.
- Remove any other ZK-only or migration-only variables.
- Stop the ZK ensemble if it is not serving another cluster.

If you skip this, `confluent.platform.all` hard-fails with:

```text
kraft_migration flag is enabled. This flag should only be used with
confluent.platform.ZKtoKraftMigration playbook. Set kraft_migration: false
to run this playbook.
```

That guard is deliberate — it stops migration logic from re-running against a migrated
cluster.

### 9.5 cp-ansible troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Jolokia poll returns `ZkMigrationState value: 2` after 10 attempts | Cluster is large; migration is slower than the retry budget | Raise `metadata_migration_retries` |
| `conditional check '(jolokia_output.content \| from_json).value.Value == 1' failed ... Expecting value: line 1 column 1` | KRaft controller crashed, or Jolokia disabled on the controller | Check controller `server.log`; enable Jolokia |
| Same conditional, but `'dict object' has no attribute 'value'` | `confluent_package_version` is 7.5 or earlier | Use CP 7.6+ |
| Authorization error on an RBAC cluster | Controller and broker do not share principals | Add both the Kafka and KRaft controller principals to the super-user variables on **both** the broker and the controller |
| `AccessDeniedException: /etc/controller/server.properties` (mTLS + RBAC + custom user) | `kafka_controller_user`/`kafka_controller_group` only defined under `kraft_controller` | Also define them under `all` and `kafka_broker` |
| `Migration already completed. Cluster is in KRaft mode (ZkMigrationState=3).` | Playbook re-run against a finalized cluster | Nothing to do — complete the post-migration checklist, use `confluent.platform.all` from now on |

---

## 10. Rollback

**Only possible before Phase 5 completes.** After `FINALIZED`, there is no path back.

### From Phase 2 (controllers provisioned, brokers untouched)

Shut down and delete the KRaft controller nodes. Done.

### From Phase 3 (hybrid)

1. Shut down and delete the controllers. *(If you must reuse a controller host, delete all
   KRaft metadata directories on it first — stale metadata will poison a later attempt.)*
2. Clear ZooKeeper state, **fast** — the cluster has no controller until you finish:
   ```bash
   ./bin/zookeeper-shell zk1:2181
   deleteall /controller     # lets a broker become the ZK controller again
   get /migration            # inspect
   delete /migration         # clear migration state
   ```
   Until `/controller` is deleted, ignore broker log errors about failing to reach the
   KRaft controller. They clear after the roll.
3. On all brokers, remove the `__cluster_metadata` log directory from every entry in
   `log.dirs`.
4. Rolling restart, one broker at a time, having removed from `server.properties`:
   `zookeeper.metadata.migration.enable`, `controller.listener.names`,
   `controller.quorum.voters` / `controller.quorum.bootstrap.servers`,
   `confluent.cluster.link.metadata.topic.enable`, and `inter.broker.protocol.version`
   (or restore it to the original value).
5. Verify the cluster is healthy in ZooKeeper mode.

### From Phase 4 (brokers on KRaft, dual write) — two rolls

**Roll 1 — brokers back to hybrid.** Per broker:

- Remove `process.roles`
- Replace `node.id=<id>` with `broker.id=<id>` (same number)
- Restore `zookeeper.connect` and any other ZK-specific config (`zookeeper.ssl.protocol`, etc.)
- **Keep `zookeeper.metadata.migration.enable=true`.** This must stay on through the first
  roll or the rollback breaks.

You are now back in `HYBRID_DUAL_WRITE`. From here you can either finish the rollback or
retry Phase 4. **Do not linger in this state.**

**Roll 2 — steps 2, 3, 4 of the Phase 3 rollback**, plus:

- Plain ACLs: `authorizer.class.name` back to `kafka.security.authorizer.AclAuthorizer`
- RBAC: `KRAFT_ACL` back to `ZK_ACL` in `confluent.authorizer.access.rule.providers`
- Now remove `zookeeper.metadata.migration.enable`

cp-ansible has no rollback playbook. Roll back by hand using the procedure above.

---

## 11. Doc drift and gotchas

Found while validating against live docs on 2026-09-28:

1. **IBP version in the `current` doc is wrong for 7.x.** `platform/current` shows
   `inter.broker.protocol.version=4.1` in the bullet list and `4.3` in the code example —
   both are 8.x-era values on a page that only applies to 7.5–7.9. The
   `platform/7.9` version of the same page correctly shows `3.9`. **Use the
   version-pinned URL**, and set the IBP to the value matching your CP line.
2. **`kafka-server-start.sh`** — the docs use the `.sh` suffix, but Confluent's DEB/RPM
   packages install the binary as `kafka-server-start`. On packaged installs use
   `systemctl start confluent-server` / `confluent-kcontroller` anyway.
3. **`_cluster_metadata` vs `__cluster_metadata`** — the rollback sections say
   "remove the `_cluster_metadata` log file". The actual on-disk directory is
   `__cluster_metadata-0` (two underscores) inside each `log.dirs` entry. Remove the
   directory, not a file.
4. **The `current` doc lists `controller.quorum.voters` as required** in the Phase 2
   bullets while the recommended example uses `controller.quorum.bootstrap.servers`. They
   are alternatives, not both. Pick one and use the same one on brokers and controllers.
5. **`--initial-controllers` string must be identical across controllers** — any
   whitespace or ordering difference produces a split quorum.
6. **Controller node IDs must not overlap broker IDs.** Shared namespace in KRaft.
7. **`ZK_ACL` → `KRAFT_ACL` is a hard startup dependency**, not a warning.

---

## 12. Command cheat sheet

```bash
# Pre-flight (before migration only)
kafka-migration-check preflight-check --controller-config /etc/kafka/kraft/controller.properties

# Status (any time) -> PREMIGRATION | HYBRID_DUAL_WRITE | PURE_DUAL_WRITE | FINALIZED
kafka-migration-check status --controller-config /etc/kafka/kraft/controller.properties

# Existing cluster ID, from ZooKeeper
./bin/zookeeper-shell zk1:2181   # then: get /cluster/id

# Directory UUID for dynamic quorum
./bin/kafka-storage random-uuid

# Format a controller (dynamic quorum)
./bin/kafka-storage format --config /etc/kafka/kraft/controller.properties \
  --cluster-id=<cluster-id> --initial-controllers "<id@host:port:dirUUID>,..."

# Quorum health
./bin/kafka-metadata-quorum --bootstrap-controller controller1:9093 describe --status
./bin/kafka-metadata-quorum --bootstrap-controller controller1:9093 describe --replication

# Under-replicated partitions gate between rolling restarts
kafka-topics --bootstrap-server broker1:9092 --command-config /etc/kafka/admin.properties \
  --describe --under-replicated-partitions

# ACL diff, before vs after
kafka-acls --bootstrap-server broker1:9092 --command-config /etc/kafka/admin.properties --list
```

Migration state via JMX (what cp-ansible polls through Jolokia):

```text
kafka.controller:type=KafkaController,name=ZkMigrationState
  0 = NONE   1 = MIGRATION   2 = POST_MIGRATION (dual write)   3 = KRAFT (finalized)
```

---

## 13. FSI overlay

For regulated workloads, add these to the standard procedure:

- **mTLS on the CONTROLLER listener**, not just the broker listeners. Control-plane
  traffic carries ACLs and SCRAM credentials during migration.
- **Exactly-once**: run a transactional producer against the cluster through a deliberate
  controller failover while in `PURE_DUAL_WRITE`, and confirm no duplicate or lost
  transactions, before finalizing. This is the last state from which you can retreat.
- **Audit logs**: confirm the audit log topic's cluster link / metadata still resolves
  after Phase 4; `confluent.cluster.link.metadata.topic.enable` is removed in that phase.
- **RBAC**: the `ZK_ACL` → `KRAFT_ACL` switch changes the authorization path. Re-run your
  access-control test matrix in `PURE_DUAL_WRITE`, not after finalizing.
- **Change window**: the 1–2 week `PURE_DUAL_WRITE` soak means the migration spans
  multiple change windows. Plan Phase 5 as its own approved change.

---

## 14. Sources

All fetched 2026-09-28 via the `confluent-docs` MCP server:

- `docs.confluent.io/platform/current/installation/migrate-zk-kraft.html`
- `docs.confluent.io/platform/7.9/installation/migrate-zk-kraft.html` — authoritative for 7.9 IBP values
- `docs.confluent.io/platform/current/tools/kraft-migration-tool.html`
- `docs.confluent.io/platform/7.9/kafka-metadata/kraft.html` — limitations and known issues
- `docs.confluent.io/platform/7.9/kafka-metadata/config-kraft.html` — controller config, security, other properties
- `docs.confluent.io/ansible/current/ansible-migrate-kraft.html` — last published 2026-09-16
- Confluent also publishes downloadable checklists on the migration page:
  `zooKeeper-kraft-migration-checklist.docx` and `kraft-zookeeper-revert-checklist.docx`

For CFK-managed deployments, the equivalent is
`docs.confluent.io/operator/current/co-migrate-kraft.html` — not covered here.
