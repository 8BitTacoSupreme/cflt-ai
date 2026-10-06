---
title: Schema Registry Shared-Types Library
tags: [schema-registry, avro, references, governance, fsi, shared-types]
sources: [raw/articles/shared-schema-howto.md]
related: [concepts/schema-registry-best-practices, concepts/schema-evolution-strategies, patterns/topic-naming, patterns/fsi-governance-automation, concepts/fsi-compliance]
confidence: high
last_updated: 2026-05-15
last_validated: 2026-05-15
---

# Schema Registry Shared-Types Library

## Summary

In FSI environments where money, identifiers, and addresses recur across dozens of domain schemas, model them once as a versioned shared-types library in Schema Registry and reference them from domain subjects via schema references. The pattern gives you a single point of governance for cross-cutting types, evolvability for wrapped primitives, and pinned references so shared-type evolution doesn't auto-propagate to consumers. Trade-off: more subjects to manage and verbosity at the record level, paid back the first time you need to add a field to `Money` without touching every payments schema.

## Pattern

### Library layout

A shared-types library is just a set of normal Schema Registry subjects, distinguished only by a reserved namespace prefix and `FULL_TRANSITIVE` compatibility. For an FSI firm:

- Reserve a namespace: `com.fsifirm.common` (or your firm's reverse-DNS equivalent).
- Use `TopicNameStrategy`-style subject names that match the fully qualified Avro name — `com.fsifirm.common.Money`, `com.fsifirm.common.CustomerId`, etc. The "topic" doesn't exist; the subject is just a registry slot for the type.
- Compatibility: `FULL_TRANSITIVE` on every shared type. These are consumed by many domains; both forward and backward compatibility, transitively across all versions, is the only safe default.

Shared types and domain subjects coexist in the same registry. Schema IDs are assigned sequentially across all registrations, regardless of subject — there's no ID range reserved for shared types. Logical grouping comes from the subject naming convention (`com.fsifirm.common.*`), not from ID ranges.

### Example 1: `com.fsifirm.common.Money`, a stable shared type

Initial registration:

```yaml
Subject:        com.fsifirm.common.Money
Version:        1
Schema ID:      1001
Compatibility:  FULL_TRANSITIVE
```

```json
{
  "type": "record",
  "name": "Money",
  "namespace": "com.fsifirm.common",
  "fields": [
    {"name": "amount", "type": {"type": "bytes", "logicalType": "decimal", "precision": 18, "scale": 4}},
    {"name": "currency", "type": "string"}
  ]
}
```

Six months later, add an optional `asOfTimestamp` for FX-converted amounts. `FULL_TRANSITIVE` requires the new field to have a default so it stays both backward- and forward-compatible:

```yaml
Subject:        com.fsifirm.common.Money
Version:        2
Schema ID:      1247
Compatibility:  FULL_TRANSITIVE
```

```json
{
  "type": "record",
  "name": "Money",
  "namespace": "com.fsifirm.common",
  "fields": [
    {"name": "amount", "type": {"type": "bytes", "logicalType": "decimal", "precision": 18, "scale": 4}},
    {"name": "currency", "type": "string"},
    {"name": "asOfTimestamp", "type": ["null", {"type": "long", "logicalType": "timestamp-millis"}], "default": null}
  ]
}
```

Subject `com.fsifirm.common.Money` now has versions 1 and 2, mapped to schema IDs 1001 and 1247. Both remain resolvable forever.

### Example 2: `com.fsifirm.common.CustomerId`, a wrapped primitive

```yaml
Subject:        com.fsifirm.common.CustomerId
Version:        1
Schema ID:      1002
Compatibility:  FULL_TRANSITIVE
```

```json
{
  "type": "record",
  "name": "CustomerId",
  "namespace": "com.fsifirm.common",
  "fields": [
    {"name": "value", "type": "string"},
    {"name": "issuingBranch", "type": ["null", "string"], "default": null}
  ]
}
```

Wrapping primitives in records is a deliberate choice: it lets you evolve the type (add `issuingBranch`, validation metadata, a check-digit field) without breaking consumers, which a bare `string` would never allow. The cost is verbosity; the benefit is evolvability. For shared identifiers in regulated domains, worth it.

### Example 3: `com.fsifirm.common.UsAddress`, a region-specific type

```yaml
Subject:        com.fsifirm.common.UsAddress
Version:        1
Schema ID:      1003
Compatibility:  FULL_TRANSITIVE
```

```json
{
  "type": "record",
  "name": "UsAddress",
  "namespace": "com.fsifirm.common",
  "fields": [
    {"name": "line1", "type": "string"},
    {"name": "line2", "type": ["null", "string"], "default": null},
    {"name": "city", "type": "string"},
    {"name": "state", "type": {
      "type": "enum",
      "name": "UsState",
      "symbols": ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC","PR","VI","GU","AS","MP","AA","AE","AP"]
    }},
    {"name": "postalCode", "type": "string"},
    {"name": "country", "type": "string", "default": "US"}
  ]
}
```

Naming it `UsAddress` rather than `Address` signals that international addresses are a different type, not a variant of this one. The APO/FPO/DPO codes and US territories are included in the enum because valid US mailing addresses include military postal codes — leaving them out forces those records into a separate type or a free-form `state` string, both of which are worse.

### Example 4: a domain schema that references the shared types

```yaml
Subject:        payments-value
Version:        1
Schema ID:      2891
Compatibility:  BACKWARD_TRANSITIVE
References:
  - name:     com.fsifirm.common.Money
    subject:  com.fsifirm.common.Money
    version:  2
  - name:     com.fsifirm.common.CustomerId
    subject:  com.fsifirm.common.CustomerId
    version:  1
```

```json
{
  "type": "record",
  "name": "WireTransfer",
  "namespace": "com.fsifirm.payments",
  "fields": [
    {"name": "transferId", "type": "string"},
    {"name": "fromCustomer", "type": "com.fsifirm.common.CustomerId"},
    {"name": "toCustomer", "type": "com.fsifirm.common.CustomerId"},
    {"name": "amount", "type": "com.fsifirm.common.Money"},
    {"name": "initiatedAt", "type": {"type": "long", "logicalType": "timestamp-millis"}},
    {"name": "status", "type": {
      "type": "enum",
      "name": "TransferStatus",
      "symbols": ["INITIATED", "PENDING", "COMPLETED", "FAILED", "REVERSED"]
    }}
  ]
}
```

What you see in the registry: `payments-value` v1, schema ID 2891, with explicit references to `com.fsifirm.common.Money` v2 and `com.fsifirm.common.CustomerId` v1. A schema reference consists of three parts: a name (for Avro, the fully qualified schema name), a subject, and an exact version. The registry validates references at registration — if you try to register a subject that references a non-existent subject-version, registration fails. Referenced schemas must be registered first.

### What the full library looks like

```
Subject                              Versions   Latest ID   Compatibility
com.fsifirm.common.Money             1, 2       1247        FULL_TRANSITIVE
com.fsifirm.common.CustomerId          1          1002        FULL_TRANSITIVE
com.fsifirm.common.AccountId         1          1004        FULL_TRANSITIVE
com.fsifirm.common.UsAddress         1          1003        FULL_TRANSITIVE
com.fsifirm.common.RoutingNumber     1          1005        FULL_TRANSITIVE
com.fsifirm.common.Timestamp         1          1006        FULL_TRANSITIVE
com.fsifirm.common.TransactionType   1, 2       1389        FULL_TRANSITIVE
com.fsifirm.common.AccountType       1          1008        FULL_TRANSITIVE
payments-value                       1, 2, 3    2913        BACKWARD_TRANSITIVE
customers-value                        1, 2       2456        BACKWARD_TRANSITIVE
accounts-value                       1          2502        BACKWARD_TRANSITIVE
account-events-value                 1, 2       2887        BACKWARD_TRANSITIVE
```

A few things worth noting about this layout:

- **ID ranges are illustrative, not enforced.** Shared-type IDs (1001–1500) and domain IDs (2000+) are grouped here for readability, but Schema Registry assigns IDs sequentially across all subjects. In practice they're interleaved chronologically. Logical grouping comes from the namespace prefix, not from ID ranges.
- **Shared types stay on low version numbers because they evolve rarely** — that's the point. If `Money` is on v8 after six months, your shared-types governance has failed and you should pull back to a more conservative review process (cross-domain approval, ADR per change).
- **Domain subjects evolve faster, which is fine** — they're owned by domain teams and their compatibility scope is bounded to that domain's consumers.
- **References are pinned.** `payments-value` v1 references `com.fsifirm.common.Money` v2. If `Money` later evolves to v3, `payments-value` v1 still resolves to `Money` v2. To pick up v3, register a new `payments-value` version with an updated reference. This is the right default: shared-type evolution should not auto-propagate; domain teams control when they adopt new versions.

## When to Use

- You have cross-cutting types — `Money`, customer/account IDs, addresses, timestamps, transaction enums — that appear in three or more domain schemas.
- You expect those types to evolve over years (new currencies, new ID issuers, new enum members).
- You want one team (a C4E / data contracts / schema review group) to own the cross-domain types separately from per-domain schemas.
- You're already on Avro or Protobuf — schema references are an Avro/Protobuf/JSON-Schema feature; not relevant if you're still on raw bytes or strings.

## Caveats

- **Referenced schemas must be registered first.** CI must apply the shared-types library before any domain subject that references it. Order matters in your Terraform/registration pipeline.
- **Schema IDs are not portable across environments.** Dev `Money` v2 might be ID 1247; prod might be ID 73. Use Schema Linking (CC↔CC / CC↔CP) or the `subjects` export/import API; never hardcode IDs in code. See `concepts/schema-registry-best-practices.md` for the operational details.
- **Don't over-share.** Every entry in the shared-types library becomes a cross-domain coordination point. If a type is really only used by one domain, it belongs in that domain's namespace.
- **Don't wrap every primitive.** Wrap the ones that have a meaningful identity (`CustomerId`, `AccountId`, `RoutingNumber`) and a plausible evolution path (validation metadata, check digits, issuer). A wrapped `EmailAddress` with one field is usually noise.
- **Reference depth matters.** Schemas referencing schemas referencing schemas works but makes the resolved schema harder to read and harder to debug. Keep the reference graph one level deep where you can.
- **Compatibility mode mismatch.** Shared types are `FULL_TRANSITIVE` (most restrictive). Domain subjects that reference them can use a looser mode (typically `BACKWARD_TRANSITIVE`). The compatibility check applied at registration is the *referencing* subject's mode, applied to the full resolved schema — including the referenced type's current shape. Adding a field to `Money` v2 with a default is still safe for a `BACKWARD_TRANSITIVE` `payments-value` because the resolved Avro is still backward-compatible. Type changes that aren't safe on `Money` itself were already blocked by `FULL_TRANSITIVE` on the shared subject.

## Related

- [Schema Registry Best Practices](../concepts/schema-registry-best-practices.md) — operational surface: subject strategy, `auto.register.schemas=false`, ID portability, Data Contracts, CSFLE
- [Schema Evolution Strategies](../concepts/schema-evolution-strategies.md) — compatibility-by-SLA-tier and the evolution runbook
- [Topic Naming Convention](topic-naming.md) — domain naming convention for the referencing subjects
- [FSI Governance Automation](fsi-governance-automation.md) — Terraform module that registers schemas in dependency order
- [FSI Compliance](../concepts/fsi-compliance.md) — schema-change audit trail for regulatory frameworks
