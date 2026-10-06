---
title: Schema Registry Manual Install — Required ACLs and RBAC Role Bindings
tags: [schema-registry, acls, rbac, security, kafkastore, troubleshooting, mrc]
sources: []
related: [concepts/schema-registry-best-practices, patterns/yaml-topic-rbac-admin-tool, concepts/kafka-streams-schema-patterns]
confidence: medium
last_updated: 2026-09-09
last_validated: 2026-09-09
---

# Schema Registry Manual Install — Required ACLs and RBAC Role Bindings

## Summary

When Schema Registry (SR) is installed by hand (no `cp-ansible`) against a Kafka cluster running
plain ACL authorization, SR startup fails with a `TopicAuthorizationException` unless the SR
service principal is explicitly granted a specific set of broker-side ACLs — `cp-ansible` normally
grants these automatically, so the requirement is easy to miss on a hand-rolled install. This
article covers the broker-side ACL list, the RBAC role-binding equivalent, and a subtle
`kafkastore.group.id` default-naming gotcha that silently breaks ACL matching if the consumer-group
grant is copied in as a literal string.

## Pattern

### Why this happens

SR's entire state is derived from consuming its internal `_schemas` topic (single partition,
compacted, write-ahead log) — every SR node produces to and consumes from it continuously, and a
new node bootstraps by replaying it from offset 0. SR's own Kafka client config lives under the
`kafkastore.*` namespace (`kafkastore.bootstrap.servers`, `kafkastore.topic` default `_schemas`,
`kafkastore.topic.replication.factor` default 3, `kafkastore.group.id`). On startup, SR calls
`AdminClient.createTopics()` (or connects to a pre-created topic) and starts a consumer/producer
against it — every one of those calls is subject to normal Kafka broker authorization, exactly
like any other client. `cp-ansible` provisions the required ACLs/role bindings as part of its
install; a manual install has to do this step explicitly, and skipping it is the single most common
cause of `TopicAuthorizationException` / `StoreInitializationException` on SR startup.

Note `auto.create.topics.enable` is unrelated here — it only governs *implicit* topic creation via
produce/fetch/metadata requests. SR's explicit `AdminClient.createTopics()` call bypasses that
setting entirely, and ACLs are never implicit: even a pre-created `_schemas` topic still requires
explicit Read/Write ACLs for the SR principal.

### Required ACLs (ACL-only clusters)

Source: Confluent's "Authorizing Access to the Schemas Topic" documentation
(`docs.confluent.io/platform/current/schema-registry/security/index.html`).

