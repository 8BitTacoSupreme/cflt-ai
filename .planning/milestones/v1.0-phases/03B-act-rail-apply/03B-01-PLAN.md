---
phase: 03B-act-rail-apply
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/profiles/read-only.json
  - tools/profiles/engineer.json
  - tools/profiles/break-glass.json
  - tools/apply_engine.py
  - tests/test_apply_engine.py
autonomous: true
requirements: [ACTA-02, ACTA-03, ACTA-04, ACTA-05]

must_haves:
  truths:
    - "Unknown profile names raise ValueError immediately (fail-closed)"
    - "read-only profile permits zero apply operations"
    - "engineer profile permits standard modules (module/topic, module/flink, role/*)"
    - "break-glass profile permits all operations via wildcard"
    - "Activity log append writes /dsp:apply entries with operator, profile, confirmation_status, execution_result, duration_seconds"
    - "Incident article creates wiki/incidents/<slug>-<YYYY-MM-DD>.md with frontmatter and four sections"
    - "apply_engine.py source contains no bypass patterns (no input(), skip_confirmation, bypass_confirmation)"
  artifacts:
    - path: "tools/profiles/read-only.json"
      provides: "Read-only policy profile — empty allowed_operations"
      contains: '"allowed_operations": []'
    - path: "tools/profiles/engineer.json"
      provides: "Engineer policy profile — standard non-destructive modules"
      contains: '"module/topic"'
    - path: "tools/profiles/break-glass.json"
      provides: "Break-glass policy profile — wildcard all operations"
      contains: '"*"'
    - path: "tools/apply_engine.py"
      provides: "Apply engine: load_profile, check_profile_permits, emit_activity_log_apply, write_incident_article"
      exports: ["load_profile", "check_profile_permits", "emit_activity_log_apply", "write_incident_article"]
      min_lines: 80
    - path: "tests/test_apply_engine.py"
      provides: "Unit tests for apply engine — profile loading, enforcement, activity log, incident article, bypass prevention"
      min_lines: 100
  key_links:
    - from: "tools/apply_engine.py"
      to: "tools/profiles/*.json"
      via: "json.loads(profile_path.read_text())"
      pattern: "PROFILES_DIR.*\\.json"
    - from: "tools/apply_engine.py"
      to: "wiki/activity/YYYY-MM.md"
      via: "emit_activity_log_apply appends apply entry"
      pattern: "wiki.*activity"
    - from: "tools/apply_engine.py"
      to: "wiki/incidents/"
      via: "write_incident_article creates per-apply article"
      pattern: "wiki.*incidents"
    - from: "tools/apply_engine.py"
      to: "canon/stack.py"
      via: "import active_layers for provenance"
      pattern: "from canon\\.stack import"
---

<objective>
Build the apply engine module and three policy profile files that enforce least-privilege access control for /dsp:apply operations, with full provenance logging and wiki incident article generation.

Purpose: This is the core infrastructure for Phase 3b — every other deliverable (skill file, golden harness) depends on these profile files and engine functions.
Output: tools/profiles/ directory with 3 JSON files, tools/apply_engine.py with 4 exported functions, tests/test_apply_engine.py with comprehensive unit tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03B-act-rail-apply/03B-CONTEXT.md
@.planning/phases/03B-act-rail-apply/03B-RESEARCH.md

# Prior phase artifacts this plan builds on
@.planning/phases/03A-act-rail-plan/03A-01-SUMMARY.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From tools/act_gates.py (lines 26-48):
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from canon.stack import resolve_stack

GATE_NAMES: List[str] = ["canon_compliance", "fsi_dsp_coverage", "confluent_docs_schema", "mcp_confluent_state"]
GateResult = Dict  # Dict with keys: gate (str), status (str), detail (str), evidence (list)
```

From tools/act_gates.py (lines 323-366):
```python
def run_gate_chain(
    request: str,
    overlay: Optional[str] = None,
    bypass: Optional[List[str]] = None,
) -> List[GateResult]:
    """Execute the four-gate validation chain. Fail-fast."""
```

From canon/stack.py (lines 53-110):
```python
def resolve_stack(layers=None, customer=None, engagement=None) -> Tuple[Dict, str]:
    """Returns (merged_config_dict, sha256_hex_hash)."""

def active_layers() -> List[str]:
    """Return list of layers that have config files present."""

def provenance_footer() -> str:
    """Generate a provenance footer string for artifact embedding."""
