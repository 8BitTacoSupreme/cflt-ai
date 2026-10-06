---
phase: H.3a-plugin-install-canon-overlay-wiki-article
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - wiki/patterns/fsi-canon-overlay-for-confluent-skills.md
  - wiki/_index.md
  - wiki/_graph.md
  - CLAUDE.md
autonomous: true
requirements: [INST-01, CAN-OVR-01]
requirements_addressed: [INST-01, CAN-OVR-01]

must_haves:
  truths:
    - "`streaming-skills-plugin@confluent-agent-skills` install state is recorded in `~/.claude/plugins/installed_plugins.json` (project scope), version 1.0.0, gitCommitSha matches the H.1 vendor pin `91d1871ef8c320be92bca955c8e42492a2778cb4`"
    - "The four upstream SKILL.md files exist under `~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/` — `kafka-streams-programming`, `developing-kafka-python-client`, `kafka-schema-registry`, `confluent-cloud-cdc-tableflow`"
    - "`wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` exists with one section per upstream skill (4 sections in the order specified by D-05), each containing a 5-column override table (`Override Key | Upstream Default | FSI Override | Rationale | Canon Source`)"
    - "Every row in every override table cites a Canon Source — CLAUDE.md section, ADR, fsi-dsp:// URI, or wiki article path"
    - "Article frontmatter has `confidence: high`, `last_validated: 2026-05-17`, `source: streaming-skills-plugin@1.0.0` (free-form pending H.3b), `tags` includes at least `fsi`, `overlay`, `upstream-skills`, `canon`"
    - "Article body ends with a provenance footer citing all four upstream SKILL.md paths (form: `streaming-skills-plugin/<skill>/SKILL.md @ 91d1871e`)"
    - "`wiki/_index.md` lists the new article under the patterns/ section"
    - "`wiki/_graph.md` contains at least 2 inbound edges pointing to `patterns/fsi-canon-overlay-for-confluent-skills.md` (target: 2–3)"
    - "`CLAUDE.md` (project root) gains a new `## Upstream Confluent Skills (streaming-skills-plugin)` section positioned after `## Confluent Canon — Always-On Rules` (line 23) and before `## MCP Tool Availability` (current line 111). New section is ~5 lines: declarative tone, lists the four upstream skills, directs Claude to read the overlay article on activation"
    - "`tools/wiki-lint.py` runs clean on the new article (no orphan, no decay, no broken-link findings) — drift findings from H.1's `check_vendor_drift` remain non-fatal per H.1-03 D-09"
    - "No changes to `~/.claude/CLAUDE.md` (the user's global file) per H.3a CONTEXT.md D-09"
    - "No `tools/`, no `tests/`, no `.github/workflows/` changes in this plan — H.3b territory"
  artifacts:
    - path: "wiki/patterns/fsi-canon-overlay-for-confluent-skills.md"
      provides: "Single canonical overlay article documenting FSI overrides on top of streaming-skills-plugin upstream defaults, per upstream skill"
      contains:
        - "## Section: kafka-streams-programming"
        - "## Section: developing-kafka-python-client"
        - "## Section: kafka-schema-registry"
        - "## Section: confluent-cloud-cdc-tableflow"
        - "| Override Key | Upstream Default | FSI Override | Rationale | Canon Source |"
        - "confidence: high"
        - "last_validated: 2026-05-17"
        - "source: streaming-skills-plugin@1.0.0"
    - path: "CLAUDE.md"
      provides: "Project canon file gains Upstream Confluent Skills section that hooks the overlay article into upstream-skill activations"
      contains:
        - "## Upstream Confluent Skills (streaming-skills-plugin)"
        - "wiki/patterns/fsi-canon-overlay-for-confluent-skills.md"
        - "kafka-streams-programming"
        - "developing-kafka-python-client"
        - "kafka-schema-registry"
        - "confluent-cloud-cdc-tableflow"
    - path: "wiki/_index.md"
      provides: "Master article index gains entry for the new overlay article"
      contains:
        - "fsi-canon-overlay-for-confluent-skills.md"
    - path: "wiki/_graph.md"
      provides: "Backlink registry gains inbound edges to the new overlay article"
      contains:
        - "fsi-canon-overlay-for-confluent-skills"
  key_links:
    - from: "CLAUDE.md"
      to: "wiki/patterns/fsi-canon-overlay-for-confluent-skills.md"
      via: "Direct path reference inside the new `## Upstream Confluent Skills` section so Claude loads the overlay whenever an upstream skill activates"
      pattern: "wiki/patterns/fsi-canon-overlay-for-confluent-skills.md"
    - from: "wiki/patterns/fsi-canon-overlay-for-confluent-skills.md"
      to: "CLAUDE.md (Confluent Canon — Always-On Rules)"
      via: "Every override table's Canon Source column cites the relevant CLAUDE.md section (Producers, Consumers, Schema Registry, Cluster/Topic Design, Flink SQL, Security, FSI-Specific Overlay)"
      pattern: "CLAUDE.md §"
    - from: "wiki/patterns/fsi-canon-overlay-for-confluent-skills.md"
      to: "raw/vendor/confluent-agent-skills/91d1871ef8c320be92bca955c8e42492a2778cb4/"
      via: "Provenance footer cites the four upstream SKILL.md paths at the H.1 pinned SHA"
      pattern: "streaming-skills-plugin/.*/SKILL.md @ 91d1871e"
