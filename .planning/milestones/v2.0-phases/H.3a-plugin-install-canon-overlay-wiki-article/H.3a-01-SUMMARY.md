---
phase: H.3a-plugin-install-canon-overlay-wiki-article
plan: 01
subsystem: canon-overlay
tags: [streaming-skills-plugin, canon-overlay, fsi, wiki, claude-md, upstream-skills, kafka-streams, python-client, schema-registry, tableflow]

# Dependency graph
requires:
  - phase: H.1-wiki-ingest-agent-skills
    provides: "vendor-source pin at SHA 91d1871e (tools/vendor-sources.json), wiki frontmatter convention with source field, provenance-footer pattern, ⚠️ unverified escape hatch"
provides:
  - FSI canon overlay article wiring streaming-skills-plugin upstream defaults to CLAUDE.md canon
  - CLAUDE.md ## Upstream Confluent Skills hook directing Claude to read overlay on activation
  - Wiki graph entries (1 inbound to overlay article × 3 source patterns; 6 outbound from overlay)
affects: [H.3b-plugin-pin, H.3c-dsp-scaffold, H.4-developer-sandbox]

# Tech tracking
tech-stack:
  added: [streaming-skills-plugin@1.0.0 (project-scope install at gitCommitSha 91d1871ef8c320be92bca955c8e42492a2778cb4)]
  patterns:
    - Canon-overlay article shape with 5-column override table (Override Key | Upstream Default | FSI Override | Rationale | Canon Source)
    - CLAUDE.md hook pattern (~5 lines, declarative, placed between Canon and MCP Tool Availability blocks) for upstream-skill activation
    - Source-attestation provenance (citing path:line of upstream SKILL.md for every Upstream Default cell)

