# Wiki Validation — 2026-09-14

**Scope:** `wiki/concepts/cluster-linking-topology.md` (single article; triggered by the transactional-semantics drift flagged in `outputs/reports/osk-to-cp-migration-preflight-review-2026-09-14.md`)
**Articles checked:** 1 (`confidence: high`)
**Preload bundle:** none (single-article scope, under threshold)
**MCP sources:** `confluent-docs` — CP Cluster Linking overview (known limitations, support matrix), configs (property defaults), mirror topics (prefix limits, offset sync, `__transaction_state`). Pages read by targeted section. `context7` not used. `mcp-confluent` failed to connect this session (not needed).
**Skills consulted:** none (claim routed to no streaming-skills-plugin skill)
**Skill-MCP conflicts:** 0

## Claims validated: 16

| # | Claim (article) | MCP finding | Outcome |
|---|-----------------|-------------|---------|
| 1 | Transactional messages replicated; cross-topic atomicity not preserved | "Cluster Linking doesn't support mirroring topics that contain messages produced using the Kafka transactions feature"; `__transaction_state` "is not replicated because Cluster Linking does not support transactions" | **Drift — fixed** |
| 2 | `auto.create.mirror.topics.enable` default `false` | Default false | Confirmed |
| 3 | `auto.create.mirror.topics.filters` default none | Default null | Confirmed |
| 4 | `cluster.link.prefix` default null, max 12 chars, immutable | Default null; "maximum of 12 characters"; "cannot be changed after the cluster link is created" | Confirmed |
| 5 | `consumer.offset.sync.enable` default `false` | Default false | Confirmed |
| 6 | `consumer.offset.sync.ms` default 30000 | Default 30000 | Confirmed |
| 7 | `acl.sync.enable` default `false`, incompatible with prefix | Default false; "ACL syncing and prefixing cannot be enabled together on a single cluster link" | Confirmed |
| 8 | `num.cluster.link.fetchers` default 1 | Default 1 | Confirmed |
| 9 | `mirror.start.offset.spec` default `earliest` | Default earliest | Confirmed |
| 10 | `link.mode` / `connection.mode` (OUTBOUND on source, INBOUND on destination) | `connection.mode` default OUTBOUND, set on source link; `link.mode` default DESTINATION | Confirmed |
| 11 | Bidirectional mode CP 7.5+ | "Confluent Platform 7.5 or later"; not supported with "open source Apache Kafka" | Confirmed |
| 12 | Promote checks zero lag; failover does not | promote "checks that there is no mirroring lag, config sync lag, or consumer offset lag"; failover "succeeds regardless of the mirroring lag" | Confirmed |
| 13 | Schema Linking is separate | CL overview covers topic data/metadata only | Confirmed |
| 14 | No repartitioning; names preserved | mirror topic "always created with the same name as its source topic"; partition count copied | Confirmed |
| 15 | Cloud-vs-Platform table: destination "Any Confluent Server 7.0.0+", source "Kafka 3.0+ / CP 7.0+ (CP 7.1+ source-initiated)" | Current support matrix: Kafka 3.8.x+ / CP 7.8.x+ → CP 7.8.0+; source-initiated listed only for CP 7.8.0+ sources; footnote: "all currently supported versions" | **Drift — queued** (not auto-fixed; user scoped this pass to the transactional item) |
| 16 | Hub default limit 10 source clusters; CFK 300 s reconcile | Not on the CP pages fetched | Unverifiable — queued with ⚠️ marker |

**Omission logged (not a false claim):** the article never states that an Apache Kafka source cannot be source-initiated. Queued alongside item 15.

## Drift instances: 2 (1 fixed, 1 queued)

1. **Fixed.** Limitations bullet rewritten: transactions unsupported, `__transaction_state` not replicated, alternative paths named. Added the adjacent v0/v1 message-format limitation from the same docs section. Frontmatter `last_updated` / `last_validated` set to 2026-09-14.
2. **Fixed (second pass, same day, on user approval).** Cloud-vs-Platform table now points at "currently supported versions" with the CP 8.3-docs floors (Kafka 3.8+ / CP 7.8+; source-initiated only from CP 7.8+) instead of fixed 7.0/7.1 numbers. Added a paragraph under Link Initiation Types stating an Apache Kafka source cannot initiate a link. The Version Requirements Summary table is unchanged: it records feature-introduction versions, which remain correct. Queue entry cleared.

## Stubs with expansion potential: 0 (none in scope)

## Source-staleness: 0 STALE-SOURCE-1 findings for this article (it cites no `fsi-dsp://` sources)
## Missing/ambiguous sources: 0 for this article

**Lint evidence:** `tools/wiki-lint.py` fails under system Python (`ModuleNotFoundError: yaml`); run as `uv run --with pyyaml --no-project python3 tools/wiki-lint.py`. Under `uv`, the `--full` sweep reports 13 STALE/MISSING/AMBIGUOUS-SOURCE findings wiki-wide (gate is live), none on `cluster-linking-topology.md`. Plain lint after the fix reports no findings on this article. Pre-existing wiki-wide lint noise (missing `last_validated` on several articles, one vendor-source SHA drift on `fsi-canon-overlay-for-confluent-skills.md`) is unrelated and untouched.

## Health assessment

The article's configuration table and operational claims hold. The one substantive error was the transactional-semantics bullet, which understated a hard limitation as a soft one; that matters for any migration or DR plan involving EOS producers and is now corrected. The remaining queued item is version drift in a table that will keep aging; the suggested fix replaces fixed numbers with a pointer to the compatibility matrix.
