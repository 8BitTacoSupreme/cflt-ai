---
phase: H.3c-dsp-scaffold-wrapper
plan: 01
type: execute
wave: 1
depends_on: [H.3a-01, H.3b-01, H.4a-01, H.4b-01, H.4c-01]
files_modified:
  - .claude/commands/dsp-scaffold.md
  - tools/scaffold_engine.py
  - tools/profiles/read-only.json
  - tests/test_scaffold_engine.py
  - .gitignore
autonomous: true
requirements: [SCAF-01, SCAF-02, SCAF-03]
requirements_addressed: [SCAF-01, SCAF-02, SCAF-03]

must_haves:
  truths:
    - "`.claude/commands/dsp-scaffold.md` exists with the /dsp:scaffold skill specification (numbered Step structure mirroring /dsp:apply)"
    - "`tools/scaffold_engine.py` exists with: ARTIFACT_TYPE_TO_SKILL triage dict, scaffold() orchestrator function, three gates (skill blocklist, read-only operator, cross-family canon), output-directory generator, provenance.json writer, manifest-entry.yaml writer, activity-log emitter"
    - "`tools/profiles/read-only.json` gains a `skill_blocklist` field containing `\"dsp-scaffold\"` (defense in depth alongside the empty allowed_operations)"
    - "Existing operator profiles (engineer.json, break-glass.json) and developer profiles (developer/sandbox.json, canon/customer/acme-bank/profiles/developer/sandbox.json) UNCHANGED in this plan"
    - "`/dsp:scaffold producer my-payments-producer --profile developer/sandbox` writes the full output directory under `outputs/scaffolded/producer-my-payments-producer-<timestamp>/` with all 4 components: manifest-entry.yaml, provenance.json, scaffold/ (with producer.py + config.json + README.md or equivalent), and a top-level README.md"
    - "`/dsp:scaffold producer my-payments-producer --profile read-only` exits non-zero with `blocked-by-profile` error message; no output directory written"
    - "`/dsp:scaffold producer my-payments-producer --profile developer/sandbox --prod` exits non-zero with `blocked-by-canon-family` error message naming the cross-family refusal; no output directory written"
    - "`/dsp:scaffold cdc-pipeline x --profile engineer` exits with `not-implemented` error referencing the H.3c follow-up TODO; activity log entry written"
    - "`provenance.json` for a successful scaffold contains all 14 D-08 keys (operator, profile, profile_family, overlay, artifact_type, name, upstream_skill, upstream_plugin, upstream_plugin_version, upstream_commit_sha, canon_stack_hash, canon_family, timestamp_utc, scaffold_dir, phase)"
    - "`manifest-entry.yaml` is a valid YAML doc with the proposed fsi-dsp MANIFEST capability entry shape (id, type, name, path, description, provenance block)"
    - "Every `/dsp:scaffold` invocation appends one entry to `wiki/activity/2026-05.md` with the schema in CONTEXT D-10"
    - "`outputs/scaffolded/` is added to `.gitignore` if not already covered by an existing `outputs/` pattern"
    - "`tests/test_scaffold_engine.py` has 7 test cases per CONTEXT D-11 (happy dev path, happy operator path, read-only blocked, cross-family canon refused, not-implemented type, triage table sanity, provenance round-trip)"
    - "`pytest tests/test_scaffold_engine.py -v` exits 0 — all 7 tests pass"
    - "`pytest tests/` exits 0 (or only same 2 pre-existing failures as H.4a/H.4b/H.4c/H.3b)"
    - "No changes to `raw/repos/fsi-dsp/MANIFEST.yaml` (that's a separate PR against fsi-dsp submodule)"
    - "No changes to `.github/workflows/`, `canon/stack.py`, `canon/industry/`, `canon/customer/`, `tools/apply_engine.py` (beyond what's documented above), or any operator profile JSON beyond read-only.json's blocklist field"
  artifacts:
    - path: ".claude/commands/dsp-scaffold.md"
      provides: "User-facing /dsp:scaffold skill specification with numbered Steps mirroring /dsp:apply"
      contains:
        - "/dsp:scaffold"
        - "artifact-type"
        - "--profile"
        - "--prod"
        - "developer/sandbox"
        - "scaffold_engine"
    - path: "tools/scaffold_engine.py"
      provides: "Scaffold orchestrator: triage, gating, output generation, provenance, MANIFEST entry, activity log"
      contains:
        - "ARTIFACT_TYPE_TO_SKILL"
        - "def scaffold"
        - "blocked-by-profile"
        - "blocked-by-canon-family"
        - "not-implemented"
        - "streaming-skills-plugin"
        - "canon_stack_hash"
    - path: "tools/profiles/read-only.json"
      provides: "Read-only operator profile gains explicit skill_blocklist with dsp-scaffold"
      contains:
        - "\"family\": \"operator\""
        - "\"skill_blocklist\""
        - "\"dsp-scaffold\""
    - path: "tests/test_scaffold_engine.py"
      provides: "Unit tests covering all 5 scaffold outcomes + triage sanity + provenance round-trip"
      contains:
        - "test_scaffold_producer_happy_path_developer_sandbox"
        - "test_scaffold_producer_happy_path_engineer_prod"
        - "test_scaffold_read_only_blocked"
        - "test_scaffold_cross_family_canon_refused"
        - "test_scaffold_not_implemented_artifact_type"
        - "test_triage_table_all_target_streaming_skills_plugin"
        - "test_provenance_round_trip"
    - path: ".gitignore"
      provides: "Excludes outputs/scaffolded/ from version control"
      contains:
        - "outputs/scaffolded"
  key_links:
    - from: ".claude/commands/dsp-scaffold.md"
      to: "tools/scaffold_engine.py"
      via: "Skill spec invokes tools/scaffold_engine.py scaffold() with the parsed args"
      pattern: "tools/scaffold_engine.py"
    - from: "tools/scaffold_engine.py"
      to: "tools/apply_engine.py"
      via: "Reuses load_profile, check_skill_permitted, check_profile_permits from H.4a/H.4b"
      pattern: "from tools.apply_engine import"
    - from: "tools/scaffold_engine.py"
      to: "canon/stack.py"
      via: "Calls resolve_stack(family=..., canon_layer=...) for the canon_stack_hash in provenance"
      pattern: "from canon.stack import resolve_stack"
    - from: "tools/scaffold_engine.py"
      to: "tools/vendor-sources.json"
      via: "Reads streaming-skills-plugin.commit + .version for provenance footer"
      pattern: "vendor-sources.json"
    - from: "outputs/scaffolded/.../manifest-entry.yaml"
      to: "raw/repos/fsi-dsp/MANIFEST.yaml"
      via: "Proposed entry — copied into fsi-dsp via a separate PR (not auto-merged by H.3c)"
      pattern: "manifest-entry.yaml"
