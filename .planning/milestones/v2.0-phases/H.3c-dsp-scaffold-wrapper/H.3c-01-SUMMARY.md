---
phase: H.3c-dsp-scaffold-wrapper
plan: 01
subsystem: dsp-scaffold
tags: [scaffold, profile-gating, canon-overlay, provenance, fsi-dsp, wrapper]
dependency_graph:
  requires:
    - H.3a-01 (streaming-skills-plugin install + canon-overlay article)
    - H.3b-01 (vendor-sources.json pin + drift gate; provenance reads commit/version)
    - H.4a-01 (profile-family schema; check_skill_permitted contract)
    - H.4b-01 (developer/sandbox profile; canon/stack.py family+canon_layer kwargs)
    - H.4c-01 (acme-bank developer overlay; --overlay routing in load_profile)
  provides:
    - "/dsp:scaffold skill (.claude/commands/dsp-scaffold.md)"
    - "tools/scaffold_engine.py orchestrator (triage + 3 gates + output + activity log)"
    - "outputs/scaffolded/<artifact-type>-<name>-<timestamp>/ artifact proposal directory"
    - "manifest-entry.yaml shape for fsi-dsp MANIFEST.yaml capabilities[] proposals"
    - "scaffolded-producer canon-compliant Python producer template (acks/compression/idempotence inlined)"
  affects:
    - "tools/profiles/read-only.json (gains skill_blocklist defense-in-depth)"
    - "raw/repos/fsi-dsp (proposed entry only — no submodule edits this phase)"
tech_stack:
  added:
    - "PyYAML (already a project dep; first use in scaffold_engine)"
  patterns:
    - "Three-gate sequence: skill blocklist → read-only operator → cross-family canon refusal"
    - "Provenance footer schema with upstream-plugin pin (operator + profile + canon_stack_hash + upstream commit SHA)"
    - "Activity log append per ACTA-04 for every invocation (success, blocked, not-implemented)"
key_files:
  created:
    - .claude/commands/dsp-scaffold.md
    - tools/scaffold_engine.py
    - tests/test_scaffold_engine.py
    - .planning/phases/H.3c-dsp-scaffold-wrapper/H.3c-01-SUMMARY.md
  modified:
    - tools/profiles/read-only.json
    - .gitignore
decisions:
  - "Three-gate sequence ordered skill-blocklist → read-only → cross-family; gate priority matters for activity-log granularity"
  - "scaffold_dir provenance field uses _safe_relative() fallback to absolute path when tmp_path lives outside PROJECT_ROOT (test isolation requirement)"
  - "Producer stub generator reads resolved canon dict (acks, compression, idempotence, sr format, auth) — proves end-to-end canon-stack wiring without invoking upstream skill's interactive HARD-GATE flow"
  - "Activity log entries written even on blocked/not-implemented paths — audit trail completeness over silence"
metrics:
  duration_minutes: 6
  completed_date: 2026-05-17
  tasks: 6
  files_changed: 6
  tests_added: 8
---

# Phase H.3c Plan 01: /dsp:scaffold Wrapper Summary

`/dsp:scaffold` lands as a cflt-ai skill that wraps streaming-skills-plugin upstream skills + applies the active profile-family canon overlay + materializes the output as a canon-compliant fsi-dsp artifact proposal (MANIFEST entry + provenance.json + activity log entry).

## What Landed

- **`.claude/commands/dsp-scaffold.md`** — /dsp:scaffold skill specification (numbered Step structure mirroring /dsp:apply; 69 lines)
- **`tools/scaffold_engine.py`** — 502-line orchestrator: triage (5 artifact-types, producer fully implemented), three gates (skill blocklist, read-only operator, cross-family canon refusal), output generator (provenance.json + manifest-entry.yaml + scaffold/producer.py + scaffold/config.json + README.md), activity-log emitter, CLI entry point with explicit exit codes (0/10/11/20)
- **`tools/profiles/read-only.json`** — Gained `skill_blocklist: ["dsp-scaffold"]` defense-in-depth alongside existing empty `allowed_operations`
- **`tests/test_scaffold_engine.py`** — 8 test cases covering all 5 outcomes + triage table sanity + provenance round-trip + YAML validity
- **`.gitignore`** — Added `outputs/scaffolded/` exclusion (audit trail lives in wiki/activity/, not the file tree)

## Requirements Satisfied

- **SCAF-01** ✅ — `/dsp:scaffold` skill exists; end-to-end for `producer` artifact-type (developer-sandbox happy path + engineer --prod happy path proven)
- **SCAF-02** ✅ — manifest-entry.yaml emitted with full provenance (operator, profile, canon-stack hash, timestamp, upstream-skill version, upstream commit SHA, canon family) — 15 keys per D-08
- **SCAF-03** ✅ — Profile-gated + activity-logged; fail-closed under read-only AND under cross-family --prod request (proven by negative-space tests)

## ROADMAP H.3c Success Criteria