| Resource | Operation(s) | Notes |
|---|---|---|
| `Topic:_schemas` | `Write`, `Read` | Produce/consume the backing topic |
| `Topic:_schemas` | `Describe`, `DescribeConfigs` | Metadata + config lookups on startup |
| `Topic:__consumer_offsets` | `Describe` | Implicit dependency of any consumer group |
| Group (SR's consumer group — see gotcha below) | `Read` | Group-resource ACL for the consumer side of `kafkastore` |
| Cluster (bare `--cluster` flag, no value) | `Create` | Only needed if SR is expected to auto-create `_schemas`; omit if the topic is pre-created out-of-band (e.g. via an admin tool with explicit `confluent.placement.constraints`, as required on MRC — see [YAML-Driven Topic & RBAC Admin Tooling](../patterns/yaml-topic-rbac-admin-tool.md)) |

Example `kafka-acls` invocations:

```bash
kafka-acls --bootstrap-server <brokers> \
  --add --allow-principal User:sr-principal \
  --operation Write --operation Read --operation Describe --operation DescribeConfigs \
  --topic _schemas

kafka-acls --bootstrap-server <brokers> \
  --add --allow-principal User:sr-principal \
  --operation Describe --topic __consumer_offsets

kafka-acls --bootstrap-server <brokers> \
  --add --allow-principal User:sr-principal \
  --operation Read --group <sr-consumer-group>

# Only if SR must be allowed to create _schemas itself:
kafka-acls --bootstrap-server <brokers> \
  --add --allow-principal User:sr-principal \
  --operation Create --cluster
```

`kafka-cluster` is **not** a cluster ID to substitute — `Cluster` is Kafka's singleton resource
type, always referenced with a bare `--cluster` flag and no trailing value/argument. Don't copy a
literal `--cluster kafka-cluster` token from older doc examples; the correct current syntax takes
no argument after `--cluster`.

### `kafkastore.group.id` gotcha

`schema.registry.group.id` and `kafkastore.group.id` are two different, easily-conflated config
keys:

- **`schema.registry.group.id`** — the SR-cluster-identity setting. Must match across every node
  in the same logical SR cluster (default `"schema-registry"`).
- **`kafkastore.group.id`** — the actual Kafka **consumer group.id** SR's `kafkastore` client uses
  against `_schemas`. If left unset, it defaults to `schema-registry-<host>-<port>` — different
  per node, and unstable across redeploys or renames.

A literal `--group schema-registry` ACL grant only matches traffic if `kafkastore.group.id` is
explicitly set to that exact value in every node's `schema-registry.properties`. If it's left at
its default, each node generates its own host/port-derived group ID, the ACL grant silently stops
matching, and the failure looks identical to a missing-ACL problem even though the ACL exists. Set
both `schema.registry.group.id` and `kafkastore.group.id` explicitly on every node to avoid this.

### RBAC role-binding equivalent

For clusters using Confluent RBAC/MDS instead of plain ACLs, the equivalent is a `ResourceOwner` (or
narrower custom) role binding scoped to the `_schemas` topic and the SR consumer group, plus
`DeveloperRead` on `__consumer_offsets`. This mirrors the ACL list above conceptually (topic
read/write/describe, group read, cluster create), but the exact `confluent iam rbac
role-binding create` invocations in this article have **not** been re-verified against current
Confluent docs in this session (several RBAC-specific doc URLs 302-redirected during research) —
treat this section as `medium` confidence and re-validate the specific role names/scopes against
live docs (`confluent-docs` MCP) before applying.

## When to Use

- Any manual (non-`cp-ansible`) Schema Registry install against a Kafka cluster with ACL or RBAC
  authorization enabled.
- Diagnosing `TopicAuthorizationException` / `StoreInitializationException` /
  `SchemaRegistryInitializationException` on SR startup.
- Auditing an existing SR install's permission footprint for least-privilege review (e.g. dropping
  `Create` once `_schemas` is pre-provisioned).

## Caveats

- Don't conflate this article's broker-side ACLs with the *separate* Schema Registry Security
  Plugin, which governs subject-level operations (`SUBJECT_READ`/`SUBJECT_WRITE`/`SUBJECT_DELETE`,
  `GLOBAL_READ`, etc.) for end-user REST API calls to SR itself. A 401/403 on an SR REST call is
  usually that plugin, not the broker ACLs described here — see the triage table in
  [[concepts/schema-registry-best-practices]].
- On a Multi-Region Cluster, `_schemas` does **not** automatically inherit cluster-wide replica
  placement the way `__consumer_offsets` or Control Center's internal topics do — it needs explicit
  `confluent.placement.constraints`, and specifying a replication factor at topic-creation time
  causes any placement-constraint default to be ignored. Pre-create `_schemas` via an admin tool
  with explicit constraints rather than relying on SR's own auto-create path in that topology.
- The RBAC role-binding section is not MCP-verified — confirm role names/scopes before applying in
  a production RBAC environment.

## Related

- [Schema Registry Best Practices](../concepts/schema-registry-best-practices.md) — the operational/governance surface this article's security layer sits underneath.
- [YAML-Driven Topic & RBAC Admin Tooling](yaml-topic-rbac-admin-tool.md) — the `replication.factor: -1` + explicit `confluent.placement.constraints` mechanism referenced above for pre-creating `_schemas` on MRC.
- [Kafka Streams Schema Patterns](../concepts/kafka-streams-schema-patterns.md) — client-side SR integration patterns, a different layer from broker-side authorization.