```

From wiki/activity/2026-04.md (existing entry format):
```markdown
## 2026-04-28T00:00:00Z
**Skill:** /gsd:map-codebase
**Overlay:** base
**Input:** cflt-ai repository (initial codebase mapping)
**Output:** .planning/codebase/*.md
**Canon stack:** base
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create profile JSON files and apply_engine.py with TDD unit tests</name>
  <files>
    tools/profiles/read-only.json
    tools/profiles/engineer.json
    tools/profiles/break-glass.json
    tools/apply_engine.py
    tests/test_apply_engine.py
  </files>
  <read_first>
    tools/act_gates.py
    canon/stack.py
    wiki/activity/2026-04.md
    tests/test_act_gates.py
  </read_first>
  <behavior>
    Profile Loading (ACTA-03):
    - load_profile("read-only") returns dict with name="read-only", allowed_operations=[]
    - load_profile("engineer") returns dict with name="engineer", allowed_operations containing "module/topic", "module/flink", "role/cp_schema", "role/cp_rbac", "role/cp_connect"
    - load_profile("break-glass") returns dict with name="break-glass", allowed_operations=["*"]
    - load_profile("admin") raises ValueError mentioning "Unknown profile"
    - load_profile("") raises ValueError

    Profile Enforcement (ACTA-03):
    - check_profile_permits(read_only_profile, "module/topic") returns False
    - check_profile_permits(engineer_profile, "module/topic") returns True
    - check_profile_permits(engineer_profile, "script/fsi-dr") returns False (not in engineer list)
    - check_profile_permits(break_glass_profile, "module/topic") returns True (wildcard)
    - check_profile_permits(break_glass_profile, "anything") returns True (wildcard)

    Activity Log (ACTA-04):
    - emit_activity_log_apply writes to wiki/activity/YYYY-MM.md
    - Entry contains "**Skill:** /dsp:apply"
    - Entry contains "**Operator:**", "**Profile:**", "**Confirmation status:**", "**Execution result:**", "**Duration seconds:**"
    - Creates log file if it does not exist
    - Appends to existing log file if it exists

    Incident Article (ACTA-05):
    - write_incident_article returns a Path to wiki/incidents/<slug>-<YYYY-MM-DD>.md
    - Article contains YAML frontmatter with keys: artifact, operator, profile, outcome, canon_hash, plan_ref, timestamp
    - Article contains sections: "## What Changed", "## Why", "## Gate Results", "## Provenance"
    - Gate results section contains a markdown table with Gate/Status/Detail columns

    Bypass Prevention (ACTA-02):
    - apply_engine.py source does not contain "input("
    - apply_engine.py source does not contain "skip_confirmation"
    - apply_engine.py source does not contain "bypass_confirmation"
  </behavior>
  <action>
    **Step 1: Create tools/profiles/ directory with three JSON files.**

    tools/profiles/read-only.json:
    ```json
    {
      "name": "read-only",
      "description": "Plan and inspect only. No apply operations.",
      "allowed_operations": []
    }
    ```

    tools/profiles/engineer.json:
    ```json
    {
      "name": "engineer",
      "description": "Plan + apply standard non-destructive modules (topics, schemas, RBAC, Flink).",
      "allowed_operations": ["module/topic", "module/flink", "role/cp_schema", "role/cp_rbac", "role/cp_connect"]
    }
    ```

    tools/profiles/break-glass.json:
    ```json
    {
      "name": "break-glass",
      "description": "All operations including destructive (DR failover, cluster reconfig, deletion).",
      "allowed_operations": ["*"]
    }
    ```

    **Step 2: Write tests/test_apply_engine.py FIRST (RED).**

    Mirror test_act_gates.py structure exactly: PROJECT_ROOT + sys.path.insert pattern, test classes per concern. Classes:
    - TestProfileLoading: test_load_known_profiles, test_unknown_profile_raises, test_empty_profile_raises
    - TestProfileFiles: test_readonly_permits_nothing, test_engineer_permits_standard_modules, test_break_glass_permits_all, test_engineer_denies_destructive
    - TestProfileEnforcement: test_permit_exact_match, test_deny_unknown_artifact, test_wildcard_permits_all, test_empty_list_denies_all
    - TestActivityLog: test_emit_creates_file, test_emit_appends_to_existing, test_entry_contains_apply_fields (check for Skill, Operator, Profile, Confirmation status, Execution result, Duration seconds)
    - TestIncidentArticle: test_creates_file, test_frontmatter_keys (artifact, operator, profile, outcome, canon_hash, plan_ref, timestamp), test_incident_sections (What Changed, Why, Gate Results, Provenance), test_gate_results_table
    - TestBypassPrevention: test_no_input_call, test_no_skip_confirmation, test_no_bypass_confirmation (source scan of apply_engine.py)

    Use tmp_path fixture for activity log and incident tests. Do NOT use wiki/ directly — write to tmp_path and override PROJECT_ROOT in tests.

    **Step 3: Create tools/apply_engine.py (GREEN).**

    Follow act_gates.py pattern exactly:
    - Lines 1-5: shebang + docstring referencing ACTA-01 through ACTA-05
    - Lines 6-12: imports (json, time, datetime, pathlib, typing, yaml, sys)
    - Lines 13-16: PROJECT_ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(PROJECT_ROOT))
    - Line 17: from canon.stack import active_layers
    - Lines 18-20: Constants — PROFILES_DIR = PROJECT_ROOT / "tools" / "profiles"; VALID_PROFILES = {"read-only", "engineer", "break-glass"}

    Functions to implement:
    1. load_profile(profile_name: str) -> Dict — validate name in VALID_PROFILES, load JSON, return dict. Raise ValueError on unknown.
    2. check_profile_permits(profile: Dict, artifact_id: str) -> bool — check allowed_operations list. "*" permits all. Empty list denies all. Exact match on artifact_id.
    3. emit_activity_log_apply(overlay, plan_path, artifact_id, profile_name, confirmation_status, execution_result, duration_seconds, gate_results, operator) -> None — append formatted entry to wiki/activity/YYYY-MM.md. Create file with header if missing. Entry includes all 11 fields from CONTEXT.md apply entry format.
    4. write_incident_article(slug, artifact_id, operator, profile_name, outcome, canon_hash, plan_path, gate_results, execution_result) -> Path — write wiki/incidents/<slug>-<YYYY-MM-DD>.md. Create directory if missing. Article has YAML frontmatter (7 keys) + 4 sections.

    Add CLI __main__ block with argparse (matches act_gates.py convention). No input() calls anywhere.

    Use Optional[str], List[Dict] from typing (Python 3.9 compat per STATE.md decision). Never use X|Y union syntax.
  </action>
  <verify>
    <automated>cd <repo-root> && python3 -m pytest tests/test_apply_engine.py -v --tb=short -q</automated>
  </verify>
  <acceptance_criteria>
    - tools/profiles/read-only.json contains '"allowed_operations": []'
    - tools/profiles/engineer.json contains '"module/topic"' and '"module/flink"' and '"role/cp_schema"'
    - tools/profiles/break-glass.json contains '"*"'
    - tools/apply_engine.py contains 'def load_profile('
    - tools/apply_engine.py contains 'def check_profile_permits('
    - tools/apply_engine.py contains 'def emit_activity_log_apply('
    - tools/apply_engine.py contains 'def write_incident_article('
    - tools/apply_engine.py contains 'from canon.stack import active_layers'
    - tools/apply_engine.py contains 'VALID_PROFILES'
    - tools/apply_engine.py does NOT contain 'input('
    - tools/apply_engine.py does NOT contain 'skip_confirmation'
    - tests/test_apply_engine.py contains 'class TestProfileLoading'
    - tests/test_apply_engine.py contains 'class TestBypassPrevention'
    - tests/test_apply_engine.py contains 'class TestIncidentArticle'
    - tests/test_apply_engine.py contains 'class TestActivityLog'
    - python3 -m pytest tests/test_apply_engine.py -v exits 0
    - python3 -c "from tools.apply_engine import load_profile, check_profile_permits" exits 0
  </acceptance_criteria>
  <done>
    Three profile JSON files exist in tools/profiles/ with correct schemas. apply_engine.py exports four functions (load_profile, check_profile_permits, emit_activity_log_apply, write_incident_article). All unit tests pass. No bypass patterns present in source. Import from tools.apply_engine succeeds.
  </done>
</task>

</tasks>

<verification>
- `python3 -m pytest tests/test_apply_engine.py -v --tb=short -q` — all tests pass
- `python3 -c "from tools.apply_engine import load_profile; p = load_profile('engineer'); print(p['allowed_operations'])"` — prints list with module/topic
- `python3 -c "import json; d = json.load(open('tools/profiles/read-only.json')); assert d['allowed_operations'] == []; print('OK')"` — prints OK
- `python3 -m pytest tests/ -v --tb=short -q` — full suite green (existing 524 + new tests)
</verification>

<success_criteria>
- Profile files load without error and enforce least-privilege semantics
- Activity log appends work for both new and existing log files
- Incident articles are created with full frontmatter and four required sections
- Zero bypass patterns in apply_engine.py source
- Full test suite remains green
</success_criteria>

<output>
After completion, create `.planning/phases/03B-act-rail-apply/03B-01-SUMMARY.md`
</output>
