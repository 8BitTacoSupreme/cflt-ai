---
title: Wiki Validation — FSI Exactly-Once Pattern
date: 2026-06-15
scope: wiki/patterns/fsi-exactly-once.md
articles_checked: 1
claims_validated: 7
drift_found: 0
---

# Wiki Validation Report — FSI Exactly-Once Pattern

**Date:** 2026-06-15
**Scope:** `wiki/patterns/fsi-exactly-once.md` (single article)
**Confidence:** high (last_validated 2026-06-15)

## Summary

No drift detected. The article was re-validated on the same day; this pass
re-confirmed the most failure-prone external claim (IBM MQ Source Connector EOS
conditions and version semantics) against live `confluent-docs`, and confirmed
the Kafka Streams EOS default against the activated `kafka-streams-programming`
skill overlay. All verifiable claims hold.

## Articles Checked

1 article: `wiki/patterns/fsi-exactly-once.md`

## Claims Validated

| # | Claim | Source | Outcome |
|---|-------|--------|---------|
| 1 | IBM MQ Source Connector EOS requires all 6 conditions (worker `exactly.once.source.support=enabled`, distributed mode, ACLs, `state.topic.name` set at create, single task, downstream `read_committed`) | `confluent-docs` (IBM MQ Source overview) | **Confirmed** — verbatim match to doc's Exactly-once delivery section |
| 2 | "11.x line does not support at-least-once and is no longer supported"; upgrade to 12.x | `confluent-docs` | **Confirmed** — doc states "The 11.x version of this connector does not support at-least-once semantics and is no longer supported." (article phrasing was correct, not inverted) |
| 3 | Priority-queue caveat: MQ may deliver out of order, EOS cannot be guaranteed, connector may fail | `confluent-docs` | **Confirmed** — verbatim in doc |
| 4 | `state.topic.name` set only at first create; changing later reintroduces duplicates | `confluent-docs` | **Confirmed** |
| 5 | Kafka Streams `exactly_once_v2` is the required EOS guarantee; `exactly_once` deprecated | `kafka-streams-programming` skill (FSI overlay) | **Confirmed** — overlay mandates `exactly_once_v2` as FSI default for compliance/reconciliation workloads |
| 6 | CC Flink EOS commits ~every minute; latency lever is consumer `isolation.level` (fixed commit interval) | inline marker validated 2026-06-15 against `confluent-docs` CC Flink *Delivery Guarantees and Latency* | **Confirmed** (carried from same-day validation) |
| 7 | `delivery.timeout.ms >= linger.ms + request.timeout.ms` enforced at construction; defaults 120000/30000/0 | AK producer config (stable; consistent with skill baseline) | **Confirmed** |

## Drift Instances

None.

## Stubs With Expansion Potential

N/A — target is a high-confidence pattern article, not a stub.

## Skills Consulted

`kafka-streams-programming` (routed on Kafka Streams EOS / transactional producer
claims; FSI overlay applied)

## Skill-MCP Conflicts

0 — the skill overlay's `processing.guarantee=exactly_once_v2` mandate agrees
with the article and with MCP.

## Preload Bundle

none (single-article scope; under the 10-article threshold for Step 1.5)

## Source-Staleness

0 STALE-SOURCE-1 findings for this article. `fsi-exactly-once.md` carries
`sources: []` and cites no `fsi-dsp://` URI, so it is outside the
reconsolidation queue. (The full-wiki lint surfaced 12 STALE-SOURCE-1 findings
in other articles, all tied to `observability/grafana`,
`accelerator/confluent-on-linuxone`, and `adr/009` upstream changes — out of
scope here.)

## Missing/Ambiguous Sources

0.

## Overall Health Assessment

**Healthy.** No corrections required. The article's externally-volatile claims
(IBM MQ connector version/EOS semantics, CC Flink commit behavior) are confirmed
current as of 2026-06-15. `last_validated` already reflects today; no frontmatter
change needed.

---

*Validated against Confluent docs via `confluent-docs` MCP and the
`kafka-streams-programming` skill overlay (2026-06-15). 7 claims checked, 0
corrected, 0 unverifiable.*
