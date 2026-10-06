# Phase H.3a: Plugin install + canon-overlay wiki article — Context

**Gathered:** 2026-05-17
**Status:** Ready for planning
**Mode:** Auto (--auto) — gray-area defaults selected from prior decisions (H.1, H.2, G.2c, CLAUDE.md canon)

<domain>
## Phase Boundary

Install `streaming-skills-plugin` (the Confluent-published Claude Code plugin containing the four upstream skills: `kafka-streams-programming`, `developing-kafka-python-client`, `kafka-schema-registry`, `confluent-cloud-cdc-tableflow`) into this cflt-ai project, and author **one** wiki overlay article at `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` that documents every FSI-canon override that must apply on top of the upstream defaults — per upstream skill, as a table of (override key → upstream default → FSI override → rationale → canon source). Hook the overlay article into cflt-ai's CLAUDE.md so it is loaded into context whenever an upstream skill activates.

After H.3a: the four upstream skills are available in this session; any developer invoking one inside cflt-ai sees the FSI guardrails in the same context window without having to remember them; the overlay article is wiki-validated (`/wiki:validate` passes, zero MCP drift) and carries `confidence: high`.

**Out of scope (do not let scope creep pull these in):**
- Version pin + drift CI gate (H.3b — separate phase, mirrors G.2c exactly)
- `/dsp:scaffold` wrapper skill (H.3c — depends on H.4 canon family)
- Developer-sandbox profile family (H.4a/b/c — orthogonal to overlay-article work)
- Editing the upstream skills themselves (out of scope forever — they are pinned via H.3b)
- New evals for the overlay article (H.2 harness can add them post-H.3a; not blocking)

</domain>

<decisions>
## Implementation Decisions

