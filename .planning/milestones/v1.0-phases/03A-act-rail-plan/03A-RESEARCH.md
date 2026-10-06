# Phase 03A: act-rail-plan - Research

**Researched:** 2026-04-28
**Domain:** Claude skill implementation, four-gate validation pipeline, Terraform MCP, golden harness, GitHub Actions parity CI
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Skill Interface & Output Contract**
- `/dsp:plan` accepts natural language request strings (e.g., "create a topic for trade events with DR") — consistent with /ask and /review input patterns
- Flags: `--overlay <name>` (reuse from /review for customer overlay resolution), `--dry-run` (default true, plan-only mode), `--gate-bypass <gate>` (dev mode — skip specific named gates per ACT-03)
- Output: Markdown plan document with sections (Selected Artifact, Arguments, Gate Results, Canon Compliance, Provenance Footer) written to `outputs/plans/<slug>-plan-<YYYY-MM-DD>.md`
- Unresolvable requests: Return structured "no matching artifact" response with suggested alternatives from MANIFEST.yaml — never generate inline Terraform (per Out of Scope constraint). Unresolvable requests may suggest a PR proposal to fsi-dsp.

**Four-Gate Architecture**
- Gates execute sequentially in fail-fast order: gate 1 (canon compliance) failure skips gates 2-4
- Dev-mode bypass via `--gate-bypass <gate-name>` flag, requiring explicit gate name (not blanket skip-all) — satisfies ACT-03
- Each gate returns structured result dict: `{gate: str, status: pass|fail|skipped, detail: str, evidence: list}`
- Gate pipeline lives in `tools/act_gates.py` module with one function per gate + `run_gate_chain()` orchestrator

**Terraform MCP & Parity CI**
- Wire `hashicorp/terraform-mcp-server` (official HashiCorp Terraform MCP) into `.mcp.json`
- Canon-fsi-dsp parity checked by `tools/check-canon-parity.py` reading MANIFEST.yaml capabilities vs. canon defaults.yaml keys
- Parity CI runs in GitHub Actions for both repos; failure is bidirectional
- Gate 4 (mcp-confluent state) calls mcp-confluent to verify target cluster/environment is reachable

### Claude's Discretion
- Internal gate implementation details (error messages, evidence format, timeout handling)
- Golden harness case selection and negative-space coverage design
- CI workflow YAML structure and trigger patterns

### Deferred Ideas (OUT OF SCOPE)
- Policy profiles (read-only, engineer, break-glass) — Phase 3b concern
- Human confirmation gate for apply — Phase 3b concern
- Per-tool classification of mcp-confluent tools — Phase 3c concern
- Negative-space test suites for forbidden tools — Phase 3c concern
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ACT-01 | Terraform MCP wired into .mcp.json | hashicorp/terraform-mcp-server entry; npx pattern matches existing MCP servers |
| ACT-02 | Four-gate validation chain implemented (canon compliance → fsi-dsp coverage → confluent-docs schema → mcp-confluent state) | act_gates.py module structure; each gate independently testable function |
| ACT-03 | Each gate individually testable and bypassable in dev mode | `--gate-bypass <gate-name>` flag; `status=skipped` in gate result; pytest parametrize per gate |
| ACT-04 | /dsp:plan read-only act rail skill implemented | `.claude/commands/dsp-plan.md`; mirrors ask.md/review.md pattern |
| ACT-05 | Golden test harness at tests/golden/act/ with >= 20 cases including negative-space | Mirrors tests/golden/ask/ structure; frontmatter + parametrize runner |
| ACT-06 | Agent never generates inline Terraform; never invokes mcp-confluent write tools directly | Skill steps enforce read-only; gate chain calls terraform-mcp read tools only |
| ACT-07 | Structural correctness >= 95% (right artifact selected, right arguments, schemas validate) | Golden harness pass rate threshold; `required_artifact` field in case frontmatter |
| ACT-08 | Canon <-> fsi-dsp parity test running in both repos' CI and blocking on drift | check-canon-parity.py + .github/workflows/canon-parity.yml in both repos |
</phase_requirements>

---

## Summary

