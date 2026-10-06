# H.3a-01 Verify Install — Scratch Notes

**Purpose:** Plan-scratch (NOT committed to wiki). Captures install state + per-skill upstream defaults
extracted from the four SKILL.md files. Task 2 (override-table authoring) sources every "Upstream
Default" cell from this file with a `path:line` citation, so override rows are traceable.

**Plan:** H.3a-01
**Generated:** 2026-05-17

---

## Install state

`jq '.plugins["streaming-skills-plugin@confluent-agent-skills"][0]' ~/.claude/plugins/installed_plugins.json`:

```json
{
  "scope": "project",
  "installPath": "~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0",
  "version": "1.0.0",
  "installedAt": "2026-05-17T16:29:23.537Z",
  "lastUpdated": "2026-05-17T16:29:23.537Z",
  "gitCommitSha": "91d1871ef8c320be92bca955c8e42492a2778cb4",
  "projectPath": "<repo-root>"
}
```

- `scope: project` ✓
- `version: 1.0.0` ✓
- `gitCommitSha: 91d1871ef8c320be92bca955c8e42492a2778cb4` ✓ (matches H.1 `tools/vendor-sources.json` pin)
- `projectPath: <repo-root>` ✓

All four SKILL.md files present under
`~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/<skill>/SKILL.md`:

```
confluent-cloud-cdc-tableflow/SKILL.md
developing-kafka-python-client/SKILL.md
kafka-schema-registry/SKILL.md
kafka-streams-programming/SKILL.md
```

Vendor pin (`tools/vendor-sources.json` → `confluent-agent-skills.commit`) =
`91d1871ef8c320be92bca955c8e42492a2778cb4`. **No drift.**

**Install state: GREEN. Proceed to Task 2.**

---

## kafka-streams-programming — upstream defaults

Source roots:
- `kafka-streams-programming/SKILL.md` (Invariant Checklist, Build Mode Step 3)
- `kafka-streams-programming/references/config-baseline.md` (Core Properties, EOS Configuration, Security Patterns)

### Extracted defaults

| Default | Upstream value | Source citation |
|---------|---------------|-----------------|
| `processing.guarantee` | Not set by default (at-least-once); EOS opt-in via `processing.guarantee=exactly_once_v2` | `references/config-baseline.md:219-230` ("Required Properties" section under "EOS Configuration"); also `SKILL.md:24-26` (WarpStream: "Default to `at_least_once` with downstream deduplication unless ... strong need for EOS") |
| `acks` (producer) | `all` — "default since KS 3.0 — no need to set explicitly" | `references/config-baseline.md:46-47` |
| `enable.idempotence` (producer) | Auto-enabled when EOS is on; otherwise inherits Java producer default (`true` since AK 3.0). On WarpStream override path: `producer.enable.idempotence=false` recommended | `references/config-baseline.md:150-152`; EOS-enforced values table `references/config-baseline.md:258-263` |
| `replication.factor` (internal topics) | `3` — only documented under EOS section, no default for non-EOS apps in baseline | `references/config-baseline.md:271-272` ("EOS + Resilience Properties") |
| `min.insync.replicas` (broker side) | Not set by client config; broker default `1`; baseline only mentions `min.isr=2` in EOS checklist item 7 | `references/config-baseline.md:286` ("`min.isr=2`") |
| `commit.interval.ms` | `30000` (30s) for at-least-once; **NOT set** for EOS (EOS defaults to 100ms internally) | `references/config-baseline.md:54-57` and `references/config-baseline.md:233-238` |
| `compression.type` | `lz4` (set explicitly in baseline) | `references/config-baseline.md:48` |
| `auto.register.schemas` | `true` (baseline default); "Set to false in production" inline comment | `references/config-baseline.md:19-20` |
| `default.key.serde` | `org.apache.kafka.common.serialization.Serdes$StringSerde` | `references/config-baseline.md:25` |
| `default.value.serde` | Set per schema format (SpecificAvroSerde / KafkaProtobufSerde / KafkaJsonSchemaSerde); no Avro-vs-JSON-Schema-vs-Protobuf priority | `references/config-baseline.md:27-30` |
| `group.protocol` | `streams` (KIP-1071 default) | `references/config-baseline.md:34` and `SKILL.md:190` (Invariant 3) |
| Naming convention | None enforced; topic names are user-provided strings (no `<domain>.<entity>.<event>` convention in upstream) | absence — `SKILL.md` Build Mode Step 2 `references/config-baseline.md:186-194` (topic management rules say nothing about naming) |
| Partition count | None enforced; output and DLQ topics are "pre-create before deploying to production" but no partition-count formula | `references/config-baseline.md:189-191` |
| State-store backup / standby replicas | `num.standby.replicas=0` default outside EOS; `=1` under EOS resilience block | `references/config-baseline.md:268-269` |
| Security (auth mechanism) | No default; baseline shows SASL_SSL+PLAIN, SCRAM-SHA-256, mTLS, OAUTHBEARER as side-by-side patterns; CC environment block hardcodes `SASL_SSL with PLAIN (always required)` | `references/config-baseline.md:61-94`, `references/config-baseline.md:123-126` |