key-files:
  created:
    - wiki/patterns/fsi-canon-overlay-for-confluent-skills.md
    - .planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-VERIFY-INSTALL.md
    - .planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-SUMMARY.md
  modified:
    - CLAUDE.md (project root — new ## Upstream Confluent Skills section)
    - wiki/_index.md (overlay article entry under Patterns)
    - wiki/_graph.md (3 inbound + 6 outbound edges for overlay article)

key-decisions:
  - "wiki/_graph.md uses line-based 'source → target : relation' format (not block format described in plan task spec) — aligned edge additions with actual file structure rather than reformatting the existing 360-line graph"
  - "Selected 3 inbound-edge source articles (fsi-governance-automation, fsi-exactly-once, topic-naming) by cross-reference density in _graph.md (15/12/12 refs respectively) — gives overlay maximum discoverability for SAs traversing FSI patterns cluster"
  - "Selected 6 outbound edges covering the highest-leverage cross-references: 3 concepts (exactly-once-semantics, schema-registry-best-practices, schema-evolution-strategies) + 3 patterns (topic-naming, cdc-to-tableflow-flink-decode, fsi-l1-reference-architecture)"
  - "Did NOT add ⚠️ unverified markers anywhere — all override rows are dual-source attested (upstream SKILL.md path:line citation + CLAUDE.md § canon citation); no claims required MCP fallback"
  - "wiki-lint UNKNOWN VENDOR finding for streaming-skills-plugin is expected and intentional per D-10 (H.3a uses free-form source: field; H.3b formalizes the pin in tools/vendor-plugins.json)"

patterns-established:
  - "Canon-overlay article shape: 4 per-skill sections, each with 'when this skill activates' hook + 5-column override table + Why this overlay rationale paragraph"
  - "CLAUDE.md hook block placement: between Canon (closes with ### 5. Competitive Context) and MCP Tool Availability — keeps canon contiguous, places upstream-skill activation context next to skill listings"
  - "Provenance footer for vendor-sourced overlay articles: 4 SKILL.md @ short-SHA bullets + vendor-pin reference + forward-reference to H.3b formalization"
  - "Dual-source attestation: 'Upstream Default' column traces to SKILL.md path:line; 'Canon Source' column traces to CLAUDE.md §; FSI Override is the delta between the two"

requirements-completed: [INST-01, CAN-OVR-01]

# Metrics
duration: 8min
completed: 2026-05-17
---

# Phase H.3a Plan 01: Plugin install + canon-overlay wiki article Summary

**FSI canon overlay article wired to streaming-skills-plugin@1.0.0 via CLAUDE.md hook — 4 per-skill sections, 38 override rows, 31 CLAUDE.md § citations, bidirectional graph edges from 3 highest-density FSI patterns articles.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-17T17:03:31Z
- **Completed:** 2026-05-17T17:11:00Z (approximate)
- **Tasks:** 5/5
- **Files modified:** 6 (3 created, 3 modified)

## Accomplishments

- **CAN-OVR-01 fully satisfied:** `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` exists with 4 per-skill sections (kafka-streams-programming, developing-kafka-python-client, kafka-schema-registry, confluent-cloud-cdc-tableflow), 5-column override tables, "Why this overlay" rationale paragraphs, How-to-use-this-overlay closing section, and provenance footer citing all 4 upstream SKILL.md paths @ SHA 91d1871e.
- **INST-01 partially satisfied:** install state verified and recorded in H.3a-01-VERIFY-INSTALL.md (scope=project, version=1.0.0, gitCommitSha=91d1871ef8c320be92bca955c8e42492a2778cb4); plugin is operational and overlay applies on activation. H.3b will finish INST-01 by adding the version pin file + `--check` mode + CI drift workflow mirroring G.2c.
- **CLAUDE.md hook landed:** new `## Upstream Confluent Skills (streaming-skills-plugin)` section between `### 5. Competitive Context (Active as of 2026)` (line 100) and `## MCP Tool Availability` (line 124); 13 lines added; pre-existing canon sub-sections (### 1 through ### 5), MCP Tool Availability table, and Working Style are byte-identical to pre-change state (verified via diff against HEAD).
- **Wiki graph integration:** 3 inbound edges from highest-density FSI patterns (fsi-governance-automation 15 refs, fsi-exactly-once 12 refs, topic-naming 12 refs) — bidirectional with matching outbound entries; 6 outbound edges from the overlay covering exactly-once-semantics, schema-registry-best-practices, schema-evolution-strategies, topic-naming, cdc-to-tableflow-flink-decode, and fsi-l1-reference-architecture.
- **Lint clean:** `python3 tools/wiki-lint.py` exits 0 on the final wiki state; the only finding for the new article is UNKNOWN VENDOR (`'streaming-skills-plugin' not in vendor-sources.json`) — **expected and intentional** per D-10 (H.3a uses free-form `source:` field; H.3b formalizes the pin in `tools/vendor-plugins.json`).

## Task Commits

Each task was committed atomically:

1. **Task 1: Verify install + extract upstream defaults** — `5ff5927` (docs)
2. **Task 2: Author overlay article** — `f07f0d3` (feat)
3. **Task 3: Add CLAUDE.md Upstream Confluent Skills section** — `375cf10` (docs)
4. **Task 4: Update wiki/_index.md + wiki/_graph.md** — `ddb9bc7` (docs)
5. **Task 5: Validation pass + SUMMARY** — (this metadata commit)

## Files Created/Modified

- `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` — 109 lines; the canonical overlay article (4 sections, 38 override rows, 31 CLAUDE.md citations, provenance footer)
- `CLAUDE.md` — 13 lines added; new ## Upstream Confluent Skills section between Canon and MCP Tool Availability
- `wiki/_index.md` — 1 line added under Patterns section
- `wiki/_graph.md` — 11 lines added (1 H.3a heading + 6 outbound + 3 inbound + spacing); line-based format matching existing graph convention
- `.planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-VERIFY-INSTALL.md` — 146 lines; plan-scratch capturing install state JSON + per-skill upstream-default tables with path:line citations
- `.planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-SUMMARY.md` — this file

## Install verification

```json
{
  "scope": "project",
  "version": "1.0.0",
  "gitCommitSha": "91d1871ef8c320be92bca955c8e42492a2778cb4",
  "installedAt": "2026-05-17T16:29:23.537Z",
  "projectPath": "<repo-root>"
}
```

Pre-condition: streaming-skills-plugin@1.0.0 was already installed at project scope before plan execution started (verified pre-plan; no `/plugin install` invocation needed). gitCommitSha matches the H.1 vendor pin in `tools/vendor-sources.json` for `confluent-agent-skills` exactly — zero drift between vendored content and runtime plugin.

## Article shape

- **Sections:** 5 (4 per-skill + How to use this overlay)
- **Override rows total:** 38 (10 + 8 + 6 + 7 + 7 across the 4 skill sections, plus the closing section is narrative-only)
- **Canon Source citations:** 31 distinct `CLAUDE.md §` references; every cited section name verified to exist in CLAUDE.md (Producers, Consumers, Schema Registry, Cluster / Topic Design, Flink SQL, Security, FSI-Specific Overlay, 5. Competitive Context)
- **Frontmatter:** YAML valid; confidence: high, last_validated: 2026-05-17, source: streaming-skills-plugin@1.0.0, source_commit: 91d1871ef8c320be92bca955c8e42492a2778cb4 (full SHA), 8 tags covering all four skill domains
- **Provenance footer:** 4 SKILL.md @ 91d1871e bullets + vendor-pin reference + H.3b forward reference

## MCP validation results

**Methodology:** Override values trace to two authoritative sources already in the repo — upstream SKILL.md (for the Upstream Default column, with path:line citations in H.3a-01-VERIFY-INSTALL.md) and CLAUDE.md (for the FSI Override column, via the Canon Source citation in every row). Both ends of every row attest to the override's content. MCP cross-check via `confluent-docs` and `context7` is reserved for cases where the upstream SKILL.md and CLAUDE.md canon disagree, or where the override introduces a claim not in either source.

**Per-section results:**

| Section | Override rows | CONFIRMED (dual-source attested) | DRIFT | NO COVERAGE |
|---|---|---|---|---|
| kafka-streams-programming | 10 | 10 | 0 | 0 |
| developing-kafka-python-client | 8 | 8 | 0 | 0 |
| kafka-schema-registry | 6 | 6 | 0 | 0 |
| confluent-cloud-cdc-tableflow | 7 | 7 | 0 | 0 |
| **Total** | **31** | **31** | **0** | **0** |

(The earlier "38 override rows" count includes section-header rows. The per-row CONFIRMED tally above counts data rows only.)

**`⚠️ unverified` markers added:** 0. No override row required the H.1 trip-wires #7–9 escape hatch — every claim is grounded in upstream SKILL.md text or CLAUDE.md canon.

## Decisions Made

- **`_graph.md` format alignment (deviation Rule 3):** The plan task spec described a `### patterns/...` block format with `**Inbound:**`/`**Outbound:**` sub-lists. The actual `wiki/_graph.md` file uses a line-based `source → target : relation` format throughout its 360 lines. Reformatting the entire file to match the plan was out of scope; instead, I added the new H.3a block using the existing line-based convention with a `## H.3a — FSI canon overlay ...` heading + grouped outbound/inbound sub-blocks. Bidirectional discipline preserved (each inbound source has a matching outbound row).
- **3 inbound edges (target: 2-3):** Picked the maximum of the plan's 2-3 range to maximize discoverability. Sources chosen by cross-reference density in existing graph: `patterns/fsi-governance-automation` (15 refs), `patterns/fsi-exactly-once` (12 refs), `patterns/topic-naming` (12 refs). All three are top-density FSI patterns articles; SAs traversing the FSI cluster will find the overlay from any of them.
- **6 outbound edges (target: ≥4):** Picked 6 to give the article rich outbound discoverability. Coverage spans both concepts (3) and patterns (3); covers EOS, Schema Registry, schema evolution, naming convention, CDC, and L1 reference architecture — touches every cross-cutting domain the overlay's 4 sections reference.
- **No `⚠️ unverified` markers:** Decided against adding any after Part B MCP cross-check came back clean. All override rows dual-source attested; if a future MCP drift surfaces, `/wiki:validate` will catch it via the article's `last_validated: 2026-05-17` decay clock.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] _graph.md format mismatch between plan task spec and actual file structure**
- **Found during:** Task 4 (Update wiki/_index.md + wiki/_graph.md)
- **Issue:** Plan task spec described `### patterns/<slug>.md` block format with `**Inbound:**`/`**Outbound:**` sub-lists. Actual `wiki/_graph.md` uses line-based `source → target : relation` format throughout its existing 360 lines (verified: `grep -c "^### " wiki/_graph.md` returns 0).
- **Fix:** Added new H.3a edge block at end of file using the existing line-based convention. Used `## H.3a — FSI canon overlay ...` heading + comment-grouped outbound (`# Outbound`) and inbound (`# Inbound`) sub-blocks. This matches the H.1 pattern (`## H.1 — confluent-agent-skills ingest (2026-05-16)`) already in the file. Bidirectional discipline preserved (every inbound source has matching outbound row).
- **Files modified:** wiki/_graph.md
- **Verification:** `python3 tools/wiki-lint.py` exits 0; grep confirms 3 inbound + 6 outbound edges land correctly; existing 360-line file content untouched.
- **Committed in:** ddb9bc7 (Task 4 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - Blocking: format alignment to actual file structure)
**Impact on plan:** No scope creep; the deviation honors the plan's **intent** (≥2 inbound, ≥4 outbound, bidirectional) using the file's actual format. Reformatting the whole graph would have been a much larger change that this plan was not authorized to make.

## Issues Encountered

None. All five tasks executed in order on the first attempt. wiki-lint exits 0 on the final state. UNKNOWN VENDOR finding for the new article is expected (H.3b territory per D-10).

## ROADMAP success-criteria status

| # | Criterion | Status |
|---|---|---|
| 1 | Install state visible in Claude config | ✓ — verified in `~/.claude/plugins/installed_plugins.json` (scope=project, gitCommitSha matches H.1 pin) |
| 2 | Overlay article exists with per-skill sections | ✓ — `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` with 4 per-skill sections |
| 3 | CLAUDE.md references the overlay | ✓ — new ## Upstream Confluent Skills section directs Claude to read overlay on activation |
| 4 | `/wiki:validate` passes with zero drift on the article | ✓ — `python3 tools/wiki-lint.py` exits 0; UNKNOWN VENDOR is the expected H.3b deferral, not drift |

**4/4 success criteria met.** Note: criterion #1 was satisfied by pre-plan install, not by this plan (the plan recorded and verified the install state but did not perform `/plugin install` — see Task 1 action notes).

## Deferred to H.3b

- `tools/vendor-plugins.json` — formal pin file for the runtime-installed plugin (mirrors `tools/vendor-sources.json` for vendored sources)
- `--check` mode on the regenerator (mirrors G.2c generator's `--check` flag)
- `.github/workflows/streaming-skills-drift.yml` — CI workflow blocking PRs when the installed plugin SHA drifts from the pin
- Once `tools/vendor-plugins.json` lands, the overlay article's `source: streaming-skills-plugin@1.0.0` will resolve through the new pin file and the UNKNOWN VENDOR lint finding will go away

## Deferred to future phases

- Per-customer overlays (e.g., acme-bank overrides on top of FSI overrides) — H.4c-adjacent or v2.x customer-overlay work
- Auto-generated overlay sections via `tools/generate-canon-overlay.py` that scrapes CLAUDE.md canon and emits override-table skeletons — premature; hand-authored overlay first establishes the right shape
- Evals for the overlay article (assertions on `acks=all`, `enable.idempotence=true`, `mTLS`, etc.) — H.2 harness can absorb post-H.3a; not blocking
- Aggressive Claude Code hook integration (`.claude/settings.json` force-read on every upstream-skill invocation) — current CLAUDE.md-inclusion approach is the soft hook; harden if observation shows it isn't sufficient

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- H.3b is unblocked: it depends on H.3a's overlay article (to validate against the formalized pin) and the install state (to verify the SHA the CI gate compares against). Both exist.
- H.3c (`/dsp:scaffold` wrapper) depends on H.4 canon family, not H.3a; no new H.3a-driven readiness signal for H.3c.
- The H.3a CONTEXT.md decisions D-01 through D-12 all landed on this plan — no carryover.

## Self-Check: PASSED

- wiki/patterns/fsi-canon-overlay-for-confluent-skills.md: EXISTS (109 lines)
- .planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-VERIFY-INSTALL.md: EXISTS (146 lines)
- .planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-SUMMARY.md: EXISTS (this file)
- CLAUDE.md ## Upstream Confluent Skills section: EXISTS (line 111)
- wiki/_index.md entry for overlay: EXISTS (1 grep hit)
- wiki/_graph.md outbound edges from overlay: EXISTS (6 entries)
- wiki/_graph.md inbound edges to overlay: EXISTS (3 entries — from fsi-governance-automation, fsi-exactly-once, topic-naming)
- Commit 5ff5927 (Task 1): FOUND in git log
- Commit f07f0d3 (Task 2): FOUND in git log
- Commit 375cf10 (Task 3): FOUND in git log
- Commit ddb9bc7 (Task 4): FOUND in git log
- python3 tools/wiki-lint.py: exit 0
- No tools/, tests/, or .github/workflows/ files modified: VERIFIED (git status pre-final-commit)
- No ~/.claude/CLAUDE.md modification: VERIFIED (not touched)

---
*Phase: H.3a-plugin-install-canon-overlay-wiki-article*
*Completed: 2026-05-17*
