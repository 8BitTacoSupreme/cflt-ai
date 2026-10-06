# Phase 2: Review Skill - Research

**Researched:** 2026-04-28
**Domain:** Claude Code skill authoring, python-docx, golden test harness, canon overlay system
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Claim Extraction Determinism**
- Structured extraction schema with numbered claim categories (config values, behavior assertions, architecture choices, metrics, comparisons) — forces consistent claim boundaries
- Claims extracted into YAML/JSON intermediate format before rendering to markdown table — enables golden harness comparison and reproducibility measurement
- Extraction proceeds in document-order, section-by-section, with explicit "stop when exhausted" — determinism from structured prompting, not temperature controls
- A "claim" is any statement making a falsifiable technical assertion — configs, behaviors, defaults, comparisons, metrics — consistent with existing Step 2 categories

**Premise-Challenge Step**
- New Step 2.5 — after claim extraction (Step 2), before wiki cross-reference (Step 3); challenges the document's premises before validating individual claims
- Constructive critique depth — identify unstated assumptions, question whether premises hold in the customer's context (FSI SLA tiers, regulatory requirements), flag logical gaps
- Dedicated "## Premise Challenge" section in report with table: Premise / Assumption / Challenge / Severity (Critical/Moderate/Minor)
- Overlay-aware challenges: "under your FSI overlay, this premise conflicts with X" when a customer overlay changes the baseline

**.docx Output & Provenance**
- python-docx library for .docx generation — pure Python, no external dependencies, write `tools/review-to-docx.py` converter
- Provenance footer schema matches CANST-04: canon stack hash (16-char truncated SHA-256), MANIFEST.yaml version, floor model used, MCP server versions called, timestamp, operator
- Structured formatting with heading styles (Heading1 for title, Heading2 for sections), proper table formatting for claim tables, provenance as footer paragraph with smaller font
- Generated via `--output docx` flag on /review — produces both .md and .docx side by side in `outputs/reports/`

**Multi-Document Input & Customer Overlay**
- Multiple documents specified as space-separated paths: `/review deck.pdf runbook.md vars.tfvars` — treated as single review scope
- Each doc's claims extracted separately (labeled by source file), then merged into a single claim validation pass — cross-doc contradictions flagged explicitly
- Customer overlay directory at `canon/overlays/<customer>/` with override YAML files that modify canon defaults — consistent with CANST-01/02 scaffolding from Phase 0
- Overlay validation: golden harness case runs same review twice — once with base canon, once with customer overlay — differential results (different verdicts on at least one claim)

### Claude's Discretion
- Internal wording of claim category definitions and extraction prompting
- Exact premise-challenge question templates
- python-docx style choices (fonts, colors, spacing)
- Golden harness case selection strategy for the 15+ review test cases
- Specific sanitized customer doc content for test fixtures

### Deferred Ideas (OUT OF SCOPE)
- PDF input parsing (extract text from customer PDFs) — requires pdfplumber or similar, separate concern
- Automated review scheduling (nightly review of tracked customer docs) — Phase 4+
- Review diff mode (compare two versions of the same document) — future enhancement
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REVW-01 | Claim extraction reproducibility >= 95% across runs (same doc → same claims) | Structured prompting with numbered categories + YAML intermediate output eliminates free-form variance; golden harness measures this structurally |
| REVW-02 | Explicit premise-challenge step shipped and tested in harness | Named Step 2.5 in review.md with dedicated report section; at least one golden harness case exercises it |
| REVW-03 | .docx output with full provenance footer (canon stack hash, manifest version, model floors, MCP versions) | python-docx 1.2.0 already installed; `canon/stack.py::provenance_footer()` provides hash; `tools/review-to-docx.py` is the new converter |
| REVW-04 | Multi-document review supported (deck + tfvars + runbook as single input) | Argument parsing extended from /ask pattern; each doc labeled by source, merged claim table, cross-doc contradiction detection |
| REVW-05 | Golden test harness at tests/golden/review/ with >= 15 cases from sanitized customer docs | Mirrors tests/golden/ask/ structure; same YAML front matter schema; structural-only pytest runner |
| REVW-06 | >= 1 customer overlay validated end-to-end with differential canon override | canon/customer/ scaffold already present; create at least one customer override YAML; harness case compares base vs overlay verdicts |
</phase_requirements>

---

## Summary

