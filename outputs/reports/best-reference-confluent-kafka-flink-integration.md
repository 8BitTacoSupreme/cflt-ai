# Best Reference for Confluent Kafka + Flink Integration

**Query:** What is the best reference for Confluent Kafka + Flink integration? Some public link(s) would help.
**Mode:** report | **Route:** mcp (forced) | **Date:** 2026-06-23

---

## Answer

For **Confluent + Flink integration specifically**, the single best reference is Confluent's own
Flink documentation tree, not the Apache Flink docs — because on Confluent Cloud you're working
with the serverless CC Flink surface (compute pools, CFUs, Autopilot, auto-exposed Kafka tables),
which diverges meaningfully from vanilla open-source Flink.

### Primary — Confluent Cloud for Apache Flink (canonical entry point)
- Overview / landing: https://docs.confluent.io/cloud/current/flink/overview.html
- Flink SQL reference (queries, DDL, functions): https://docs.confluent.io/cloud/current/flink/reference/queries/overview.html
- Get started / quick start: https://docs.confluent.io/cloud/current/flink/get-started/quick-start-cloud-console.html

### Core concepts (design-relevant)
- Compute pools (CFU sizing): https://docs.confluent.io/cloud/current/flink/concepts/compute-pools.html
- Statements & lifecycle: https://docs.confluent.io/cloud/current/flink/concepts/statements.html
- Autopilot (autoscaling): https://docs.confluent.io/cloud/current/flink/concepts/autopilot.html
- Timely stream processing (watermarks/event time): https://docs.confluent.io/cloud/current/flink/concepts/timely-stream-processing.html
- Schema & statement evolution: https://docs.confluent.io/cloud/current/flink/concepts/schema-statement-evolution.html
- Flink RBAC: https://docs.confluent.io/cloud/current/flink/operate-and-deploy/flink-rbac.html

### Learning path (free, hands-on)
- developer.confluent.io Flink courses: https://developer.confluent.io/courses/#apache-flink
  ("Apache Flink 101" + the Flink SQL course are the fastest ramp.)

### Engine internals only (when CC abstractions aren't enough)
- Apache Flink official docs: https://nightlies.apache.org/flink/flink-docs-stable/
  Use for DataStream API, checkpointing mechanics, state backends. On CC, checkpointing is fully
  managed and not user-tunable, so this is rarely needed unless on CMF or self-managed.

### Pick by runtime
- **CC Flink** → Confluent Cloud docs above.
- **Confluent Manager for Apache Flink (CMF)** on CP/k8s → https://docs.confluent.io/platform/current/flink/index.html
- **Self-managed OSS Flink against Confluent Kafka** → Apache docs + the Kafka connector page.

For a **CDC → Flink → lake pipeline**, the `streaming-skills-plugin:confluent-cloud-cdc-tableflow`
skill scaffolds the Debezium → Flink → Tableflow path end-to-end.

---

## Wiki Sources Consulted
- `wiki/concepts/flink-confluent-cloud-setup.md` — canonical CC Flink setup/RBAC/lifecycle article;
  its `sources:` front matter is the validated public-URL set above (last_validated 2026-05-15).
- `wiki/concepts/flink-checkpointing.md`, `wiki/patterns/flink-runtime-models.md` — runtime split.

## MCP Validation
| Claim | Source | Result |
|-------|--------|--------|
| `docs.confluent.io/cloud/current/flink/overview.html` is a live, valid public reference | confluent-docs (`fetch_docs`) | Confirmed (page fetched, 109K chars) |
| Confluent llms.txt is the authoritative doc index | confluent-docs (`list_doc_sources`) | Confirmed (`https://docs.confluent.io/llms.txt`) |
| Concept sub-page URLs | wiki front matter, validated 2026-05-15 | Confirmed via wiki (not re-fetched individually) |

## Canon Compliance
Pure reference request — no config under evaluation. CC Flink defaults to event-time with
`SOURCE_WATERMARK()`; the Canon `BOUNDED_OUT_OF_ORDERNESS` watermark rule applies at the
runtime-model layer. No deviations to flag.

---
*Validated against Confluent docs via MCP (2026-06-23). 3 claims checked, 0 corrected, 0 unverifiable.*
