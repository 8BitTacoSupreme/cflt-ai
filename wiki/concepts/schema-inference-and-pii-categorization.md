---
title: Schema Inference and PII Categorization
tags: [schema-registry, schema-inference, pii, csfle, fsi, governance, confluent-agent-skills]
sources:
  - raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-schema-registry/references/schema-inference.md
  - raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-schema-registry/references/categorization.md
related: [concepts/schema-registry-best-practices, concepts/fsi-compliance, patterns/schema-registry-shared-types, patterns/schema-registry-adoption-playbook, concepts/schema-evolution-strategies]
confidence: high
last_updated: 2026-08-18
last_validated: 2026-08-18
source: confluent-agent-skills@91d1871ef8c320be92bca955c8e42492a2778cb4
upstream_path:
  - skills/kafka-schema-registry/references/schema-inference.md
  - skills/kafka-schema-registry/references/categorization.md
---

# Schema Inference and PII Categorization

## Summary

The two halves of preparing a codebase for SR governance: (1) **inference** — deriving the actual schema from existing code paths (typed classes, inline data structures, manual JSON construction, builder patterns, ORM forwarding, even string-concatenated JSON) across Java, Python, .NET, Go, and Node/TS; (2) **categorization** — tagging the inferred fields with `confluent:tags` for PII, PRIVATE, SENSITIVE, and PHI so downstream CSFLE and data-contract rules can enforce field-level encryption automatically. The inference step is where you discover the schema; the categorization step is what makes it FSI-deployable.

Sourced from `confluentinc/agent-skills@91d1871e` (Apache-2.0) — upstream maintains an eval gate at 90%+ pass before merge, so this article is `confidence: high` via source attestation rather than per-claim MCP re-validation. Trip-wire micro-articles in `wiki/concepts/` carry full MCP validation.

## Detail

### Section 1 — Schema inference

The job is to extract a schema from code, data models, or inline data structures when the existing producer doesn't have one declared. Start by searching for existing schemas; then infer from data models; then fall back to inline-data inspection.

#### Finding existing schemas

```
**/*.avsc          (Avro schema)
**/*.avro          (Avro schema)
**/*.proto         (Protobuf)
**/schema*.json    (JSON Schema)
**/*.schema.json   (JSON Schema)
**/schemas/**      (schema directories)
**/avro/**         (Avro directories)
```

If schemas exist, prefer them over inference — they're the canonical source.

#### Inferring from data models (per language)

**Java** — classes used as generic type in `KafkaTemplate<K, V>` or `ProducerRecord<K, V>`; classes with `@JsonProperty`, `@JsonInclude`, or other Jackson annotations; Avro-generated classes extending `SpecificRecord`; Protobuf-generated classes extending `GeneratedMessageV3`; Java Records used in producer calls; POJOs with getters/setters passed to `send()`.

**Python** — `@dataclass` classes used in `produce()` calls; Pydantic `BaseModel` subclasses; `TypedDict` definitions; named tuples; dict literals passed to `produce()` (infer field types from values); Avro schema dicts defined in code (`{"type": "record", ...}`).

**.NET** — classes/records with `[JsonProperty]`, `[DataMember]`, or `[ProtoMember]` attributes; types used as generic parameter in `IProducer<TKey, TValue>`; classes in a `Models` or `Events` namespace near producer code.

**Go** — struct types with `json:"field_name"` tags; structs used in `Produce()` calls after `json.Marshal()`; structs with `avro:"field_name"` tags.

**TypeScript/Node** — interfaces or types used in `producer.send({ value: ... })`; Zod schemas (`z.object({...})`); io-ts codecs; JSON objects passed directly to send.

#### Inferring from inline data

When there's no typed class, infer from the code that constructs the data.

**Java — HashMap / Map.of / JSONObject:**

```
new HashMap<>
Map.of(
Map.ofEntries(
new JSONObject(
put("field_name",
```

**Python — dict literals:**

```
produce.*{
send.*{
json.dumps.*{
dict(
```

**Go — map[string]interface{}:**

```
map\[string\]interface
map\[string\]any
```

**Node/TS — plain objects:**

```
producer.send.*value:.*{
send.*{
```

**.NET — Dictionary / anonymous objects:**

```
new Dictionary<string
new {
anonymous
```

**Manual JSON construction (string concatenation/formatting):**