Phase 2 builds on a well-established foundation. The project already has: a working /review skill at `.claude/commands/review.md` (6-step process), a proven golden harness pattern from Phase 1's /ask harness, `canon/stack.py` with `provenance_footer()`, and `python-docx 1.2.0` installed with a real usage example at `outputs/reports/build-docx.py`. The canon overlay system (`canon/base/`, `canon/industry/fsi/`, `canon/customer/`, `canon/engagement/`) is scaffolded and functional.

The four implementation tracks are: (1) extend `review.md` with Step 2.5 (premise-challenge), `--output` flag, and multi-doc argument parsing; (2) write `tools/review-to-docx.py` using the same python-docx patterns already in the codebase; (3) build `tests/golden/review/` mirroring the /ask harness structure; and (4) create at least one customer overlay in `canon/customer/<name>/` and a golden case that exercises differential behavior. All four tracks are independently implementable — no blocking dependencies between them.

The main design risk is claim extraction reproducibility (REVW-01). Determinism comes from structured prompting (numbered categories, document-order traversal, explicit stopping condition) — NOT from temperature=0, which Claude Code's runtime does not expose. The golden harness measures this structurally by comparing claim YAML outputs, but actual LLM execution is not tested in Phase 2 (same deferral as Phase 1: structural tests only, LLM evaluation deferred to Phase 4).

**Primary recommendation:** Implement in wave order — review.md extension first (all other tracks depend on the output format), then review-to-docx.py, then golden harness, then customer overlay. Keep the golden harness runner a close copy of `test_golden_ask.py` — the review harness should be structurally identical, just with different required fields.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-docx | 1.2.0 (installed) | .docx generation | Already in project (see `outputs/reports/build-docx.py`); pure Python; no LibreOffice/COM dependency |
| PyYAML | stdlib-adjacent (already installed via wiki-lint.py) | YAML claim intermediate format | Already used in canon/stack.py and test infrastructure |
| pytest | installed (used in Phase 0/1) | Golden harness structural tests | Existing test runner for all cflt-ai tests |
| pathlib | Python stdlib | File path handling | Already the project standard |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | Python stdlib | `--output` flag parsing in review.md | Parse `--output docx` and multi-doc paths |
| hashlib + json | Python stdlib | Canon stack hash computation | Already used in canon/stack.py |
| datetime | Python stdlib | Timestamp in provenance footer | ISO-8601 timestamps in .docx footer |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-docx | docxtpl (template-based) | docxtpl adds Jinja2 dependency; python-docx is direct and already proven in build-docx.py |
| python-docx | pandoc (CLI tool) | pandoc not confirmed installed; python-docx is pure Python with no external binary dependency |
| YAML intermediate | JSON intermediate | Both work; YAML chosen per CONTEXT.md decision; more human-readable for golden cases |

**Installation:** No new packages required. python-docx 1.2.0 is already installed at `the user-local Python 3.9 site-packages`.

**Version verification:** Confirmed `python-docx 1.2.0` via `pip3 show python-docx`. Python 3.9.6 confirmed available.

---

## Architecture Patterns

### Recommended Project Structure

```
.claude/commands/
└── review.md              # Extended: Step 2.5, --output flag, multi-doc args

tools/
└── review-to-docx.py      # New: convert .md report to .docx with provenance footer

tests/golden/review/
├── __init__.py
├── cases/
│   ├── review-bad-acks-001.md       # doc with wrong acks — tests correction accuracy
│   ├── review-premise-fsi-001.md    # premise-challenge FSI context case
│   ├── review-multi-doc-001.md      # deck + tfvars + runbook combined
│   ├── review-overlay-base-001.md   # base canon verdict
│   ├── review-overlay-fsi-001.md    # same doc, FSI overlay — differential result
│   └── ...                          # 15+ total cases
├── README.md
└── test_golden_review.py

canon/customer/
└── <customer-name>/
    ├── overrides.yaml              # At least one override that changes a verdict
    └── adrs/
        └── adr-001.md              # Required: ADR for every override
```

### Pattern 1: Skill Extension — Step Insertion

The existing `/review` 6-step process is extended to 7 steps by inserting Step 2.5. The pattern follows the same markdown structure as `ask.md` — numbered steps with named sub-headings.