Phase 3a builds the read-only `/dsp:plan` act rail — a Claude skill that accepts a natural language infrastructure request and walks it through a four-gate validation chain before producing a Markdown plan document. The skill selects an existing fsi-dsp artifact from MANIFEST.yaml, never generates new Terraform inline, and produces a plan with full provenance.

The implementation is entirely additive: three new Python modules (`tools/act_gates.py`, `tools/check-canon-parity.py`), one new skill file (`.claude/commands/dsp-plan.md`), one new MCP entry (hashicorp/terraform-mcp-server in `.mcp.json`), one new golden harness (`tests/golden/act/`), and one new GitHub Actions workflow (`.github/workflows/canon-parity.yml`). All patterns replicate what already exists in phases 1 and 2.

The key architectural risk is gate 4's dependency on a live mcp-confluent connection. The `--gate-bypass gate4` flag handles dev/CI contexts where no live cluster is present. The golden harness validates structural correctness (right artifact selected, right arguments) not live execution.

**Primary recommendation:** Implement in two waves — Wave 1: MCP wiring + gate chain + skill (ACT-01, ACT-02, ACT-03, ACT-04, ACT-06); Wave 2: golden harness + parity CI (ACT-05, ACT-07, ACT-08). Golden harness drives TDD RED-GREEN discipline same as phases 1 and 2.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python 3.x | 3.9+ | Gate chain + parity checker | All tools/ are Python; 3.9+ already enforced (Optional typing) |
| PyYAML | existing | Parse MANIFEST.yaml, canon defaults.yaml | Already in requirements.txt |
| pytest | existing | Golden harness runner | Established test runner for all phases |
| hashicorp/terraform-mcp-server | npx latest | Terraform plan/validate/state reads via MCP | Official HashiCorp MCP; read-only tools |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | stdlib | CLI flags for act_gates.py, check-canon-parity.py | Matches review-to-docx.py pattern |
| pathlib | stdlib | File path resolution | All tools use pathlib |
| json | stdlib | Gate result serialization | Structured result dicts |
| github/actions | latest | Canon parity CI workflow | Already used for check-citations CI |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Sequential fail-fast gates | Parallel gate execution | Parallel saves time but loses "fix this first" guidance; sequential wins |
| npx terraform-mcp-server | Local terraform binary | Local install required; npx matches existing MCP pattern |
| Single parity script | Inline CI step | Script is importable for unit testing; inline YAML step is not |

**Installation:**

```bash
# No new Python packages required — all dependencies already present
# terraform-mcp-server installed via npx at runtime (no local install needed)
# Verify MCP server is reachable:
npx -y @hashicorp/terraform-mcp-server --version 2>/dev/null || echo "fetches on first run"
```

---

## Architecture Patterns

### Recommended Project Structure

```
.claude/commands/
└── dsp-plan.md          # New: /dsp:plan skill file

tools/
├── act_gates.py          # New: four-gate chain (gate1-4 + run_gate_chain)
├── check-canon-parity.py # New: parity checker for CI
└── (existing files unchanged)

tests/golden/act/
├── __init__.py
├── cases/               # >= 20 .md case files with YAML frontmatter
├── README.md
└── test_golden_act.py   # Structural harness (mirrors test_golden_ask.py)

.github/workflows/
└── canon-parity.yml     # New: CI workflow for both repos

outputs/plans/           # Written by /dsp:plan at runtime
```

### Pattern 1: Gate Result Struct

Each gate returns a consistent dict. This is the composable abstraction that lets gates be tested in isolation and bypassed by name.

```python
# Source: CONTEXT.md gate architecture decision
GateResult = dict  # typed as:
# {
#   "gate": str,       # "canon_compliance" | "fsi_dsp_coverage" | "confluent_docs_schema" | "mcp_confluent_state"
#   "status": str,     # "pass" | "fail" | "skipped"
#   "detail": str,     # human-readable summary
#   "evidence": list   # list of strings, supporting facts
# }

def gate1_canon_compliance(request: str, config: dict, overlay: str | None) -> GateResult:
    ...

def run_gate_chain(request: str, overlay: str | None, bypass: list[str]) -> list[GateResult]:
    results = []
    for gate_fn, gate_name in GATES:
        if gate_name in bypass:
            results.append({"gate": gate_name, "status": "skipped", "detail": "bypassed via --gate-bypass", "evidence": []})
            continue
        result = gate_fn(request, ...)
        results.append(result)
        if result["status"] == "fail":
            break  # fail-fast
    return results
```