### Install mechanism
- **D-01:** Install via `/plugin install streaming-skills-plugin@confluent-agent-skills` from the existing `confluentinc/agent-skills` marketplace (already added during H.1's vendoring exploration if not earlier — verify via `/plugin marketplace list`; add with `/plugin marketplace add confluentinc/agent-skills` if missing). Reason: this is the Confluent-published source of truth; H.1 already pinned the vendored copy of `agent-skills` at SHA `91d1871ef8c320be92bca955c8e42492a2778cb4` and the plugin is the same upstream repo packaged as a Claude plugin.
- **D-02:** Do **not** pin the version inside H.3a. Pinning + drift gate is H.3b's responsibility (mirrors G.2c pattern exactly — generator + `--check` mode + CI workflow). H.3a's job is to land the install + overlay article so developers immediately benefit; H.3b locks the install down 24–48 hours later. Document the currently-installed version in the overlay article's `source:` frontmatter (free-form text — H.3b will formalize into `tools/vendor-plugins.json`).
- **D-03:** Verify install by confirming the four upstream skills appear in `/help` skill listings (the four named in the phase goal). If any are missing or named differently in the actual published plugin, the H.3a plan must surface that as a deviation, not silently retitle the overlay article sections.

### Overlay article shape
- **D-04:** Single article at `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` (not four separate articles). Reason: developers reading the overlay want one entry point that covers the whole upstream family; cross-cutting decisions (e.g., "FSI uses Avro everywhere, not JSON Schema") show up in multiple sections and are easier to keep consistent in one file. Patterns/ namespace (not concepts/) because this is operational guidance layered on top of vendor defaults.
- **D-05:** Four sections, one per upstream skill, in this order: (1) `kafka-streams-programming`, (2) `developing-kafka-python-client`, (3) `kafka-schema-registry`, (4) `confluent-cloud-cdc-tableflow`. Order matches both the phase-description list and developer adoption sequence (most-used first). Each section opens with a one-paragraph "when this skill activates" hook, then a table of overrides, then a `## Why this overlay` rationale paragraph.
- **D-06:** Override table shape (identical across all four sections): `| Override Key | Upstream Default | FSI Override | Rationale | Canon Source |`. Canon Source cites the relevant section of cflt-ai's CLAUDE.md (e.g., "CLAUDE.md §Producers — `acks=all`, `enable.idempotence=true`") or the relevant ADR / wiki article via fsi-dsp:// URI when applicable. This keeps the overlay article auditable: every override is traceable back to canon, not opinion.
- **D-07:** Override scope per skill is bounded by the **Confluent Canon — Always-On Rules** section of CLAUDE.md (Cluster/Topic Design, Schema Registry, Producers, Consumers, Flink SQL, Cluster Linking, Security) + the FSI-Specific Overlay subsection. If an upstream skill touches a canon dimension, that dimension is in the override table. If it doesn't, it's not. No speculation about future overrides — the article documents what's true today and what canon requires today.

### CLAUDE.md hook
- **D-08:** Add a new short section in cflt-ai's `CLAUDE.md` (root project file) titled `## Upstream Confluent Skills (streaming-skills-plugin)` immediately after the existing "Confluent Canon — Always-On Rules" block and before "MCP Tool Availability". The section is ~5 lines: one sentence stating the plugin is installed, a bullet listing the four upstream skills, and a single sentence directing Claude to "Read `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` whenever an upstream skill activates so the FSI overrides apply." This keeps the canon hook visible without bloating the main canon block.
- **D-09:** Do **not** modify the `.claude/CLAUDE.md` user-global file. The hook lives in the project-level CLAUDE.md only (which Claude Code reads automatically every session for this project). Reason: the global file is the user's personal global instructions and applies across all projects; the upstream-skills hook is cflt-ai-specific.

### Provenance + validation
- **D-10:** Overlay article frontmatter follows the H.1 trip-wire pattern: `confidence: high`, `last_validated: 2026-05-17`, `source: streaming-skills-plugin@<installed-version>` (free-form pending H.3b), `tags: [fsi, overlay, upstream-skills, canon]`, plus a provenance footer at the end of the body citing the four upstream skill source paths (e.g., `streaming-skills-plugin/kafka-streams-programming/SKILL.md`). H.3b will replace the free-form `source:` line with a structured pin once `tools/vendor-plugins.json` exists.
- **D-11:** `/wiki:validate` against MCP sources (context7 + confluent-docs) MUST pass with zero drift findings before the phase exits. Any drift surfaced becomes either (a) an override-table correction (if the canon claim is stale relative to live Confluent docs — fix the article) or (b) a flagged exception with an `⚠️ unverified` inline marker (only if context7/confluent-docs have limited published coverage for that specific override, matching the H.1 trip-wire-#7-thru-#9 WarpStream pattern). No bulk-bypass.
- **D-12:** Update `wiki/_index.md` to list the new article under the patterns/ section and update `wiki/_graph.md` with at least one inbound edge from an existing patterns article (e.g., `patterns/fsi-governance-automation.md` or `patterns/fsi-exactly-once.md` are the most semantically adjacent — pick whichever has the most active cross-references already). H.1's add-3-inbound-edges discipline applies — the article needs ≥1 inbound to satisfy the graph rule, target 2–3 for discoverability.

### Folded Todos
None — `todo match-phase H.3a` returned zero matches.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project canon
- `CLAUDE.md` (project root) — Confluent Canon Always-On Rules + FSI-Specific Overlay. This is the override source-of-truth that every overlay-table row must trace back to.
- `.planning/PROJECT.md` — Core value statement (canon overlay stack works), v2.0 active requirements, Key Decisions table including the G.2c upstream-pinning pattern.
- `.planning/REQUIREMENTS.md` — H.3a satisfies INST-01 (install — partial; full satisfaction requires H.3b's pin) and CAN-OVR-01 (overlay article + CLAUDE.md hook).

### Prior-phase contexts (patterns to reuse)
- `.planning/phases/H.1-wiki-ingest-agent-skills/H.1-CONTEXT.md` — Vendoring with pinned SHA + `tools/vendor-sources.json` + provenance footer pattern. H.3a's overlay article inherits the provenance-footer discipline.
- `.planning/phases/G.2c-tool-classification-rename/G.2c-CONTEXT.md` — Generator + `--check` mode + CI drift gate pattern that H.3b will mirror; H.3a does NOT implement this but the H.3b plan will reuse this CONTEXT.
- `.planning/phases/H.2-eval-harness-extension/H.2-CONTEXT.md` — Eval schema; if any H.3a outputs warrant evals, they layer on top of this harness (deferred — not in H.3a scope).

### Wiki convention references
- `wiki/_index.md` — Master article index; H.3a appends an entry.
- `wiki/_graph.md` — Backlink registry; H.3a adds inbound edges.
- `.claude/commands/wiki/references/article-format.md` — Article frontmatter / structure spec (read this before authoring the overlay article).
- `.claude/commands/wiki/references/quality-standards.md` — Confidence levels, validation rules, drift handling.

### Vendor source (already pinned by H.1)
- `tools/vendor-sources.json` — Current `confluent-agent-skills` SHA pin (`91d1871ef8c320be92bca955c8e42492a2778cb4`). The overlay article cites this commit in section provenance.
- `raw/vendor/confluent-agent-skills/91d1871ef8c320be92bca955c8e42492a2778cb4/skills/` — The four upstream skill source trees; read each `SKILL.md` to enumerate every default that the overlay article must address.

### MCP sources for `/wiki:validate`
- `confluent-docs` MCP server — Live Confluent documentation (llms.txt). Validates every override claim against current Confluent guidance.
- `context7` MCP server — Confluent Canon architecture patterns. Validates that FSI overrides are consistent with documented Confluent best practices.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`wiki/patterns/fsi-governance-automation.md` and `wiki/patterns/fsi-exactly-once.md`** — Closest sibling articles in the patterns/ namespace; their frontmatter shape + `confidence: high` + provenance footer + tag conventions are the direct template for H.3a's article.
- **`raw/vendor/confluent-agent-skills/91d1871ef8c320be92bca955c8e42492a2778cb4/skills/*/SKILL.md`** — Source for upstream defaults. The overlay table's "Upstream Default" column reads directly from these files.
- **`tools/vendor-sources.json`** — Already exists; the overlay article references the pinned commit; H.3b will extend the schema to include `claude-plugin` kind for the runtime-installed plugin.
- **`.claude/commands/wiki/references/article-format.md`** — Article authoring template (frontmatter, sections, provenance footer placement).
- **CLAUDE.md (project root)** — Has clearly-delineated sections (`## Confluent Canon — Always-On Rules`, `## MCP Tool Availability`, `## Working Style`); H.3a inserts a new section between Canon and MCP Tool Availability following the existing heading conventions.

### Established Patterns
- **Vendor-source provenance** — H.1 established `confluentinc/agent-skills@<sha>` footer + frontmatter `source:` line. H.3a reuses identically.
- **Wiki index + graph maintenance** — Every new wiki article updates `_index.md` and `_graph.md`; lint enforces ≥1 inbound edge.
- **`/wiki:validate` zero-drift gate** — Phase exit blocker. H.1 trip-wires used `⚠️ unverified` markers for specific WarpStream gaps where MCP coverage was thin; same escape hatch available here if needed.
- **CLAUDE.md hook style** — Existing canon sections are concise, declarative, and section-bounded; the new "Upstream Confluent Skills" section follows the same shape (~5 lines, declarative tone, no preamble).
- **Patterns/ vs concepts/ split** — concepts/ = foundational definitional articles; patterns/ = operational layered guidance. Overlay article is unambiguously patterns/.

### Integration Points
- **`CLAUDE.md` (project root)** — New section insertion (one diff hunk).
- **`wiki/patterns/fsi-canon-overlay-for-confluent-skills.md`** — New file.
- **`wiki/_index.md`** — One-line append in the patterns section.
- **`wiki/_graph.md`** — Edge additions (2–3 inbound to the new article).
- **Claude Code plugin manifest** — Install state captured in Claude's plugin registry (verified via `/plugin marketplace list` + `/help`); not a file in this repo. H.3b will codify the pin in `tools/vendor-plugins.json`.
- **No `tools/`, no `tests/`, no CI workflow changes in H.3a.** Those are H.3b territory.

</code_context>

<specifics>
## Specific Ideas

- **Override-table source-of-truth example** (from CLAUDE.md): for the `developing-kafka-python-client` section, an override row would read: `| acks | (varies — often acks=1 in upstream examples) | acks=all | Durable writes mandatory in FSI; never acks=0 or acks=1 | CLAUDE.md §Producers |`. Every row in every section follows this shape — no narrative bullets in the table itself, narrative belongs in the "Why this overlay" paragraph below the table.
- **The four upstream skills publish under slugs that may not exactly match the human-friendly names** (e.g., the plugin SKILL.md slug might be `kafka-streams-programming` vs documentation referring to "Kafka Streams"). The overlay article uses the actual plugin slug in section headings so that future `/help`-driven lookups land on the right section.
- **Reuse the H.1 WarpStream-style `⚠️ unverified` inline marker** if context7/confluent-docs have thin coverage for a specific override (e.g., a Confluent Cloud-only behavior not yet in llms.txt). This is the established escape hatch — do not bypass `/wiki:validate` wholesale.

</specifics>

<deferred>
## Deferred Ideas

- **Per-customer overlay articles** (e.g., acme-bank overrides on top of FSI overrides on top of upstream defaults) — Deferred to H.4c-adjacent work (acme-bank developer overlay) or a v2.x follow-on. H.3a establishes the FSI-layer overlay only; customer-layer overlays follow the same shape one level down.
- **Auto-generated overlay sections from CLAUDE.md** — A `tools/generate-canon-overlay.py` script that scrapes CLAUDE.md canon sections and emits override-table skeletons. Tempting but premature — write the article by hand first to discover what the table shape actually needs, then automate in a future phase if the maintenance burden warrants it.
- **Evals for the overlay article** (e.g., `expectations[]` asserting the article cites `acks=all`, `enable.idempotence=true`, `mTLS`, etc.) — H.2 harness can absorb these post-H.3a; not blocking phase exit. The wiki-lint drift detection from H.1 already provides a passive guard.
- **Hooking the overlay into upstream skill activation via Claude Code hooks** — Currently CLAUDE.md inclusion is the hook. A more aggressive integration (a hook config in `.claude/settings.json` that forces overlay-read on every upstream-skill invocation) is a candidate v2.x enhancement once we observe whether the implicit CLAUDE.md inclusion is enough in practice.

### Reviewed Todos (not folded)
None — no pending todos matched H.3a in `gsd-tools todo match-phase`.

</deferred>

---

*Phase: H.3a-plugin-install-canon-overlay-wiki-article*
*Context gathered: 2026-05-17 (auto-mode)*
