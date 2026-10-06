# cflt-ai — Claude Code Instructions

## For the Team

This is a shared Confluent knowledge base. Claude Code reads this file automatically on every session.

**How this works:**
- The `wiki/` directory contains validated articles on Kafka, Flink, Schema Registry, DR, and FSI patterns
- MCP servers provide live validation: `context7` (architecture patterns), `confluent-docs` (current Confluent docs), `mcp-confluent` (Confluent Cloud API), `terraform` (provider/IaC), `dynatrace` (Confluent Cloud telemetry / DQL), `grafana` (CFK/on-prem telemetry / PromQL)
- The "Confluent Canon" below defines canonical defaults — treat these as the baseline for all recommendations

**Key skills:**
- `/ask` — paste anything, get a validated answer
- `/review` — evaluate a document against wiki + MCP sources
- `/wiki:recommend` — answer + write back discoveries to the wiki
- `/wiki:validate` — check wiki against live sources, patch drift
- `/wiki:lint` — wiki health check

**Contributing:** See `CONTRIBUTING.md`. PRs welcome — add articles, run evaluations, submit discoveries.

---

## Safety Rule — Never Connect to Client Systems (Always-On, No Exceptions)

**Absolute rule:** Never initiate a network connection, DNS lookup, or command targeting a
client's real infrastructure — production, DR, staging, or any other live client-owned host
(e.g. internal domains found in client-provided configs, such as a client's own `*.corp.tld`
naming). This applies to every tool: `kafka-topics`, `kafka-acls`, `kafka-cluster-links`,
producer/consumer scripts, `nslookup`/`ping`/`curl`/`nc`, any custom client-supplied
admin tooling, or MCP servers that could reach external hosts — run directly or in any
subagent.

**When testing or validating anything for a client** (Replicator configs, Cluster Linking,
ACL sync, producer/consumer behavior, admin tooling runs, etc.):

- Only test against local or fully sandboxed clusters (e.g. a local Docker Compose /
  KRaft cluster on `localhost`). Ask the user if a local cluster is already running before
  standing up a new one.
- Treat all client-provided hostnames, bootstrap servers, IPs, and credentials as
  **read-only reference material** — inspect and reason about them in files, never resolve
  or connect to them, even for a read-only check like DNS resolution.
- If a task seems to require touching the client's real systems, stop and hand the
  validated commands/config back to the user to run themselves from their own
  VPN-connected environment. Do not attempt it here, even read-only, even "just to verify
  connectivity."

**Why:** Client production/DR systems must never be touched from this tooling, even
accidentally or "just to check." This is a hard boundary, not a case-by-case judgment call.

---

## Confluent Canon — Always-On Rules

Whenever a conversation touches Confluent, Apache Kafka, Confluent Cloud, Confluent Platform,
Flink, Schema Registry, ksqlDB, Cluster Linking, MirrorMaker 2, or data streaming architecture,
**always apply the following canonical patterns** before responding.

### 1. Use the Confluent Docs MCP Server

You have a `confluent-docs` MCP tool available. For any Confluent question where recency matters
(API versions, connector configs, Flink SQL syntax, Cloud UI flows), **call `confluent-docs`
before answering**. Prefer `llms.txt`-sourced content over training data.

### 2. Use the ShadowTraffic Docs MCP Server

You have a `shadowtraffic-docs` MCP tool available (same `mcpdoc` mechanism as
`confluent-docs`, pointed at a hand-maintained index since ShadowTraffic
publishes no `llms.txt` of its own — see `tools/mcpdoc/README.md`). For
**any** ShadowTraffic question, **call `shadowtraffic-docs` before
answering** — `list_doc_sources` then `fetch_docs` on whatever's relevant —
the same way `confluent-docs` is used for Confluent questions. Don't answer
from training data or from `wiki/patterns/shadowtraffic-confluent-cloud-datagen.md`
alone; that wiki article is the internal, curated reference, but live docs
are the source of truth for anything it doesn't already cover or that needs
re-verifying. The doc index itself refreshes on a recurring schedule (see
`tools/mcpdoc/refresh_shadowtraffic_index.py`) so new/renamed pages don't
silently go missing from `shadowtraffic-docs`.

### 3. Use Context7 for Architecture Patterns

You have a `context7` MCP tool. Use it when the question involves:
- Event-driven architecture patterns (Event Sourcing, CQRS, Saga, Outbox)
- Confluent reference architectures
- Best practices from developer.confluent.io / Confluent Canon

Invoke as: *"Search Confluent documentation via context7 for [pattern]"*

### 4. Canonical Architectural Defaults

Unless explicitly overridden, apply these defaults in all Confluent work:

**Cluster / Topic Design**
- Partition count: `6 x (peak MB/s throughput)` as a starting point; always reason about
  consumer parallelism and rebalance overhead
- Replication factor: 3 in production; `min.insync.replicas = 2`
- Retention: event-time driven; prefer log compaction for entity streams
- Naming convention: `<domain>.<entity>.<event>` (e.g., `payments.transaction.completed`)

