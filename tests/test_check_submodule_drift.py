"""
Phase 09-02 — Unit tests for tools/check_submodule_drift.py.

Mocks the small `_git_*` helpers via monkeypatch so failure-path tests never
shell out. The fresh-pointer test exercises the real SHA-match early-return
against the live submodule (Phase 09-01 just bumped raw/repos/fsi-dsp to
upstream main HEAD, so committed_sha == upstream_sha and timestamp logic is
short-circuited — no network call needed for that path).

Mirrors tests/test_check_streaming_skills_drift.py shape: real CI workflow
run is the only place real network calls happen.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools import check_submodule_drift as drift_mod  # noqa: E402


# Real committed SHA on the submodule (post-09-01 bump). The fresh-pointer
# test uses the real subprocess so we exercise the SHA-match early-return
# without network.
LIVE_SUBMODULE_SHA = "5a86fd28935d4732f22ea139634987769777faf8"


# ---------------------------------------------------------------------------
# Test 6: Module exposes the documented exit-code + window constants
# ---------------------------------------------------------------------------
def test_module_exposes_exit_code_and_window_constants():
    """Public contract: exit codes 0/1/2/3 and the 14-day window are constants."""
    assert drift_mod.EXIT_OK == 0
    assert drift_mod.EXIT_DRIFT == 1
    assert drift_mod.EXIT_CONFIG_ERR == 2
    assert drift_mod.EXIT_TRANSIENT_ERR == 3
    assert drift_mod.DRIFT_WINDOW_DAYS == 14


# ---------------------------------------------------------------------------
# Test 1: Fresh pointer — SHAs match, exit OK
# ---------------------------------------------------------------------------
def test_fresh_pointer_within_window_exits_zero():
    """
    Live submodule SHA equals upstream main HEAD (Phase 09-01 just bumped).
    check_drift() should hit the SHA-match early-return and exit 0 without
    needing the timestamp branch.

    This is the real-network-touching test: it calls git ls-remote against
    the submodule's origin (network required). Skip cleanly if offline.
    """
    code, msg = drift_mod.check_drift()
    if code == drift_mod.EXIT_TRANSIENT_ERR:
        pytest.skip(f"network unavailable for live ls-remote: {msg}")
    assert code == drift_mod.EXIT_OK, f"expected fresh pointer to pass; got: {msg}"
    assert "OK" in msg


# ---------------------------------------------------------------------------
# Test 2: Stale pointer — SHAs differ + >14d behind → exit DRIFT with remediation
# ---------------------------------------------------------------------------
def test_stale_pointer_beyond_window_returns_drift_with_remediation(monkeypatch):
    """
    Force a SHA mismatch and a 15-day-old upstream timestamp by stubbing the
    internal helpers; assert the returned tuple carries EXIT_DRIFT and the
    exact remediation command per ROADMAP success criterion 3.
    """
    committed_sha = "1111111111111111111111111111111111111111"
    upstream_sha = "2222222222222222222222222222222222222222"

    # The committed pointer was authored 15 days BEFORE upstream HEAD.
    upstream_ts = 1_700_000_000
    committed_ts = upstream_ts - (15 * 86400)
    timestamps = {committed_sha: committed_ts, upstream_sha: upstream_ts}

    monkeypatch.setattr(drift_mod, "_git_rev_parse_submodule_sha",
                        lambda submodule_path: committed_sha)
    monkeypatch.setattr(drift_mod, "_git_ls_remote",
                        lambda submodule_path, remote, branch: upstream_sha)
    monkeypatch.setattr(drift_mod, "_git_show_timestamp",
                        lambda submodule_path, sha: timestamps[sha])

    code, msg = drift_mod.check_drift()

    assert code == drift_mod.EXIT_DRIFT, f"expected EXIT_DRIFT; got code={code}, msg={msg}"
    assert "stale" in msg.lower(), f"message must mention 'stale': {msg!r}"
    # ROADMAP success criterion 3: exact remediation command must appear.
    assert "git submodule update --remote raw/repos/fsi-dsp" in msg
    assert "git add raw/repos/fsi-dsp" in msg
    assert "git commit" in msg


# ---------------------------------------------------------------------------
# Test 2b: Pointer AHEAD of upstream — SHAs differ, pointer newer → exit OK
# ---------------------------------------------------------------------------
def test_pointer_ahead_of_upstream_is_not_stale(monkeypatch):
    """
    Regression for the 2026-10-07 false positive: raw/repos/fsi-dsp was pinned
    to a feature-branch commit four commits AHEAD of upstream main, whose HEAD
    had not moved in 134 days. The gate measured `now - upstream_ts` (how long
    since upstream main last moved) and reported STALE. Drift is a property of
    the pointer relative to upstream, so a pointer newer than upstream HEAD can
    never be stale.
    """
    committed_sha = "1111111111111111111111111111111111111111"
    upstream_sha = "2222222222222222222222222222222222222222"

    upstream_ts = 1_700_000_000
    committed_ts = upstream_ts + (134 * 86400)   # pointer is 134 days NEWER
    timestamps = {committed_sha: committed_ts, upstream_sha: upstream_ts}

    monkeypatch.setattr(drift_mod, "_git_rev_parse_submodule_sha",
                        lambda submodule_path: committed_sha)
    monkeypatch.setattr(drift_mod, "_git_ls_remote",
                        lambda submodule_path, remote, branch: upstream_sha)
    monkeypatch.setattr(drift_mod, "_git_show_timestamp",
                        lambda submodule_path, sha: timestamps[sha])

    code, msg = drift_mod.check_drift()

    assert code == drift_mod.EXIT_OK, f"pointer ahead of upstream must pass; got code={code}, msg={msg}"
    assert "ahead" in msg.lower(), f"message should say the pointer is ahead: {msg!r}"


# ---------------------------------------------------------------------------
# Test 2c: Pointer behind upstream but inside the window → exit OK
# ---------------------------------------------------------------------------
def test_pointer_behind_within_window_is_ok(monkeypatch):
    """
    A pointer 3 days older than upstream HEAD is normal lag, not drift.
    Under the old `now - upstream_ts` formula this failed whenever upstream
    main itself was older than 14 days, regardless of the pointer.
    """
    committed_sha = "1111111111111111111111111111111111111111"
    upstream_sha = "2222222222222222222222222222222222222222"

    upstream_ts = 1_700_000_000
    committed_ts = upstream_ts - (3 * 86400)
    timestamps = {committed_sha: committed_ts, upstream_sha: upstream_ts}

    monkeypatch.setattr(drift_mod, "_git_rev_parse_submodule_sha",
                        lambda submodule_path: committed_sha)
    monkeypatch.setattr(drift_mod, "_git_ls_remote",
                        lambda submodule_path, remote, branch: upstream_sha)
    monkeypatch.setattr(drift_mod, "_git_show_timestamp",
                        lambda submodule_path, sha: timestamps[sha])

    code, msg = drift_mod.check_drift()

    assert code == drift_mod.EXIT_OK, f"3d behind is within the 14d window; got code={code}, msg={msg}"


# ---------------------------------------------------------------------------
# Test 3: Submodule not registered — exit CONFIG_ERR
# ---------------------------------------------------------------------------
def test_nonexistent_submodule_returns_config_err(monkeypatch):
    """A submodule path the parent repo does not recognize → EXIT_CONFIG_ERR."""

    def _raises(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            128, ["git", "rev-parse"], stderr="fatal: ambiguous argument"
        )

    monkeypatch.setattr(drift_mod, "_git_rev_parse_submodule_sha", _raises)

    code, msg = drift_mod.check_drift(submodule_path="raw/repos/nonexistent")
    assert code == drift_mod.EXIT_CONFIG_ERR
    assert "raw/repos/nonexistent" in msg
    assert ("not registered" in msg.lower()
            or "not found" in msg.lower()
            or "config" in msg.lower())


# ---------------------------------------------------------------------------
# Test 4: ls-remote failure → fail-closed → exit TRANSIENT_ERR
# ---------------------------------------------------------------------------
def test_ls_remote_failure_returns_transient_err(monkeypatch):
    """
    Network failure / offline / auth-denied → exit 3 so CI fails closed.
    A transient error must NEVER be treated as 'no drift' — that would let
    silent rot through.
    """
    monkeypatch.setattr(drift_mod, "_git_rev_parse_submodule_sha",
                        lambda submodule_path: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    def _raises(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            128, ["git", "ls-remote"], stderr="Could not resolve host"
        )

    monkeypatch.setattr(drift_mod, "_git_ls_remote", _raises)

    code, msg = drift_mod.check_drift()
    assert code == drift_mod.EXIT_TRANSIENT_ERR
    assert "ls-remote" in msg.lower() or "transient" in msg.lower() or "git" in msg.lower()


# ---------------------------------------------------------------------------
# Test 5: CLI plumbing — main(--check) returns the same exit code as check_drift()
# ---------------------------------------------------------------------------
def test_main_check_flag_returns_check_drift_exit_code(monkeypatch, capsys):
    """
    main() must propagate check_drift()'s exit code so the CI workflow's
    `python tools/check_submodule_drift.py --check` step fails when drift
    is detected.
    """
    sentinel_msg = "STALE: stub message for plumbing test"
    monkeypatch.setattr(drift_mod, "check_drift",
                        lambda **kwargs: (drift_mod.EXIT_DRIFT, sentinel_msg))

    exit_code = drift_mod.main(["--check"])
    assert exit_code == drift_mod.EXIT_DRIFT

    captured = capsys.readouterr()
    # Non-zero outcomes write to stderr (per the exit-code contract).
    assert sentinel_msg in captured.err