### Pattern 2: Skill File (dsp-plan.md)

The skill mirrors ask.md and review.md structure exactly:

```markdown
# /dsp:plan — FSI-DSP Infrastructure Plan

## Input
$ARGUMENTS

## Step 1: Parse arguments
- Extract --overlay, --dry-run (default true), --gate-bypass
- Remaining text is the request string

## Step 2: Load canon stack
- Call resolve_stack(customer=overlay) from canon/stack.py

## Step 3: Run gate chain
- Call run_gate_chain(request, overlay, bypass_list) from tools/act_gates.py
- If gate 1 fails: return structured no-pass response

## Step 4: Select artifact
- Gate 2 result contains matched artifact ID from MANIFEST.yaml
- Never generate inline Terraform

## Step 5: Produce plan document
- Write to outputs/plans/<slug>-plan-<YYYY-MM-DD>.md
- Sections: Selected Artifact, Arguments, Gate Results, Canon Compliance, Provenance Footer

## Step 6: Emit activity log
- Append to wiki/activity/<YYYY-MM>.md (established pattern from all previous skills)
```

### Pattern 3: Golden Case Frontmatter (act harness)

```yaml
---
id: topic-trade-events-with-dr-001
request: "create a topic for trade events with DR"
expected_artifact: "module/topic"
floor_model: sonnet
tags: [topic, dr, terraform, fsi]
required_claims:
  - "module/topic"
  - "confluent_kafka_topic"
forbidden_claims:
  - "resource \"confluent_kafka_topic\""  # Never inline Terraform
negative_space: false
---
```

For negative-space cases (no matching artifact):
```yaml
---
id: negative-unsupported-nosql-001
request: "provision a MongoDB Atlas cluster with Kafka CDC"
expected_artifact: null
floor_model: haiku
tags: [negative-space, out-of-scope]
required_claims:
  - "no matching artifact"
  - "PR proposal"
negative_space: true
---
```

### Pattern 4: Parity Checker

```python
# tools/check-canon-parity.py
# Reads MANIFEST.yaml capability IDs and canon/base/defaults.yaml keys
# Detects: (1) MANIFEST has capability with no canon key, (2) canon has key with no MANIFEST artifact
# Exit 0 = parity, Exit 1 = drift detected (blocks CI merge)

import sys
import yaml
from pathlib import Path

def check_parity(manifest_path: Path, defaults_path: Path) -> list[str]:
    """Returns list of drift items. Empty = no drift."""
    ...

if __name__ == "__main__":
    drift = check_parity(...)
    if drift:
        for item in drift:
            print(f"DRIFT: {item}", file=sys.stderr)
        sys.exit(1)
    print("OK: canon <-> fsi-dsp parity confirmed")
    sys.exit(0)
```

### Anti-Patterns to Avoid

- **Blanket gate bypass:** `--gate-bypass all` is not supported — only named gates. Prevents accidental bypass in production-like usage.
- **Inline Terraform generation:** If no MANIFEST artifact matches, return "no matching artifact" with alternatives — never generate `resource "confluent_kafka_topic"` blocks. ACT-06 requires this.
- **Write tool invocation:** Skill may call terraform-mcp read tools (plan, validate, show) but must never call mcp-confluent create/update/delete tools. Gate 4 is read-only state inspection only.
- **Hard-coded MANIFEST path:** Always resolve relative to project root via `Path(__file__).resolve().parent.parent` pattern (matches review-to-docx.py).
- **Argparse in test imports:** Gate functions must be importable without triggering argparse. Use `if __name__ == "__main__":` guard (matches tools/ convention).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Canon config resolution | Custom YAML loader | `canon.stack.resolve_stack()` | Already handles deep merge, overlay layers, hash |
| Provenance footer | String formatting | `canon.stack.provenance_footer()` | Consistent format, stack hash, active layers |
| MANIFEST parsing | Ad-hoc YAML | PyYAML + existing MANIFEST.yaml schema | Stable v1.0 schema with type prefix IDs |
| MCP server setup | Custom HTTP client | `npx -y @hashicorp/terraform-mcp-server` via .mcp.json | Official HashiCorp distribution, matches existing pattern |
| Golden test runner | Custom pytest plugin | Mirror `test_golden_ask.py` exactly | `load_case()`, `ALL_CASES` glob, `parametrize` — established pattern |
| Activity logging | New log format | Existing `wiki/activity/YYYY-MM.md` append pattern | Phase 1 introduced this; all skills must use it |

