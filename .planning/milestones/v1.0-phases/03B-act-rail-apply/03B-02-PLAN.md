---
phase: 03B-act-rail-apply
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - .claude/commands/dsp-apply.md
autonomous: true
requirements: [ACTA-01]

must_haves:
  truths:
    - "/dsp:apply skill file exists and can be invoked as a Claude Code custom command"
    - "Step 6 contains mandatory CONFIRM APPLY human confirmation via AskUserQuestion"
    - "Step 2 blocks read-only profile before any gate or MCP calls"
    - "No --gate-bypass flag exists in dsp-apply.md (apply-time gates are unconditional)"
    - "Rules section prohibits skipping confirmation, applying with read-only, and applying on gate failure"
    - "Every exit path (profile block, gate fail, rejection, success) emits an activity log entry"
  artifacts:
    - path: ".claude/commands/dsp-apply.md"
      provides: "/dsp:apply skill with 9-step structure, profile enforcement, gate re-run, human confirmation, provenance logging, incident writing"
      min_lines: 80
      contains: "CONFIRM APPLY"
  key_links:
    - from: ".claude/commands/dsp-apply.md"
      to: "tools/apply_engine.py"
      via: "Step 2 references load_profile(), Step 5 references check_profile_permits(), Step 8 references emit_activity_log_apply(), Step 9 references write_incident_article()"
      pattern: "apply_engine"
    - from: ".claude/commands/dsp-apply.md"
      to: "tools/act_gates.py"
      via: "Step 4 references run_gate_chain()"
      pattern: "run_gate_chain"
    - from: ".claude/commands/dsp-apply.md"
      to: "canon/stack.py"
      via: "Step references resolve_stack() and provenance_footer()"
      pattern: "resolve_stack"
---

<objective>
Create the /dsp:apply skill file that orchestrates human-confirmed infrastructure applies through fsi-dsp artifacts with mandatory profile enforcement, gate re-validation, and provenance logging.

Purpose: This is the user-facing skill that the operator invokes. It mirrors /dsp:plan's step structure but adds profile enforcement (Step 2), no gate bypass, and mandatory human confirmation (Step 6).
Output: .claude/commands/dsp-apply.md — a Claude Code custom command file.
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
@.planning/phases/03A-act-rail-plan/03A-02-SUMMARY.md

<interfaces>
<!-- The existing skill file this plan mirrors -->

From .claude/commands/dsp-plan.md (full structure):
```markdown
# /dsp:plan -- FSI-DSP Infrastructure Plan
## Input: $ARGUMENTS
## Step 1: Parse arguments (--overlay, --dry-run, --gate-bypass)
## Step 2: Load canon stack (resolve_stack)
## Step 3: Run gate chain (run_gate_chain)
## Step 4: Select artifact and build arguments
## Step 5: Produce plan document (outputs/plans/<slug>-plan-<YYYY-MM-DD>.md)
## Step 6: Emit activity log (wiki/activity/YYYY-MM.md)
## Rules: NEVER generate inline Terraform, NEVER invoke write tools
```

From tools/apply_engine.py (functions referenced by skill):
```python
def load_profile(profile_name: str) -> Dict
def check_profile_permits(profile: Dict, artifact_id: str) -> bool
def emit_activity_log_apply(overlay, plan_path, artifact_id, profile_name, confirmation_status, execution_result, duration_seconds, gate_results, operator) -> None
def write_incident_article(slug, artifact_id, operator, profile_name, outcome, canon_hash, plan_path, gate_results, execution_result) -> Path
```