---

<objective>
Land /dsp:scaffold as a cflt-ai skill that wraps streaming-skills-plugin upstream skills + applies the active profile-family canon overlay + materializes the output as a canon-compliant fsi-dsp artifact proposal (MANIFEST entry + provenance). Profile-gated (read-only blocked, cross-family canon refused), activity-logged, end-to-end working for the `producer` artifact-type. Other artifact types stub with `NotImplementedError` + H.3c follow-up TODO marker.

After this plan: SCAF-01 / SCAF-02 / SCAF-03 are fully satisfied. The H.3 sub-phase set is complete (H.3a install + overlay article ✓, H.3b pin + drift gate ✓, H.3c scaffold wrapper ✓). The H.3 phase boundary delivers a working end-to-end demonstration: developer/sandbox profile invokes `/dsp:scaffold producer X` → gets a scaffolded producer with FSI dev canon values inlined + a manifest entry ready for fsi-dsp registration + an activity log entry for audit.

Single PLAN, single wave, autonomous. 5 files modified/created. No fsi-dsp submodule changes (proposed entry only). No CI workflow changes. No canon-stack changes.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/H.3c-dsp-scaffold-wrapper/H.3c-CONTEXT.md
@.planning/phases/H.3a-plugin-install-canon-overlay-wiki-article/H.3a-CONTEXT.md
@.planning/phases/H.3b-version-pin-ci-drift-gate/H.3b-CONTEXT.md
@.planning/phases/H.4a-profile-family-schema-extension/H.4a-CONTEXT.md
@.planning/phases/H.4b-developer-sandbox-profile-fsi-dev-canon/H.4b-CONTEXT.md
@.claude/commands/dsp-apply.md
@.claude/commands/dsp-plan.md
@tools/apply_engine.py
@tools/profiles/read-only.json
@tools/profiles/developer/sandbox.json
@tools/vendor-sources.json
@canon/stack.py
@raw/repos/fsi-dsp/MANIFEST.yaml
@.gitignore
</context>

<tasks>

