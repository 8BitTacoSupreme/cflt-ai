# Phase 0: Foundation - Research

**Researched:** 2026-04-28
**Domain:** Python tooling hygiene, YAML contract design, GitHub Actions CI, Flox environment management, Canon overlay scaffolding
**Confidence:** HIGH (all findings from direct codebase inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None — pure infrastructure phase. All implementation choices are at Claude's discretion.

### Claude's Discretion
All implementation choices are at Claude's discretion — use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — infrastructure phase.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HYG-01 | wiki-stats.py syntax errors fixed and tool runs without crashes | Bug identified: Unicode em-dash U+2500 on lines 57, 59, 75 — replace with `"-" * 50` |
| HYG-02 | wiki-lint.py broken-link regex correctly matches all wiki-internal link formats including anchors | Bug identified: line 81 regex misses fragment identifiers — extend to `(wiki/[^)#]+(?:#[^)]*)?)`  |
| HYG-03 | evaluate.md literal-ellipsis paths resolved to real file references | Ellipsis on lines 21-22: real paths are `reference/java-producer/src/main/java/org/fsi/kafka/producer/FsiProducer.java` and `reference/java-consumer/src/main/java/org/fsi/kafka/consumer/FsiConsumer.java` |
| HYG-04 | Flox manifest committed in cflt-ai and works on clean clone | Manifest exists at `.flox/env/manifest.toml` — needs verification it handles `pyyaml` dep correctly |
| HYG-05 | Flox manifest committed in fsi-kafka-platform and works on clean clone | No `.flox/` directory exists in `raw/repos/fsi-dsp/` — must be created |
| CNTR-01 | MANIFEST.yaml v1 published with capabilities blocks for every existing fsi-dsp asset | No MANIFEST.yaml exists in fsi-dsp — must be authored from scratch covering 9 roles, 2 modules, 6 scenarios, 8 ADRs, 10 reference implementations, 7 scripts, 5 observability configs |
| CNTR-02 | Wiki citations migrated from prose references to MANIFEST.yaml ID form | 10 wiki articles have `sources:` frontmatter citing raw file paths — migrate to `fsi-dsp://{id}` form |
| CNTR-03 | CI parity checks green in both repos (cflt-ai and fsi-kafka-platform) | cflt-ai has wiki-lint.yml; fsi-dsp has ansible-ci.yml — new manifest-parity workflows needed in both |
| CNTR-04 | fsi-dsp blocks PRs that drop a stable ID without a major bump | New GitHub Actions workflow needed in fsi-dsp: check `MANIFEST.yaml` ID set never shrinks |
| CNTR-05 | cflt-ai blocks PRs where any wiki citation fails to resolve against MANIFEST.yaml | New GitHub Actions workflow needed in cflt-ai: parse wiki `sources:` frontmatter, resolve against MANIFEST.yaml |
| CANST-01 | Canon overlay stack scaffolding present (base → industry → customer → engagement layers) | No overlay directory structure exists — must scaffold `canon/base/`, `canon/industry/fsi/`, `canon/customer/`, `canon/engagement/` |
| CANST-02 | Each overlay layer can override defaults from the layer above | Override resolution logic must be defined (composition by merge, not inheritance by fork) |
| CANST-03 | Every override is an ADR in the layer that introduces it | ADR template from fsi-dsp `docs/adr/000-template.md` is the model — copy or reference it in each overlay layer |
| CANST-04 | Active stack recorded in artifact provenance footers | A `canon-stack.yaml` or equivalent in each overlay directory should record which ADRs are active |
| WIKI-01 | LinuxONE wiki articles ingested from fsi-dsp adr/009 and LinuxONE guides | ADR-009 does not yet exist in fsi-dsp — it must be authored as part of this phase; then compiled into wiki article(s) |
| WIKI-02 | Activity log directory live and emitting per overlay-scoped path | `wiki/activity/` directory does not exist; needs creation with a 2026-04.md seed file and emit-on-run pattern |
</phase_requirements>

---

## Summary

Phase 0 is a pure infrastructure and scaffolding phase — no new features, all foundation-laying. The work splits into five distinct tracks: (1) fix three known Python tool bugs so the wiki CLI actually runs, (2) create MANIFEST.yaml v1 in fsi-dsp and wire both repos' CI to enforce ID stability and citation resolution, (3) scaffold the four-layer canon overlay directory structure with composition semantics, (4) author ADR-009 (LinuxONE) in fsi-dsp and compile it into wiki articles, and (5) create the activity log infrastructure.

All bugs are already precisely diagnosed in `.planning/codebase/CONCERNS.md`. The MANIFEST.yaml schema must cover every existing asset in fsi-dsp (9 Ansible roles, 2 Terraform modules, 6 scenarios, 8 ADRs, 10 reference implementations, 7 operational scripts, 5 observability configs). The canon overlay stack has no existing code — it must be scaffolded from first principles, with `CLAUDE.md` serving as the base layer and fsi-dsp ADRs as the industry layer's opinionated defaults. The Flox manifest for cflt-ai is already present and functional; fsi-dsp needs one created from scratch.

CI for citation resolution (CNTR-04, CNTR-05) requires two new GitHub Actions workflows: one in fsi-dsp that diffs MANIFEST.yaml ID sets on PRs, and one in cflt-ai that parses wiki article frontmatter `sources:` fields and resolves each against MANIFEST.yaml. Both must block merge on failure.

**Primary recommendation:** Execute the five tracks in dependency order — bugs first (unblocks tooling confidence), then MANIFEST.yaml (unblocks citation migration and CI), then canon overlay structure (unblocks CANST requirements), then ADR-009 + wiki ingest (unblocks WIKI-01), then activity log (straightforward directory creation).

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python 3 | 3.9+ (system), 3.11 in CI | wiki tool scripts | Existing codebase language |
| pyyaml | >=6.0 | YAML frontmatter parsing in wiki tools | Already in `requirements.txt`, used by wiki-lint.py, wiki-stats.py |
| pytest | 7.x (CI pinned) | Test validation of MANIFEST.yaml and CI scripts | Already in fsi-dsp CI (`pip install pytest pyyaml`) |
| GitHub Actions | current | CI enforcement for CNTR-04 and CNTR-05 | Existing CI platform in both repos |
| Flox | 1.11.x | Reproducible dev environments | Already adopted; cflt-ai has manifest.toml |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uv | bundled in Flox | Fast Python venv + pip | Used in cflt-ai Flox `on-activate` hook |
| re (stdlib) | Python stdlib | Regex fixes in wiki-lint.py | Fixing HYG-02 |
| pathlib (stdlib) | Python stdlib | Path operations in wiki tools | Already in wiki-stats.py, wiki-lint.py |
| yaml (pyyaml) | >=6.0 | MANIFEST.yaml parsing in CI scripts | CNTR-04, CNTR-05 validation scripts |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| YAML for MANIFEST.yaml | JSON or TOML | YAML is already the dominant format in fsi-dsp (`sla_tiers.yml`, `naming_rules.yml`, `ansible/vars/`); TOML or JSON would be inconsistent |
| GitHub Actions for CI | Pre-commit hooks | CI is already the enforcement model; pre-commit is local-only and doesn't block PRs |
| Flat overlay files | Nested directory hierarchy | Directories naturally express the composition chain and are navigable; flat files would require a custom merge resolver |

**Installation:**
```bash
# cflt-ai Python deps (via flox activate)
uv pip install pyyaml pytest

# fsi-dsp (new Flox manifest)
flox init
# then add python3, uv, git, pytest
```

---

## Architecture Patterns

### Canon Overlay Directory Structure

```
cflt-ai/
├── canon/
│   ├── base/                    # GoodLabs defaults (sourced from CLAUDE.md)
│   │   ├── README.md            # What the base layer governs
│   │   └── defaults.yaml        # Extracted canonical defaults
│   ├── industry/
│   │   └── fsi/                 # FSI-specific overrides
│   │       ├── README.md
│   │       ├── overrides.yaml   # Which base defaults are overridden
│   │       └── adrs/            # ADRs from fsi-dsp that govern this layer
│   ├── customer/                # Customer-specific overrides (empty scaffold)
│   │   ├── README.md
│   │   └── .gitkeep
│   └── engagement/              # Engagement-specific overrides (empty scaffold)
│       ├── README.md
│       └── .gitkeep
```

### MANIFEST.yaml v1 Schema

The MANIFEST.yaml lives at the root of `fsi-dsp` (i.e., `raw/repos/fsi-dsp/MANIFEST.yaml`). Each capability block must have a stable `id` that never changes without a major version bump.

**Schema:**
```yaml
# raw/repos/fsi-dsp/MANIFEST.yaml
version: "1.0.0"
schema: "fsi-dsp/manifest/v1"

capabilities:
  # Ansible roles
  - id: "role/cp_topic"
    type: ansible-role
    name: "cp_topic"
    path: "ansible/roles/cp_topic"
    description: "Create and manage governed Kafka topics on Confluent Platform"

  # Terraform modules
  - id: "module/topic"
    type: terraform-module
    name: "topic"
    path: "modules/topic"
    description: "Single-call governed topic: topic + schema + RBAC + DR mirror"

  # Scenarios
  - id: "scenario/cc-aws"
    type: scenario
    name: "cc-aws"
    path: "scenarios/cc-aws"
    description: "Confluent Cloud on AWS starter kit"

  # ADRs
  - id: "adr/001"
    type: adr
    name: "Avro over Protobuf"
    path: "docs/adr/001-avro-over-protobuf.md"
    status: accepted

  # Reference implementations
  - id: "reference/java-producer"
    type: reference
    name: "Java Producer"
    path: "reference/java-producer"
    description: "FSI-ready Java producer with idempotency, Avro, DLQ"

  # Scripts
  - id: "script/mirror-failover"
    type: script
    name: "mirror-failover.sh"
    path: "scripts/mirror-failover.sh"
    description: "DR failover via Cluster Linking"
```

### Wiki Citation ID Form (CNTR-02)

Before (prose path):
```yaml
# wiki/patterns/dr-cluster-linking.md frontmatter
sources: [raw/repos/fsi-dsp/docs/dr-runbook.md]
```

After (MANIFEST.yaml ID form):
```yaml
sources:
  - fsi-dsp://adr/005
  - fsi-dsp://script/mirror-failover
```

### CI Parity Checks

**CNTR-04 — fsi-dsp: block ID removal (new workflow: `.github/workflows/manifest-stability.yml`)**
```yaml
name: Manifest Stability
on:
  pull_request:
    paths: ['MANIFEST.yaml']
jobs:
  check-id-stability:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Check no stable ID was removed
        run: python scripts/check-manifest-stability.py
```

The `check-manifest-stability.py` script diffs `MANIFEST.yaml` ID sets between base and head commits. A stable ID that disappears (without a major version bump) fails the check.

**CNTR-05 — cflt-ai: block unresolvable citations (new workflow: `.github/workflows/manifest-citations.yml`)**
```yaml
name: Manifest Citations
on:
  pull_request:
    paths: ['wiki/**', 'raw/repos/fsi-dsp/MANIFEST.yaml']
jobs:
  check-citations:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { submodules: true }
      - name: Resolve wiki citations against MANIFEST.yaml
        run: python tools/check-citations.py
```

### Activity Log Pattern

```
wiki/activity/
└── 2026-04.md       # Append-only log; created when activity first occurs

# 2026-04.md entry format:
## 2026-04-28T10:30:00Z
**Skill:** /wiki:ingest
**Overlay:** base
**Input:** raw/repos/fsi-dsp/docs/adr/009-linuxone.md
**Output:** wiki/concepts/linuxone-kafka-integration.md
**Canon stack:** base + fsi
```

The `wiki/activity/` directory must exist with a `README.md` and a `.gitkeep` or seed file. Overlay-scoped logging means: the path embeds which overlay layer was active during invocation, or the log entry records it in the `Overlay:` field.

### Pattern: ADR-Backed Override

Every override introduced in the canon overlay stack must be an ADR in the layer's `adrs/` directory. The ADR template from fsi-dsp's `docs/adr/000-template.md` is the canonical format:

```markdown
# ADR-NNN: [Title]
**Status:** Proposed | Accepted | Deprecated | Superseded
**Date:** YYYY-MM-DD
**Author:** [Name]

## Context
## Decision
## Consequences
```

For the canon overlay scaffolding (CANST-03), the very act of deciding to override a base default is documented via an ADR placed in the layer that introduces the override. No override without an ADR; this is the trust mechanism.

### Anti-Patterns to Avoid

- **Hard-coding paths in evaluate.md**: Use real paths from file system, not `...` ellipsis. The evaluate.md currently has `raw/repos/fsi-dsp/reference/java-producer/.../FsiProducer.java` — the real path is `raw/repos/fsi-dsp/reference/java-producer/src/main/java/org/fsi/kafka/producer/FsiProducer.java`.
- **Using `─` (U+2500) directly in Python f-strings without enclosure**: Python parser treats `─*50` as invalid syntax. Use `"-" * 50` or `print("─" * 50)` with a proper string literal.
- **Regex that doesn't account for fragment identifiers**: `wiki/[^)]+` stops at `)` but so does `wiki/path.md#anchor` — without explicit anchor handling, anchored links are double-checked and may produce false positives or false negatives.
- **MANIFEST.yaml IDs that include version suffixes**: IDs like `role/cp_topic_v2` break the contract. The ID is stable; version is tracked via the `version` field at MANIFEST root.
- **Inheritance-based canon overrides**: Overrides should compose (layer N's override.yaml merges onto layer N-1's defaults) rather than replace. A customer fork that replaces the entire base defaults breaks the audit trail.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing for MANIFEST.yaml | Custom text parser | `pyyaml` | Already a dependency; handles anchors, multi-doc, indentation edge cases |
| CI diff of YAML ID sets | Bash `diff` | Python script with `yaml.safe_load` + set operations | Git diff output is unreliable for YAML key ordering; Python set diff is deterministic |
| Wiki frontmatter extraction | Hand-rolled `---` splitter | Existing `parse_frontmatter()` in wiki-lint.py | Already correct and handles `yaml.safe_load`; reuse for check-citations.py |
| Overlay merge resolution | Custom DSL | Python `dict.update()` with explicit merge order | Complexity is in the order, not the mechanics; deep merge via `deepmerge` library if needed |
| Activity log timestamps | Custom format | ISO 8601 (`datetime.utcnow().isoformat() + "Z"`) | Sortable, standard, unambiguous in any timezone context |

**Key insight:** This phase is scaffolding, not product code. Prefer copy-paste of existing patterns (e.g., parse_frontmatter from wiki-lint.py) into new utility scripts over new abstractions.

---

## Runtime State Inventory

> This is a greenfield scaffolding phase. No rename/refactor is involved. No runtime state is affected.

**Nothing found in any category.** Verified by direct codebase inspection:
- Stored data: None — no databases, no Mem0, no ChromaDB in scope
- Live service config: None — no n8n, no Datadog, no external service config being renamed
- OS-registered state: None — no cron jobs, no pm2, no launchd plists
- Secrets/env vars: None — no key names changing; `CFLT_WIKI_ROOT` and Flox vars are additive, not renamed
- Build artifacts: None — no compiled artifacts affected by this phase

---

## Common Pitfalls

### Pitfall 1: Flox manifest for fsi-dsp must target the right systems array
**What goes wrong:** New Flox manifest created for fsi-dsp uses `aarch64-darwin` only, then CI fails on `x86_64-linux` (GitHub Actions runners).
**Why it happens:** `flox init` defaults to current host architecture.
**How to avoid:** Copy the `[options] systems = [...]` block from cflt-ai's manifest.toml which already covers `["aarch64-darwin", "x86_64-darwin", "x86_64-linux", "aarch64-linux"]`.
**Warning signs:** `flox activate` succeeds locally but CI errors with `unsupported system`.

### Pitfall 2: MANIFEST.yaml `id` field collisions across asset types
**What goes wrong:** `role/cp_topic` and a future Terraform resource called `cp_topic` get the same ID path prefix, causing ambiguous resolution.
**Why it happens:** ID scheme not typed upfront.
**How to avoid:** The `id` field must include the type prefix: `role/cp_topic`, `module/topic`, `scenario/cc-aws`, `adr/001`, `reference/java-producer`, `script/mirror-failover`, `observability/datadog`. Type is embedded in the ID, not just the `type` field.
**Warning signs:** `check-citations.py` returns ambiguous match for a citation.

### Pitfall 3: Wiki citation migration breaks `_index.md` and `_graph.md` cross-references
**What goes wrong:** Migrating `sources:` frontmatter in 10 articles from raw paths to `fsi-dsp://` IDs, but `_index.md` and `_graph.md` still reference the old path-based source format. Lint then flags orphan links.
**Why it happens:** Frontmatter migration happens in isolation without updating the index.
**How to avoid:** After migrating all 10 articles, run `python tools/wiki-lint.py --full` to verify no new broken links. Also grep for any raw `fsi-dsp/docs/` references in `_graph.md`.
**Warning signs:** `wiki-lint --full` reports new orphaned articles after citation migration.

### Pitfall 4: check-manifest-stability.py cannot diff against base branch if submodule is detached
**What goes wrong:** `git diff origin/main...HEAD -- MANIFEST.yaml` works in fsi-dsp's own CI, but the script can't easily compare against base when fsi-dsp is consumed as a submodule in cflt-ai.
**Why it happens:** Submodule checked out at specific commit SHA, not on a branch.
**How to avoid:** The stability check workflow lives in fsi-dsp's own `.github/workflows/`, not in cflt-ai's CI. It runs on PRs to fsi-dsp's own main branch. cflt-ai's CI (CNTR-05) only resolves citations — it does not check ID stability.
**Warning signs:** CI workflow uses `git submodule` commands where they aren't needed.

### Pitfall 5: Canon overlay `defaults.yaml` diverges from CLAUDE.md within one edit cycle
**What goes wrong:** Developer updates CLAUDE.md canonical defaults but forgets to update `canon/base/defaults.yaml`, causing the two sources of truth to drift.
**Why it happens:** No automated sync between CLAUDE.md (the human-readable canon) and defaults.yaml (the machine-readable overlay base).
**How to avoid:** In Phase 0, `canon/base/defaults.yaml` should explicitly state it is extracted from CLAUDE.md, with a comment citing the section. Full sync automation is Phase 1+ work. For Phase 0, keep the defaults.yaml minimal (topic design, producer, consumer, Flink defaults) and note the canonical source.
**Warning signs:** A PR changes CLAUDE.md but not `canon/base/defaults.yaml`.

### Pitfall 6: ADR-009 (LinuxONE) must exist before WIKI-01 compilation
**What goes wrong:** WIKI-01 requires ingesting content from "fsi-dsp adr/009" but that ADR does not yet exist in `raw/repos/fsi-dsp/docs/adr/`. If wiki ingest runs first, it fails with a missing source.
**Why it happens:** ADR-009 needs to be authored as part of this phase.
**How to avoid:** Author ADR-009 in fsi-dsp first, register it in MANIFEST.yaml, then run the wiki ingest. The dependency order within Phase 0 plans must encode this.
**Warning signs:** WIKI-01 task runs before CNTR-01 (MANIFEST.yaml creation) is complete.

---

## Code Examples

### HYG-01: Fix wiki-stats.py Unicode syntax error

```python
# Before (broken): uses Unicode box-drawing character directly in expression
print(f"\n{─*50}")  # SyntaxError: invalid character '─' (U+2500)

# After (fixed): use ASCII hyphen string multiplication
print(f"\n{'-' * 50}")
print(f"  cflt-ai wiki stats")
print(f"{'-' * 50}")
```

Lines 57, 59, 75 in `tools/wiki-stats.py` — replace `{─*50}` with `{'-' * 50}`.

### HYG-02: Fix wiki-lint.py broken-link regex

```python
# Before (broken): stops at ')' but doesn't handle anchors
links = re.findall(r"\[.*?\]\((wiki/[^)]+)\)", content)

# After (fixed): capture optional fragment identifier
links = re.findall(r"\[.*?\]\((wiki/[^)#]+(?:#[^)]*)?)\)", content)
```

Line 81 in `tools/wiki-lint.py`.

### HYG-03: Fix evaluate.md ellipsis paths

```markdown
<!-- Before (broken) -->
   - `raw/repos/fsi-dsp/reference/java-producer/.../FsiProducer.java`
   - `raw/repos/fsi-dsp/reference/java-consumer/.../FsiConsumer.java`

<!-- After (fixed) -->
   - `raw/repos/fsi-dsp/reference/java-producer/src/main/java/org/fsi/kafka/producer/FsiProducer.java`
   - `raw/repos/fsi-dsp/reference/java-consumer/src/main/java/org/fsi/kafka/consumer/FsiConsumer.java`
```

Lines 21-22 in `.claude/commands/wiki/evaluate.md`.

### CNTR-01: MANIFEST.yaml full asset inventory

**All fsi-dsp assets to enumerate:**

Ansible roles (9): `cp_topic`, `cp_schema`, `cp_rbac`, `cp_connect`, `cp_dr_mm2`, `cp_dr_mrc`, `cp_observability`, `cfk_operator`, `cfk_topic`

Terraform modules (2): `topic`, `flink`

Scenarios (6): `cc-aws`, `cc-azure`, `cc-gcp`, `cfk-openshift`, `cp-rhel`, `private-cloud`

ADRs (8): `001` through `008` (009 to be authored)

Reference implementations (10): `java-producer`, `java-consumer`, `dotnet-producer`, `dotnet-consumer`, `python-producer`, `python-consumer`, `flink-sql`, `connect-configs`, `integration-test`, `local-dev`

Scripts (7): `mirror-failover.sh`, `mirror-failback.sh`, `fsi-dr.sh`, `consul-flip-region.sh`, `connect-pause-all.sh`, `validate-apply.sh`, `validate-fips.sh`

Observability (5): `datadog`, `dynatrace`, `grafana`, `instana`, `newrelic`, `splunk` (6 subdirs under `observability/` — also `metrics-mapping.md`)

Schemas (1): `examples/` directory

Environments (1): `prod/`

### CNTR-05: check-citations.py pattern

```python
# tools/check-citations.py
from pathlib import Path
import yaml
import sys

def load_manifest(manifest_path: Path) -> set:
    """Return set of all stable IDs from MANIFEST.yaml."""
    data = yaml.safe_load(manifest_path.read_text())
    return {cap["id"] for cap in data.get("capabilities", [])}

def parse_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(content[3:end]) or {}
    except Exception:
        return {}

def main():
    root = Path(__file__).resolve().parent.parent
    manifest = root / "raw" / "repos" / "fsi-dsp" / "MANIFEST.yaml"
    if not manifest.exists():
        print("ERROR: MANIFEST.yaml not found at expected path", file=sys.stderr)
        sys.exit(1)

    known_ids = load_manifest(manifest)
    failures = []

    for md in sorted((root / "wiki").rglob("*.md")):
        if md.name.startswith("_"):
            continue
        fm = parse_frontmatter(md.read_text(errors="replace"))
        for source in fm.get("sources", []):
            if isinstance(source, str) and source.startswith("fsi-dsp://"):
                cited_id = source[len("fsi-dsp://"):]
                if cited_id not in known_ids:
                    failures.append(f"{md.relative_to(root)}: unresolvable citation '{source}'")

    if failures:
        print(f"Citation resolution failures ({len(failures)}):")
        for f in failures:
            print(f"  {f}")
        sys.exit(1)
    print(f"All citations resolved ({len(known_ids)} IDs in MANIFEST.yaml).")

if __name__ == "__main__":
    main()
```

### WIKI-02: Activity log seed structure

```markdown
<!-- wiki/activity/README.md -->
# Activity Log

Append-only audit trail of skill invocations.
One file per calendar month: `YYYY-MM.md`.
Each entry records: skill invoked, overlay active, inputs, outputs, timestamp.

Never edit entries retroactively. Archive (do not delete) files older than 12 months.

## Entry Format
```markdown
## YYYY-MM-DDTHH:MM:SSZ
**Skill:** /{skill-name}
**Overlay:** {base | fsi | customer/{name} | engagement/{name}}
**Input:** {path or description}
**Output:** {path or "none"}
**Canon stack:** {layers active, e.g., "base + fsi"}
```
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Prose source paths in wiki frontmatter | MANIFEST.yaml ID citations (`fsi-dsp://role/cp_topic`) | Phase 0 introduces | Citations are stable across fsi-dsp refactors |
| No MANIFEST.yaml | MANIFEST.yaml v1 in fsi-dsp root | Phase 0 introduces | Stable contract between repos; CI can enforce it |
| No canon overlay structure | `canon/base` → `canon/industry/fsi` → `canon/customer` → `canon/engagement` | Phase 0 scaffolds | Customers can fork and override without touching base |
| `wiki/activity/` doesn't exist | `wiki/activity/YYYY-MM.md` append-only logs | Phase 0 creates | Immutable audit trail per overlay |

**Deprecated/outdated:**
- Direct `raw/repos/fsi-dsp/...` paths in wiki `sources:` frontmatter: replaced by `fsi-dsp://` ID references after CNTR-02 migration.

---

## Open Questions

1. **LinuxONE ADR-009 content scope**
   - What we know: WIKI-01 says "ingest from fsi-dsp adr/009 and LinuxONE guides"; ADR-009 does not yet exist
   - What's unclear: What specific IBM LinuxONE content should ADR-009 cover? The CLAUDE.md mentions "IBM MQ Source Connector → Kafka as canonical bridge pattern; IBM LinuxONE preferred compute for z/OS offload" — this is the likely subject
   - Recommendation: Author ADR-009 scoped to: LinuxONE as preferred compute for z/OS Kafka offload, IBM MQ Source Connector bridge pattern, LinuxONE FIPS compliance posture. Keep it narrow for Phase 0; wiki article can be expanded in Phase 1.

2. **Canon overlay: how thin is "thin"?**
   - What we know: `canon/base/defaults.yaml` should extract from CLAUDE.md; `canon/industry/fsi/overrides.yaml` should reference fsi-dsp ADRs
   - What's unclear: Whether the base layer's `defaults.yaml` should be a machine-readable extract of CLAUDE.md defaults or just a `README.md` that points to CLAUDE.md
   - Recommendation: For Phase 0, make it machine-readable YAML (enables CI validation later). Extract the key-value defaults (partition formula, replication factor, acks, compression, etc.) from CLAUDE.md into `defaults.yaml` with comments citing CLAUDE.md section headers.

3. **fsi-dsp Flox manifest Python version**
   - What we know: fsi-dsp uses Python 3.11 in its CI (`actions/setup-python@v5` with `python-version: '3.11'`)
   - What's unclear: Whether the fsi-dsp Flox manifest should pin 3.11 or use `python3` (resolved by Flox to current nixpkgs stable)
   - Recommendation: Use `python311.pkg-path = "python311"` explicitly to match CI. Add `pytest.pkg-path = "python311Packages.pytest"` if pytest is needed in the Flox environment.

4. **Fsi-dsp submodule write access for MANIFEST.yaml**
   - What we know: `raw/repos/fsi-dsp` is a git submodule pointing to `git@github.com:goodlabs-studio/fsi-dsp.git`
   - What's unclear: Whether the planner should assume write access to the fsi-dsp repo, or only to cflt-ai
   - Recommendation: MANIFEST.yaml and ADR-009 must be created inside `raw/repos/fsi-dsp/` and committed to the fsi-dsp repo. Plans should include a separate commit step for fsi-dsp. The cflt-ai CI then pins the submodule to the new commit containing MANIFEST.yaml.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | wiki tool scripts, CI scripts | Yes | 3.9.6 (system) | — |
| pyyaml | wiki-stats.py, wiki-lint.py, check-citations.py | Yes (via flox activate) | 6.x | pip install pyyaml |
| Flox | HYG-04, HYG-05 | Yes | 1.11.2 | — |
| GitHub Actions | CNTR-03, CNTR-04, CNTR-05 | Yes (both repos have .github/workflows/) | current | — |
| pytest | CNTR-04 stability script | Yes (fsi-dsp CI already uses it) | pinned by CI | pip install pytest |
| git submodule write access (fsi-dsp) | CNTR-01, HYG-05, WIKI-01 | Presumed (submodule initialized) | — | Manual creation in local checkout |

**Missing dependencies with no fallback:**
- None identified.

**Missing dependencies with fallback:**
- Flox FloxHub token expired (`flox auth login` needed for `flox push`/`flox pull`). For Phase 0 local work, `flox activate` still functions. CI uses `flox activate` without requiring FloxHub auth for the manifest itself.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already in fsi-dsp CI; adding to cflt-ai) |
| Config file | none — pytest defaults apply; Wave 0 adds `tests/conftest.py` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HYG-01 | wiki-stats.py runs without SyntaxError | smoke | `python tools/wiki-stats.py` (exit 0) | No — Wave 0 |
| HYG-02 | wiki-lint.py detects anchored links | unit | `pytest tests/test_wiki_lint.py::test_anchor_links -x` | No — Wave 0 |
| HYG-03 | evaluate.md has no ellipsis paths | unit | `pytest tests/test_evaluate_paths.py -x` | No — Wave 0 |
| HYG-04 | cflt-ai flox activate succeeds | smoke | `flox activate -- python3 -c "import yaml; print('OK')"` | No — manual |
| HYG-05 | fsi-dsp flox activate succeeds | smoke | `flox activate -- python3 -c "print('OK')"` in fsi-dsp | No — Wave 0 |
| CNTR-01 | MANIFEST.yaml covers all assets | unit | `pytest tests/test_manifest.py::test_all_assets_present -x` | No — Wave 0 |
| CNTR-02 | No wiki article has raw fsi-dsp path in sources | unit | `pytest tests/test_wiki_citations.py::test_no_raw_paths -x` | No — Wave 0 |
| CNTR-04 | check-manifest-stability.py blocks ID removal | unit | `pytest tests/test_manifest_stability.py -x` in fsi-dsp | No — Wave 0 |
| CNTR-05 | check-citations.py resolves all wiki citations | integration | `python tools/check-citations.py` (exit 0) | No — Wave 0 |
| CANST-01 | Canon overlay directories exist with expected structure | unit | `pytest tests/test_canon_overlay.py::test_structure -x` | No — Wave 0 |
| WIKI-02 | wiki/activity/ directory exists | smoke | `python -c "from pathlib import Path; assert Path('wiki/activity').is_dir()"` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `python tools/wiki-stats.py && python tools/wiki-lint.py`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green + all five success criteria manually verified before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/__init__.py` — empty file to make tests/ a package
- [ ] `tests/conftest.py` — shared fixtures (wiki root path, manifest path)
- [ ] `tests/test_wiki_lint.py` — covers HYG-02 anchor regex fix
- [ ] `tests/test_wiki_stats.py` — covers HYG-01 (runs to completion)
- [ ] `tests/test_evaluate_paths.py` — covers HYG-03 (no ellipsis in evaluate.md)
- [ ] `tests/test_manifest.py` — covers CNTR-01 (all assets present in MANIFEST.yaml)
- [ ] `tests/test_wiki_citations.py` — covers CNTR-02 (no raw fsi-dsp paths remain)
- [ ] `tests/test_canon_overlay.py` — covers CANST-01 (directory structure exists)

---

## Project Constraints (from CLAUDE.md)

These directives from `CLAUDE.md` apply to all work in this phase:

- **Confluent Canon defaults**: Any `defaults.yaml` or `overrides.yaml` authored in the canon overlay must reflect the canonical defaults from CLAUDE.md (acks=all, replication factor 3, min.insync.replicas=2, compression=lz4, auto.commit disabled, etc.)
- **Avro/Protobuf in production**: Schema files added to fsi-dsp or wiki articles must not recommend JSON Schema for production use
- **MCP tools available**: `context7`, `confluent-docs`, `mcp-confluent` are all available for validation steps
- **No custom application server**: Claude Code is the runtime; no new services should be introduced in this phase
- **fsi-dsp linked as submodule**: Do not vendor fsi-dsp content into cflt-ai directly — always reference via submodule
- **MANIFEST.yaml is the contract**: New fsi-dsp citations in wiki articles must use `fsi-dsp://` ID form after CNTR-02 migration
- **Code style**: Python 4-space indentation, snake_case, docstrings with Args/Returns, constants UPPER_SNAKE_CASE
- **YAML style**: 2-space indentation, inline comments with `#` explaining *why*

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — all findings from reading actual files in `<repo-root>/` and `<repo-root>/raw/repos/fsi-dsp/`
- `tools/wiki-stats.py` — SyntaxError on line 1 confirmed by running `python3 tools/wiki-stats.py`
- `tools/wiki-lint.py` — lint output confirmed by running `python3 tools/wiki-lint.py --full`
- `.flox/env/manifest.toml` — Flox manifest confirmed present; `flox activate` runs successfully
- `.planning/codebase/CONCERNS.md` — Precise bug diagnosis already performed by codebase mapping