```java
// Java
String json = "{\"order_id\":\"" + orderId + "\",\"amount\":" + amount + "}";
String.format("{\"order_id\":\"%s\",\"amount\":%f}", orderId, amount);
```

```python
# Python
f'{{"order_id": "{order_id}", "amount": {amount}}}'
```

```go
// Go
fmt.Sprintf(`{"order_id":"%s","amount":%f}`, orderID, amount)
```

```javascript
// Node/TS
`{"order_id": "${orderId}", "amount": ${amount}}`
```

**JSON tree APIs:**

```java
// Jackson JsonNode / ObjectNode
ObjectNode node = mapper.createObjectNode();
node.put("order_id", orderId);
node.put("amount", amount);

// Gson JsonObject
JsonObject obj = new JsonObject();
obj.addProperty("order_id", orderId);
```

```csharp
// .NET JObject / JsonNode
var obj = new JObject { ["order_id"] = orderId, ["amount"] = amount };
```

**Builder patterns:**

```java
Event.builder().orderId(id).amount(amt).build();
new EventBuilder().setOrderId(id).setAmount(amt).build();
```

Trace the builder to find all setter methods — each setter = a field.

**ORM forwarding:**

```java
// JPA/Hibernate
kafkaTemplate.send("topic", objectMapper.writeValueAsString(entity));
```

```python
# SQLAlchemy / Django
producer.produce("topic", json.dumps(model.__dict__))
```

The ORM model/entity class IS the schema.

**Protobuf without SR:**

```java
MyEvent.newBuilder().setOrderId(id).build();
producer.send(new ProducerRecord<>("topic", event.toByteArray()));
```

The `.proto` file IS the schema — find it via the generated class import.

**CSV / delimited strings** — field names are NOT in the data. Check comments, header rows, or variable names.

#### Type mapping

**To JSON Schema:**

- `String` → `"type": "string"`
- `int` / `long` → `"type": "integer"`
- `float` / `double` → `"type": "number"`
- `boolean` → `"type": "boolean"`
- `List` / `array` → `"type": "array"`
- `Map` / `object` → `"type": "object"`
- `Object` / `interface{}` / `any` → `"type": "string"` (default, add TODO)

Add `"$schema": "http://json-schema.org/draft-07/schema#"`, `"title"` matching class/model name, `"required"` array for non-nullable fields.

**To Avro:**

- `String` → `"string"`
- `int` → `"int"`
- `long` → `"long"`
- `float` → `"float"`
- `double` → `"double"`
- `boolean` → `"boolean"`
- `List` → `"array"`
- `Map` → `"map"`

Use `"type": "record"` with `"namespace"` from package/module. `["null", "type"]` union for nullable fields with `"default": null`.

**To Protobuf:**

- `String` → `string`
- `int` → `int32`
- `long` → `int64`
- `float` → `float`
- `double` → `double`
- `boolean` → `bool`
- `List` → `repeated`
- `Map` → `map<K,V>`

Use `syntax = "proto3"` and `package` from namespace.

#### Multi-schema topics

When multiple data models produce to the same topic, create a wrapper schema.

**JSON Schema wrapper:**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "{TopicName}Event",
  "oneOf": [
    { "$ref": "{event-type-1}.json" },
    { "$ref": "{event-type-2}.json" }
  ]
}
```

**Avro wrapper:**

```json
["{namespace}.EventType1", "{namespace}.EventType2"]
```

**Protobuf wrapper:**

```protobuf
import "{event_type_1}.proto";
import "{event_type_2}.proto";

