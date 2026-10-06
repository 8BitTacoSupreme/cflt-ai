# Phase H.3a: Plugin install + canon-overlay wiki article — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** H.3a-plugin-install-canon-overlay-wiki-article
**Mode:** Auto (`--auto`) — Claude selected recommended defaults from prior decisions; no interactive user prompts.
**Areas discussed:** Install mechanism · Overlay article shape · CLAUDE.md hook · Provenance + validation

---

## Install mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Install via `/plugin install streaming-skills-plugin@confluent-agent-skills` (Claude marketplace) | Confluent-published source of truth; reuses already-vendored upstream from H.1 | ✓ |
| Vendor-only (copy plugin source into raw/vendor) | Avoids runtime install dependency but loses live skill availability | |
| Hybrid (install + parallel vendor) | Redundant in H.3a; H.3b's pin file already provides a vendor-equivalent snapshot | |

**Notes:** Recommended default. Marketplace install gives developers immediate use of the four upstream skills; H.3b adds the pin + drift gate to lock the version.

---

## Pin in H.3a vs defer to H.3b

| Option | Description | Selected |
|--------|-------------|----------|
| Pin inside H.3a | Couples install + pin; larger diff; muddles single-purpose phase | |
| Defer pin entirely to H.3b (mirrors G.2c exactly) | Smallest H.3a diff; H.3b's pattern reused unchanged from G.2c | ✓ |

**Notes:** D-02 in CONTEXT.md. H.3a documents the currently-installed version in the overlay article's `source:` frontmatter as free-form text; H.3b formalizes into `tools/vendor-plugins.json` with a `--check`/CI gate that mirrors G.2c byte-for-byte where structurally possible.

---

## Overlay article shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single article with 4 sections (one per upstream skill) | One entry point; easier to keep cross-cutting overrides consistent | ✓ |
| Four separate articles (one per upstream skill) | Each upstream skill activation reads its own dedicated overlay file | |
| Single article + per-skill child articles | Heaviest; defers value to phase-boundary worth | |

**Notes:** D-04 in CONTEXT.md. Single article wins because (a) cross-cutting overrides (Avro everywhere, mTLS everywhere, exactly-once for regulatory) span multiple sections and are easier to keep in sync in one file, and (b) developers reading the overlay want one entry point, not a four-way scavenger hunt.

---

## Override-table shape

| Option | Description | Selected |
|--------|-------------|----------|
| 5-col: `Override Key | Upstream Default | FSI Override | Rationale | Canon Source` | Audit-grade: every override traceable to canon | ✓ |
| 3-col: `Setting | FSI Value | Why` | Minimal but loses upstream-default visibility | |
| Narrative bullets (no table) | Less scannable; harder to grep | |

**Notes:** D-06 in CONTEXT.md. 5-col table includes Canon Source citation (CLAUDE.md section, ADR, or fsi-dsp:// URI) so every row is auditable. Narrative belongs in a `## Why this overlay` paragraph below each table, not in the table itself.

---

## CLAUDE.md hook location

| Option | Description | Selected |
|--------|-------------|----------|
| New section after "Confluent Canon — Always-On Rules", before "MCP Tool Availability" | Visible alongside other canon hooks; preserves existing structure | ✓ |
| Inline footnote inside Canon section | Buries the hook; harder for Claude to surface as a top-level reference | |
| New separate file `.claude/UPSTREAM-SKILLS.md` | Requires Claude Code config to auto-read; extra plumbing | |

**Notes:** D-08 in CONTEXT.md. Project-root CLAUDE.md is already auto-loaded every session; new section is ~5 lines, declarative, follows existing heading conventions. Do NOT touch `~/.claude/CLAUDE.md` (the user's global file) — overlay is cflt-ai-specific (D-09).

---

## Provenance + validation discipline

| Option | Description | Selected |
|--------|-------------|----------|
| H.1 trip-wire pattern: `confidence: high`, `last_validated: today`, `source: streaming-skills-plugin@<version>`, provenance footer citing 4 upstream SKILL.md paths | Reuses proven H.1 frontmatter shape; survives H.3b's pin formalization without rewrite | ✓ |
| Minimal frontmatter (title + tags only) | Loses provenance + confidence signal; breaks `/wiki:lint` decay rules | |
| Inline-only provenance (no frontmatter) | Breaks the established wiki schema | |

**Notes:** D-10 in CONTEXT.md. Reuses H.1's proven pattern. H.3b will replace the free-form `source:` line with a structured pin once `tools/vendor-plugins.json` exists.

---

## `/wiki:validate` drift handling

| Option | Description | Selected |
|--------|-------------|----------|
| Zero-drift gate; H.1 `⚠️ unverified` escape hatch for thin MCP coverage; no bulk bypass | Established pattern from H.1 trip-wires #7–9 (WarpStream gaps) | ✓ |
| Allow validation to pass with documented drift findings | Slips article quality; lowers `confidence` to medium | |
| Skip MCP validation entirely | Violates phase success criterion #4 | |

**Notes:** D-11 in CONTEXT.md. Drift findings become either (a) article correction (canon claim was stale) or (b) `⚠️ unverified` inline marker (MCP coverage thin). No bulk bypass.

---

## Wiki graph integration

| Option | Description | Selected |
|--------|-------------|----------|
| ≥1 inbound edge required; target 2–3 for discoverability (mirrors H.1 discipline) | Article lands findable and lint-clean from day one | ✓ |
| ≥0 inbound edges (rely on _index.md discovery only) | Fails `/wiki:lint` orphan check; H.1 already established the 3-edge correction pattern | |

**Notes:** D-12 in CONTEXT.md. Patterns/ namespace target candidates: `patterns/fsi-governance-automation.md` and `patterns/fsi-exactly-once.md` are most semantically adjacent.

---

## Claude's Discretion

- Exact wording of CLAUDE.md hook (5 lines, follows existing heading conventions — planner / executor write the prose)
- Exact `tags:` array values beyond the required `[fsi, overlay, upstream-skills, canon]` baseline
- Selection of which 2–3 patterns/ articles get inbound edges (CONTEXT.md names two candidates; final pick at execution time based on which already has highest cross-reference density)

## Deferred Ideas

See `<deferred>` section of CONTEXT.md. Notable:
- Per-customer overlay articles (H.4c-adjacent or v2.x)
- Auto-generated overlay sections from CLAUDE.md (`tools/generate-canon-overlay.py`)
- Overlay-article evals via H.2 harness (post-H.3a, not blocking)
- Hooking overlay into upstream-skill activation via `.claude/settings.json` hooks (v2.x candidate after observing CLAUDE.md inclusion in practice)

## Reviewed Todos (not folded)

None — `gsd-tools todo match-phase H.3a` returned zero matches.