### Secondary (MEDIUM confidence)
- `.planning/codebase/STRUCTURE.md` — Asset inventory for MANIFEST.yaml scope derived from documented structure
- `.planning/REQUIREMENTS.md` — Requirements verbatim from project planning docs

### Tertiary (LOW confidence)
- None — all findings grounded in direct file inspection

---

## Metadata

**Confidence breakdown:**
- Bug fixes (HYG-01 through HYG-03): HIGH — bugs confirmed by direct execution and inspection
- Flox environment (HYG-04): HIGH — manifest.toml confirmed; `flox activate` tested
- Flox for fsi-dsp (HYG-05): HIGH — confirmed no `.flox/` exists; Flox 1.11.2 available
- MANIFEST.yaml schema (CNTR-01): HIGH — all assets enumerated from direct `ls` inspection
- CI workflows (CNTR-03 through CNTR-05): HIGH — existing CI patterns understood; new workflows follow same shape
- Canon overlay structure (CANST-01 through CANST-04): MEDIUM — structure is principled but novel (no prior art in repo)
- ADR-009 content (WIKI-01): MEDIUM — content domain (LinuxONE) is clear from CLAUDE.md; exact article scope is at Claude's discretion
- Activity log (WIKI-02): HIGH — straightforward directory + file creation

**Research date:** 2026-04-28
**Valid until:** 2026-05-28 (stable infrastructure work; no fast-moving dependencies)