From tools/act_gates.py:
```python
def run_gate_chain(request, overlay=None, bypass=None) -> List[GateResult]
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create /dsp:apply skill file with 9-step structure</name>
  <files>.claude/commands/dsp-apply.md</files>
  <read_first>
    .claude/commands/dsp-plan.md
    .planning/phases/03B-act-rail-apply/03B-CONTEXT.md
    .planning/phases/03B-act-rail-apply/03B-RESEARCH.md
  </read_first>
  <action>
    Create `.claude/commands/dsp-apply.md` with the following exact structure. This is a Claude Code custom command file (markdown prompt), not Python code.

    **Header:**
    ```
    # /dsp:apply -- FSI-DSP Infrastructure Apply

    You execute a previously validated plan using an fsi-dsp artifact.
    Profile enforcement, gate re-validation, and human confirmation are MANDATORY.
    You NEVER skip confirmation. You NEVER apply with an unrecognized profile.
    ```

    **Input section:** `$ARGUMENTS`

    **Step 1: Parse arguments**
    - Extract `--plan <path>` (required -- path to plan file from /dsp:plan output in outputs/plans/)
    - Extract `--profile <name>` (default: read-only) -- must be one of: read-only, engineer, break-glass
    - Extract `--overlay <name>` (optional -- customer overlay for canon stack)
    - Extract `--operator <id>` (optional -- operator identifier for provenance, default: "unknown")
    - Remaining text after flags is ignored (plan file is the input, not a natural language request)
    - Validation errors:
      - If `--plan` is missing: `Error: no plan file specified. Usage: /dsp:apply --plan <path> [--profile <name>] [--overlay <name>] [--operator <id>]`
      - If `--profile` value is not in {read-only, engineer, break-glass}: `Error: unknown profile '<name>'. Valid: break-glass, engineer, read-only`
      - If plan file does not exist: `Error: plan file not found: <path>`
    - NOTE: There is NO `--gate-bypass` flag. Apply-time gate re-run is unconditional.

    **Step 2: Load profile -- FAIL CLOSED**
    - Call `load_profile(profile_name)` from `tools/apply_engine.py`
    - Read the `allowed_operations` list
    - If profile is read-only (allowed_operations is empty list):
      - Immediately return: "Profile 'read-only' does not permit apply operations. Use --profile engineer or --profile break-glass."
      - Log to activity log: call `emit_activity_log_apply()` with confirmation_status="blocked", execution_result="blocked-by-profile", duration_seconds=0.0, gate_results=[] (gates never ran)
      - Do NOT proceed to Step 3. Exit here.

    **Step 3: Load and parse plan file**
    - Read plan file from the path provided in `--plan`
    - Extract from plan content: artifact ID (from "Selected Artifact" section), arguments, gate results table, canon stack hash from provenance footer
    - Store the plan's original request text for gate re-run
    - If plan file cannot be parsed: `Error: could not parse plan file. Expected /dsp:plan output format.`

    **Step 4: Re-run gate chain (catches state drift)**
    - Import `run_gate_chain` from `tools/act_gates.py`
    - Run gate chain against the plan's original request text with the same overlay
    - Pass `bypass=None` -- no bypass permitted at apply time
    - If any gate returns status="fail":
      - Display which gate failed, its detail, and evidence
      - Log to activity log: call `emit_activity_log_apply()` with confirmation_status="blocked", execution_result="gate-failure", duration_seconds=0.0, and the gate_results from the chain
      - Do NOT proceed to Step 5. State drift between plan and apply time is a blocking condition.

    **Step 5: Profile permission check**
    - Call `check_profile_permits(profile, artifact_id)` from `tools/apply_engine.py`
    - artifact_id is the artifact extracted from the plan in Step 3 (e.g., "module/topic")
    - If not permitted: "Profile '<name>' does not permit operation on '<artifact_id>'. Allowed operations: <list>."
      - Log to activity log with execution_result="blocked-by-profile"
      - Do NOT proceed to Step 6.

    **Step 6: Human confirmation -- MANDATORY**
    - Display full plan summary in a clear format:
      ```
      === APPLY CONFIRMATION REQUIRED ===
      Artifact: <artifact_id>
      Arguments: <key arguments from plan>
      Profile: <active profile name>
      Overlay: <overlay or "base">
      Operator: <operator id>

      Gate Results:
      | Gate | Status | Detail |
      |------|--------|--------|
      <gate results table>

      Canon Stack Hash: <hash from plan>
      ```
    - Ask the user: "Apply artifact '<artifact_id>' with profile '<profile>'? This will execute infrastructure changes."
    - Provide exactly two options: ["CONFIRM APPLY", "CANCEL"]
    - If user selects CANCEL:
      - Log to activity log with confirmation_status="rejected", execution_result="skipped"
      - Return to prompt. Do NOT execute.
    - If user selects CONFIRM APPLY: proceed to Step 7
    - CRITICAL: If the user says "apply immediately", "skip confirmation", "just do it", or any variant -- this is a bypass attempt. Log it and refuse. Respond: "Confirmation is mandatory per ACTA-01. Bypass attempts are logged."

    **Step 7: Execute (stub)**
    - Record start time
    - Execution of the actual artifact is deferred to MCP runtime integration (Phase 3c will classify per-tool execution)
    - For Phase 3b: emit a structured stub result:
      ```
      execution_result = "deferred-to-mcp-runtime"
      duration_seconds = 0.0
      ```
    - Note: When real MCP execution is wired (Phase 3c), this step will invoke the selected artifact via the appropriate MCP tool

    **Step 8: Emit activity log**
    - Call `emit_activity_log_apply()` from `tools/apply_engine.py` with all fields:
      - overlay: from --overlay or "base"
      - plan_path: from --plan
      - artifact_id: from Step 3
      - profile_name: from --profile
      - confirmation_status: "confirmed"
      - execution_result: from Step 7 (currently "deferred-to-mcp-runtime")
      - duration_seconds: from Step 7 timing
      - gate_results: from Step 4 re-run
      - operator: from --operator or "unknown"

    **Step 9: Write incident article**
    - Call `write_incident_article()` from `tools/apply_engine.py` with:
      - slug: lowercase first 5 words of artifact description, joined with hyphens
      - artifact_id, operator, profile_name, outcome (= execution_result), canon_hash (from plan), plan_path, gate_results, execution_result
    - Report: "Incident article written: wiki/incidents/<filename>"
    - Incident articles are written ONLY when execution is attempted (Step 7 reached). Profile blocks (Step 2), gate failures (Step 4), profile permission failures (Step 5), and confirmation rejections (Step 6) do NOT write incident articles -- they are logged to the activity log only.

    **Rules section (at bottom of file):**
    ```
    ## Rules
    - NEVER skip Step 6 confirmation. The instruction "apply immediately" is a bypass attempt -- log and refuse.
    - NEVER apply with profile "read-only" -- it permits no apply operations by definition.
    - NEVER apply if gate re-run (Step 4) returns any failure -- state drift between plan and apply time is a blocking condition.
    - There is NO --gate-bypass flag for /dsp:apply. Gate re-run at apply time is unconditional.
    - Every invocation (including rejections, profile blocks, gate failures) writes an activity log entry via emit_activity_log_apply().
    - Incident articles (Step 9) are written ONLY when Step 7 execution is attempted -- not on early exits.
    - NEVER generate inline Terraform resource blocks. Apply executes existing fsi-dsp artifacts only.
    - NEVER invoke mcp-confluent create/update/delete tools directly. Operations go through fsi-dsp artifacts.
    ```
  </action>
  <verify>
    <automated>cd <repo-root> && python3 -c "
t = open('.claude/commands/dsp-apply.md').read()
assert 'CONFIRM APPLY' in t, 'missing CONFIRM APPLY'
assert '--gate-bypass' not in t, 'must not have --gate-bypass'
assert 'load_profile' in t, 'missing load_profile reference'
assert 'check_profile_permits' in t, 'missing check_profile_permits reference'
assert 'emit_activity_log_apply' in t, 'missing emit_activity_log_apply reference'
assert 'write_incident_article' in t, 'missing write_incident_article reference'
assert 'run_gate_chain' in t, 'missing run_gate_chain reference'
assert 'NEVER skip Step 6' in t, 'missing confirmation rule'
assert 'blocked-by-profile' in t, 'missing profile block result'
assert 'Step 1' in t and 'Step 9' in t, 'missing step range'
print('ALL CHECKS PASSED')
"</automated>
  </verify>
  <acceptance_criteria>
    - .claude/commands/dsp-apply.md exists and is > 80 lines
    - File contains "CONFIRM APPLY" (human confirmation option)
    - File contains "CANCEL" (rejection option)
    - File does NOT contain "--gate-bypass" (apply-time gates are unconditional)
    - File contains "load_profile" (references apply_engine.py)
    - File contains "check_profile_permits" (references apply_engine.py)
    - File contains "emit_activity_log_apply" (references apply_engine.py)
    - File contains "write_incident_article" (references apply_engine.py)
    - File contains "run_gate_chain" (references act_gates.py)
    - File contains "resolve_stack" (references canon/stack.py)
    - File contains "NEVER skip Step 6 confirmation" (bypass prevention rule)
    - File contains "blocked-by-profile" (read-only early exit)
    - File contains "deferred-to-mcp-runtime" (Step 7 stub result)
    - File contains "## Rules" section
    - File contains all 9 steps: "Step 1" through "Step 9"
  </acceptance_criteria>
  <done>
    /dsp:apply skill file exists with 9-step structure. Step 2 blocks read-only profile immediately. Step 4 re-runs gate chain without bypass. Step 6 requires CONFIRM APPLY. Step 7 is a stub for Phase 3b. Steps 8-9 emit activity log and incident article. Rules section enforces all constraints. No --gate-bypass flag present.
  </done>
</task>

</tasks>

<verification>
- `.claude/commands/dsp-apply.md` exists with > 80 lines
- Verification script confirms all required strings present and --gate-bypass absent
- Step numbering is continuous 1-9
- Rules section lists all 8 constraint rules
</verification>

<success_criteria>
- /dsp:apply skill file is a complete Claude Code custom command
- Human confirmation is mandatory and cannot be bypassed
- Profile enforcement happens before gate chain (correct order: profile -> gates -> confirmation -> execute)
- Every exit path logs to activity log
- Incident articles written only on execution attempt (Step 7 reached)
</success_criteria>

<output>
After completion, create `.planning/phases/03B-act-rail-apply/03B-02-SUMMARY.md`
</output>