---

<objective>
Land the FSI canon overlay article that hooks the just-installed `streaming-skills-plugin` (already at version 1.0.0 / SHA `91d1871ef8c320be92bca955c8e42492a2778cb4`, project scope) into cflt-ai's canon stack so any developer invoking one of the four upstream skills inside cflt-ai gets the FSI overrides applied without having to remember them.

After this plan:
- INST-01 is **partially satisfied** — install is verified, plugin is usable; H.3b finishes the requirement by adding the version pin file + `--check` mode + CI drift workflow that mirrors G.2c.
- CAN-OVR-01 is **fully satisfied** — overlay article exists, 4 sections, override tables with Canon Source citations; CLAUDE.md hook directs Claude to read it on upstream-skill activation.
- The four ROADMAP success criteria for H.3a are met: (1) install state visible in claude config — yes, already installed; (2) overlay article exists with per-skill sections — this plan; (3) CLAUDE.md references the overlay — this plan; (4) `/wiki:validate` passes with zero drift on the article — this plan's verification gate.

Single PLAN.md, single wave, autonomous. No code, no tests, no CI workflow — content + canon-hook only. Total surface area: 4 files modified (new article, CLAUDE.md update, _index.md append, _graph.md edges), 0 files deleted, 0 dependencies added.

</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-CONTEXT.md
@.planning/phases/H.1-wiki-ingest-agent-skills/H.1-CONTEXT.md
@CLAUDE.md
@wiki/_index.md
@wiki/_graph.md
@wiki/patterns/fsi-governance-automation.md
@wiki/patterns/fsi-exactly-once.md
@.claude/commands/wiki/references/article-format.md
@.claude/commands/wiki/references/quality-standards.md
@tools/vendor-sources.json
@~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/kafka-streams-programming/SKILL.md
@~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/developing-kafka-python-client/SKILL.md
@~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/kafka-schema-registry/SKILL.md
@~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/confluent-cloud-cdc-tableflow/SKILL.md

<interfaces>
<!-- Article frontmatter shape — H.1 trip-wire-article pattern, extended with `source:` per H.3a D-10 -->
---
title: FSI Canon Overlay for Confluent Agent Skills
slug: fsi-canon-overlay-for-confluent-skills
category: pattern
confidence: high
last_validated: 2026-05-17
source: streaming-skills-plugin@1.0.0
source_commit: 91d1871ef8c320be92bca955c8e42492a2778cb4
tags: [fsi, overlay, upstream-skills, canon, kafka-streams, python-client, schema-registry, tableflow]
---

<!-- Override-table column order (D-06 — every section uses this shape) -->
| Override Key | Upstream Default | FSI Override | Rationale | Canon Source |

<!-- CLAUDE.md hook section shape (D-08 — ~5 lines, declarative, placed between Canon and MCP Tool Availability) -->
## Upstream Confluent Skills (streaming-skills-plugin)

The `streaming-skills-plugin@confluent-agent-skills` plugin is installed at project scope (version 1.0.0, commit `91d1871e`). It exposes four upstream Confluent skills:

- `kafka-streams-programming` — KStream/KTable topology, debugging, production hardening
- `developing-kafka-python-client` — Python producer/consumer scaffolding + Schema Registry integration
- `kafka-schema-registry` — Schema discovery, PII tagging, Terraform registration
- `confluent-cloud-cdc-tableflow` — Debezium → Flink → Tableflow CDC pipelines

**FSI guardrails:** When any of these skills activates, read `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` and apply the documented FSI overrides on top of the upstream defaults. The overlay is the source of truth for FSI-tier values (mTLS, exactly_once_v2, Avro/Protobuf, FULL compatibility, etc.).

<!-- Provenance footer shape (D-10 + H.1 vendoring convention) -->
---

**Provenance**
- `streaming-skills-plugin/kafka-streams-programming/SKILL.md` @ 91d1871e
- `streaming-skills-plugin/developing-kafka-python-client/SKILL.md` @ 91d1871e
- `streaming-skills-plugin/kafka-schema-registry/SKILL.md` @ 91d1871e
- `streaming-skills-plugin/confluent-cloud-cdc-tableflow/SKILL.md` @ 91d1871e