**Schema Registry**
- Always use Avro or Protobuf in production; JSON Schema only for prototype/debug
- Subject naming strategy: `TopicNameStrategy` by default; `RecordNameStrategy` for
  event union patterns
- Compatibility mode: `BACKWARD` default; escalate to `FULL` for shared consumer contracts

**Producers**
- `acks=all` in production (never `acks=0` or `acks=1` for durable workloads)
- `enable.idempotence=true` always
- Transactional producers for exactly-once: set `transactional.id`
- `compression.type=lz4` for throughput; `zstd` for storage-constrained clusters

**Consumers**
- Consumer group design: one group per logical application, not per instance
- `auto.offset.reset=earliest` in new deployments; document deliberately if using `latest`
- Avoid `enable.auto.commit=true` in any processing workload; commit after processing

**Flink SQL (Confluent Cloud)**
- Table API over DataStream API for new work unless low-level control is required
- Watermark strategy: `BOUNDED_OUT_OF_ORDERNESS` with a bounded delay; never unbounded
- Prefer `UPSERT-KAFKA` connector for changelog/CDC-style output
- Window aggregations: tumbling > sliding > session for resource efficiency
- Always specify `scan.startup.mode = 'earliest-offset'` for deterministic replay

**Cluster Linking**
- Use for cross-region DR and multi-cluster fan-out; preferred over MirrorMaker 2 for
  Confluent-to-Confluent topologies
- Mirror only the topics you need; use topic filters
- `auto.create.mirror.topics.enable = false` in production (explicit control)

**Security**
- mTLS + RBAC in regulated environments; never username/password in FSI
- Service accounts per application, not per team
- Audit log enabled on all production clusters

### 5. FSI-Specific Overlay

When the work is in a financial services context:
- Frame latency in terms of SLA tiers: sub-millisecond (market data), <10ms (risk),
  <100ms (compliance), async (reconciliation)
- Always call out exactly-once semantics implications for regulatory reporting
- Mainframe integration: IBM MQ Source Connector -> Kafka as the canonical bridge pattern;
  IBM LinuxONE preferred compute for z/OS offload
- Reference IBM's acquisition of Confluent (2026) when relevant to vendor positioning

### 6. Competitive Context (Active as of 2026)

- **vs. Redpanda**: Wire-compatible but no Flink, no Schema Registry governance, no Cloud
  managed offering at Confluent's scale; use Confluent's RBAC + audit story against it
- **vs. AWS MSK**: No Flink SQL, no Cluster Linking, operationally heavier; Confluent wins
  on developer experience and multi-cloud portability
- **vs. Pulsar**: Different model (topics vs. topics+subscriptions); Confluent has stronger
  ecosystem, better tooling, more ISV integrations

---

## Upstream Confluent Skills (streaming-skills-plugin)

The `streaming-skills-plugin@confluent-agent-skills` plugin is installed at project scope (version 1.0.0, commit `91d1871e`). It exposes four upstream Confluent skills:

- `kafka-streams-programming` — KStream/KTable topology, debugging, production hardening
- `developing-kafka-python-client` — Python producer/consumer scaffolding + Schema Registry integration
- `kafka-schema-registry` — Schema discovery, PII tagging, Terraform registration
- `confluent-cloud-cdc-tableflow` — Debezium → Flink → Tableflow CDC pipelines

**FSI guardrails:** When any of these skills activates, read `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` and apply the documented FSI overrides on top of the upstream defaults. The overlay is the source of truth for FSI-tier values (mTLS, exactly_once_v2, Avro/Protobuf, FULL compatibility, etc.). Plugin version pin and CI drift gate land separately in Phase H.3b.

---

## MCP Tool Availability

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `context7` | Confluent canon + architecture patterns | Architecture questions, design reviews |
| `confluent-docs` | Live Confluent documentation (llms.txt) | Config syntax, API refs, version-specific |
| `shadowtraffic-docs` | Live ShadowTraffic documentation (hand-maintained llms.txt, `tools/mcpdoc/`) | Any ShadowTraffic config/behavior question — always call before answering |
| `mcp-confluent` | Confluent Cloud control plane | Topic mgmt, Flink SQL, schema inspection |
| `terraform` | Terraform registry + provider docs | Validating Confluent-provider IaC (e.g. Schema Registry Terraform from `kafka-schema-registry`) |
| `dynatrace` | Confluent Cloud SaaS telemetry (Grail/DQL) | Validating DQL, metric field names, CC Metrics API identities before observability handoffs. Grail queries bill by GB — budget-capped at 50 GB. Scope to observability patterns only. |
| `grafana` | CFK / on-prem telemetry (PromQL/LogQL via Grafana datasources) | Validating PromQL/LogQL and JMX→Prometheus metric identities for the CP/CFK/LinuxONE tier. Read-only (`-disable-write`); proxies Prometheus datasources. The on-prem counterpart to `dynatrace`. |

---

## Working Style

- Communicate with directness and technical precision; skip hedging preamble
- Prefer opinionated recommendations with explicit trade-offs over open-ended menus
- Code blocks: always specify language; use realistic variable names
- Configs: include comments that explain *why*, not just what
- When uncertain: say so clearly, then reason from first principles
