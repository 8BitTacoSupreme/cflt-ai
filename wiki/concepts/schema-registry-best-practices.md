---
title: Schema Registry Best Practices
tags: [schema-registry, avro, protobuf, compatibility, governance, fsi, csfle]
sources: [outputs/reports/confluent-best-practices-quickstart.md]
related: [concepts/schema-evolution-strategies, patterns/schema-linking-cp-to-cc-mtls, patterns/fsi-governance-automation, patterns/topic-naming, patterns/producer-config-fsi, concepts/fsi-compliance, patterns/schema-registry-shared-types, patterns/schema-registry-manual-install-permissions]
confidence: high
last_updated: 2026-10-01
last_validated: 2026-08-18
---

# Schema Registry Best Practices

## Summary

Schema Registry is the data contract authority for Kafka. This article captures the operational and governance best practices: `TopicNameStrategy` by default, compatibility-mode-per-subject, `auto.register.schemas=false` in prod, register in CI, never assume schema IDs are portable across environments. Pairs with `concepts/schema-evolution-strategies.md` (compatibility-by-SLA-tier and the evolution runbook) — this article is the *operational surface*, that one is the *evolution policy*.

## Detail

### What Schema Registry / the schema team owns

- **Subject naming strategy** — `TopicNameStrategy` by default (Canon). `RecordNameStrategy` / `TopicRecordNameStrategy` only for genuine multi-event-type topics or event-union patterns — a deliberate, documented choice because it changes how producers and consumers resolve schemas.
- **Compatibility mode** per subject (Canon: `BACKWARD` default; escalate to `FULL` for shared consumer contracts):
  - `BACKWARD` — new schema can read old data → **consumers upgrade first**. Adding a field *with a default* is OK; adding a required field or removing a field is not.
  - `FORWARD` — old schema can read new data → **producers upgrade first**.
  - `FULL` — both. Safe default for contracts with many independent consumers.
  - `*_TRANSITIVE` — checks against *all* prior versions, not just the last. Use for long-lived, widely-shared schemas.
- **Schema IDs in the wire format** — magic byte + 4-byte ID. **IDs are not portable across environments** (dev ID 100 ≠ prod ID 100). Use **Schema Linking** for CC↔CC / CC↔CP, or export/import — never assume IDs match.
- **References** — compose schemas instead of shipping one 4000-line Avro file. Versioned, reusable, governable.
- **Data Contracts** (Confluent's feature) — schema + **rules** (validation, domain constraints) + **migration rules** (transform on read across breaking versions) + metadata/tags. This is where CSFLE tags live too.
- **CSFLE** (client-side field-level encryption) — tag PII fields in the schema; the client encrypts those fields against a KMS *before* the record hits the broker. Whether Confluent itself can decrypt depends on the KEK-sharing mode: with shared KEK access, Confluent's own systems (DEK Registry, RBAC'd connectors) can decrypt temporarily for processing — no Confluent *employee* can, but the platform can. Only the no-shared-access mode gives the stronger "not even Confluent" guarantee. The FSI PII answer. See `fsi-dsp:docs/csfle-guide.md`.

### Best practices (opinionated)

- **Avro by default** (Canon, ADR-001) — best evolution story, compact, native unions, first-class in Flink/Connect/ksqlDB.
- **Protobuf** when you're polyglot / gRPC-native.
- **JSON Schema** prototype/debug only.
- **`auto.register.schemas=false` in prod.** Register schemas in **CI** (fail the build on incompatibility — `mvn schema-registry:test-compatibility`); clients use `use.latest.version=true` or a pinned version. Auto-register from clients = governance bypass + a race where two instances register slightly different "latest" schemas.
- **Set compatibility per subject**, not just globally, when you have mixed requirements. Consider `latest.compatibility.strict=true`.
- **Pre-register before deploy** — never let the first message in production be the thing that registers the schema.
- **Stream Governance package (CC)** — Essentials vs **Advanced** (confirmed against `cloud/current/stream-governance/packages.html` on 2026-08-18). Corrected: Stream Lineage (10-min point-in-time view) and Stream Catalog tags now ship in **Essentials** too — Advanced only adds the longer 7-day Lineage window and Catalog's business-metadata/GraphQL layer. Schema Linking is available in both tiers, just at a lower exporter quota (10 vs 100), not an absence. The only genuinely Advanced-exclusive feature is **Data Contracts** (data rules). For FSI governance, Advanced remains the baseline (for Data Contracts and the longer retention windows), but don't describe Lineage/Catalog-tags/Schema-Linking as Advanced-only — that feature split moved, not just the numerical caps.