```markdown
### Step 2: Extract verifiable claims
[existing — add structured schema with numbered categories]

Claim categories (extract in document order, stop when exhausted):
1. Config values (specific property = value assertions)
2. Behavior assertions (X does Y under condition Z)
3. Architecture choices (use X over Y for this use case)
4. Metrics / limits / SLAs (numbers, thresholds, latencies)
5. Comparisons (X is better/faster/safer than Y)

Output as YAML block before proceeding:
```yaml
claims:
  - id: 1
    category: config_value
    text: "acks=all is the default in Kafka 3.x"
    source_section: "Producer Configuration"
```

### Step 2.5: Challenge premises
[new]

### Step 3: Cross-reference against wiki
[existing — unchanged]
```

**Source:** Derived from CONTEXT.md decisions + existing review.md pattern

### Pattern 2: Premise-Challenge Step

The premise-challenge step is positioned between claim extraction and wiki cross-reference. It operates on the document's stated or implied premises — the assumptions the document takes for granted.

```markdown
### Step 2.5: Challenge premises

Before validating individual claims, interrogate the document's unstated assumptions:

1. Identify 3-5 premises the document implicitly assumes (not explicit claims)
2. For each premise: does it hold for this customer's context?
   - Check FSI overlay: does the premise conflict with latency tiers or regulatory requirements?
   - Check for logical gaps: does the premise require conditions the document never establishes?
3. Rate severity: Critical (blocks a key recommendation) / Moderate (weakens a claim) / Minor (pedantic)

Output as "## Premise Challenge" section:

| # | Premise | Assumption | Challenge | Severity |
|---|---------|------------|-----------|---------|
| 1 | [what doc assumes] | [what must be true] | [why it may not hold] | Critical/Moderate/Minor |
```

**Source:** CONTEXT.md decisions

### Pattern 3: Argument Parsing — Multi-Doc + --output Flag

Follow the `ask.md` pattern for flag parsing. `/review` gets two new parsing behaviors:

```markdown
## Input

$ARGUMENTS

## Step 1: Parse arguments

Parse `$ARGUMENTS`:
- Extract `--output` value if present: `md` (default) | `docx` | `both`
- Extract `--overlay` value if present: customer overlay name (e.g., `acme-bank`, `fsi`)
- Remaining non-flag tokens after flag extraction are treated as file paths to review
- If any path does not exist, stop and report: `Error: file not found: <path>`
- If no paths provided and no pasted content, stop and report: `Error: no input specified`
```

Multi-doc handling:
```markdown
### Step 1.5: Load documents

For each file path:
- Read the file
- Label it with its basename for claim attribution
- Identify file type from extension (.md, .tfvars, .yaml, .txt) — treat all as text
- Build a labeled corpus: { "deck.md": <content>, "vars.tfvars": <content>, ... }
```

**Source:** ask.md flag parsing pattern + CONTEXT.md decisions

### Pattern 4: python-docx Converter (tools/review-to-docx.py)

The converter takes a `outputs/reports/<slug>-review-<date>.md` file as input and produces `outputs/reports/<slug>-review-<date>.docx` beside it. Key design from `outputs/reports/build-docx.py`:

```python
# Source: outputs/reports/build-docx.py (existing codebase pattern)
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

def build_review_docx(md_path: Path, provenance: dict) -> Path:
    doc = Document()

    # Set base font
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # Parse markdown sections and render to docx
    # Heading1 for document title, Heading2 for section headers
    # Tables for claim validation tables (matching markdown table structure)

    # Provenance footer — small font, last paragraph
    footer_text = (
        f"Canon stack: {provenance['stack_hash']} | "
        f"MANIFEST: {provenance['manifest_version']} | "
        f"Floor model: {provenance['floor_model']} | "
        f"MCP: {provenance['mcp_versions']} | "
        f"Generated: {provenance['timestamp']} | "
        f"Operator: {provenance['operator']}"
    )
    p = doc.add_paragraph(footer_text)
    run = p.runs[0]
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    out_path = md_path.with_suffix(".docx")
    doc.save(str(out_path))
    return out_path
```

**Source:** Derived from `outputs/reports/build-docx.py` (HIGH confidence — actual working code in repo)

### Pattern 5: Golden Harness — Review Cases

Review case files use the same YAML front matter schema as ask cases, with review-specific additions:

```yaml
---
id: review-bad-acks-001
input_files:
  - tests/golden/review/fixtures/bad-acks-doc.md
expected_claims_min: 3          # minimum claim count (reproducibility anchor)
expected_verdict_contains:      # at least one claim must get this verdict
  - "Corrected"
premise_challenge_expected: true  # does Step 2.5 fire a challenge?
overlay: null                    # null = base canon; "fsi" = FSI overlay
floor_model: haiku
tags: [kafka, producers, acks, corrections]
required_report_sections:        # sections that must appear in report
  - "## Claim Validation"
  - "## Premise Challenge"
  - "## Canon Compliance"
forbidden_content:
  - "I cannot verify"
---
```

The structural test runner (`test_golden_review.py`) is a close copy of `test_golden_ask.py` with:
- `CASES_DIR = Path(__file__).parent / "cases"`
- Minimum 15 cases (vs. 30 for ask)
- Required fields: `id`, `input_files`, `expected_claims_min`, `floor_model`, `tags`, `required_report_sections`, `forbidden_content`
- At least one case with `overlay` set to a non-null value (REVW-06)
- At least one case with `premise_challenge_expected: true` (REVW-02)

**Source:** `tests/golden/ask/test_golden_ask.py` + `tests/golden/ask/README.md` (HIGH confidence — direct pattern copy)

### Pattern 6: Customer Overlay for REVW-06

The customer overlay follow the exact same structure as `canon/industry/fsi/`:

```yaml
# canon/customer/<name>/overrides.yaml
# Each override references an ADR — no override without an ADR
latency_tiers:
  market_data: "sub-100-microsecond"    # Stricter than FSI base
  override_source: "customer/adr-001"

producer:
  compression_type: "zstd"              # Storage-constrained cluster
  override_source: "customer/adr-002"
```

A golden harness review case runs the same document under base canon and under this overlay — the compression_type override should change the canon compliance verdict for any claim about producer compression.

**Source:** `canon/industry/fsi/overrides.yaml` + CONTEXT.md (HIGH confidence)

### Anti-Patterns to Avoid

- **Generating .docx directly in the skill:** The skill writes .md first, then calls the converter tool. Never generate .docx inline in the skill process — separation of concerns, and the .md is the canonical output.
- **Hardcoding provenance fields in review.md:** The skill should call `canon/stack.py::provenance_footer()` or pass a dict to `review-to-docx.py`. Hardcoded hash/version in the skill body defeats the purpose.
- **Temperature control for determinism:** Claude Code does not expose temperature to skill authors. Determinism comes exclusively from structured prompting (schema, numbered categories, document-order traversal, explicit stop condition). Do not attempt to describe a temperature setting in review.md.
- **Monolithic multi-doc claim table:** Each source doc's claims should be labeled by filename in the merged table. A single undifferentiated claim pool hides cross-doc contradictions.
- **Skipping the YAML intermediate step:** The CONTEXT.md decision to output claims as YAML before rendering is load-bearing for REVW-01. Do not optimize it away by going straight to markdown table.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| .docx generation | Custom XML/ZIP writer | python-docx 1.2.0 | Already installed; handles OOXML complexity; proven in build-docx.py |
| Canon stack hash | Custom hash function | `canon/stack.py::resolve_stack()` | Already implemented, tested; 16-char SHA-256 truncation already decided |
| Provenance footer | Inline string in review.md | `canon/stack.py::provenance_footer()` | Single source of truth for hash format |
| YAML front matter parsing | Custom parser | `yaml.safe_load()` with `---` split | Same pattern used in test_golden_ask.py and wiki-lint.py |
| Overlay resolution | Custom merge logic | `canon/stack.py::resolve_stack(customer=<name>)` | Already handles deep merge; customer param already supported |
| Markdown table parsing | Custom regex | Line-by-line `|`-split | Markdown tables are regular enough; no library needed for this use case |

**Key insight:** The project already has implementations for every hard part of this phase. The work is integration and extension, not invention.

---

## Common Pitfalls

### Pitfall 1: canon/overlays/ vs canon/customer/

**What goes wrong:** CONTEXT.md mentions `canon/overlays/<customer>/` but the actual directory structure uses `canon/customer/` (confirmed by `ls canon/`). Using the wrong path causes overlay resolution to silently return empty config.

**Why it happens:** The CONTEXT.md was written based on the Phase 0 spec; the actual implementation during Phase 0 used `canon/customer/` instead of `canon/overlays/`.

