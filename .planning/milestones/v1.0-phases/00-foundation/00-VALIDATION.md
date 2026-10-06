---
phase: 0
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-28
---

# Phase 0 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (Python tools) + bash assertions (CI/manifest) |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python tools/wiki-stats.py && python tools/wiki-lint.py` |
| **Full suite command** | `python tools/wiki-stats.py && python tools/wiki-lint.py && python tools/check-citations.py` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python tools/wiki-stats.py && python tools/wiki-lint.py`
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 0-01-01 | 01 | 1 | HYG-01 | functional | `python tools/wiki-stats.py` | ❌ W0 | ⬜ pending |
| 0-01-02 | 01 | 1 | HYG-02 | functional | `python tools/wiki-lint.py` | ❌ W0 | ⬜ pending |
| 0-01-03 | 01 | 1 | HYG-03 | functional | `grep -r '\\.\\.\\.' .claude/skills/` | ❌ W0 | ⬜ pending |
| 0-02-01 | 02 | 1 | HYG-04 | functional | `cd <repo-root> && flox activate -- echo ok` | ✅ | ⬜ pending |
| 0-02-02 | 02 | 1 | HYG-05 | functional | `cd raw/repos/fsi-dsp && flox activate -- echo ok` | ❌ W0 | ⬜ pending |
| 0-03-01 | 03 | 2 | CNTR-01 | structural | `test -f raw/repos/fsi-dsp/MANIFEST.yaml` | ❌ W0 | ⬜ pending |
| 0-03-02 | 03 | 2 | CNTR-02 | structural | `python -c "import yaml; yaml.safe_load(open('raw/repos/fsi-dsp/MANIFEST.yaml'))"` | ❌ W0 | ⬜ pending |
| 0-04-01 | 04 | 2 | CANST-01 | structural | `test -d canon/base` | ❌ W0 | ⬜ pending |
| 0-04-02 | 04 | 2 | CANST-02 | structural | `test -f canon/base/defaults.yaml` | ❌ W0 | ⬜ pending |
| 0-05-01 | 05 | 3 | WIKI-01 | functional | `test -f wiki/linuxone-*.md` | ❌ W0 | ⬜ pending |
| 0-05-02 | 05 | 3 | WIKI-02 | structural | `test -d activity-log` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Python tools run without crashes (HYG-01, HYG-02, HYG-03 bug fixes)
- [ ] Flox manifests in both repos (HYG-04, HYG-05)
- [ ] PyYAML available for MANIFEST.yaml validation

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fresh git clone produces working env | HYG-04/HYG-05 | Requires clean clone | `git clone` in temp dir, run `flox activate` |
| CI blocks drift PRs | CNTR-04/CNTR-05 | Requires GitHub Actions | Push test PR with broken manifest ID |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
