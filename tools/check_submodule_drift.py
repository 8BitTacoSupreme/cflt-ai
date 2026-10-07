#!/usr/bin/env python3
"""
tools/check_submodule_drift.py — Stale-submodule drift gate for raw/repos/fsi-dsp.

Fails CI when the locally-committed submodule pointer is more than 14 days
behind upstream main HEAD's commit timestamp. Mirrors the H.3b
streaming-skills-drift shape: pure Python + git ls-remote, no Node.js,
no API auth.

Algorithm:
  1. Resolve the parent repo's recorded submodule SHA via
     `git rev-parse HEAD:<submodule_path>`.
  2. Fetch upstream HEAD via `git -C <submodule_path> ls-remote <remote> <branch>`.
  3. If SHAs match → EXIT_OK (early return, no timestamp resolution needed).
  4. If SHAs differ → resolve BOTH commit timestamps via
     `git -C <submodule_path> log -1 --format=%ct <sha>` and compute
     delta = upstream_ts - committed_ts (how far the pointer lags upstream).
     - delta ≤ 0 → EXIT_OK (pointer is newer than upstream HEAD, e.g. pinned
       to a feature branch built on top of main — cannot be stale).
     - 0 < delta ≤ DRIFT_WINDOW_DAYS → EXIT_OK (within window — drift is
       normal, not stale).
     - delta > DRIFT_WINDOW_DAYS → EXIT_DRIFT with remediation message
       containing the literal command sequence:
         git submodule update --remote raw/repos/fsi-dsp
         git add raw/repos/fsi-dsp
         git commit -m "chore(submodule): bump fsi-dsp to upstream main"

Used by .github/workflows/submodule-drift.yml as the CI gate. Triggers on
PR + push:main, path-scoped to raw/repos/fsi-dsp + this script + the workflow.

History: until 2026-10-07 step 4 computed `now - upstream_ts`, i.e. how long
since upstream main last moved. That measures upstream's quietness, not the
pointer's lag, and produced a false STALE (134 days) when the pointer was
four commits AHEAD of an upstream main that had been idle since May. The
pointer's own commit timestamp is now part of the comparison.

Exit codes (mirrors H.3b):
  0 = within drift window (or SHAs equal — fresh pointer; or pointer ahead)
  1 = stale (>14 days behind upstream main) — CI fails with remediation
  2 = config error (submodule not registered in parent repo)
  3 = transient error (git ls-remote failed, timestamp unresolvable) —
      fail-closed for CI (a transient error must never be treated as 'no drift')
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Public exit-code contract (referenced by tests and CI workflow comments).
EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_CONFIG_ERR = 2
EXIT_TRANSIENT_ERR = 3

# Defaults — overridable via check_drift() parameters for unit tests.
SUBMODULE_PATH = "raw/repos/fsi-dsp"
UPSTREAM_REMOTE = "origin"
UPSTREAM_BRANCH = "main"
DRIFT_WINDOW_DAYS = 14


# ---------------------------------------------------------------------------
# Small, individually monkeypatch-able git helpers. Each one shells out via
# subprocess with check=True so failures surface as CalledProcessError and
# the calling logic can decide the exit code (config vs transient).
# ---------------------------------------------------------------------------

def _git_rev_parse_submodule_sha(submodule_path: str) -> str:
    """Return the parent repo's recorded SHA for the submodule.

    Equivalent to `git rev-parse HEAD:<submodule_path>`. Raises
    subprocess.CalledProcessError if the submodule is not registered or the
    path is unknown.
    """
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", f"HEAD:{submodule_path}"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


def _git_ls_remote(submodule_path: str, remote: str, branch: str) -> str:
    """Return upstream HEAD SHA for <remote>/<branch> via `git ls-remote`.

    Runs `git -C <submodule_path> ls-remote <remote> <branch>`. Uses the
    submodule's own remote configuration so URLs / auth work the same way
    a developer's `git fetch` would.

    Raises subprocess.CalledProcessError on network failure, auth denial,
    git missing, or any non-zero exit. Raises ValueError if output is empty
    or malformed.
    """
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT / submodule_path), "ls-remote", remote, branch],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    stdout = result.stdout.strip()
    if not stdout:
        raise ValueError(
            f"git ls-remote {remote} {branch} returned empty output for {submodule_path}"
        )
    first_line = stdout.splitlines()[0]
    parts = first_line.split()
    if not parts or len(parts[0]) < 40:
        raise ValueError(f"git ls-remote output malformed: {first_line!r}")
    return parts[0]


def _git_show_timestamp(submodule_path: str, sha: str) -> int:
    """Return the Unix epoch commit timestamp for <sha> inside the submodule.

    Uses `git -C <submodule_path> log -1 --format=%ct <sha>`. The upstream
    SHA from ls-remote may not yet be fetched locally; callers are
    responsible for triggering a fetch if this raises CalledProcessError
    (we fail-closed via EXIT_TRANSIENT_ERR rather than auto-fetching here —
    auto-fetch hides drift behind a side-effect).
    """
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT / submodule_path), "log", "-1", "--format=%ct", sha],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return int(result.stdout.strip())


# ---------------------------------------------------------------------------
# Pure drift logic — returns (exit_code, human_readable_message). All side
# effects (git subprocess calls, network) live in the _git_* helpers above.
# ---------------------------------------------------------------------------

def check_drift(
    submodule_path: str = SUBMODULE_PATH,
    upstream_remote: str = UPSTREAM_REMOTE,
    upstream_branch: str = UPSTREAM_BRANCH,
    drift_window_days: int = DRIFT_WINDOW_DAYS,
) -> "tuple[int, str]":
    """Check whether the submodule pointer is stale.

    Args:
      submodule_path: Repo-relative path to the submodule (default raw/repos/fsi-dsp).
      upstream_remote: Submodule remote name (default 'origin').
      upstream_branch: Upstream branch to compare against (default 'main').
      drift_window_days: Days the pointer's commit may lag upstream HEAD's
        commit before exit is EXIT_DRIFT.

    Returns:
      (exit_code, human_readable_message) — never raises. Translates all
      git failures into the documented exit codes so the CLI can mirror them
      directly.
    """
    # Step 1: parent repo's recorded SHA for the submodule.
    try:
        committed_sha = _git_rev_parse_submodule_sha(submodule_path)
    except subprocess.CalledProcessError as e:
        return (
            EXIT_CONFIG_ERR,
            f"submodule {submodule_path} not registered in parent repo "
            f"(git rev-parse failed: {e.stderr.strip() if e.stderr else e})",
        )

    # Step 2: upstream HEAD via ls-remote (no clone, no fetch).
    try:
        upstream_sha = _git_ls_remote(submodule_path, upstream_remote, upstream_branch)
    except subprocess.CalledProcessError as e:
        return (
            EXIT_TRANSIENT_ERR,
            f"git ls-remote {upstream_remote} {upstream_branch} failed for "
            f"{submodule_path}: {e.stderr.strip() if e.stderr else e}",
        )
    except ValueError as e:
        return (EXIT_TRANSIENT_ERR, f"git ls-remote returned unusable output: {e}")

    # Step 3: SHA-match early-return. The committed pointer is byte-equal
    # to upstream HEAD — no need to resolve timestamps.
    if committed_sha == upstream_sha:
        return (
            EXIT_OK,
            f"OK: submodule at upstream {upstream_remote}/{upstream_branch} "
            f"HEAD ({committed_sha[:12]})",
        )

    # Step 4: SHAs differ. Resolve both commit timestamps and compute how far
    # the committed pointer lags upstream HEAD. Drift is a property of the
    # pointer relative to upstream; "now" plays no part (a quiet upstream is
    # not drift, and a pointer newer than upstream cannot be stale).
    try:
        upstream_ts = _git_show_timestamp(submodule_path, upstream_sha)
    except subprocess.CalledProcessError as e:
        return (
            EXIT_TRANSIENT_ERR,
            f"could not resolve upstream commit timestamp for {upstream_sha[:12]} "
            f"(git log failed: {e.stderr.strip() if e.stderr else e})",
        )
    try:
        committed_ts = _git_show_timestamp(submodule_path, committed_sha)
    except subprocess.CalledProcessError as e:
        return (
            EXIT_TRANSIENT_ERR,
            f"could not resolve committed pointer timestamp for {committed_sha[:12]} "
            f"(git log failed: {e.stderr.strip() if e.stderr else e})",
        )

    delta_days = (upstream_ts - committed_ts) / 86400

    if delta_days <= 0:
        return (
            EXIT_OK,
            f"OK: submodule pointer ({committed_sha[:12]}) is {-delta_days:.1f}d ahead of "
            f"upstream {upstream_remote}/{upstream_branch} HEAD ({upstream_sha[:12]})",
        )

    if delta_days <= drift_window_days:
        return (
            EXIT_OK,
            f"OK: submodule {delta_days:.1f}d behind upstream "
            f"{upstream_remote}/{upstream_branch} HEAD "
            f"(within {drift_window_days}d window)",
        )

    # Step 5: stale. Emit the exact remediation command per ROADMAP
    # success criterion 3 so the CI failure log tells the operator
    # precisely what to run.
    msg = (
        f"STALE: {submodule_path} is {delta_days:.1f} days behind "
        f"upstream {upstream_remote}/{upstream_branch} HEAD ({upstream_sha[:12]}); "
        f"drift window is {drift_window_days} days.\n"
        f"Remediate:\n"
        f"  git submodule update --remote {submodule_path}\n"
        f"  git add {submodule_path}\n"
        f'  git commit -m "chore(submodule): bump fsi-dsp to upstream main"'
    )
    return (EXIT_DRIFT, msg)


# ---------------------------------------------------------------------------
# CLI entry point. --check is the CI mode (writes nonzero exits to stderr).
# Default mode writes to stdout regardless. Either way the exit code from
# check_drift() is propagated unchanged so the workflow step fails on drift.
# ---------------------------------------------------------------------------

def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stale-submodule drift gate for raw/repos/fsi-dsp. Fails CI when "
            "the committed submodule pointer is >14 days behind upstream main."
        ),
        epilog=(
            "Exit codes: 0 within window, 1 stale (CI fails), "
            "2 config error, 3 transient error (fail-closed)."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="CI mode — exit non-zero on drift, config error, or transient error",
    )
    args = parser.parse_args(argv)

    code, msg = check_drift()

    # Non-zero outcomes write to stderr so they surface in CI logs as
    # error-stream output; OK writes to stdout. The --check flag does not
    # change the exit code (the contract is identical) — it only signals
    # operator intent for log scrapers / shell pipelines that key on stdout.
    stream = sys.stdout if code == EXIT_OK else sys.stderr
    print(msg, file=stream)

    # Silence pyflakes for the unused --check binding when callers omit it:
    # the flag is part of the documented CLI surface; tests assert it parses
    # without error.
    _ = args.check

    return code


if __name__ == "__main__":
    sys.exit(main())