**Key insight:** Every new component in this phase has a direct precedent in the existing codebase. The only genuinely new abstraction is the gate chain — everything else is a composition of existing patterns.

---

## Common Pitfalls

### Pitfall 1: Gate 4 Blocks CI
**What goes wrong:** Gate 4 (mcp-confluent state) calls a live cluster. Golden harness cases and CI run without a live cluster. Test runner hangs or fails on connection timeout.
**Why it happens:** No explicit bypass in test setup for gate 4.
**How to avoid:** Golden harness test runner passes `bypass=["mcp_confluent_state"]` by default in test fixture. Document this in README. `--gate-bypass gate4` is the canonical dev-mode flag.
**Warning signs:** Tests hanging more than 5 seconds, `ConnectionRefusedError` in CI logs.

### Pitfall 2: MANIFEST Artifact Matching is Too Broad
**What goes wrong:** Gate 2 matches the wrong artifact (e.g., "topic" request matches `role/cp_topic` instead of `module/topic`) because keyword matching is too loose.
**Why it happens:** Multiple artifacts touch "topic" — `role/cp_topic`, `module/topic`, `role/cfk_topic`.
**How to avoid:** Gate 2 matching must consider artifact type (terraform-module vs ansible-role) based on deployment model context in request. Use MANIFEST `type` field as tiebreaker. Golden cases cover this explicitly.
**Warning signs:** `expected_artifact` mismatch in golden harness hitting ACT-07's 95% threshold.

### Pitfall 3: Inline Terraform in Plan Output
**What goes wrong:** Skill generates `resource "confluent_kafka_topic"` blocks in the plan output when a near-match artifact exists, rather than returning "no matching artifact."
**Why it happens:** Model helpfully fills the gap without being explicitly forbidden.
**How to avoid:** Skill step 4 has explicit instruction: "Never generate Terraform resource blocks. If no MANIFEST artifact matches, go to step 4b (no-match response)." Golden negative-space cases enforce this.
**Warning signs:** `forbidden_claims` failures in golden harness on cases with `negative_space: true`.