Vendor pin: `tools/vendor-sources.json` → `confluent-agent-skills` @ commit `91d1871ef8c320be92bca955c8e42492a2778cb4`. Upgrade workflow: bump SHA in vendor-sources.json, re-run `/wiki:validate` against this article, re-commit as a single PR. H.3b will formalize the plugin-install pin separately in `tools/vendor-plugins.json` with a `--check` mode and CI drift workflow.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Verify streaming-skills-plugin install state and capture the four upstream SKILL.md content for override-table sourcing</name>
  <files>
    - .planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-VERIFY-INSTALL.md
  </files>
  <read_first>
    - ~/.claude/plugins/installed_plugins.json (must contain `streaming-skills-plugin@confluent-agent-skills` at scope `project`, version `1.0.0`, gitCommitSha `91d1871ef8c320be92bca955c8e42492a2778cb4`)
    - ~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/kafka-streams-programming/SKILL.md
    - ~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/developing-kafka-python-client/SKILL.md
    - ~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/kafka-schema-registry/SKILL.md
    - ~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/confluent-cloud-cdc-tableflow/SKILL.md
    - tools/vendor-sources.json (confirm `confluent-agent-skills` pin matches plugin gitCommitSha — sanity check on the H.1 / H.3a alignment)
  </read_first>
  <action>
    Confirm the install pre-condition is met and capture the upstream default values that the overlay table will override. This is a passive verification task — do NOT run `/plugin install` again (idempotent but generates noise).

    Concrete checks:
    1. `jq '.plugins["streaming-skills-plugin@confluent-agent-skills"][0]' ~/.claude/plugins/installed_plugins.json` returns an object with `scope == "project"`, `version == "1.0.0"`, `gitCommitSha == "91d1871ef8c320be92bca955c8e42492a2778cb4"`. If absent or different scope/SHA: STOP and report — do not attempt to re-install (install is a user action; if the install is missing, the developer running this plan should run `/plugin install streaming-skills-plugin@confluent-agent-skills` manually).
    2. All four SKILL.md files exist under `~/.claude/plugins/cache/confluent-agent-skills/streaming-skills-plugin/1.0.0/skills/<skill-name>/SKILL.md`. If any are missing: STOP and report.
    3. `tools/vendor-sources.json` `confluent-agent-skills.commit` field equals `91d1871ef8c320be92bca955c8e42492a2778cb4`. If divergent: surface the drift but DO NOT modify vendor-sources.json (H.3b territory).

    For each of the four SKILL.md files, extract the upstream defaults relevant to canon dimensions covered by CLAUDE.md §Confluent Canon — Always-On Rules. The extracted defaults will populate the "Upstream Default" column of each override table in Task 2. Specifically grep for:
    - **kafka-streams-programming/SKILL.md**: `processing.guarantee`, `replication.factor`, `min.insync.replicas`, `commit.interval.ms`, `cache.max.bytes.buffering`, exactly-once vs at-least-once defaults, state-store backup, RocksDB tuning
    - **developing-kafka-python-client/SKILL.md**: `acks`, `enable.idempotence`, `compression.type`, `auto.offset.reset`, `enable.auto.commit`, schema format defaults (JSON vs Avro vs Protobuf), authentication mechanism (PLAIN, SCRAM, OAUTHBEARER, mTLS)
    - **kafka-schema-registry/SKILL.md**: subject naming strategy (TopicNameStrategy vs RecordNameStrategy), compatibility mode (NONE/BACKWARD/FULL), schema format (JSON Schema / Avro / Protobuf) recommended defaults
    - **confluent-cloud-cdc-tableflow/SKILL.md**: Tableflow destination format (JSON/Avro/Protobuf/Iceberg/Delta), Debezium signal config defaults, Flink watermark strategy, scan.startup.mode

    Write findings to `.planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-VERIFY-INSTALL.md` as a one-page note: install-state check result + per-skill upstream-default extracts (raw quotes with `path:line-range` anchors). This file is plan-scratch (not committed to wiki, not user-facing) — its purpose is to give Task 2 a single ground-truth doc to copy from when authoring the override tables, so each row is traceable to an exact upstream source line.
  </action>
  <acceptance_criteria>
    - `.planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-VERIFY-INSTALL.md` exists.
    - File contains the literal string `gitCommitSha: 91d1871ef8c320be92bca955c8e42492a2778cb4` (or the install JSON snippet showing it).
    - File contains a section per upstream skill (4 sections), each with at least 5 upstream-default rows quoted from the corresponding SKILL.md with file-path + line-range citations.
    - File contains a section "Install state" with the literal string `scope: project` and `version: 1.0.0` (or the install JSON snippet).
    - If the install is missing OR the SHA is divergent OR any SKILL.md is missing, the file contains a `## BLOCKED` heading instead, naming the specific failure, and Task 2 does NOT execute until the blocker is resolved.
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 2: Author wiki/patterns/fsi-canon-overlay-for-confluent-skills.md with 4 sections (one per upstream skill), each containing a 5-column override table and a "Why this overlay" rationale paragraph, plus the article-format-compliant frontmatter and provenance footer</name>
  <files>
    - wiki/patterns/fsi-canon-overlay-for-confluent-skills.md
  </files>
  <read_first>
    - .planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-VERIFY-INSTALL.md (upstream defaults captured in Task 1 — every "Upstream Default" cell pulls from here)
    - CLAUDE.md (project root — every "Canon Source" cell cites a section here)
    - .claude/commands/wiki/references/article-format.md (frontmatter + section conventions)
    - .claude/commands/wiki/references/quality-standards.md (confidence tier rules, `last_validated` discipline)
    - wiki/patterns/fsi-governance-automation.md (sibling article — frontmatter shape + tag conventions)
    - wiki/patterns/fsi-exactly-once.md (sibling article — provenance footer shape)
    - .planning/phases/H.1-wiki-ingest-agent-skills/H.1-CONTEXT.md (vendoring + provenance footer pattern at SHA `91d1871e`)
  </read_first>
  <action>
    Create `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` with the structure below. Use exact section headings, exact column order, and exact frontmatter keys.

    **Frontmatter (verbatim — keep field order):**
    ```yaml
    ---
    title: FSI Canon Overlay for Confluent Agent Skills
    slug: fsi-canon-overlay-for-confluent-skills
    category: pattern
    confidence: high
    last_validated: 2026-05-17
    source: streaming-skills-plugin@1.0.0
    source_commit: 91d1871ef8c320be92bca955c8e42492a2778cb4
    tags: [fsi, overlay, upstream-skills, canon, kafka-streams, python-client, schema-registry, tableflow]
    ---
    ```

    **Article body structure (exact heading text):**

    1. Opening paragraph (3–5 sentences): explain what the article does — when `streaming-skills-plugin` upstream skills activate inside cflt-ai, Claude reads this overlay and applies the FSI overrides documented below on top of the upstream defaults. Note that the FSI tier is the operator/production overlay; developer-sandbox overrides are separately handled in H.4 (forward reference).

    2. `## kafka-streams-programming`
       - One-paragraph "when this skill activates" hook (what KStream/KTable scenarios trigger it inside cflt-ai)
       - Override table — 5 columns: `| Override Key | Upstream Default | FSI Override | Rationale | Canon Source |`. Cover at minimum: `processing.guarantee`, `replication.factor`, `min.insync.replicas`, state-store backup, naming convention (`<domain>.<entity>.<event>`), partition-count starting point (`6 × peak MB/s`). Every "Canon Source" cell cites `CLAUDE.md §<section name>` (e.g., `CLAUDE.md §Cluster / Topic Design`, `CLAUDE.md §Flink SQL` — Kafka Streams shares processing.guarantee semantics with Flink).
       - `### Why this overlay` paragraph: 2–3 sentences explaining why FSI imposes these overrides (regulatory durability, exactly-once for compliance, etc.).

    3. `## developing-kafka-python-client`
       - "When this skill activates" hook (Python producer/consumer scaffolding requests)
       - Override table covering: `acks`, `enable.idempotence`, `compression.type`, `auto.offset.reset`, `enable.auto.commit`, authentication mechanism (PLAIN → mTLS/OAUTHBEARER), schema format (JSON → Avro/Protobuf). Canon Source cells cite `CLAUDE.md §Producers`, `CLAUDE.md §Consumers`, `CLAUDE.md §Security`, `CLAUDE.md §FSI-Specific Overlay`.
       - `### Why this overlay` paragraph.

    4. `## kafka-schema-registry`
       - "When this skill activates" hook (schema discovery / Terraform registration / PII tagging)
       - Override table covering: subject naming strategy (`TopicNameStrategy` default, `RecordNameStrategy` for event unions), compatibility mode (`BACKWARD` default, `FULL` for shared contracts), schema format (Avro/Protobuf — never JSON Schema in prod). Canon Source cells cite `CLAUDE.md §Schema Registry`.
       - `### Why this overlay` paragraph.

    5. `## confluent-cloud-cdc-tableflow`
       - "When this skill activates" hook (CDC pipeline construction requests — Debezium → Flink → Tableflow / Iceberg / Delta)
       - Override table covering: Flink watermark strategy (`BOUNDED_OUT_OF_ORDERNESS`), `scan.startup.mode` (`earliest-offset` for deterministic replay), connector preference (`UPSERT-KAFKA` for changelog), window choice (tumbling > sliding > session), Tableflow destination format. Canon Source cells cite `CLAUDE.md §Flink SQL (Confluent Cloud)`.
       - `### Why this overlay` paragraph.

    6. `## How to use this overlay`
       - 4–6 lines: when an upstream skill activates, Claude reads this article; for any override key not listed in a section, the upstream default applies; if the upstream skill produces output that conflicts with an FSI override row, the overlay wins and the conflict is logged as a review note.

    7. `## Open questions`
       - Bullet list of overrides where `confluent-docs` / `context7` MCP coverage was thin and we used `⚠️ unverified` markers inline (mirrors H.1 trip-wires #7–9 escape hatch — only include this section if any such markers were needed; otherwise omit).

    **Provenance footer (verbatim — last paragraph of body):**
    ```markdown
    ---

    **Provenance**
    - `streaming-skills-plugin/kafka-streams-programming/SKILL.md` @ 91d1871e
    - `streaming-skills-plugin/developing-kafka-python-client/SKILL.md` @ 91d1871e
    - `streaming-skills-plugin/kafka-schema-registry/SKILL.md` @ 91d1871e
    - `streaming-skills-plugin/confluent-cloud-cdc-tableflow/SKILL.md` @ 91d1871e

    Vendor pin: `tools/vendor-sources.json` → `confluent-agent-skills` @ commit `91d1871ef8c320be92bca955c8e42492a2778cb4`. Plugin pin formalized in H.3b (`tools/vendor-plugins.json` + `.github/workflows/streaming-skills-drift.yml`).
    ```

    **Validation discipline (D-11):**
    - Every claim about an upstream default must be traceable to a `path:line` citation in `H.3a-01-VERIFY-INSTALL.md`.
    - Every override row must cite a real CLAUDE.md section (no inventing section names — verify against the section list grepped from CLAUDE.md).
    - Where `confluent-docs` MCP coverage cannot confirm a specific override value (e.g., a recent Confluent Cloud-only behavior), prepend the value with `⚠️ unverified` and add a bullet to the `## Open questions` section. Do NOT bypass this — drift findings on phase exit are blocking per H.3a CONTEXT D-11.
  </action>
  <acceptance_criteria>
    - `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` exists.
    - File contains the literal string `title: FSI Canon Overlay for Confluent Agent Skills`.
    - File contains the literal string `confidence: high`.
    - File contains the literal string `last_validated: 2026-05-17`.
    - File contains the literal string `source_commit: 91d1871ef8c320be92bca955c8e42492a2778cb4`.
    - `grep -c "^## " wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` returns ≥ 5 (4 skill sections + "How to use this overlay"; +1 if "Open questions" present).
    - File contains the literal heading `## kafka-streams-programming`.
    - File contains the literal heading `## developing-kafka-python-client`.
    - File contains the literal heading `## kafka-schema-registry`.
    - File contains the literal heading `## confluent-cloud-cdc-tableflow`.
    - File contains the literal heading `## How to use this overlay`.
    - File contains the column header line `| Override Key | Upstream Default | FSI Override | Rationale | Canon Source |` at least 4 times (one per skill section).
    - File contains at least 4 occurrences of `CLAUDE.md §` (one per skill section minimum — proves Canon Source citations exist).
    - File ends with the Provenance footer containing all 4 `streaming-skills-plugin/.../SKILL.md @ 91d1871e` lines.
    - `python3 -c "import yaml,sys; yaml.safe_load(open('wiki/patterns/fsi-canon-overlay-for-confluent-skills.md').read().split('---')[1])"` exits 0 (frontmatter is valid YAML).
    - `python3 tools/wiki-lint.py --article wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` exits 0 (no stub, no decay, no broken-link, no missing-graph-edge findings — drift findings non-fatal per H.1-03 D-09).
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 3: Add Upstream Confluent Skills section to CLAUDE.md (project root) between the Confluent Canon block and MCP Tool Availability block</name>
  <files>
    - CLAUDE.md
  </files>
  <read_first>
    - CLAUDE.md (current — section list: For the Team, Confluent Canon — Always-On Rules (sub-sections 1–5), MCP Tool Availability, Working Style)
    - .planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-CONTEXT.md (D-08 + D-09 — placement rule + ~5-line shape + project-CLAUDE-only)
  </read_first>
  <action>
    Insert a new `## Upstream Confluent Skills (streaming-skills-plugin)` section into `CLAUDE.md` immediately after the existing `### 5. Competitive Context (Active as of 2026)` block (which closes the Confluent Canon — Always-On Rules block — see CLAUDE.md current line ~109) and before the `---` divider preceding `## MCP Tool Availability` (current line 111).

    Exact section content (do not paraphrase — copy verbatim):

    ```markdown
    ---

    ## Upstream Confluent Skills (streaming-skills-plugin)

    The `streaming-skills-plugin@confluent-agent-skills` plugin is installed at project scope (version 1.0.0, commit `91d1871e`). It exposes four upstream Confluent skills:

    - `kafka-streams-programming` — KStream/KTable topology, debugging, production hardening
    - `developing-kafka-python-client` — Python producer/consumer scaffolding + Schema Registry integration
    - `kafka-schema-registry` — Schema discovery, PII tagging, Terraform registration
    - `confluent-cloud-cdc-tableflow` — Debezium → Flink → Tableflow CDC pipelines

    **FSI guardrails:** When any of these skills activates, read `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` and apply the documented FSI overrides on top of the upstream defaults. The overlay is the source of truth for FSI-tier values (mTLS, exactly_once_v2, Avro/Protobuf, FULL compatibility, etc.). Plugin version pin and CI drift gate land separately in Phase H.3b.
    ```

    Placement rule:
    - The leading `---` is the existing divider between Canon and MCP Tool Availability — keep it where it is and insert the new section BEFORE the `## MCP Tool Availability` heading.
    - If the leading `---` already exists, do NOT duplicate it — insert the new `## Upstream Confluent Skills (...)` heading after it and a fresh blank line before `## MCP Tool Availability`.
    - Do NOT modify `### 1. Use the Confluent Docs MCP Server` through `### 5. Competitive Context (Active as of 2026)`.
    - Do NOT modify `## MCP Tool Availability` table contents.
    - Do NOT modify `## Working Style`.
    - Do NOT touch `~/.claude/CLAUDE.md` (the user's user-global file).

    After insertion, the CLAUDE.md section sequence reads:
    1. `# cflt-ai — Claude Code Instructions`
    2. `## For the Team`
    3. `## Confluent Canon — Always-On Rules` (with sub-sections 1–5)
    4. `## Upstream Confluent Skills (streaming-skills-plugin)` ← NEW
    5. `## MCP Tool Availability`
    6. `## Working Style`
  </action>
  <acceptance_criteria>
    - `grep -c "^## Upstream Confluent Skills (streaming-skills-plugin)$" CLAUDE.md` returns exactly 1.
    - `grep -c "wiki/patterns/fsi-canon-overlay-for-confluent-skills.md" CLAUDE.md` returns ≥ 1.
    - `grep -c "kafka-streams-programming" CLAUDE.md` returns ≥ 1.
    - `grep -c "developing-kafka-python-client" CLAUDE.md` returns ≥ 1.
    - `grep -c "kafka-schema-registry" CLAUDE.md` returns ≥ 1.
    - `grep -c "confluent-cloud-cdc-tableflow" CLAUDE.md` returns ≥ 1.
    - In CLAUDE.md, the line number of `## Upstream Confluent Skills (streaming-skills-plugin)` is GREATER than the line number of `### 5. Competitive Context (Active as of 2026)` AND LESS than the line number of `## MCP Tool Availability` (verify ordering with `grep -n`).
    - `## Confluent Canon — Always-On Rules` still exists at exactly one location (`grep -c` returns 1).
    - `## MCP Tool Availability` still exists at exactly one location.
    - `## Working Style` still exists at exactly one location.
    - The 5 Confluent Canon sub-sections (`### 1.` through `### 5.`) all still exist with byte-identical text to pre-change state — confirm with `diff <(git show HEAD:CLAUDE.md | sed -n '/^### 1\./,/^### 5\./p') <(sed -n '/^### 1\./,/^### 5\./p' CLAUDE.md)` returning no differences.
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 4: Update wiki/_index.md to list the new overlay article under the patterns section and update wiki/_graph.md to add ≥2 inbound edges</name>
  <files>
    - wiki/_index.md
    - wiki/_graph.md
  </files>
  <read_first>
    - wiki/_index.md (current — find the patterns/ section listing; understand the existing entry shape for sibling articles like fsi-governance-automation.md, fsi-exactly-once.md)
    - wiki/_graph.md (current — find the patterns/fsi-governance-automation.md and patterns/fsi-exactly-once.md blocks; understand inbound/outbound edge shape; identify highest-cross-reference patterns articles for inbound edge candidates)
    - wiki/patterns/fsi-canon-overlay-for-confluent-skills.md (the new article — for outbound edge generation: which articles does the new article reference?)
    - tools/wiki-lint.py (lint expectations — orphan rule requires ≥1 inbound edge; graph format must validate)
  </read_first>
  <action>
    **Sub-task 4a — `wiki/_index.md`:**
    Add a single line under the `## Patterns` section (or whichever heading lists patterns/ articles) for the new article. Insertion shape must match sibling entries — match the existing format byte-for-byte (e.g., if siblings are `- [Title](patterns/slug.md) — one-line description`, follow the same shape).

    Concrete entry (adapt format to match existing index entries):
    ```markdown
    - [FSI Canon Overlay for Confluent Agent Skills](patterns/fsi-canon-overlay-for-confluent-skills.md) — FSI overrides on top of streaming-skills-plugin upstream defaults; read on upstream-skill activation
    ```

    Insert alphabetically within the patterns/ section, OR at the end of the patterns/ list if entries are not alphabetized. Verify with the surrounding entries before committing to a position.

    **Sub-task 4b — `wiki/_graph.md`:**
    Add a new block for `patterns/fsi-canon-overlay-for-confluent-skills.md` listing inbound and outbound edges. Format must match existing blocks for `patterns/fsi-governance-automation.md` and `patterns/fsi-exactly-once.md`.

    Required inbound edges (≥ 2, target 2–3) — pick from these candidates based on which already has the highest cross-reference density in the existing graph:
    - `patterns/fsi-governance-automation.md` — closest semantic sibling (FSI operator patterns + canon enforcement)
    - `patterns/fsi-exactly-once.md` — both reference Producers / processing.guarantee canon
    - `concepts/fsi-data-streaming-platform.md` — top-level FSI concept article
    - `patterns/topic-naming.md` — both reference naming convention canon

    Pick 2 (target 3) candidates. For each chosen candidate, also add a matching outbound edge from the candidate's block pointing to the new article.

    Required outbound edges from the new article (read article body and graph-existing relationships):
    - `concepts/exactly-once-semantics.md` (referenced in kafka-streams + python-client sections)
    - `concepts/schema-evolution-strategies.md` (referenced in kafka-schema-registry section)
    - `concepts/flink-checkpointing.md` (referenced in confluent-cloud-cdc-tableflow section)
    - `patterns/topic-naming.md` (referenced in all 4 sections via naming-convention override)

    Block shape (mirror existing — verify against fsi-governance-automation.md block):
    ```markdown
    ### patterns/fsi-canon-overlay-for-confluent-skills.md

    **Inbound:**
    - patterns/<chosen-1>.md
    - patterns/<chosen-2>.md

    **Outbound:**
    - concepts/exactly-once-semantics.md
    - concepts/schema-evolution-strategies.md
    - concepts/flink-checkpointing.md
    - patterns/topic-naming.md
    ```

    For each chosen inbound-edge source, edit that source's block in `_graph.md` to add `patterns/fsi-canon-overlay-for-confluent-skills.md` to its `**Outbound:**` list (so the edge is bidirectional, matching H.1's 3-inbound discipline).
  </action>
  <acceptance_criteria>
    - `grep -c "fsi-canon-overlay-for-confluent-skills" wiki/_index.md` returns ≥ 1.
    - `grep -c "patterns/fsi-canon-overlay-for-confluent-skills.md" wiki/_index.md` returns ≥ 1.
    - `grep -c "### patterns/fsi-canon-overlay-for-confluent-skills.md" wiki/_graph.md` returns exactly 1.
    - In the new `_graph.md` block for the article, `**Inbound:**` list has ≥ 2 entries (count lines starting with `- ` between `**Inbound:**` and `**Outbound:**`).
    - In the new block, `**Outbound:**` list has ≥ 4 entries.
    - For each inbound-edge source listed, that source's `**Outbound:**` list now includes `patterns/fsi-canon-overlay-for-confluent-skills.md` (verify with `grep -A 20 "### patterns/<source>.md" wiki/_graph.md | grep "fsi-canon-overlay"`).
    - `python3 tools/wiki-lint.py` exits 0 — no new orphans, no broken outbound edges (every outbound target must exist as a wiki article).
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 5: Run /wiki:validate equivalent — invoke tools/wiki-lint.py + manual MCP cross-check pass for the new article; record results in a phase summary</name>
  <files>
    - .planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-SUMMARY.md
  </files>
  <read_first>
    - wiki/patterns/fsi-canon-overlay-for-confluent-skills.md (the article being validated)
    - tools/wiki-lint.py (lint runner — confirm it covers frontmatter, links, decay, orphan, and the H.1-03 vendor-drift check)
    - .claude/commands/wiki/validate.md (the /wiki:validate skill spec — confirm what validation steps are required)
    - .planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-VERIFY-INSTALL.md (so every override row's upstream-default citation can be re-confirmed)
  </read_first>
  <action>
    Perform the H.3a CONTEXT D-11 phase-exit validation gate. Two-part check:

    **Part A — Structural / lint validation (mechanical):**
    1. Run `python3 tools/wiki-lint.py` and capture full output. Expected: exit code 0; new article appears in the "validated articles" count with no orphan / decay / broken-link findings. Drift findings (from H.1-03's `check_vendor_drift`) are non-fatal per H.1 D-09 — log them but don't block.
    2. Run `python3 -c "import yaml; print(yaml.safe_load(open('wiki/patterns/fsi-canon-overlay-for-confluent-skills.md').read().split('---')[1]))"` to confirm frontmatter parses.
    3. Grep the article for every `CLAUDE.md §<section>` citation and confirm each cited section name actually exists in CLAUDE.md (`grep -F "<section name>" CLAUDE.md` returns ≥ 1 hit for each).

    **Part B — MCP drift cross-check (per CONTEXT D-11):**
    For each override row in each of the 4 sections, cross-check the override against `confluent-docs` and/or `context7` MCP sources. Three outcomes per row:
    - **CONFIRMED**: MCP source independently agrees with the override value. Pass.
    - **DRIFT**: MCP source says something different. Correction required — either fix the override row (if MCP is right) or add an `⚠️ unverified` marker (if MCP coverage is thin or the upstream is documented stale).
    - **NO COVERAGE**: MCP has no data on this override. Add `⚠️ unverified` marker per H.1 trip-wires #7–9 pattern.

    For any DRIFT outcomes: edit `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` to correct the override row OR add the `⚠️ unverified` marker, then re-run Part A to confirm the article still lints clean.

    Write `.planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-SUMMARY.md` capturing:
    - **Install verification**: `streaming-skills-plugin@1.0.0` at SHA `91d1871e`, scope `project`, install timestamp.
    - **Article creation**: `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` — N sections, M override rows (total across all tables), frontmatter shape.
    - **CLAUDE.md hook**: section inserted at line X (post-Canon, pre-MCP), Y lines added.
    - **Wiki graph**: K inbound edges, J outbound edges; lint clean.
    - **MCP validation results**: per-section CONFIRMED / DRIFT / NO-COVERAGE counts; total `⚠️ unverified` markers added.
    - **Requirements addressed**: INST-01 (partial — pin/drift-gate in H.3b), CAN-OVR-01 (complete).
    - **ROADMAP success-criteria status**: 4/4 ✓ (with explicit note: criterion #1 install state is verified, not installed-by-this-plan since plugin was already at the H.1 SHA).
    - **Deferred to H.3b**: pin file (`tools/vendor-plugins.json`), `--check` mode, CI workflow (`.github/workflows/streaming-skills-drift.yml`).
    - **Deferred to future phases**: per-customer overlays (H.4c-adjacent), auto-generated overlay sections (`tools/generate-canon-overlay.py`), overlay evals via H.2 harness.
  </action>
  <acceptance_criteria>
    - `.planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-01-SUMMARY.md` exists.
    - File contains the literal string `INST-01` and the literal string `CAN-OVR-01`.
    - File contains the literal string `streaming-skills-plugin@1.0.0` AND `91d1871e`.
    - File contains a "MCP validation results" section.
    - File ends with a "Deferred to H.3b" subsection naming the pin file and CI workflow.
    - `python3 tools/wiki-lint.py` exits 0 after any DRIFT-driven article corrections.
    - The final article passes the frontmatter YAML parse test from Part A step 2.
  </acceptance_criteria>
</task>

</tasks>

<verification>
After all tasks complete, verify the phase exit gate:

1. **Install verification** — `jq '.plugins["streaming-skills-plugin@confluent-agent-skills"][0].gitCommitSha' ~/.claude/plugins/installed_plugins.json` returns `"91d1871ef8c320be92bca955c8e42492a2778cb4"`.
2. **Article exists and lints** — `wiki/patterns/fsi-canon-overlay-for-confluent-skills.md` exists; `python3 tools/wiki-lint.py` exits 0; frontmatter parses as valid YAML.
3. **CLAUDE.md hook present** — `grep "## Upstream Confluent Skills (streaming-skills-plugin)" CLAUDE.md` returns the heading; the line number is between the Canon and MCP Tool Availability section headings.
4. **Wiki graph integration** — new article has ≥ 2 inbound edges in `_graph.md`; `wiki-lint.py` does not report orphan.
5. **Requirements coverage** — INST-01 install half satisfied (pin/CI deferred to H.3b explicitly); CAN-OVR-01 fully satisfied.
6. **No spillover** — `git status` shows ONLY the four `files_modified` paths plus the two `.planning/phases/H.3a-.../H.3a-01-VERIFY-INSTALL.md` and `H.3a-01-SUMMARY.md` scratch files. No `tools/`, no `tests/`, no `.github/workflows/`.

All 6 must pass before the phase is considered done. Any failure → re-route to gap closure (do not skip).
</verification>