1. ✅ /dsp:scaffold runs end-to-end for `producer` artifact-type. `developer/sandbox` → success; scaffold dir contains producer.py + config.json + manifest-entry.yaml + provenance.json + README.md.
2. ✅ Scaffolded output appears as a MANIFEST.yaml capability entry proposal (`outputs/scaffolded/<...>/manifest-entry.yaml`; manual review-then-PR into fsi-dsp).
3. ✅ /dsp:scaffold refuses to run under `read-only` profile (exit 10, `blocked-by-profile`) AND refuses to scaffold a prod-canon artifact under `developer-sandbox` profile (exit 11, `blocked-by-canon-family`). Negative-space tests prove fail-closed.

## Regression Results

| Suite | Result |
| ----- | ------ |
| `pytest tests/test_scaffold_engine.py` | 8/8 PASS |
| `pytest tests/test_profile_gating.py tests/test_per_family_isolation.py tests/test_canon_overlay.py tests/test_check_streaming_skills_drift.py tests/test_scaffold_engine.py` | 236/236 PASS |
| `pytest tests/golden/` | 539/539 PASS |
| `pytest tests/` (full) | 959 PASS, 2 pre-existing failures (test_check_canon_parity, test_manifest — same as H.4a/H.4b/H.4c/H.3b baseline) |
| Live smoke: `python3 tools/scaffold_engine.py producer demo --profile developer/sandbox --operator h3c-smoke --dry-run` | exit 0, prints DRY RUN message |

## H.3 Sub-Phase Set Complete

- **H.3a** ✅ — Plugin install + canon-overlay wiki article
- **H.3b** ✅ — Version pin + CI drift gate
- **H.3c** ✅ — /dsp:scaffold wrapper

H.3 satisfies: **INST-01** (install + pin + CI gate), **CAN-OVR-01** (overlay article), **SCAF-01/02/03** (scaffold wrapper + MANIFEST entry + profile gating) — 5 of 5 H.3-tagged requirements.

## v2.0 Milestone Complete

All 8 v2.0 phases complete: H.1 ✅ H.2 ✅ H.3a ✅ H.4a ✅ H.4b ✅ H.4c ✅ H.3b ✅ H.3c ✅.

All 16 v2.0 requirements satisfied (WIKI-06/07/08, EVAL-01/02/03, INST-01, CAN-OVR-01, SCAF-01/02/03, PROFAM-01/02, DEVPROF-01/02, DEVCAN-01).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `scaffold_dir.relative_to(PROJECT_ROOT)` raised ValueError under test isolation**
- **Found during:** Task 5 (first pytest run)
- **Issue:** When the test fixture monkeypatches `OUTPUT_ROOT` to a `tmp_path` outside the repo, `Path.relative_to()` raises `ValueError: '... is not in the subpath of <repo-root>'`. Four tests failed because of this.
- **Fix:** Added `_safe_relative(path)` helper in `tools/scaffold_engine.py` that returns the relative-to-PROJECT_ROOT path when possible, else the absolute path. The provenance field is always populated and machine-readable in both production and test isolation contexts.
- **Files modified:** `tools/scaffold_engine.py`
- **Commit:** Same as test commit (`f25773f` — `test(H.3c-01)`)

**2. [Rule 3 - Blocking] sys.path needed for direct script invocation**
- **Found during:** Task 1 (first `--help` invocation)
- **Issue:** `python3 tools/scaffold_engine.py --help` raised `ModuleNotFoundError: No module named 'tools'` because the script wasn't being run as a package — same constraint as `tools/apply_engine.py` already handles via `sys.path.insert`.
- **Fix:** Added the matching `sys.path.insert(0, str(_PROJECT_ROOT))` block at module top before the `tools.apply_engine` and `canon.stack` imports.
- **Files modified:** `tools/scaffold_engine.py`
- **Commit:** Folded into the original Task 1 commit (`41a54dd` — `feat(H.3c-01): add tools/scaffold_engine.py`)

### Test count

D-11 specified 7 test cases; landed with 8 (added `test_manifest_entry_yaml_is_valid` as a natural sanity check on the proposed MANIFEST shape).

## Deferred (post-H.3c)

- Implement scaffold paths for `consumer`, `kafka-streams-app`, `schema`, `cdc-pipeline` — each a follow-on phase using the corresponding upstream skill from `ARTIFACT_TYPE_TO_SKILL`.
- Auto-PR-against-fsi-dsp for `manifest-entry.yaml` — currently manual.
- `scaffolded-producer` executor in fsi-dsp — needed before `/dsp:apply` can consume scaffolded artifacts.
- Eval cases for `/dsp:scaffold` via H.2 harness — covered by future H.2 extension PR.
- Real upstream-skill interactive invocation (instead of the stub generator) — requires interactive Claude Code session; H.3c's stub proves end-to-end wiring without the HARD-GATE prompt.

## Self-Check: PASSED

- `.claude/commands/dsp-scaffold.md` — FOUND
- `tools/scaffold_engine.py` — FOUND
- `tools/profiles/read-only.json` — FOUND (with skill_blocklist)
- `tests/test_scaffold_engine.py` — FOUND
- `.gitignore` — FOUND (with outputs/scaffolded/)
- Commits `41a54dd`, `96f38ce`, `5c6e03f`, `258819e`, `f25773f` — all present on `main`
- Live smoke test — exit 0 confirmed