**How to avoid:** Use `canon/customer/<name>/overrides.yaml` (confirmed structure). The `resolve_stack(customer=<name>)` call in `canon/stack.py` looks at `canon/customer/{name}/overrides.yaml`.

**Warning signs:** `provenance_footer()` returns hash that doesn't change when overlay is active — means overlay wasn't loaded.

### Pitfall 2: Argument Parsing in Claude Code Skills

**What goes wrong:** `/review deck.pdf runbook.md --output docx` — the `$ARGUMENTS` variable is the raw string passed by the user. The skill must parse it; Claude Code does not pre-parse flags.

**Why it happens:** Unlike a CLI tool, skill files receive `$ARGUMENTS` as an unstructured string. The ask.md parsing step is the pattern to follow exactly.

**How to avoid:** Step 1 of the revised review.md must explicitly parse flags and file paths from `$ARGUMENTS`, exactly as ask.md parses `--mode` and `--force-route`.

**Warning signs:** Tests fail with unexpected argument values or flags are silently ignored.

### Pitfall 3: python-docx Table Cell Styling

**What goes wrong:** Claim validation tables require consistent column widths; python-docx tables default to auto-fit and can produce unreadable output with very wide claim text columns.

**Why it happens:** python-docx doesn't enforce column widths unless explicitly set via `set_column_width` or cell width properties.

**How to avoid:** Set explicit column widths on the claim table. The existing `build-docx.py` doesn't need tables (it uses bullet lists), so the review-to-docx.py converter is the first place this matters.

```python
# Source: python-docx 1.2.0 docs
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def set_col_width(cell, width_inches):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcW = OxmlElement('w:tcW')
    tcW.set(qn('w:w'), str(int(width_inches * 1440)))  # 1440 twips per inch
    tcW.set(qn('w:type'), 'dxa')
    tcPr.append(tcW)
```

**Warning signs:** .docx output has columns that overflow or are unreadably narrow.

### Pitfall 4: MANIFEST.yaml Version in Provenance

**What goes wrong:** CANST-04 requires MANIFEST.yaml version in the provenance footer. MANIFEST.yaml lives at `raw/repos/fsi-dsp/MANIFEST.yaml` (fsi-dsp submodule), not at the repo root. A hardcoded path `./MANIFEST.yaml` will fail.

**Why it happens:** MANIFEST.yaml is in the fsi-dsp submodule, not cflt-ai root.

**How to avoid:** `review-to-docx.py` should derive the MANIFEST version by reading `raw/repos/fsi-dsp/MANIFEST.yaml` with a fallback of `"fsi-dsp/manifest/v1"` if not found. Alternatively, embed the version string at review-time by reading it in the skill itself.

```python
# Source: derived from raw/repos/fsi-dsp/MANIFEST.yaml structure
MANIFEST_PATH = Path(__file__).resolve().parent.parent / "raw" / "repos" / "fsi-dsp" / "MANIFEST.yaml"

def get_manifest_version() -> str:
    if MANIFEST_PATH.exists():
        data = yaml.safe_load(MANIFEST_PATH.read_text())
        return data.get("version", "unknown")
    return "unknown"
```

**Warning signs:** Provenance footer shows `"unknown"` for MANIFEST version in all outputs.

### Pitfall 5: Multi-Doc Claim ID Collision

**What goes wrong:** When two documents each have a "Claim #1", the merged claim table has duplicate IDs. Golden harness reproducibility comparison breaks.

**Why it happens:** Each document's claims are numbered independently; merging without namespace produces collisions.

**How to avoid:** Prefix claim IDs with the source file slug: `deck-1`, `runbook-1`, `vars-1`. The YAML intermediate format should include `source_file` field.

```yaml
claims:
  - id: "deck-1"
    source_file: "deck.md"
    category: config_value
    text: "acks=all required"
```

**Warning signs:** Golden harness YAML comparison reports false mismatches on multi-doc reviews.

### Pitfall 6: Review Golden Harness Fixture File Strategy

**What goes wrong:** Using real customer documents as test fixtures exposes sensitive data; using fully synthetic documents fails to exercise real edge cases.

**Why it happens:** REVW-05 requires "sanitized customer docs" — this is a real constraint, not just flavor text.