message {TopicName}Event {
  oneof event {
    EventType1 type1 = 1;
    EventType2 type2 = 2;
  }
}
```

Generate Terraform with `schema_reference` blocks pointing to individual event schemas. See [Schema Registry Shared-Types Library](../patterns/schema-registry-shared-types.md) for the reference-composition pattern.

---

### Section 2 — PII categorization (tagging inferred schemas)

After inference, every field that could be PII, PRIVATE, SENSITIVE, or PHI must be tagged. The tags drive client-side field-level encryption (CSFLE) and downstream data-contract rules.

#### PII field-detection patterns

The "Tag" column shows the EXACT tags to use in `confluent:tags`:

| Pattern | Tag | Examples |
|---|---|---|
| `email`, `e_mail`, `email_address`, `emailAddress` | `PII` | user_email, contact_email |
| `phone`, `phone_number`, `phoneNumber`, `mobile`, `telephone`, `tel` | `PII` | home_phone, mobile_number |
| `ssn`, `social_security`, `socialSecurity`, `social_security_number` | `PII`, `PRIVATE` | ssn_last4 |
| `name`, `first_name`, `firstName`, `last_name`, `lastName`, `full_name`, `fullName` | `PII` | customer_name |
| `address`, `street`, `city`, `state`, `zip`, `zip_code`, `zipCode`, `postal_code`, `postalCode` | `PII` | billing_address |
| `date_of_birth`, `dateOfBirth`, `dob`, `birth_date`, `birthday` | `PII` | customer_dob |
| `ip`, `ip_address`, `ipAddress`, `client_ip`, `remote_addr` | `PII` | source_ip |
| `credit_card`, `creditCard`, `card_number`, `cardNumber`, `ccn`, `pan` | `PII`, `PRIVATE` | payment_card_number |
| `passport`, `passport_number`, `passportNumber` | `PII`, `PRIVATE` | |
| `driver_license`, `driverLicense`, `license_number` | `PII`, `PRIVATE` | |
| `account_number`, `accountNumber`, `bank_account`, `iban`, `routing_number` | `PII`, `PRIVATE` | |
| `password`, `secret`, `token`, `api_key`, `apiKey` | `PRIVATE` | auth_token |
| `salary`, `income`, `compensation`, `wage` | `SENSITIVE` | annual_salary |
| `gender`, `sex`, `race`, `ethnicity`, `religion`, `nationality` | `SENSITIVE` | |
| `medical`, `diagnosis`, `prescription`, `health` | `SENSITIVE`, `PHI` | medical_record |

#### Supported tag values

| Tag | Meaning |
|---|---|
| `PII` | Personally Identifiable Information |
| `PRIVATE` | Highly sensitive — should be encrypted or masked |
| `SENSITIVE` | Sensitive but not directly identifying |
| `PHI` | Protected Health Information (HIPAA) |
| `PUBLIC` | Safe for broad access |

#### Tagging in each schema format

**Avro:**

```json
{
  "name": "email",
  "type": "string",
  "confluent:tags": ["PII"]
}
```

**JSON Schema:**

```json
{
  "email": {
    "type": "string",
    "confluent:tags": ["PII"]
  }
}
```

**Protobuf:**

```protobuf
import "confluent/meta.proto";

message Customer {
  string email = 1 [(confluent.field_meta).tags = "PII"];
  string ssn   = 2 [
    (confluent.field_meta).tags = "PII",
    (confluent.field_meta).tags = "PRIVATE"
  ];
}
```

#### FSI-specific behaviour

Tagging is not optional in regulated environments. Once a field has `["PII"]` or `["PRIVATE"]`, downstream tooling (CSFLE rules in the data contract, audit-log routing, masking proxies) can enforce encryption automatically. The client encrypts those fields against a KMS *before* the record hits the broker. Whether Confluent itself can decrypt depends on the KEK-sharing mode: only the no-shared-KEK-access mode gives the "not even Confluent" guarantee — with shared access, Confluent's own systems can decrypt temporarily for processing (no Confluent *employee* can, but the platform can).

This is the canonical FSI PII answer; see [FSI Compliance](fsi-compliance.md) for how PII tagging connects to the regulatory frameworks (OCC/FFIEC, PRA, MAS, APRA, OSFI) and to the [Schema Registry Best Practices](schema-registry-best-practices.md) section on Data Contracts (schema + rules + migration + tags).

## Related

- [Schema Registry Best Practices](schema-registry-best-practices.md) — operational surface, Data Contracts, CSFLE
- [FSI Compliance](fsi-compliance.md) — PII categorization connects to regulatory frameworks
- [Schema Registry Shared-Types Library](../patterns/schema-registry-shared-types.md) — shared types (Money, CustomerId, UsAddress) include PII-tagged fields
- [Schema Registry Adoption Playbook](../patterns/schema-registry-adoption-playbook.md) — adoption playbook sibling (detection + migration)
- [Schema Evolution Strategies](schema-evolution-strategies.md) — compatibility modes for evolving inferred schemas

---

*Source: confluentinc/agent-skills@91d1871e · skills/kafka-schema-registry/references/{schema-inference,categorization}.md · Ingested 2026-05-16 · Apache-2.0*
