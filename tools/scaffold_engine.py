#!/usr/bin/env python3
"""
tools/scaffold_engine.py — /dsp:scaffold wrapper orchestrator.

Wraps the upstream streaming-skills-plugin skills so their output materializes
as canon-compliant fsi-dsp artifacts. Profile-gated, activity-logged.

Phase H.3c: lands one artifact-type end-to-end (producer); stubs others.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

# Add project root to path so direct script invocation (python3 tools/scaffold_engine.py)
# resolves the `tools` and `canon` packages. Module/import invocation already works.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.apply_engine import (  # noqa: E402 — after sys.path.insert
    load_profile,
    check_skill_permitted,
    PROJECT_ROOT,
)
from canon.stack import resolve_stack, validate_industry, layer_has_overrides  # noqa: E402


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
# Industry selection (operator-side)
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_industry(industry: Optional[str], profile: dict) -> str:
    """Resolve the operator industry: explicit arg > profile field > 'fsi' default.

    Validation (must have a directory under canon/industry/) is shared with the act
    rail via canon.stack.validate_industry.
    """
    return validate_industry(industry or profile.get("industry"))


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
    industry: Optional[str] = None,
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
        msg = (
            f"Profile {profile_name!r} (read-only) cannot scaffold. "
            f"Use --profile engineer or --profile developer/sandbox."
        )
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
    # Industry selection: developer profiles encode their full canon_layer (incl.
    # industry + developer-sandbox suffix). Operators select an industry (default fsi)
    # via --industry or a profile `industry` field; prod targets industry/<X>, while
    # operator non-prod targets the industry's developer-sandbox tier.
    canon_family = "operator-prod" if (prod and family == "operator") else "developer-sandbox"
    canon_stack_family_param = "developer" if canon_family == "developer-sandbox" else "operator"
    if family == "developer":
        canon_layer = profile.get("canon_layer")
    else:
        selected_industry = _resolve_industry(industry, profile)
        canon_layer = (
            f"industry/{selected_industry}"
            if canon_family == "operator-prod"
            else f"industry/{selected_industry}/developer-sandbox"
        )
    # Validate the actual layer we're about to compose has overrides — guards against
    # a missing developer-sandbox tier or a typo'd developer-profile canon_layer
    # silently degrading to base-only canon. (canon_layer=None defers to resolve_stack's
    # validated default.)
    if canon_layer and not layer_has_overrides(canon_layer):
        raise ValueError(
            f"Canon layer {canon_layer!r} has no overrides.yaml in any root — "
            f"cannot scaffold against empty canon. Check the industry/tier or "
            f"the profile's canon_layer."
        )
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
        "canon_layer": canon_layer,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scaffold_dir": _safe_relative(scaffold_dir),
        "phase": "H.3c",
    }
    (scaffold_dir / "provenance.json").write_text(json.dumps(provenance, indent=2))

    # ── Write manifest-entry.yaml (D-09)
    manifest_entry = {
        "id": f"{artifact_type}/{name}",
        "type": f"scaffolded-{artifact_type}",
        "name": name,
        "path": f"scaffolded/{artifact_type}/{name}/",
        "description": (
            f"Scaffolded {artifact_type} '{name}' via /dsp:scaffold "
            f"(upstream: {upstream_skill_name})"
        ),
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
        _write_producer_stub(
            scaffold_subdir,
            name=name,
            canon_dict=canon_dict,
            canon_family=canon_family,
        )
    else:
        (scaffold_subdir / "STUB.md").write_text(
            f"# Stub: {artifact_type}/{name}\n\n"
            f"Upstream skill `{upstream_skill_full}` would generate this directory's contents.\n"
            f"H.3c lands the wrapper + provenance + MANIFEST entry; per-skill output is a follow-up.\n"
        )

    # ── Write top-level README.md
    readme = _render_top_readme(
        artifact_type=artifact_type,
        name=name,
        profile=profile_name,
        canon_family=canon_family,
        upstream_skill=upstream_skill_name,
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

def _safe_relative(path: Path) -> str:
    """Return path relative to PROJECT_ROOT when possible; otherwise absolute.

    Tests monkeypatch OUTPUT_ROOT to a tmp_path that lives outside the repo —
    relative_to() raises ValueError in that case. Fall back to the absolute
    path so the provenance.json field is always populated and machine-readable.
    """
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _write_producer_stub(
    target_dir: Path,
    *,
    name: str,
    canon_dict: dict,
    canon_family: str,
) -> None:
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


def _render_top_readme(
    *,
    artifact_type: str,
    name: str,
    profile: str,
    canon_family: str,
    upstream_skill: str,
    plugin_version: str,
) -> str:
    return f'''# {artifact_type}/{name}

Scaffolded via `/dsp:scaffold {artifact_type} {name} --profile {profile}` (Phase H.3c).

## Provenance
- Upstream skill: `{upstream_skill}` (from `streaming-skills-plugin@{plugin_version}`)
- Canon family: `{canon_family}`
- Profile: `{profile}`

See `provenance.json` for the full machine-readable record.

## To register in fsi-dsp
1. Review `manifest-entry.yaml`.
2. Open a PR against `8BitTacoSupreme/fsi-dsp` adding the entry to `MANIFEST.yaml capabilities[]`.
3. After merge: bump cflt-ai's `raw/repos/fsi-dsp` submodule pointer.
4. Then `/dsp:plan` and `/dsp:apply` can reference this artifact by ID.

## To run
See `scaffold/` for upstream-skill output (producer.py + config.json for `producer` type;
STUB.md for other types pending H.3c follow-up phases).
'''


def _emit_activity(
    *,
    operator: str,
    profile: str,
    overlay: Optional[str],
    artifact: str,
    status: str,
    duration: float,
    gates_run: list,
    canon_stack: Optional[str] = None,
) -> None:
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
    parser = argparse.ArgumentParser(
        description="/dsp:scaffold — scaffold a Kafka artifact via upstream skill."
    )
    parser.add_argument("artifact_type", choices=sorted(ARTIFACT_TYPE_TO_SKILL))
    parser.add_argument("name")
    parser.add_argument("--profile", default="read-only")
    parser.add_argument("--overlay", default=None)
    parser.add_argument("--operator", default="unknown")
    parser.add_argument("--prod", action="store_true")
    parser.add_argument(
        "--industry", default=None,
        help="Operator industry overlay (default: fsi, or the profile's `industry` field). "
             "Developer profiles set their industry via canon_layer.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = scaffold(
            artifact_type=args.artifact_type,
            name=args.name,
            profile_name=args.profile,
            overlay=args.overlay,
            operator=args.operator,
            prod=args.prod,
            industry=args.industry,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
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