**How to avoid:** Create small, focused fixture files (15-50 lines) in `tests/golden/review/fixtures/` that exercise specific behaviors. Each fixture should contain exactly the claims needed for its test case. Include at least one "bad" document (wrong acks, wrong replication factor) per CONTEXT.md specifics.

**Warning signs:** Cases with large fixture files are slow to reason about and fragile when fixture content changes.

---

## Code Examples

### provenance_footer() — Existing Implementation

```python
# Source: canon/stack.py (existing)
def provenance_footer() -> str:
    """Generate a provenance footer string for artifact embedding."""
    config, stack_hash = resolve_stack()
    layers = active_layers()
    return f"Canon stack: {' + '.join(layers)} | Hash: {stack_hash}"
```

The provenance footer for .docx needs to extend this with additional fields (MANIFEST version, floor model, MCP versions, timestamp, operator):

```python
# Source: pattern derived from canon/stack.py + CONTEXT.md provenance schema
import datetime
import yaml
from pathlib import Path

def build_provenance(floor_model: str, mcp_versions: dict, operator: str = "claude-code") -> dict:
    config, stack_hash = resolve_stack()
    layers = active_layers()

    manifest_path = Path(__file__).resolve().parent.parent / "raw" / "repos" / "fsi-dsp" / "MANIFEST.yaml"
    manifest_version = "unknown"
    if manifest_path.exists():
        data = yaml.safe_load(manifest_path.read_text())
        manifest_version = data.get("version", "unknown")

    return {
        "stack_hash": stack_hash,
        "canon_layers": " + ".join(layers),
        "manifest_version": manifest_version,
        "floor_model": floor_model,
        "mcp_versions": mcp_versions,  # e.g., {"confluent-docs": "1.0", "context7": "2.1"}
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "operator": operator,
    }
```

### Golden Case Front Matter — Review Harness

```yaml
# Source: derived from tests/golden/ask/cases/mcp-acks-config-001.md pattern
---
id: review-bad-acks-001
input_files:
  - tests/golden/review/fixtures/bad-acks-doc.md
expected_claims_min: 3
expected_verdict_contains:
  - "Corrected"
premise_challenge_expected: false
overlay: null
floor_model: haiku
tags: [kafka, producers, acks, correction-accuracy]
required_report_sections:
  - "## Claim Validation"
  - "## Canon Compliance"
  - "## Recommendations"
forbidden_content:
  - "I cannot verify"
  - "unclear"
---
```

### test_golden_review.py Structural Skeleton

```python
# Source: mirrors tests/golden/ask/test_golden_ask.py exactly
"""
Golden harness structural tests for /review skill (REVW-05).
Tests verify case file structure and minimum coverage requirements.
LLM evaluation deferred to Phase 4.
"""
import yaml
from pathlib import Path
import pytest

CASES_DIR = Path(__file__).parent / "cases"
REQUIRED_FIELDS = {
    "id", "input_files", "expected_claims_min",
    "floor_model", "tags", "required_report_sections", "forbidden_content"
}
VALID_FLOOR_MODELS = {"haiku", "sonnet"}

def load_case(path: Path) -> dict:
    content = path.read_text()
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    return yaml.safe_load(content[3:end]) or {}

ALL_CASES = sorted(CASES_DIR.glob("*.md")) if CASES_DIR.exists() else []

class TestGoldenReviewStructure:
    def test_minimum_case_count(self):
        assert len(ALL_CASES) >= 15

    def test_premise_challenge_case_exists(self):
        """REVW-02: at least one case exercises premise-challenge."""
        pc_cases = [p for p in ALL_CASES if load_case(p).get("premise_challenge_expected")]
        assert len(pc_cases) >= 1

    def test_overlay_case_exists(self):
        """REVW-06: at least one case uses a non-null overlay."""
        overlay_cases = [p for p in ALL_CASES if load_case(p).get("overlay") is not None]
        assert len(overlay_cases) >= 1

    def test_multi_doc_case_exists(self):
        """REVW-04: at least one case has multiple input files."""
        multi = [p for p in ALL_CASES if len(load_case(p).get("input_files", [])) > 1]
        assert len(multi) >= 1
```

### python-docx Provenance Footer