<task type="auto">
  <name>Task 1: Author tools/scaffold_engine.py with triage, three gates, output generation, provenance, MANIFEST entry, activity log</name>
  <files>
    - tools/scaffold_engine.py
  </files>
  <read_first>
    - tools/apply_engine.py (load_profile, check_skill_permitted, check_profile_permits; emit_activity_log_apply if exposed — copy the activity-log emitter pattern)
    - canon/stack.py (resolve_stack family + canon_layer kwargs; hash format)
    - tools/vendor-sources.json (streaming-skills-plugin.commit + .version)
    - raw/repos/fsi-dsp/MANIFEST.yaml (capability entry shape for the manifest-entry.yaml emission)
    - .claude/commands/dsp-apply.md (numbered Step structure, activity-log call sites)
    - .planning/phases/H.3c-dsp-scaffold-wrapper/H.3c-CONTEXT.md (D-01 through D-11)
  </read_first>
  <action>
    Create `tools/scaffold_engine.py`. Use stdlib only (json, yaml via PyYAML, pathlib, datetime, hashlib, subprocess, sys, argparse, time). Reuse from `tools.apply_engine`.

    Module structure (~250–350 lines):

    ```python
    #!/usr/bin/env python3
    """
    tools/scaffold_engine.py — /dsp:scaffold wrapper orchestrator.

    Wraps the upstream streaming-skills-plugin skills so their output materializes
    as canon-compliant fsi-dsp artifacts. Profile-gated, activity-logged.

    Phase H.3c: lands one artifact-type end-to-end (producer); stubs others.
    """
    from __future__ import annotations

    import argparse
    import hashlib
    import json
    import os
    import sys
    import time
    from dataclasses import dataclass
    from datetime import datetime, timezone
    from pathlib import Path
    from typing import Optional

    import yaml

    from tools.apply_engine import (
        load_profile,
        check_skill_permitted,
        PROJECT_ROOT,
    )
    from canon.stack import resolve_stack


    # ─────────────────────────────────────────────────────────────────────────────
    # Triage table — artifact-type → upstream skill
    # ─────────────────────────────────────────────────────────────────────────────

    ARTIFACT_TYPE_TO_SKILL = {
        "producer": "streaming-skills-plugin:developing-kafka-python-client",
        "consumer": "streaming-skills-plugin:developing-kafka-python-client",
        "kafka-streams-app": "streaming-skills-plugin:kafka-streams-programming",
        "schema": "streaming-skills-plugin:kafka-schema-registry",
        "cdc-pipeline": "streaming-skills-plugin:confluent-cloud-cdc-tableflow",
    }

    # H.3c lands ONLY producer end-to-end; others stub
    H3C_IMPLEMENTED_TYPES = {"producer"}


    OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "scaffolded"
    VENDOR_SOURCES = PROJECT_ROOT / "tools" / "vendor-sources.json"
    ACTIVITY_LOG_DIR = PROJECT_ROOT / "wiki" / "activity"


    # ─────────────────────────────────────────────────────────────────────────────
    # Dataclass results
    # ─────────────────────────────────────────────────────────────────────────────

    @dataclass
    class ScaffoldResult:
        status: str  # "success" | "blocked-by-profile" | "blocked-by-canon-family" | "not-implemented"
        scaffold_dir: Optional[Path] = None
        message: str = ""
        duration_seconds: float = 0.0


    # ─────────────────────────────────────────────────────────────────────────────
    # Main orchestrator
    # ─────────────────────────────────────────────────────────────────────────────

    def scaffold(
        artifact_type: str,
        name: str,
        *,
        profile_name: str = "read-only",
        overlay: Optional[str] = None,
        operator: str = "unknown",
        prod: bool = False,
        dry_run: bool = False,
    ) -> ScaffoldResult:
        """Orchestrate the scaffold operation. Three gates + generation + logging.

        Args:
            artifact_type: One of ARTIFACT_TYPE_TO_SKILL keys.
            name: Kebab-case identifier for the scaffolded artifact.
            profile_name: Profile (default 'read-only' fails the first gate).
            overlay: Customer overlay name (passed to load_profile).
            operator: Operator identifier for provenance.
            prod: True → target the prod canon stack; default False → dev-sandbox stack.
            dry_run: True → don't write files; return what WOULD be written in message.

        Returns:
            ScaffoldResult with status field one of:
              - "success"            — output dir written; activity log entry written
              - "blocked-by-profile" — read-only / skill_blocklist; no files; activity log entry
              - "blocked-by-canon-family" — developer-family + --prod; no files; activity log entry
              - "not-implemented"    — artifact_type stubbed; activity log entry
        """
        start = time.monotonic()

        # ── Gate 1: skill blocklist (defense in depth with operator-tier check)
        if not check_skill_permitted(profile_name, "dsp-scaffold", customer=overlay):
            duration = time.monotonic() - start
            msg = f"Profile {profile_name!r} blocks /dsp:scaffold (skill_blocklist)."
            _emit_activity(
                operator=operator,
                profile=profile_name,
                overlay=overlay,
                artifact=f"{artifact_type}/{name}",
                status="blocked-by-profile",
                duration=duration,
                gates_run=["profile"],
            )
            return ScaffoldResult(status="blocked-by-profile", message=msg, duration_seconds=duration)

        # ── Gate 2: explicit read-only check (belt-and-suspenders)
        profile = load_profile(profile_name, customer=overlay)
        family = profile.get("family", "operator")
        if profile_name == "read-only" or (family == "operator" and not profile.get("allowed_operations")):
            duration = time.monotonic() - start
            msg = f"Profile {profile_name!r} (read-only) cannot scaffold. Use --profile engineer or --profile developer/sandbox."
            _emit_activity(
                operator=operator,
                profile=profile_name,
                overlay=overlay,
                artifact=f"{artifact_type}/{name}",
                status="blocked-by-profile",
                duration=duration,
                gates_run=["profile"],
            )
            return ScaffoldResult(status="blocked-by-profile", message=msg, duration_seconds=duration)

        # ── Gate 3: cross-family canon refusal
        if prod and family == "developer":
            duration = time.monotonic() - start
            msg = (
                "Cross-family canon refused: developer-family profiles cannot scaffold prod-canon artifacts. "
                "Use --profile engineer or --profile break-glass for prod scaffolding, "
                "or omit --prod to scaffold under the developer-sandbox canon."
            )
            _emit_activity(
                operator=operator,
                profile=profile_name,
                overlay=overlay,
                artifact=f"{artifact_type}/{name}",
                status="blocked-by-canon-family",
                duration=duration,
                gates_run=["profile", "canon-family"],
            )
            return ScaffoldResult(status="blocked-by-canon-family", message=msg, duration_seconds=duration)

        # ── Triage check (after gates so blocked invocations don't fail on unknown type)
        if artifact_type not in ARTIFACT_TYPE_TO_SKILL:
            raise ValueError(
                f"Unknown artifact type {artifact_type!r}. "
                f"Valid: {sorted(ARTIFACT_TYPE_TO_SKILL)}"
            )

        if artifact_type not in H3C_IMPLEMENTED_TYPES:
            duration = time.monotonic() - start
            msg = (
                f"Artifact type {artifact_type!r} is stubbed in H.3c. "
                f"Only {sorted(H3C_IMPLEMENTED_TYPES)} is end-to-end. "
                f"## TODO: H.3c follow-up — implement scaffold for {artifact_type!r} "
                f"using upstream {ARTIFACT_TYPE_TO_SKILL[artifact_type]}"
            )
            _emit_activity(
                operator=operator,
                profile=profile_name,
                overlay=overlay,
                artifact=f"{artifact_type}/{name}",
                status="not-implemented",
                duration=duration,
                gates_run=["profile", "canon-family", "triage"],
            )
            return ScaffoldResult(status="not-implemented", message=msg, duration_seconds=duration)

        # ── Resolve canon stack
        canon_family = "operator-prod" if (prod and family == "operator") else "developer-sandbox"
        canon_stack_family_param = "developer" if canon_family == "developer-sandbox" else "operator"
        canon_layer = profile.get("canon_layer") if family == "developer" else None
        canon_dict, canon_hash = resolve_stack(family=canon_stack_family_param, canon_layer=canon_layer)

        # ── Generate output directory
        timestamp_utc = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        scaffold_dir = OUTPUT_ROOT / f"{artifact_type}-{name}-{timestamp_utc}"

        if dry_run:
            duration = time.monotonic() - start
            return ScaffoldResult(
                status="success",
                scaffold_dir=scaffold_dir,
                message=f"DRY RUN — would scaffold {artifact_type}/{name} at {scaffold_dir}",
                duration_seconds=duration,
            )

        scaffold_dir.mkdir(parents=True, exist_ok=True)
        upstream_skill_full = ARTIFACT_TYPE_TO_SKILL[artifact_type]
        upstream_skill_name = upstream_skill_full.split(":", 1)[1]

        # ── Read upstream pin from vendor-sources.json
        vs = json.loads(VENDOR_SOURCES.read_text())
        plugin_pin = vs.get("streaming-skills-plugin", {})
        plugin_version = plugin_pin.get("version", "unknown")
        plugin_commit = plugin_pin.get("commit", "unknown")

        # ── Write provenance.json (D-08)
        provenance = {
            "operator": operator,
            "profile": profile_name,
            "profile_family": family,
            "overlay": overlay,
            "artifact_type": artifact_type,
            "name": name,
            "upstream_skill": upstream_skill_name,
            "upstream_plugin": "streaming-skills-plugin",
            "upstream_plugin_version": plugin_version,
            "upstream_commit_sha": plugin_commit,
            "canon_stack_hash": canon_hash,
            "canon_family": canon_family,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "scaffold_dir": str(scaffold_dir.relative_to(PROJECT_ROOT)),
            "phase": "H.3c",
        }
        (scaffold_dir / "provenance.json").write_text(json.dumps(provenance, indent=2))

        # ── Write manifest-entry.yaml (D-09)
        manifest_entry = {
            "id": f"{artifact_type}/{name}",
            "type": f"scaffolded-{artifact_type}",
            "name": name,
            "path": f"scaffolded/{artifact_type}/{name}/",
            "description": f"Scaffolded {artifact_type} '{name}' via /dsp:scaffold (upstream: {upstream_skill_name})",
            "provenance": {
                "generator": "cflt-ai /dsp:scaffold",
                "generator_phase": "H.3c",
                "upstream_skill": upstream_skill_name,
                "upstream_plugin_version": f"streaming-skills-plugin@{plugin_version}",
                "upstream_commit_sha": plugin_commit,
                "canon_stack_hash": canon_hash,
                "canon_family": canon_family,
                "scaffolded_at": provenance["timestamp_utc"],
                "operator": operator,
                "profile": profile_name,
            },
        }
        # Comment-prefixed YAML (operator-readable header) — use safe_dump for the list
        manifest_yaml = (
            "# Proposed entry for raw/repos/fsi-dsp/MANIFEST.yaml capabilities[]\n"
            "# Generated by /dsp:scaffold @ " + provenance["timestamp_utc"] + "\n"
            "# Review before merging into fsi-dsp.\n\n"
            + yaml.safe_dump([manifest_entry], sort_keys=False)
        )
        (scaffold_dir / "manifest-entry.yaml").write_text(manifest_yaml)

        # ── Write scaffold/ artifacts (currently producer-only)
        scaffold_subdir = scaffold_dir / "scaffold"
        scaffold_subdir.mkdir(parents=True, exist_ok=True)
        if artifact_type == "producer":
            _write_producer_stub(scaffold_subdir, name=name, canon_dict=canon_dict, canon_family=canon_family)
        else:
            (scaffold_subdir / "STUB.md").write_text(
                f"# Stub: {artifact_type}/{name}\n\n"
                f"Upstream skill `{upstream_skill_full}` would generate this directory's contents.\n"
                f"H.3c lands the wrapper + provenance + MANIFEST entry; per-skill output is a follow-up.\n"
            )

        # ── Write top-level README.md
        readme = _render_top_readme(
            artifact_type=artifact_type, name=name, profile=profile_name,
            canon_family=canon_family, upstream_skill=upstream_skill_name,
            plugin_version=plugin_version,
        )
        (scaffold_dir / "README.md").write_text(readme)

        # ── Activity log
        duration = time.monotonic() - start
        _emit_activity(
            operator=operator,
            profile=profile_name,
            overlay=overlay,
            artifact=f"{artifact_type}/{name}",
            status="success",
            duration=duration,
            gates_run=["profile", "canon-family", "triage"],
            canon_stack=canon_hash,
        )

        return ScaffoldResult(
            status="success",
            scaffold_dir=scaffold_dir,
            message=f"Scaffolded {artifact_type}/{name} → {scaffold_dir}",
            duration_seconds=duration,
        )


    # ─────────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────────

    def _write_producer_stub(target_dir: Path, *, name: str, canon_dict: dict, canon_family: str) -> None:
        """Write a representative confluent-kafka-python producer reflecting resolved canon."""
        producer_cfg = canon_dict.get("producer", {})
        acks = producer_cfg.get("acks", "all")
        compression = producer_cfg.get("compression_type", "lz4")
        idempotence = producer_cfg.get("enable_idempotence", True)
        sr_format = canon_dict.get("schema_registry", {}).get("format", "avro")
        auth = canon_dict.get("security", {}).get("auth_mechanism", "PLAIN")

        py_content = f'''"""
{name} — Confluent Kafka producer
Scaffolded via /dsp:scaffold (H.3c)
Canon family: {canon_family}
"""
from confluent_kafka import Producer

config = {{
    "bootstrap.servers": "<cluster-bootstrap-host>:9092",
    "acks": "{acks}",
    "enable.idempotence": {str(idempotence).lower()},
    "compression.type": "{compression}",
    # auth: {auth}
    # schema format: {sr_format}
    # Configure auth + schema-registry per FSI overlay before running.
}}

producer = Producer(config)


def deliver(err, msg) -> None:
    if err is not None:
        print(f"Delivery failed: {{err}}")
    else:
        print(f"Delivered: {{msg.topic()}}[{{msg.partition()}}] @ offset {{msg.offset()}}")


def main() -> None:
    producer.produce(topic="example.entity.event", value=b"hello", on_delivery=deliver)
    producer.flush()


if __name__ == "__main__":
    main()
'''
        (target_dir / "producer.py").write_text(py_content)
        (target_dir / "config.json").write_text(json.dumps({
            "name": name,
            "canon_family": canon_family,
            "producer": {
                "acks": acks,
                "enable.idempotence": idempotence,
                "compression.type": compression,
            },
            "schema_registry": {"format": sr_format},
            "security": {"auth_mechanism": auth},
        }, indent=2))


    def _render_top_readme(*, artifact_type, name, profile, canon_family, upstream_skill, plugin_version) -> str:
        return f'''# {artifact_type}/{name}

Scaffolded via `/dsp:scaffold {artifact_type} {name} --profile {profile}` (Phase H.3c).

## Provenance
- Upstream skill: `{upstream_skill}` (from `streaming-skills-plugin@{plugin_version}`)
- Canon family: `{canon_family}`
- Profile: `{profile}`

See `provenance.json` for the full machine-readable record.

## To register in fsi-dsp
1. Review `manifest-entry.yaml`.
2. Open a PR against `goodlabs-studio/fsi-dsp` adding the entry to `MANIFEST.yaml capabilities[]`.
3. After merge: bump cflt-ai's `raw/repos/fsi-dsp` submodule pointer.
4. Then `/dsp:plan` and `/dsp:apply` can reference this artifact by ID.

## To run
See `scaffold/` for upstream-skill output (producer.py + config.json for `producer` type;
STUB.md for other types pending H.3c follow-up phases).
'''


    def _emit_activity(*, operator, profile, overlay, artifact, status, duration, gates_run, canon_stack=None) -> None:
        """Append one entry to wiki/activity/YYYY-MM.md (CONTEXT D-10 shape)."""
        ACTIVITY_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = ACTIVITY_LOG_DIR / (datetime.now(timezone.utc).strftime("%Y-%m") + ".md")
        ts = datetime.now(timezone.utc).isoformat()
        entry = (
            f"\n## {ts} /dsp:scaffold\n"
            f"- operator: `{operator}`\n"
            f"- profile: `{profile}`\n"
            f"- overlay: `{overlay or 'null'}`\n"
            f"- artifact: `{artifact}`\n"
            f"- skill: `/dsp:scaffold`\n"
            f"- plan: `n/a (scaffold)`\n"
            f"- gates: `{','.join(gates_run)}`\n"
            f"- confirmation_status: `n/a`\n"
            f"- execution_result: `{status}`\n"
            f"- duration_seconds: `{duration:.3f}`\n"
        )
        if canon_stack:
            entry += f"- canon_stack: `{canon_stack}`\n"
        with log_file.open("a") as f:
            f.write(entry)


    # ─────────────────────────────────────────────────────────────────────────────
    # CLI entry point
    # ─────────────────────────────────────────────────────────────────────────────

    def main(argv=None) -> int:
        parser = argparse.ArgumentParser(description="/dsp:scaffold — scaffold a Kafka artifact via upstream skill.")
        parser.add_argument("artifact_type", choices=sorted(ARTIFACT_TYPE_TO_SKILL))
        parser.add_argument("name")
        parser.add_argument("--profile", default="read-only")
        parser.add_argument("--overlay", default=None)
        parser.add_argument("--operator", default="unknown")
        parser.add_argument("--prod", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        args = parser.parse_args(argv)

        result = scaffold(
            artifact_type=args.artifact_type,
            name=args.name,
            profile_name=args.profile,
            overlay=args.overlay,
            operator=args.operator,
            prod=args.prod,
            dry_run=args.dry_run,
        )
        print(result.message)
        if result.scaffold_dir:
            print(f"Output: {result.scaffold_dir}")

        # Exit codes
        if result.status == "success":
            return 0
        if result.status == "blocked-by-profile":
            return 10
        if result.status == "blocked-by-canon-family":
            return 11
        if result.status == "not-implemented":
            return 20
        return 1


    if __name__ == "__main__":
        sys.exit(main())
    ```

    Notes:
    - Pyyaml is already a project dependency (vendor-sources schema check uses it; canon/stack.py uses it).
    - PROJECT_ROOT is imported from apply_engine.py.
    - The `_emit_activity` writes Markdown directly to the monthly log — same approach as `/dsp:apply` uses today.
  </action>
  <acceptance_criteria>
    - File `tools/scaffold_engine.py` exists.
    - `python3 -c "from tools.scaffold_engine import scaffold, ARTIFACT_TYPE_TO_SKILL; assert 'producer' in ARTIFACT_TYPE_TO_SKILL; assert ARTIFACT_TYPE_TO_SKILL['producer'].startswith('streaming-skills-plugin:')"` exits 0.
    - `python3 tools/scaffold_engine.py --help` exits 0; help text includes `--profile`, `--prod`, `--dry-run`, `artifact_type`, `name`.
    - `python3 tools/scaffold_engine.py producer test-prod-prov --profile read-only` exits 10 (blocked-by-profile); no output directory created.
    - File contains literal strings: `ARTIFACT_TYPE_TO_SKILL`, `blocked-by-profile`, `blocked-by-canon-family`, `not-implemented`, `streaming-skills-plugin`, `canon_stack_hash`.
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 2: Add skill_blocklist to tools/profiles/read-only.json (defense in depth alongside empty allowed_operations)</name>
  <files>
    - tools/profiles/read-only.json
  </files>
  <read_first>
    - tools/profiles/read-only.json (current — H.4a state with family field)
    - .planning/phases/H.3c-dsp-scaffold-wrapper/H.3c-CONTEXT.md (D-06)
  </read_first>
  <action>
    Edit `tools/profiles/read-only.json`. Current shape (post-H.4a):
    ```json
    {
      "name": "read-only",
      "description": "Plan and inspect only. No apply operations.",
      "family": "operator",
      "allowed_operations": []
    }
    ```

    Add a `skill_blocklist` field with `dsp-scaffold` as a single entry, placed after `family` and before `allowed_operations`. Final shape:
    ```json
    {
      "name": "read-only",
      "description": "Plan and inspect only. No apply operations.",
      "family": "operator",
      "skill_blocklist": ["dsp-scaffold"],
      "allowed_operations": []
    }
    ```

    Note: H.4a's `_normalize_and_validate_profile` validates that operator profiles HAVE `allowed_operations` and do NOT have `tool_overrides`. It does NOT forbid `skill_blocklist` on operator profiles — that field is allowed in either family. Verify this by reading `_normalize_and_validate_profile` BEFORE making the edit; if H.4a's validator rejects `skill_blocklist` on operator profiles (it shouldn't, but verify), update the validator to permit it.

    Do NOT modify `tools/profiles/engineer.json` or `tools/profiles/break-glass.json` — those operator profiles continue to have NO skill_blocklist field (absence = permit all skills).
  </action>
  <acceptance_criteria>
    - `python3 -c "import json; p = json.load(open('tools/profiles/read-only.json')); assert 'dsp-scaffold' in p['skill_blocklist']; assert p['allowed_operations'] == []; assert p['family'] == 'operator'"` exits 0.
    - `python3 -c "from tools.apply_engine import load_profile, check_skill_permitted; p = load_profile('read-only'); assert check_skill_permitted('read-only', 'dsp-scaffold') is False; assert check_skill_permitted('read-only', 'dsp-apply') is True"` exits 0 (dsp-apply NOT in blocklist; dsp-scaffold is).
    - engineer.json and break-glass.json UNCHANGED: `grep -L "skill_blocklist" tools/profiles/engineer.json tools/profiles/break-glass.json` lists both.
    - `python3 -c "from tools.apply_engine import check_skill_permitted; assert check_skill_permitted('engineer', 'dsp-scaffold') is True; assert check_skill_permitted('break-glass', 'dsp-scaffold') is True"` exits 0 (operator profiles without blocklist permit all skills).
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 3: Author .claude/commands/dsp-scaffold.md skill specification</name>
  <files>
    - .claude/commands/dsp-scaffold.md
  </files>
  <read_first>
    - .claude/commands/dsp-apply.md (numbered Step structure to mirror)
    - .claude/commands/dsp-plan.md (skill header conventions)
    - tools/scaffold_engine.py (the implementation this skill delegates to)
    - .planning/phases/H.3c-dsp-scaffold-wrapper/H.3c-CONTEXT.md (D-01, D-02 — CLI signature)
  </read_first>
  <action>
    Create `.claude/commands/dsp-scaffold.md`:

    ```markdown
    # /dsp:scaffold -- FSI-DSP Artifact Scaffold via Upstream Skill

    You orchestrate the scaffolding of a canon-compliant fsi-dsp artifact using one of the upstream skills from `streaming-skills-plugin` (installed and pinned via H.3a + H.3b). The scaffolded output is registered as a proposed fsi-dsp MANIFEST.yaml capability entry with full provenance (operator, profile, canon-stack hash, timestamp, upstream-skill version).

    Profile gating, canon-family gating, and activity logging are MANDATORY. You NEVER scaffold under `read-only`. You NEVER scaffold a prod-canon artifact under a developer-family profile.

    ## Input

    $ARGUMENTS

    ## Step 1: Parse arguments

    Parse `$ARGUMENTS`:

    - Extract `<artifact-type>` (required, first positional) — one of `{producer, consumer, kafka-streams-app, schema, cdc-pipeline}`.
    - Extract `<name>` (required, second positional) — kebab-case identifier.
    - Extract `--profile <name>` (optional, default `read-only`) — `read-only`, `engineer`, `break-glass`, `developer/sandbox`.
    - Extract `--overlay <customer>` (optional) — customer overlay for canon stack (e.g., `acme-bank`).
    - Extract `--operator <id>` (optional, default `unknown`) — operator identifier for provenance.
    - Extract `--prod` (optional flag) — explicit declaration that the artifact targets the prod canon stack. Required for production scaffolding under operator-family profiles. REJECTED under developer-family profiles (cross-family canon refusal).
    - Extract `--dry-run` (optional flag) — show what would be scaffolded without writing files.

    Validation errors (stop immediately):
    - If `<artifact-type>` is missing or not in the valid set: `Error: unknown artifact-type. Valid: cdc-pipeline, consumer, kafka-streams-app, producer, schema`.
    - If `<name>` is missing: `Error: name required. Usage: /dsp:scaffold <artifact-type> <name> [--profile <name>]`.
    - If `--profile <name>` not recognized by VALID_PROFILES: `Error: unknown profile <name>`.

    ## Step 2: Invoke the scaffold engine

    Delegate to `tools/scaffold_engine.py`:

    ```bash
    python tools/scaffold_engine.py <artifact-type> <name> --profile <name> [--overlay <customer>] [--operator <id>] [--prod] [--dry-run]
    ```

    The engine runs three gates in order — skill blocklist, read-only operator, cross-family canon — and either:
    - Generates the output directory `outputs/scaffolded/<artifact-type>-<name>-<timestamp>/` containing `manifest-entry.yaml`, `provenance.json`, `scaffold/`, `README.md`. Exit 0.
    - Refuses with `blocked-by-profile` (exit 10).
    - Refuses with `blocked-by-canon-family` (exit 11).
    - Stubs with `not-implemented` for artifact types other than `producer` in H.3c (exit 20).

    Every invocation appends an entry to `wiki/activity/YYYY-MM.md` per ACTA-04 schema.

    ## Step 3: Report results

    - On success: print the output directory path; instruct the operator to review `manifest-entry.yaml`, then open a PR against `goodlabs-studio/fsi-dsp` to register the entry.
    - On blocked-by-profile: explain which gate fired; suggest the right profile.
    - On blocked-by-canon-family: explain the cross-family refusal; suggest omitting `--prod` or switching to an operator profile.
    - On not-implemented: note the artifact-type is a H.3c follow-up; suggest the manual upstream-skill invocation.

    ## Examples

    ```
    /dsp:scaffold producer my-payments-producer --profile developer/sandbox --operator <your-id>
    /dsp:scaffold producer my-payments-producer --profile engineer --prod --operator <your-id>
    /dsp:scaffold producer my-payments-producer --profile read-only      # blocked
    /dsp:scaffold producer my-payments-producer --profile developer/sandbox --prod   # blocked (cross-family)
    ```

    ## Notes

    - Output is a PROPOSAL — the MANIFEST entry must be reviewed and merged via a PR against `goodlabs-studio/fsi-dsp`.
    - Only `producer` is end-to-end in H.3c; other artifact types stub with `## TODO: H.3c follow-up` markers.
    - Activity log entries follow the `/dsp:apply` ACTA-04 schema; reproducible audit trail for every scaffold.
    ```
  </action>
  <acceptance_criteria>
    - File `.claude/commands/dsp-scaffold.md` exists.
    - `grep -c "^# /dsp:scaffold" .claude/commands/dsp-scaffold.md` returns 1.
    - File contains literal strings: `## Step 1`, `## Step 2`, `## Step 3`, `--profile`, `--prod`, `developer/sandbox`, `tools/scaffold_engine.py`, `blocked-by-canon-family`.
    - Total lines: ≥ 40, ≤ 200 (numbered-Step structure with enough detail but not bloated).
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 4: Add outputs/scaffolded/ to .gitignore if not already covered</name>
  <files>
    - .gitignore
  </files>
  <read_first>
    - .gitignore (current — check whether outputs/ or outputs/scaffolded/ is already excluded)
  </read_first>
  <action>
    Read `.gitignore`. If it already excludes `outputs/` (any pattern matching `outputs`, `outputs/`, `outputs/**`, etc.), do nothing. Otherwise, append a section:

    ```
    # Scaffolded output (H.3c) — audit trail lives in wiki/activity/, not in the file tree
    outputs/scaffolded/
    ```

    Do NOT touch other gitignore entries.
  </action>
  <acceptance_criteria>
    - `grep -E "outputs/?(/scaffolded)?(/?)$" .gitignore` returns at least one match (either pre-existing or this plan added it).
    - `git check-ignore outputs/scaffolded/test 2>&1 | grep -q "outputs/scaffolded"` succeeds (gitignore actually matches).
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 5: Author tests/test_scaffold_engine.py with 7 test cases (CONTEXT D-11)</name>
  <files>
    - tests/test_scaffold_engine.py
  </files>
  <read_first>
    - tools/scaffold_engine.py (the module under test)
    - tests/test_per_family_isolation.py (H.4b/H.4c test patterns; fixture style; monkeypatch usage)
    - .planning/phases/H.3c-dsp-scaffold-wrapper/H.3c-CONTEXT.md (D-11)
  </read_first>
  <action>
    Create `tests/test_scaffold_engine.py`:

    ```python
    """
    Phase H.3c — /dsp:scaffold engine tests.

    Covers all five scaffold outcomes (success-dev, success-prod, blocked-profile,
    blocked-canon-family, not-implemented) plus triage table sanity and provenance
    round-trip.

    All tests write to a temporary OUTPUT_ROOT via monkeypatch so the real
    outputs/scaffolded/ stays clean during testing.
    """
    import json
    from pathlib import Path

    import pytest
    import yaml

    from tools import scaffold_engine
    from tools.scaffold_engine import (
        scaffold,
        ARTIFACT_TYPE_TO_SKILL,
        ScaffoldResult,
    )


    @pytest.fixture(autouse=True)
    def isolate_output_and_activity(tmp_path, monkeypatch):
        """Redirect OUTPUT_ROOT and ACTIVITY_LOG_DIR to tmp_path so tests don't pollute repo."""
        monkeypatch.setattr(scaffold_engine, "OUTPUT_ROOT", tmp_path / "scaffolded")
        monkeypatch.setattr(scaffold_engine, "ACTIVITY_LOG_DIR", tmp_path / "activity")


    def test_scaffold_producer_happy_path_developer_sandbox(tmp_path):
        """developer/sandbox can scaffold producer → success, canon_family=developer-sandbox."""
        result = scaffold(
            artifact_type="producer",
            name="my-payments-producer",
            profile_name="developer/sandbox",
            operator="test-op",
        )
        assert result.status == "success"
        assert result.scaffold_dir is not None
        assert result.scaffold_dir.exists()
        assert (result.scaffold_dir / "provenance.json").exists()
        assert (result.scaffold_dir / "manifest-entry.yaml").exists()
        assert (result.scaffold_dir / "scaffold" / "producer.py").exists()
        assert (result.scaffold_dir / "README.md").exists()

        prov = json.loads((result.scaffold_dir / "provenance.json").read_text())
        assert prov["canon_family"] == "developer-sandbox"
        assert prov["profile_family"] == "developer"
        assert prov["upstream_skill"] == "developing-kafka-python-client"
        assert prov["upstream_commit_sha"] == "91d1871ef8c320be92bca955c8e42492a2778cb4"


    def test_scaffold_producer_happy_path_engineer_prod():
        """engineer + --prod scaffolds producer → success, canon_family=operator-prod."""
        result = scaffold(
            artifact_type="producer",
            name="my-prod-producer",
            profile_name="engineer",
            operator="test-op",
            prod=True,
        )
        assert result.status == "success"
        prov = json.loads((result.scaffold_dir / "provenance.json").read_text())
        assert prov["canon_family"] == "operator-prod"
        assert prov["profile_family"] == "operator"


    def test_scaffold_read_only_blocked():
        """read-only is blocked by skill_blocklist (Gate 1) + by empty allowed_operations (Gate 2)."""
        result = scaffold(
            artifact_type="producer",
            name="x",
            profile_name="read-only",
            operator="test-op",
        )
        assert result.status == "blocked-by-profile"
        assert result.scaffold_dir is None
        assert "/dsp:scaffold" in result.message or "read-only" in result.message.lower() or "blocks" in result.message.lower()


    def test_scaffold_cross_family_canon_refused():
        """developer/sandbox --prod is refused with cross-family error."""
        result = scaffold(
            artifact_type="producer",
            name="x",
            profile_name="developer/sandbox",
            operator="test-op",
            prod=True,
        )
        assert result.status == "blocked-by-canon-family"
        assert result.scaffold_dir is None
        assert "cross-family" in result.message.lower() or "developer-family" in result.message.lower()


    def test_scaffold_not_implemented_artifact_type():
        """cdc-pipeline (and others) is stubbed in H.3c → not-implemented."""
        result = scaffold(
            artifact_type="cdc-pipeline",
            name="x",
            profile_name="engineer",
            operator="test-op",
        )
        assert result.status == "not-implemented"
        assert "H.3c follow-up" in result.message
        assert result.scaffold_dir is None


    def test_triage_table_all_target_streaming_skills_plugin():
        """Every artifact-type in the triage table maps to a streaming-skills-plugin skill."""
        assert len(ARTIFACT_TYPE_TO_SKILL) >= 5
        for artifact_type, upstream in ARTIFACT_TYPE_TO_SKILL.items():
            assert upstream.startswith("streaming-skills-plugin:"), (
                f"{artifact_type!r} maps to {upstream!r} — must start with 'streaming-skills-plugin:'"
            )


    def test_provenance_round_trip():
        """A successful scaffold writes a provenance.json with all 14 D-08 keys."""
        result = scaffold(
            artifact_type="producer",
            name="round-trip",
            profile_name="developer/sandbox",
            operator="test-op",
        )
        assert result.status == "success"
        prov = json.loads((result.scaffold_dir / "provenance.json").read_text())
        expected_keys = {
            "operator", "profile", "profile_family", "overlay",
            "artifact_type", "name",
            "upstream_skill", "upstream_plugin", "upstream_plugin_version", "upstream_commit_sha",
            "canon_stack_hash", "canon_family",
            "timestamp_utc", "scaffold_dir", "phase",
        }
        assert expected_keys.issubset(set(prov.keys())), (
            f"provenance.json missing keys: {expected_keys - set(prov.keys())}"
        )
        assert prov["phase"] == "H.3c"


    def test_manifest_entry_yaml_is_valid():
        """Sanity: the proposed MANIFEST entry YAML is well-formed."""
        result = scaffold(
            artifact_type="producer",
            name="yaml-check",
            profile_name="developer/sandbox",
            operator="test-op",
        )
        assert result.status == "success"
        manifest_text = (result.scaffold_dir / "manifest-entry.yaml").read_text()
        loaded = yaml.safe_load(manifest_text)
        assert isinstance(loaded, list) and len(loaded) == 1
        entry = loaded[0]
        assert entry["id"] == "producer/yaml-check"
        assert entry["type"] == "scaffolded-producer"
        assert "provenance" in entry
        assert entry["provenance"]["generator_phase"] == "H.3c"
    ```

    8 tests total (D-11 specified 7; the YAML validity test was natural to add as 8th).
  </action>
  <acceptance_criteria>
    - File `tests/test_scaffold_engine.py` exists.
    - `grep -c "def test_" tests/test_scaffold_engine.py` returns ≥ 7.
    - `pytest tests/test_scaffold_engine.py -v` exits 0 — all tests pass.
    - File contains literal test names: `test_scaffold_producer_happy_path_developer_sandbox`, `test_scaffold_producer_happy_path_engineer_prod`, `test_scaffold_read_only_blocked`, `test_scaffold_cross_family_canon_refused`, `test_scaffold_not_implemented_artifact_type`, `test_triage_table_all_target_streaming_skills_plugin`, `test_provenance_round_trip`.
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 6: Full regression run + write H.3c-01-SUMMARY.md</name>
  <files>
    - .planning/phases/H.3c-dsp-scaffold-wrapper/H.3c-01-SUMMARY.md
  </files>
  <read_first>
    - tools/scaffold_engine.py (post-Task 1)
    - tests/test_scaffold_engine.py (post-Task 5)
    - .planning/phases/H.3c-dsp-scaffold-wrapper/H.3c-01-PLAN.md (this plan)
  </read_first>
  <action>
    Run:
    1. `pytest tests/test_scaffold_engine.py -v` — must exit 0.
    2. `pytest tests/test_profile_gating.py tests/test_per_family_isolation.py tests/test_canon_overlay.py tests/test_check_streaming_skills_drift.py tests/test_scaffold_engine.py -v` — full milestone-test suite. Must exit 0.
    3. `pytest tests/golden/ -v` — must exit 0.
    4. `pytest tests/ -v --tb=short` — full suite; must exit 0 OR only the 2 pre-existing failures (test_check_canon_parity, test_manifest) persist.
    5. Live smoke: `python3 tools/scaffold_engine.py producer demo --profile developer/sandbox --operator h3c-smoke --dry-run` — should print DRY RUN message + intended output path, exit 0.

    Write `.planning/phases/H.3c-dsp-scaffold-wrapper/H.3c-01-SUMMARY.md`:
    ```markdown
    # H.3c-01 Summary

    **Plan:** H.3c-01 — /dsp:scaffold wrapper
    **Status:** Complete
    **Date:** 2026-05-17

    ## What landed
    - `.claude/commands/dsp-scaffold.md` — /dsp:scaffold skill specification (numbered Step structure mirroring /dsp:apply)
    - `tools/scaffold_engine.py` — Orchestrator: triage (5 artifact-types, 1 fully implemented), 3 gates (skill blocklist, read-only, cross-family canon), output generator (manifest-entry.yaml + provenance.json + scaffold/ + README.md), activity log emitter
    - `tools/profiles/read-only.json` — Gained skill_blocklist: ["dsp-scaffold"] (defense in depth)
    - `tests/test_scaffold_engine.py` — 8 test cases (5 outcomes + triage sanity + provenance round-trip + YAML validity)
    - `.gitignore` — Excludes outputs/scaffolded/ (audit lives in wiki/activity/)

    ## Requirements
    - SCAF-01: ✓ Fully satisfied (`/dsp:scaffold` exists, end-to-end for `producer` artifact-type)
    - SCAF-02: ✓ Fully satisfied (manifest-entry.yaml emitted with full provenance: operator, profile, canon-stack hash, timestamp, upstream-skill version, upstream commit SHA)
    - SCAF-03: ✓ Fully satisfied (profile-gated + activity-logged; fail-closed under read-only AND under cross-family --prod request)

    ## ROADMAP success criteria (H.3c)
    1. ✓ /dsp:scaffold runs end-to-end for `producer` artifact-type (developer/sandbox → success, scaffold dir contains producer.py + config.json + manifest-entry + provenance)
    2. ✓ Scaffolded output appears as a MANIFEST.yaml capability entry (in `outputs/scaffolded/<...>/manifest-entry.yaml`; manual review-then-PR into fsi-dsp)
    3. ✓ /dsp:scaffold refuses to run under read-only profile AND refuses to scaffold a prod-canon artifact under developer-sandbox profile (negative-space tests prove fail-closed)

    ## Regression results
    - `pytest tests/test_scaffold_engine.py`: [N]/[N] PASS
    - `pytest tests/test_profile_gating.py + test_per_family_isolation.py + test_canon_overlay.py + test_check_streaming_skills_drift.py + test_scaffold_engine.py`: [N]/[N] PASS
    - `pytest tests/golden/`: [N]/[N] PASS
    - `pytest tests/`: [N+2 - 2 pre-existing] PASS

    ## H.3 sub-phase set complete
    - H.3a ✓ — Plugin install + canon-overlay wiki article
    - H.3b ✓ — Version pin + CI drift gate
    - H.3c ✓ — /dsp:scaffold wrapper

    H.3 satisfies: INST-01 (install + pin + CI gate), CAN-OVR-01 (overlay article), SCAF-01/02/03 (scaffold wrapper + MANIFEST entry + profile gating) — 5 of 5 H.3-tagged requirements.

    ## v2.0 milestone status
    All 8 v2.0 phases (H.1, H.2, H.3a, H.4a, H.4b, H.4c, H.3b, H.3c) complete.
    All 16 v2.0 requirements satisfied (WIKI-06/07/08, EVAL-01/02/03, INST-01, CAN-OVR-01, SCAF-01/02/03, PROFAM-01/02, DEVPROF-01/02, DEVCAN-01).

    ## Deferred (post-H.3c)
    - Implement scaffold paths for `consumer`, `kafka-streams-app`, `schema`, `cdc-pipeline` — each a follow-on phase.
    - Auto-PR-against-fsi-dsp for manifest-entry.yaml — currently manual.
    - `scaffolded-producer` executor in fsi-dsp — needed before /dsp:apply can consume scaffolded artifacts.
    - Eval cases for /dsp:scaffold via H.2 harness.
    - Real upstream-skill interactive invocation (instead of stub generator).

    ## Self-Check: PASSED
    ```
  </action>
  <acceptance_criteria>
    - `.planning/phases/H.3c-dsp-scaffold-wrapper/H.3c-01-SUMMARY.md` exists with `## Self-Check: PASSED`.
    - SUMMARY contains literal strings: `SCAF-01`, `SCAF-02`, `SCAF-03`, `/dsp:scaffold`, `developer-sandbox`, `cross-family`.
    - Live smoke test (`python3 tools/scaffold_engine.py producer demo --profile developer/sandbox --operator h3c-smoke --dry-run`) prints DRY RUN message and exits 0.
    - `git status` shows only the 5 plan-listed files + SUMMARY + STATE/ROADMAP/REQUIREMENTS metadata.
  </acceptance_criteria>
</task>

</tasks>

<verification>
After all tasks complete:

1. **Skill spec landed** — `.claude/commands/dsp-scaffold.md` exists with numbered Step structure.
2. **Engine works** — `python3 tools/scaffold_engine.py --help` exits 0; `--dry-run` exits 0; `--profile read-only` exits 10; `--profile developer/sandbox --prod` exits 11.
3. **Read-only blocklist updated** — `python3 -c "from tools.apply_engine import check_skill_permitted; assert not check_skill_permitted('read-only', 'dsp-scaffold')"` exits 0.
4. **All tests pass** — `pytest tests/test_scaffold_engine.py tests/test_per_family_isolation.py tests/test_profile_gating.py tests/test_canon_overlay.py tests/test_check_streaming_skills_drift.py -v` exits 0.
5. **No regressions** — `pytest tests/` exits 0 (or same 2 pre-existing failures).
6. **gitignore covers outputs** — `git check-ignore outputs/scaffolded/test` succeeds.
7. **No spillover** — `git status` shows only the 5 plan-modified files + SUMMARY + .planning metadata. No fsi-dsp submodule changes, no canon changes, no CI workflow changes, no operator profile changes beyond read-only.

All 7 must pass. Failure → gap closure.
</verification>
