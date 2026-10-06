---
title: Schema Evolution Strategies
tags: [schema-registry avro fsi governance]
sources: [fsi-dsp://adr/001, fsi-dsp://adr/002]
related: [concepts/sla-tiers, concepts/fsi-data-streaming-platform, patterns/fsi-governance-automation, patterns/topic-naming, patterns/schema-registry-shared-types]
confidence: high
last_updated: 2026-04-11
last_validated: 2026-04-28
---

# Schema Evolution Strategies

## Summary

Schema governance for the FSI Kafka Platform uses Apache Avro as the mandatory production format (ADR-001), with compatibility modes automatically derived from SLA tier (ADR-002). Critical and compliance topics use FULL_TRANSITIVE (most restrictive), standard uses BACKWARD_TRANSITIVE, best-effort uses BACKWARD. Evolution follows strict runbooks: safe field additions, deprecation-without-removal for critical topics, and versioned topic migration for breaking changes.

## Detail

### Schema Format

All production topics use Apache Avro. Protobuf is allowed with platform-team approval for teams with existing Protobuf infrastructure. JSON Schema is not permitted in production. Rationale in ADR-001: compact binary serialization, strong typing with financial logical types (decimal, timestamp-millis), well-defined compatibility enforcement, and first-class support across Connect, Flink SQL, and TableFlow.

### Compatibility Modes by SLA Tier

Compatibility is derived from `sla_tier`, not configured per-topic:

| SLA Tier | Mode | What It Allows |
|----------|------|----------------|
| critical | FULL_TRANSITIVE | Add optional fields with defaults only. Cannot remove or rename fields. Both forward and backward compatible across all versions. |
| compliance | FULL_TRANSITIVE | Same as critical (regulatory audit requirement, override in Terraform). |
| standard | BACKWARD_TRANSITIVE | New schema can read old data. Can add optional fields. Consumers upgraded before producers. |
| best-effort | BACKWARD | Same as standard but only checks against latest version (not all previous). |

### Topic Naming Convention

Format: `{domain}.{application}.{version}.{entity}`

The version segment (`v1`, `v2`) enables breaking change migration via versioned topics. See [Topic Naming](patterns/topic-naming.md) for full convention and regex patterns.

### Safe Evolution: Adding a Field

Works for all compatibility modes:

1. Add the field with a default value:
   ```json
   {"name": "new_field", "type": ["null", "string"], "default": null}
   ```
2. Register the new schema version (Terraform apply)
3. Deploy consumers first (they can handle both old and new), then producers

### Deprecation (Critical/Compliance Topics)

Fields **cannot be removed** from FULL_TRANSITIVE topics. Instead:

1. Stop producing values (set to null/default)
2. Add a `@deprecated` doc annotation to the field
3. Consumers stop reading the field
4. The field remains in the schema indefinitely

### Breaking Change: Versioned Topic Migration

When an incompatible change is necessary (field removal, type change, rename):

1. **Create versioned topic** — Increment version: `corebanking.transactions.v2.account-transaction`. Same Terraform module, new version parameter.
2. **Dual-write period** — Producers write to both v1 and v2 simultaneously. Minimum 2 business days; recommended 1 sprint (2 weeks) for critical-tier topics.
3. **Consumer migration** — Each consumer team updates to v2, validates in staging, deploys to production, confirms via PR comment.
4. **Deprecate old topic** — Stop producing to v1, add `deprecated = true` tag, set decommission date (retention + 30 days).
5. **Decommission** — Verify v1 consumer lag is 0, remove v1 module from Terraform, `terraform apply` deletes topic/RBAC/schema. Optionally soft-delete the schema subject for audit trail.

Never request a `compatibility_override` unless this process is exhausted and the exception is documented in an ADR.

### PII Tagging

Fields containing PII must be tagged in schema metadata:
- Add field names to `pii_fields` variable in the Terraform module call
- Module sets `pii: true` and `pii-fields: field1,field2` in schema metadata
- For field-level encryption, add CEL-based rules in data contracts (requires Advanced Stream Governance)

### Avro Best Practices

- Optional fields: `["null", "type"]` union with `"default": null`
- Timestamps: `timestamp-millis` logical type
- Money: `decimal` logical type
- Dates: `date` logical type
- Closed sets (transaction types, risk categories): enums
- Identifiers (UUIDs, account numbers): `string`, never `long`
- `"doc"` on every field — feeds into Alation catalog descriptions

### Avro Namespace Convention

Namespaces follow: `org.fsi.{domain}.{application}.{version}`

The entity is the Avro record name (e.g., `AccountTransaction`), not part of the namespace. Matches Java package conventions and allows multiple entity types per domain/application/version.

## Related

- [SLA Tiers](concepts/sla-tiers.md) — tier definitions that drive compatibility modes
- [Topic Naming](patterns/topic-naming.md) — naming convention including version segment
- [Governance Automation](patterns/fsi-governance-automation.md) — Terraform module enforcing these rules
- [FSI Compliance](concepts/fsi-compliance.md) — audit trail for schema changes
- [Schema Registry Shared-Types Library](../patterns/schema-registry-shared-types.md) — cross-cutting types governed under `FULL_TRANSITIVE` and consumed via pinned schema references
- [ADR Index](synthesis/adr-index.md) — ADR-001 (Avro), ADR-002 (compatibility by tier)