### CC vs CP

- **CC** — managed SR per environment; governance via Stream Governance packages; Schema Linking for DR/migration. CC SR does **not** accept mTLS (API key or OAuth only) — for linking from an mTLS-only CP SR see `patterns/schema-linking-cp-to-cc-mtls.md`.
- **CP** — you run the SR cluster: 3 nodes behind a load balancer, `_schemas` topic with **RF 3 and compaction on** (corruption risk if compaction gets disabled), leader election among nodes, mTLS, RBAC via MDS.

### Triage

| Symptom | Cause | Fix |
|---|---|---|
| `Schema being registered is incompatible with an earlier schema` | Breaking change vs the compat mode (added required field under BACKWARD, removed field under FORWARD, etc.) | Diff the schemas; add defaults; or — for a genuinely breaking change — stand up a new topic and migrate consumers. Keep the canon naming form `<domain>.<application>.<entity>.<event>`; the `_v2`-style suffix on `<entity>` is the sanctioned versioned-topic exception (ADR-007 / `patterns/topic-naming.md`). |
| `Subject not found` | Subject naming strategy mismatch between producer/consumer, or schema simply not registered | Confirm both sides use the same strategy; register in CI. |
| Schema IDs differ across envs | They always do — IDs are per-registry | Schema Linking or export/import; never hardcode IDs. |
| Serializer can't reach SR / 401 / 403 | Network, `basic.auth.credentials.source` / `basic.auth.user.info`, or RBAC on the subject | Check endpoint + creds + role bindings on the subject resource. |
| `_schemas` topic growing unbounded / weird SR behaviour | Compaction got disabled on `_schemas` | Restore `cleanup.policy=compact` on `_schemas` immediately; this topic is SR's database. |

## Related

- [Schema Evolution Strategies](schema-evolution-strategies.md) — tier-based compatibility, evolution runbook, versioned-topic migration
- [FSI Governance Automation](../patterns/fsi-governance-automation.md) — Terraform module enforces compatibility per SLA tier
- [Topic Naming Convention](../patterns/topic-naming.md) — `<domain>.<application>.<entity>.<event>`, versioned-topic exception
- [FSI Producer Configuration](../patterns/producer-config-fsi.md) — `auto.register.schemas=false` enforcement
- [FSI Compliance](fsi-compliance.md) — schema-change audit trail for regulatory frameworks
- [Schema Registry Shared-Types Library](../patterns/schema-registry-shared-types.md) — pattern for cross-cutting types (Money, CustomerId, UsAddress) under a reserved namespace with pinned schema references
- [Schema Registry Manual Install — Required ACLs and RBAC Role Bindings](../patterns/schema-registry-manual-install-permissions.md) — broker-side authorization layer underneath this article's operational surface; required ACLs/role bindings for the `_schemas` topic on a hand-rolled (non-cp-ansible) install
- [Schema Linking CP → CC When CP SR Uses mTLS](../patterns/schema-linking-cp-to-cc-mtls.md) — hybrid CP→CC schema migration/link when CP SR is mTLS-only
- [Top 20 Confluent Gotchas](../synthesis/confluent-gotchas-top-20.md) — #8 (schema IDs not portable), #9 (`auto.register` bypass), #10 (compatibility direction)