---

## developing-kafka-python-client — upstream defaults

Source root: `developing-kafka-python-client/SKILL.md` (the SKILL.md is comprehensive; no references/ deep-read needed for canon dimensions).

### Extracted defaults

| Default | Upstream value | Source citation |
|---------|---------------|-----------------|
| `acks` | librdkafka default (`-1`/`all`) — not explicitly set in SKILL.md; no override either way | absence — `SKILL.md` "Core Principles" section `SKILL.md:128-157` says nothing about acks |
| `enable.idempotence` | Default librdkafka `true` (since 2.x); **explicit disable on WarpStream** path (`enable.idempotence=false`) | `SKILL.md:38` ("Key changes: disable idempotence ...") |
| `compression.type` | Not set explicitly; librdkafka default `none`; WarpStream guidance: "dramatically increase batch sizes and in-flight requests" but compression unspecified | absence — searched `SKILL.md` Core Principles + WarpStream subsections |
| `auto.offset.reset` | Not set in SKILL.md; librdkafka default `latest` | absence — `SKILL.md:202-207` (consumer.py Pattern section) mentions polling but no offset reset |
| `enable.auto.commit` | librdkafka default `true`; SKILL.md does not override but graceful-shutdown text implies offsets handled via close: "Consumers must `unsubscribe()` then `close()` to leave the consumer group cleanly" | `SKILL.md:149` (Core Principles #4 "Graceful shutdown") |
| `auto.register.schemas` | **`False`** explicitly: "Always `False`. Explicit registration is a core principle." | `SKILL.md:58` (Common Agent Mistakes table) and `SKILL.md:137` ("configure the serializer with `auto.register.schemas=False`") |
| Schema format default | **JSON Schema** (with Avro fallback only on WarpStream SR) | `SKILL.md:133` ("This skill uses **JSON Schema** by default.") and `SKILL.md:49` (WarpStream SR exception) |
| Authentication mechanism | `SASL_SSL` + `PLAIN` for CC; `PLAINTEXT` for local Docker; mixed for WarpStream | `SKILL.md:151` (Core Principles #5) |
| Message key for ordering | **Always set message key for domain events** — `key=<entity_id>.encode("utf-8")` | `SKILL.md:155` (Core Principles #7) |
| WarpStream `client.id` | Append `,ws_az=<az>` suffix for zone-aware routing | `SKILL.md:38` and `SKILL.md:332` (.env.example WarpStream block) |

---

## kafka-schema-registry — upstream defaults

Source root: `kafka-schema-registry/SKILL.md`. Most defaults are encoded in the Categorization workflow (Phase 4) and the Terraform file structure (Phase 6).

### Extracted defaults

| Default | Upstream value | Source citation |
|---------|---------------|-----------------|
| Schema format | All three supported (Avro, JSON Schema, Protobuf); no single default — directory split into `schemas/avro/`, `schemas/json/`, `schemas/proto/` per-format | `SKILL.md:117-125` (Phase 5 directory structure) |
| Subject naming strategy | **TopicNameStrategy implicit** — file naming = `{topic}-value.{ext}` and `{topic}-key.{ext}` (kebab-case mandatory) | `SKILL.md:127-131` (Phase 5 file naming) |
| Compatibility mode (per subject) | **NOT set in this skill** — Terraform templates register schemas but don't set per-subject compatibility (Category A/B/E land in `schemas.tf`, Category C in commented `flagged-auto-register.tf`) | absence — `SKILL.md:137-156` (Phase 6) names no compatibility setting |
| `auto.register.schemas` | Detected as Category C risk; **flagged for migration, NOT a default**: "Uncontrolled schema evolution (Category C)" | `SKILL.md:74-75` (Phase 2 Risk Detection) |
| PII tagging vocabulary | `confluent:tags` with values `PII`, `PRIVATE`, `SENSITIVE`, `PHI` | `SKILL.md:88` (Phase 3 PII tagging) |
| Multi-event schema strategy | Wrapper schema with `oneOf`/union/`oneof` + `schema_reference` blocks (implies `RecordNameStrategy` semantics, not stated as such) | `SKILL.md:64-67` (Multi-schema topic detection) |
| Custom serializer policy | Detected as Category E risk; "Bypass SR entirely" | `SKILL.md:76` (Phase 2 Risk Detection) |
| Rollout order | **Per-category sequence** — Category B → producer first; Category A→Header → consumer-version verify → producer; Category C → Terraform register → disable auto-register → producer fetch latest; Category E → consumer first | `SKILL.md:180-184` (Migration Rollout by Category) |

---

## confluent-cloud-cdc-tableflow — upstream defaults

Source root: `confluent-cloud-cdc-tableflow/SKILL.md` (Critical Architecture Rules + Phase 2 Planning).

### Extracted defaults

| Default | Upstream value | Source citation |
|---------|---------------|-----------------|
| Schema format (connector output) | **`JSON_SR` default**; AVRO and PROTOBUF supported alternatives. **Never plain `JSON`** (breaks Flink + Tableflow) | `SKILL.md:181` (Phase 1.4 Schema Format) |
| Decimal handling | `decimal.handling.mode=string` ("BYTES default is unusable in Flink") | `SKILL.md:282` (Debezium Type Conversions note) |
| Tableflow target format | Iceberg (recommended) or Delta Lake | `SKILL.md:186-188` (Phase 1.4 Tableflow Destination) |
| Tableflow changelog mode | **MUST be `upsert` from the start** — immutable after first materialization. Create target topics with `'changelog.mode' = 'upsert'` | `SKILL.md:41-47` (Critical Architecture Rule #2); `SKILL.md:247-249` (CREATE TABLE example) |
| Flink watermark strategy | **Not set explicitly** — Cloud Flink auto-discovers CDC tables; SKILL.md says "Cloud Flink handles all of this automatically" for source-table properties | `SKILL.md:262-266` (IMPORTANT Cloud Flink differences) |
| `scan.startup.mode` | Not addressed in SKILL.md (CC Flink auto-managed; verification text notes "The consumer starts at the latest offset") | absence — `SKILL.md:477-478` (consume-messages note) |
| Connector preference | UPSERT semantics via Flink decode → target topic with `changelog.mode='upsert'` → Tableflow. **Never enable Tableflow on raw CDC topic** | `SKILL.md:31-39` (Critical Architecture Rule #1) |
| Schema Registry compatibility for CDC subjects | **`FULL_TRANSITIVE`** recommended (override from default `BACKWARD` which "can halt CDC connectors when database columns are dropped") | `SKILL.md:166-171` (Phase 1.3 Check Schema Registry Compatibility) |
| Tableflow record-failure strategy | `record_failure_strategy: SUSPEND`, `retention_ms: 6048000000` (~70 days) in MCP example | `SKILL.md:393-395` |
| Tableflow storage type | Managed (recommended) or BYOB | `SKILL.md:288-290` (Storage Options) |
| Snapshot mode | `snapshot.mode: initial` (full snapshot) or `schema_only` (test) — no default stated, user choice | `SKILL.md:449-454` (Large Table Snapshots) |

---

## Cross-skill observations (informs override authoring)

1. **No upstream default for `min.insync.replicas`, partition count, or topic-naming convention.** All four SKILLs leave these to the user/operator. The overlay can introduce FSI canon values (`min.insync.replicas=2`, `6 × peak MB/s`, `<domain>.<entity>.<event>`) as net-new requirements — the "Upstream Default" cell should say something like "not specified" with citation.
2. **WarpStream is a heavy theme** across three of the four SKILLs (Streams, Python, not Schema-Registry, not CDC). The overlay needs an explicit "WarpStream is out of scope for FSI prod" framing line in the appropriate sections (mirrors H.1 trip-wires #7-9 vendor-backing rule).
3. **Schema format defaults diverge across skills**: Streams = "set based on schema format" (no opinion), Python = JSON Schema, Schema-Registry = all three, CDC = JSON_SR. FSI canon mandates Avro/Protobuf only. The Python and CDC overrides have the largest delta from upstream.
4. **`auto.register.schemas`**: Python explicitly says `False` (aligns with canon); Streams baseline says `true` with a "set to false in production" comment (FSI override must hard-set `false`); Schema-Registry detects `true` as Category C risk (already aligned). Differential treatment required.
5. **Security/auth**: Streams shows mTLS as one of four options; Python defaults `SASL_SSL+PLAIN` for CC; CDC uses Cloud API Keys. FSI canon mandates mTLS+RBAC (`never username/password in FSI`). This is a major override across all four skills.