```python
# Source: pattern from outputs/reports/build-docx.py (existing) + CANST-04 schema
from docx import Document
from docx.shared import Pt, RGBColor

def add_provenance_footer(doc: Document, provenance: dict) -> None:
    """Add CANST-04 compliant provenance footer as final paragraph."""
    mcp_str = ", ".join(f"{k}:{v}" for k, v in provenance.get("mcp_versions", {}).items())
    footer_text = (
        f"Canon: {provenance['canon_layers']} | "
        f"Hash: {provenance['stack_hash']} | "
        f"MANIFEST: {provenance['manifest_version']} | "
        f"Floor: {provenance['floor_model']} | "
        f"MCP: {mcp_str} | "
        f"Generated: {provenance['timestamp']} | "
        f"Operator: {provenance['operator']}"
    )
    p = doc.add_paragraph()
    # Horizontal rule via paragraph border
    pPr = p._element.get_or_add_pPr()
    # Simple approach: use a small grey run
    run = p.add_run(footer_text)
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Ad-hoc review output (no structure) | 6-step structured process with claim table | Phase 0 | Consistent report format |
| No intermediate claim format | YAML claim extraction before rendering | Phase 2 (new) | Enables golden harness comparison |
| No premise interrogation | Explicit Step 2.5 | Phase 2 (new) | Catches FSI context gaps before claim validation |
| .md only output | .md + optional .docx | Phase 2 (new) | Customer-presentable artifacts |
| Single document input | Multi-document merged scope | Phase 2 (new) | Matches real engagement workflow |
| No overlay differentiation | Customer overlay differential output | Phase 2 (new) | Validates canon fork correctness |

**Deprecated/outdated:**
- Free-form claim extraction in current review.md: replaced by numbered category schema
- Report written directly without YAML intermediate: replaced by YAML-first approach

---

## Open Questions

1. **MCP version resolution at review time**
   - What we know: Provenance footer requires MCP server versions; CANST-04 specifies this
   - What's unclear: Claude Code does not expose MCP server version via a standard API; the skill may need to call each MCP tool to get its version, or use a fixed version string from a config file
   - Recommendation: Use a `canon/base/mcp-versions.yaml` file with pinned versions that is updated manually when MCP servers update; the converter reads from this file rather than querying live versions

2. **`--operator` field in provenance**
   - What we know: Provenance footer includes "operator" field
   - What's unclear: For Claude Code invocations, "operator" should probably be the username or session ID; Claude Code doesn't expose a session ID
   - Recommendation: Default to `"claude-code"` as the operator string; this is sufficient for CANST-04 compliance in an engagement context

3. **Overlay path: `canon/overlays/` vs `canon/customer/`**
   - What we know: CONTEXT.md says `canon/overlays/<customer>/`; actual filesystem has `canon/customer/`; `resolve_stack()` uses `customer/{name}/overrides.yaml`
   - What's unclear: Should the plan use the spec path or the actual path?
   - Recommendation: Use the actual implemented path `canon/customer/<name>/overrides.yaml`. The CONTEXT.md wording was aspirational; implementation chose `canon/customer/` and that's what the code supports.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.9+ | All Python tools | Yes | 3.9.6 | — |
| python-docx | REVW-03 (.docx output) | Yes | 1.2.0 | — |
| PyYAML | Claim YAML intermediate | Yes | (installed) | — |
| pytest | REVW-05 (golden harness) | Yes | (installed) | — |
| canon/stack.py | Provenance footer | Yes | Phase 0 deliverable | — |
| canon/customer/ scaffold | REVW-06 (overlay) | Yes | Phase 0 deliverable (empty) | — |
| tests/golden/ask/ pattern | REVW-05 (harness structure) | Yes | Phase 1 deliverable | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, Phase 0/1) |
| Config file | `pytest.ini` or none — uses `python3 -m pytest` |
| Quick run command | `python3 -m pytest tests/golden/review/test_golden_review.py -v` |
| Full suite command | `python3 -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REVW-01 | Claim extraction reproducibility >= 95% | structural (case schema enforces structure; LLM eval deferred) | `python3 -m pytest tests/golden/review/ -v` | Wave 0 |
| REVW-02 | Premise-challenge step ships and is tested | structural (harness asserts >= 1 premise_challenge_expected case) | `python3 -m pytest tests/golden/review/test_golden_review.py::TestGoldenReviewStructure::test_premise_challenge_case_exists` | Wave 0 |
| REVW-03 | .docx output with provenance footer | unit (tools/test_review_to_docx.py: generate docx, assert footer text present) | `python3 -m pytest tests/test_review_to_docx.py -v` | Wave 0 |
| REVW-04 | Multi-document input supported | structural (harness asserts >= 1 multi-input_files case) | `python3 -m pytest tests/golden/review/test_golden_review.py::TestGoldenReviewStructure::test_multi_doc_case_exists` | Wave 0 |
| REVW-05 | >= 15 golden review cases | structural (count assertion) | `python3 -m pytest tests/golden/review/test_golden_review.py::TestGoldenReviewStructure::test_minimum_case_count` | Wave 0 |
| REVW-06 | >= 1 customer overlay with differential result | structural (harness asserts >= 1 overlay case) + unit (test resolve_stack with customer name) | `python3 -m pytest tests/golden/review/ tests/test_canon_overlay.py -v` | Wave 0 (test_canon_overlay.py exists) |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/golden/review/test_golden_review.py -v`
- **Per wave merge:** `python3 -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/golden/review/__init__.py` — makes directory a Python package
- [ ] `tests/golden/review/test_golden_review.py` — structural test runner (mirrors test_golden_ask.py)
- [ ] `tests/golden/review/cases/` — directory for case files (empty at Wave 0)
- [ ] `tests/golden/review/fixtures/` — small synthetic fixture docs
- [ ] `tests/golden/review/README.md` — mirrors tests/golden/ask/README.md
- [ ] `tests/test_review_to_docx.py` — unit tests for the docx converter tool

---

## Project Constraints (from CLAUDE.md)

The following directives from CLAUDE.md are binding on all Phase 2 work:

| Directive | Impact on Phase 2 |
|-----------|-------------------|
| Confluent Canon defaults (acks=all, idempotence=true, etc.) | Review skill must flag deviations from these; premise-challenge must reference these |
| FSI overlay latency tiers (sub-ms, <10ms, <100ms) | Premise-challenge must check FSI SLA tier fit |
| `canon/stack.py::resolve_stack()` for canon hash | Do not reimplement hash; call existing function |
| Reports written to `outputs/reports/` | .docx output must land beside .md in same directory |
| Python CLI tools in `tools/` with argparse | `review-to-docx.py` follows this pattern |
| Activity log entry per skill invocation | /review invocations must emit activity log entry (same as /ask) |
| Auto-stub on miss (WIKI-05) | /review should also auto-stub wiki gaps discovered during cross-reference |
| No override without an ADR | Customer overlay created for REVW-06 must have an ADR |
| `acks=all` in production, `enable.idempotence=true` always | These are canonical checks the review skill must validate |

---

## Sources

### Primary (HIGH confidence)

- `canon/stack.py` — resolve_stack(), active_layers(), provenance_footer() API
- `outputs/reports/build-docx.py` — working python-docx implementation in repo
- `.claude/commands/review.md` — current 6-step review skill being extended
- `.claude/commands/ask.md` — flag parsing and routing patterns to follow
- `tests/golden/ask/test_golden_ask.py` — harness test runner to mirror
- `tests/golden/ask/README.md` — case format specification
- `tests/golden/ask/cases/mcp-acks-config-001.md` — case file example
- `canon/industry/fsi/overrides.yaml` — overlay format to replicate for customer overlay
- `canon/customer/README.md` — confirms `canon/customer/` path (not `canon/overlays/`)
- `pip3 show python-docx` — confirms version 1.2.0 installed
- `.planning/phases/02-review-skill/02-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)

- `outputs/reports/e2e-latency-evaluation-2026-04-17.md` — existing report format showing claims_checked, claims_confirmed, claims_corrected metadata fields
- `raw/repos/fsi-dsp/MANIFEST.yaml` — confirmed location and `version: "1.0.0"` format for provenance

### Tertiary (LOW confidence)

- python-docx table column width technique (OxmlElement approach) — derived from python-docx docs patterns; should be verified against python-docx 1.2.0 API before implementation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — python-docx 1.2.0 confirmed installed; all other dependencies are stdlib or already-present project tools
- Architecture: HIGH — all patterns derived from existing codebase code, not speculation
- Pitfalls: HIGH — overlay path pitfall verified by inspecting actual filesystem; MANIFEST path verified by find command; all others derived from reading actual code
- Test structure: HIGH — mirrors Phase 1 pattern exactly; test runner already working

**Research date:** 2026-04-28
**Valid until:** 2026-07-28 (stable domain; python-docx API is stable)