### Pitfall 4: Parity Check Scope Creep
**What goes wrong:** `check-canon-parity.py` tries to deep-validate MANIFEST capability arguments against canon defaults — too complex, slow, brittle.
**Why it happens:** Parity check conflated with schema validation (gate 3's job).
**How to avoid:** Parity check has one job: verify every MANIFEST capability type that maps to a canon config category has a corresponding entry. Not argument-level validation. Keep it to ~50 lines.
**Warning signs:** Parity script taking > 2 seconds, requiring MCP calls.

### Pitfall 5: `tools/__init__.py` Registration
**What goes wrong:** `from tools.act_gates import run_gate_chain` fails because `act_gates.py` (no hyphens) isn't registered in `tools/__init__.py`.
**Why it happens:** `tools/__init__.py` only registers `review-to-docx.py` (the only hyphenated module). `act_gates.py` uses underscores, so it imports normally without registration.
**How to avoid:** `act_gates.py` and `check-canon-parity.py` use underscore naming — no `__init__.py` registration needed. Verify with `python -c "from tools.act_gates import run_gate_chain"` after creating the file.
**Warning signs:** `ModuleNotFoundError` when running tests.

---

## Code Examples

### Gate Chain Orchestrator

```python
# Source: CONTEXT.md architecture decisions + tools/review-to-docx.py pattern

GATE_NAMES = [
    "canon_compliance",
    "fsi_dsp_coverage",
    "confluent_docs_schema",
    "mcp_confluent_state",
]

def run_gate_chain(
    request: str,
    overlay: str | None = None,
    bypass: list[str] | None = None,
) -> list[dict]:
    """Run the four-gate chain in fail-fast order.

    Returns list of GateResult dicts, one per gate.
    Stops after first failure (skips remaining gates).
    Gates in `bypass` list return status=skipped without executing.
    """
    bypass = bypass or []
    gates = [
        (gate1_canon_compliance, "canon_compliance"),
        (gate2_fsi_dsp_coverage, "fsi_dsp_coverage"),
        (gate3_confluent_docs_schema, "confluent_docs_schema"),
        (gate4_mcp_confluent_state, "mcp_confluent_state"),
    ]
    results = []
    for gate_fn, gate_name in gates:
        if gate_name in bypass:
            results.append({
                "gate": gate_name,
                "status": "skipped",
                "detail": f"bypassed via --gate-bypass {gate_name}",
                "evidence": [],
            })
            continue
        result = gate_fn(request, overlay)
        results.append(result)
        if result["status"] == "fail":
            break  # fail-fast: remaining gates implicitly skipped
    return results
```

### .mcp.json Terraform MCP Entry

```json
{
  "mcpServers": {
    "terraform": {
      "command": "npx",
      "args": ["-y", "@hashicorp/terraform-mcp-server"]
    }
  }
}
```

The full `.mcp.json` adds this entry alongside the existing `context7`, `confluent-docs`, and `mcp-confluent` entries.

### Canon Parity Check

```python
# tools/check-canon-parity.py
# Source: CONTEXT.md parity CI decision

CAPABILITY_TO_CANON_KEY = {
    "ansible-role": None,        # ansible roles don't map to canon config keys
    "terraform-module": "topic_design",  # module/topic → topic_design
    "scenario": None,            # scenarios are deployment targets, not config
    "reference": None,           # reference implementations are examples
    "script": None,              # operational scripts
    "observability": None,       # observability configs
    "adr": None,                 # ADRs are decisions, not config
}

def check_parity(manifest_path: Path, defaults_path: Path) -> list[str]:
    """Return list of drift strings. Empty = parity confirmed."""
    manifest = yaml.safe_load(manifest_path.read_text())
    defaults = yaml.safe_load(defaults_path.read_text())
    drift = []

    # Check: terraform-module capabilities have matching canon config key
    tf_modules = [c for c in manifest["capabilities"] if c["type"] == "terraform-module"]
    for cap in tf_modules:
        expected_key = _derive_canon_key(cap["id"])
        if expected_key and expected_key not in defaults:
            drift.append(f"MANIFEST has {cap['id']} but canon/base/defaults.yaml missing key: {expected_key}")

    return drift
```

### Golden Test Runner (act harness)

```python
# tests/golden/act/test_golden_act.py
# Source: Mirrors tests/golden/ask/test_golden_ask.py exactly

CASES_DIR = Path(__file__).parent / "cases"
REQUIRED_FIELDS = {
    "id", "request", "expected_artifact", "floor_model",
    "tags", "required_claims", "forbidden_claims", "negative_space"
}

ALL_CASES = sorted(CASES_DIR.glob("*.md")) if CASES_DIR.exists() else []

class TestGoldenActHarnessStructure:
    def test_minimum_case_count(self):
        assert len(ALL_CASES) >= 20

    def test_minimum_negative_space_cases(self):
        neg = [p for p in ALL_CASES if load_case(p).get("negative_space") is True]
        assert len(neg) >= 3  # negative-space cases: no artifact match

    def test_case_id_unique(self):
        ids = [load_case(p).get("id") for p in ALL_CASES]
        ids = [i for i in ids if i is not None]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("case_path", ALL_CASES, ids=lambda p: p.stem)
    def test_case_has_required_fields(self, case_path):
        fm = load_case(case_path)
        missing = REQUIRED_FIELDS - set(fm.keys())
        assert not missing
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Inline Terraform generation by agent | Agent selects existing artifact from MANIFEST | Phase 3a design | ACT-06 requirement |
| Manual validation | Four-gate automated chain | Phase 3a design | ACT-02, ACT-07 |
| Separate /wiki:recommend | Collapsed into /ask --mode reconsolidate | Phase 1 | Pattern to follow |

**Deprecated/outdated:**
- `/wiki:recommend` as separate command: now a thin alias. `/dsp:plan` should NOT follow this deprecated model.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | act_gates.py, check-canon-parity.py | Verified (existing tools run) | 3.9+ | — |
| pytest | Golden harness | Verified (existing harnesses run) | existing | — |
| PyYAML | MANIFEST.yaml parsing | Verified (in requirements.txt) | existing | — |
| @hashicorp/terraform-mcp-server | ACT-01, Gate 3 | npx fetch on demand | latest | — |
| mcp-confluent | Gate 4 | Available via .mcp.json | existing | `--gate-bypass gate4` |
| GitHub Actions | ACT-08 parity CI | Verified (existing workflows present) | existing | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- `@hashicorp/terraform-mcp-server`: fetched via `npx -y` at runtime; no local install required. Gate 3 can also be bypassed with `--gate-bypass confluent_docs_schema` in offline contexts.
- Live mcp-confluent cluster: Gate 4 bypassed with `--gate-bypass mcp_confluent_state` in CI and dev contexts.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, all phases) |
| Config file | `pytest.ini` or `pyproject.toml` (check existing) |
| Quick run command | `pytest tests/golden/act/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ACT-01 | terraform-mcp-server entry in .mcp.json | smoke | `python -c "import json; d=json.load(open('.mcp.json')); assert 'terraform' in d['mcpServers']"` | ❌ Wave 0 |
| ACT-02 | run_gate_chain returns 4 results on passing input | unit | `pytest tests/test_act_gates.py::test_run_gate_chain_all_pass -x` | ❌ Wave 0 |
| ACT-03 | Bypassed gate returns status=skipped | unit | `pytest tests/test_act_gates.py::test_gate_bypass_returns_skipped -x` | ❌ Wave 0 |
| ACT-03 | Fail-fast: gate 1 fail stops chain | unit | `pytest tests/test_act_gates.py::test_fail_fast_on_gate1 -x` | ❌ Wave 0 |
| ACT-04 | dsp-plan.md skill file exists with required steps | smoke | `python -c "from pathlib import Path; assert Path('.claude/commands/dsp-plan.md').exists()"` | ❌ Wave 0 |
| ACT-05 | Golden harness >= 20 cases | structural | `pytest tests/golden/act/test_golden_act.py::TestGoldenActHarnessStructure::test_minimum_case_count -x` | ❌ Wave 0 |
| ACT-05 | Negative-space cases present | structural | `pytest tests/golden/act/test_golden_act.py::TestGoldenActHarnessStructure::test_minimum_negative_space_cases -x` | ❌ Wave 0 |
| ACT-06 | No forbidden Terraform in plan output | structural | `pytest tests/golden/act/ -k "negative_space" -x` | ❌ Wave 0 |
| ACT-07 | Structural correctness >= 95% | structural | `pytest tests/golden/act/ -q` (pass rate threshold) | ❌ Wave 0 |
| ACT-08 | Parity script exits 0 on current state | unit | `pytest tests/test_check_canon_parity.py -x` | ❌ Wave 0 |
| ACT-08 | CI workflow file exists | smoke | `python -c "from pathlib import Path; assert Path('.github/workflows/canon-parity.yml').exists()"` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/golden/act/ -x -q && pytest tests/test_act_gates.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

All test infrastructure for this phase is new:

- [ ] `tests/golden/act/__init__.py` — package marker
- [ ] `tests/golden/act/test_golden_act.py` — structural harness (mirrors test_golden_ask.py)
- [ ] `tests/golden/act/README.md` — case authoring guide
- [ ] `tests/golden/act/cases/` — directory (20+ case files)
- [ ] `tests/test_act_gates.py` — unit tests for act_gates.py functions
- [ ] `tests/test_check_canon_parity.py` — unit tests for parity checker

---

## Open Questions

1. **hashicorp/terraform-mcp-server package name**
   - What we know: CONTEXT.md specifies `hashicorp/terraform-mcp-server` as the official HashiCorp Terraform MCP
   - What's unclear: The exact npm package name for npx invocation (may be `@hashicorp/terraform-mcp-server` or `terraform-mcp-server`)
   - Recommendation: Verify with `npm view @hashicorp/terraform-mcp-server` before writing .mcp.json entry. If not found, check `terraform-mcp-server` (no scope). This is LOW confidence — resolve in Wave 0.

2. **Gate 3 confluent-docs schema validation scope**
   - What we know: Gate 3 validates "the artifact's Terraform/Ansible schema validates against current Confluent docs"
   - What's unclear: Whether gate 3 calls confluent-docs MCP directly or compares against a static schema snapshot
   - Recommendation: Gate 3 should call confluent-docs MCP for Terraform provider resource schemas (e.g., `confluent_kafka_topic` argument list). Use `--gate-bypass confluent_docs_schema` in offline CI. Plan should make this explicit.

3. **fsi-dsp submodule CI access**
   - What we know: fsi-dsp is a git submodule in cflt-ai at `raw/repos/fsi-dsp/`
   - What's unclear: Whether the parity CI workflow in the fsi-dsp repo can reach cflt-ai's canon/base/defaults.yaml
   - Recommendation: Parity CI in fsi-dsp clones cflt-ai (or uses a published artifact of defaults.yaml). The cflt-ai side runs check-canon-parity.py against the submodule. Plan should address both directions explicitly.

---

## Sources

### Primary (HIGH confidence)

- `.planning/phases/03A-act-rail-plan/03A-CONTEXT.md` — all locked decisions, gate architecture, skill interface
- `<repo-root>/tools/review-to-docx.py` — tools/ module pattern, CLI structure, canon.stack usage
- `<repo-root>/canon/stack.py` — resolve_stack(), active_layers(), provenance_footer() signatures
- `<repo-root>/.claude/commands/ask.md` — skill file structure, step organization, flag parsing
- `<repo-root>/tests/golden/ask/test_golden_ask.py` — golden harness pattern, load_case(), parametrize
- `<repo-root>/raw/repos/fsi-dsp/MANIFEST.yaml` — capability IDs, types, 9 roles + 2 modules + scenarios

### Secondary (MEDIUM confidence)

- `<repo-root>/.mcp.json` — existing MCP entry pattern (npx -y, env file pattern)
- `<repo-root>/tools/__init__.py` — hyphenated module registration (clarifies naming convention for new modules)
- `<repo-root>/.planning/STATE.md` — accumulated decisions from all previous phases

### Tertiary (LOW confidence)

- hashicorp/terraform-mcp-server npm package name: assumed `@hashicorp/terraform-mcp-server` based on CONTEXT.md reference; verify before plan execution

---

## Project Constraints (from CLAUDE.md)

| Constraint | Source | Impact on Phase 3a |
|------------|--------|-------------------|
| No inline Terraform generation | REQUIREMENTS.md Out of Scope | Skill step 4 must explicitly refuse to generate `resource` blocks |
| Claude Code is the runtime host through Phase 3 | STATE.md decisions | No custom server; skill files in .claude/commands/ |
| fsi-dsp MANIFEST.yaml is the stable contract | STATE.md decisions | Gate 2 reads MANIFEST only; never inspects raw fsi-dsp file system |
| Phase exits are threshold-gated | STATE.md decisions | ACT-07 >= 95% structural correctness enforced by golden harness before phase complete |
| pytest chosen as test runner | STATE.md decisions | All golden harness tests use pytest; no alternative |
| canon/stack.py uses Optional[List[str]] for Python 3.9 compat | STATE.md decisions | act_gates.py must use Optional[list[str]] not X|Y union syntax |
| fsi-dsp:// URI scheme is stable citation form | STATE.md decisions | Provenance footers in plan output use fsi-dsp:// URIs |
| Activity log per skill invocation | Phases 1+2 pattern | /dsp:plan must append to wiki/activity/YYYY-MM.md |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies are pre-existing; only terraform-mcp-server is new and its npm name needs verification
- Architecture: HIGH — every pattern directly mirrors existing code (ask.md, review-to-docx.py, test_golden_ask.py)
- Pitfalls: HIGH — gate 4 live-cluster dependency and MANIFEST matching ambiguity are concrete and actionable

**Research date:** 2026-04-28
**Valid until:** 2026-07-28 (90 days; stable patterns, no fast-moving dependencies)
