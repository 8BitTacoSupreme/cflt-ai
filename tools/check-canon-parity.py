#!/usr/bin/env python3
"""Check parity between canon keys and MANIFEST.yaml capabilities (terraform-module + accelerator).

Bidirectional drift detection:
- MANIFEST has terraform-module or accelerator capability with no corresponding canon
  config key -> drift (blocking)
- Canon has infrastructure config key with no corresponding terraform-module -> drift
  (warning only)

The mapping from capability IDs to canon config keys:
  Terraform modules (top-level canon keys in canon/base/defaults.yaml):
    module/topic  -> topic_design   (topics need topic_design canon config)
    module/flink  -> flink_sql      (flink modules need flink_sql canon config)

  Accelerator layers (composite key <id>:<layer-name> -> dotted-path canon key in
  canon/industry/fsi/overrides.yaml; Phase 11):
    accelerator/confluent-on-linuxone:01-rbac              -> fsi.security.mds-rbac
    accelerator/confluent-on-linuxone:02-tls               -> fsi.security.tls-fips
    accelerator/confluent-on-linuxone:03-schema-governance -> fsi.schema.compatibility-full-transitive
    accelerator/confluent-on-linuxone:04-audit             -> fsi.audit.events-retention
    accelerator/confluent-on-linuxone:05-flink             -> fsi.flink.environment-mtls

This mapping is intentionally explicit rather than heuristic — each new module or
accelerator layer requires a conscious decision about which canon config key
governs it. For accelerator entries, MODULE_TO_CANON_KEY mirrors the per-layer
`canon_key` field on the upstream MANIFEST apply_sequence; drift between them
produces a blocking [DRIFT-1] violation.

Exit 0 = parity confirmed. Exit 1 = drift detected (blocks CI merge).
"""
import argparse
import sys
from pathlib import Path
from typing import List

import yaml

# Match the pattern used by review-to-docx.py and act_gates.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Explicit mapping: capability ID -> canon key.
# Terraform-module entries (no ':' in key) map to top-level canon/base/defaults.yaml keys.
# Accelerator-layer entries (composite '<id>:<layer-name>') map to dotted-path keys
# in canon/industry/fsi/overrides.yaml. Source of truth for parity enforcement.
MODULE_TO_CANON_KEY = {
    "module/topic": "topic_design",
    "module/flink": "flink_sql",
    # New terraform-modules from fsi-dsp ADR-011 (lakehouse) + ADR-012 (database connectors).
    # Each governs a top-level canon defaults key in canon/base/defaults.yaml; FSI overrides
    # land in canon/industry/fsi/overrides.yaml as that surface matures.
    "module/db_connector": "connector_config",
    "module/lakehouse_sink": "lakehouse_sink_config",
    "module/tableflow": "tableflow_config",
    # fsi-dsp PR #2: Basic-tier CC cluster provisioner. cluster_design also governs future
    # cc-cluster-* tier siblings.
    "module/cc-cluster-basic": "cluster_design",
    "accelerator/confluent-on-linuxone:01-rbac": "fsi.security.mds-rbac",
    "accelerator/confluent-on-linuxone:02-tls": "fsi.security.tls-fips",
    "accelerator/confluent-on-linuxone:03-schema-governance": "fsi.schema.compatibility-full-transitive",
    "accelerator/confluent-on-linuxone:04-audit": "fsi.audit.events-retention",
    "accelerator/confluent-on-linuxone:05-flink": "fsi.flink.environment-mtls",
}

# Canon keys that map to infrastructure modules (used for direction-2 warning check).
# Only includes terraform-module canon keys (composite accelerator keys are walked
# separately via apply_sequence; their reverse direction is enforced by the per-layer
# canon_key field on the MANIFEST, not by the existence of a top-level canon key).
# Keys NOT in this set are cross-cutting (security, producer, consumer, etc.) and
# are exempt from "no module found" warnings because they apply across all artifacts.
CANON_INFRA_KEYS = {v for k, v in MODULE_TO_CANON_KEY.items() if ":" not in k}  # {"topic_design", "flink_sql"}


# Directories under fsi-dsp/ scanned for stray assets (on-disk paths not registered
# in MANIFEST.yaml). Mode is either "subdirs" (each immediate child directory is a
# candidate) or "files" (each immediate child file is a candidate).
#
# When a new tier lands upstream (lakehouse via ADR-011, database connectors via
# ADR-012, etc.), every new subdir/file under these paths must appear in MANIFEST
# or the gate fires [STRAY-1]. This forces upstream PRs to register tiers before
# they merge into main.
STRAY_SCAN: dict[str, str] = {
    "modules": "subdirs",
    "accelerators": "subdirs",
    "ansible/roles": "subdirs",
    "scenarios": "subdirs",
    "reference": "subdirs",
    "scripts": "files",
    "observability": "subdirs",
    "docs/adr": "files",
}

# Allowlist of disk paths that are intentionally NOT registered in MANIFEST.
# Use sparingly — every entry is technical debt. Each entry needs a comment
# explaining WHY it's exempt and what the resolution path is.
ALLOWED_STRAY: set[str] = {
    # ADR template (not a real ADR). Upstream may rename to docs/adr/_template.md
    # eventually; until then, leave registered as a stray exemption.
    "docs/adr/000-template.md",
    # Duplicate ADR-009 number — upstream has both 009-linuxone-kafka-offload.md
    # (registered) and 009-linuxone-deployment-guidance.md (this one). Numbering
    # collision should be resolved by upstream rename or merge; allowlisting here
    # to unblock the gate while that PR is pending.
    "docs/adr/009-linuxone-deployment-guidance.md",
    # Empty .terraform residue from v1.0 era PR #2 (module/cc-cluster-basic).
    # The directory contains only `.terraform/` and `.terraform.lock.hcl` — no real
    # module files. Should be cleaned up upstream (added to .gitignore + removed
    # from history); allowlisting here so the gate doesn't block on stale residue.
    "modules/cc-cluster-basic",
}


def check_strays(manifest_path: Path, fsi_dsp_root: Path) -> List[str]:
    """Check that every on-disk asset under governable dirs is registered in MANIFEST.

    Walks the directories in STRAY_SCAN and asserts each child (subdir or file,
    depending on mode) appears in either:
      - some MANIFEST capability's `path` field, OR
      - some accelerator's `apply_sequence[].path` field, OR
      - the ALLOWED_STRAY allowlist.

    Returns a list of [STRAY-1] finding strings. Empty list = no strays.

    Resolution path for a STRAY-1 finding is one of:
      1. Add a MANIFEST capability for the asset (preferred — restores governance).
      2. Add the path to ALLOWED_STRAY with a justification comment (debt path).
      3. Delete the unregistered file/dir from fsi-dsp (rare — actual stray).
    """
    drift: List[str] = []

    try:
        manifest_data = yaml.safe_load(manifest_path.read_text())
    except FileNotFoundError:
        # check_parity() reports this; don't duplicate the error here.
        return drift
    except yaml.YAMLError:
        return drift

    capabilities = manifest_data.get("capabilities", []) if isinstance(manifest_data, dict) else []

    # Build the set of paths the MANIFEST claims to own.
    registered: set[str] = set()
    for cap in capabilities:
        if "path" in cap:
            registered.add(cap["path"])
        for layer in cap.get("apply_sequence", []) or []:
            if isinstance(layer, dict) and "path" in layer:
                registered.add(layer["path"])

    # Walk each governance-relevant directory and find disk paths not registered.
    for relpath, mode in STRAY_SCAN.items():
        scan_dir = fsi_dsp_root / relpath
        if not scan_dir.exists():
            continue
        for child in sorted(scan_dir.iterdir()):
            if child.name.startswith("."):
                continue
            if mode == "subdirs" and not child.is_dir():
                continue
            if mode == "files" and not child.is_file():
                continue
            rel = f"{relpath}/{child.name}"
            if rel in registered or rel in ALLOWED_STRAY:
                continue
            drift.append(
                f"[STRAY-1] {rel} exists on disk but is not registered in MANIFEST "
                f"and not in ALLOWED_STRAY — register it as a typed capability or "
                f"add to ALLOWED_STRAY with justification"
            )

    return drift


def check_parity(
    manifest_path: Path,
    defaults_path: Path,
    fsi_overrides_path: "Path | None" = None,
) -> List[str]:
    """Check parity between MANIFEST.yaml capabilities and canon keys.

    Returns a list of drift strings. Empty list means parity confirmed.

    Direction 1 (blocking): Each terraform-module + accelerator-layer in MANIFEST must
    have a corresponding canon config key. Missing canon config = the capability has
    no governing defaults.

    Direction 2 (warning): Each canon key in CANON_INFRA_KEYS should have a
    corresponding terraform-module. Missing module = canon config exists but no
    artifact implements it yet (warning, not blocking).

    Args:
        manifest_path: Path to raw/repos/fsi-dsp/MANIFEST.yaml
        defaults_path: Path to canon/base/defaults.yaml
        fsi_overrides_path: Path to canon/industry/fsi/overrides.yaml (defaults to
            the project-root path; pass an explicit path or a tempdir file in tests
            that want to assert against a synthetic canon. Pass a non-existent path
            to skip the overrides union entirely.)

    Returns:
        List of drift description strings. Empty = no drift.
    """
    drift: List[str] = []

    # Load MANIFEST
    try:
        manifest_data = yaml.safe_load(manifest_path.read_text())
    except FileNotFoundError:
        drift.append(f"MANIFEST not found: {manifest_path}")
        return drift
    except yaml.YAMLError as e:
        drift.append(f"MANIFEST parse error: {e}")
        return drift

    capabilities = manifest_data.get("capabilities", []) if isinstance(manifest_data, dict) else []

    # Load canon defaults
    try:
        defaults_data = yaml.safe_load(defaults_path.read_text())
    except FileNotFoundError:
        drift.append(f"Canon defaults not found: {defaults_path}")
        return drift
    except yaml.YAMLError as e:
        drift.append(f"Canon defaults parse error: {e}")
        return drift

    canon_keys = set(defaults_data.keys()) if isinstance(defaults_data, dict) else set()

    # Load fsi industry overrides (Phase 11: accelerator dotted-path keys live here).
    # Mirrors the defaults-load error-handling pattern above. Production callers
    # union the file into canon_keys; tests pass an explicit path (often a tempdir
    # fixture) or omit it to skip the union and exercise only defaults-resolution.
    if fsi_overrides_path is None:
        fsi_overrides_path = PROJECT_ROOT / "canon" / "industry" / "fsi" / "overrides.yaml"
    try:
        fsi_overrides_data = yaml.safe_load(fsi_overrides_path.read_text())
        if isinstance(fsi_overrides_data, dict):
            canon_keys |= set(fsi_overrides_data.keys())
    except FileNotFoundError:
        # Silent skip: missing overrides is not an error in test fixtures that
        # exercise only terraform-module defaults resolution. Real-CI failure is
        # caught by the production-path test_no_drift_on_current_state.
        pass
    except yaml.YAMLError as e:
        drift.append(f"[DRIFT-3] fsi overrides parse error: {e}")

    # Extract terraform-modules from MANIFEST
    tf_modules = [c for c in capabilities if c.get("type") == "terraform-module"]
    tf_module_ids = {c.get("id") for c in tf_modules}

    # Direction 1: Each terraform-module must have a corresponding canon defaults key.
    # Missing canon config key = blocking drift.
    for module_id in sorted(tf_module_ids):
        canon_key = MODULE_TO_CANON_KEY.get(module_id)
        if canon_key is None:
            drift.append(
                f"[DRIFT-1] terraform-module '{module_id}' has no entry in "
                f"MODULE_TO_CANON_KEY mapping — add it to check-canon-parity.py"
            )
        elif canon_key not in canon_keys:
            drift.append(
                f"[DRIFT-1] terraform-module '{module_id}' maps to canon key "
                f"'{canon_key}' but that key is absent from defaults.yaml"
            )

    # Direction 1 (accelerator, Phase 11): walk apply_sequence per accelerator entry,
    # compute composite key '<id>:<layer>', compare MANIFEST canon_key vs MODULE_TO_CANON_KEY.
    # Three failure modes (all blocking [DRIFT-1]):
    #   a) Composite key not in MODULE_TO_CANON_KEY — unknown layer; add to map.
    #   b) MANIFEST canon_key disagrees with MODULE_TO_CANON_KEY — drift between map and
    #      upstream source of truth; reconcile one or the other.
    #   c) MODULE_TO_CANON_KEY value not present in canon (defaults + fsi overrides) —
    #      orphan canon key reference; add the canon definition.
    accelerators = [c for c in capabilities if c.get("type") == "accelerator"]
    for acc in accelerators:
        acc_id = acc.get("id", "")
        apply_seq = acc.get("apply_sequence", []) or []
        for layer_entry in apply_seq:
            layer_name = layer_entry.get("layer", "")
            manifest_canon_key = layer_entry.get("canon_key", "")
            composite = f"{acc_id}:{layer_name}"
            mapped_key = MODULE_TO_CANON_KEY.get(composite)
            if mapped_key is None:
                drift.append(
                    f"[DRIFT-1] accelerator '{acc_id}' layer '{layer_name}' "
                    f"(composite '{composite}') has no entry in MODULE_TO_CANON_KEY "
                    f"— add it to check-canon-parity.py"
                )
                continue
            if manifest_canon_key and manifest_canon_key != mapped_key:
                drift.append(
                    f"[DRIFT-1] accelerator '{acc_id}' layer '{layer_name}' "
                    f"declares canon_key '{manifest_canon_key}' but "
                    f"MODULE_TO_CANON_KEY says '{mapped_key}'"
                )
                continue
            if mapped_key not in canon_keys:
                drift.append(
                    f"[DRIFT-1] accelerator '{acc_id}' layer '{layer_name}' "
                    f"maps to canon key '{mapped_key}' but that key is absent "
                    f"from defaults.yaml + fsi overrides"
                )

    # Direction 2: Each canon infra key should have a corresponding terraform-module.
    # Missing module = warning (not blocking — some keys are purely advisory).
    for canon_key in sorted(CANON_INFRA_KEYS):
        expected_module = next(
            (mid for mid, ckey in MODULE_TO_CANON_KEY.items() if ckey == canon_key), None
        )
        if expected_module and expected_module not in tf_module_ids:
            drift.append(
                f"[WARN-2] canon key '{canon_key}' has no corresponding "
                f"terraform-module '{expected_module}' in MANIFEST — "
                f"expected module ID missing from fsi-dsp"
            )

    return drift


def main() -> int:
    """CLI entry point. Returns exit code: 0 = parity, 1 = drift."""
    parser = argparse.ArgumentParser(
        description="Check parity between canon/base/defaults.yaml and MANIFEST.yaml terraform-modules."
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=PROJECT_ROOT / "raw" / "repos" / "fsi-dsp" / "MANIFEST.yaml",
        help="Path to fsi-dsp MANIFEST.yaml (default: raw/repos/fsi-dsp/MANIFEST.yaml)",
    )
    parser.add_argument(
        "--defaults-path",
        type=Path,
        default=PROJECT_ROOT / "canon" / "base" / "defaults.yaml",
        help="Path to canon base defaults.yaml (default: canon/base/defaults.yaml)",
    )
    parser.add_argument(
        "--fsi-overrides-path",
        type=Path,
        default=PROJECT_ROOT / "canon" / "industry" / "fsi" / "overrides.yaml",
        help="Path to canon fsi overrides.yaml (default: canon/industry/fsi/overrides.yaml)",
    )
    parser.add_argument(
        "--fsi-dsp-root",
        type=Path,
        default=PROJECT_ROOT / "raw" / "repos" / "fsi-dsp",
        help="Path to fsi-dsp submodule root for stray-asset scan (default: raw/repos/fsi-dsp)",
    )
    parser.add_argument(
        "--skip-strays",
        action="store_true",
        help="Skip the stray-asset walker (useful for early test fixtures that only exercise drift logic)",
    )
    args = parser.parse_args()

    drift = check_parity(args.manifest_path, args.defaults_path, args.fsi_overrides_path)
    if not args.skip_strays:
        drift.extend(check_strays(args.manifest_path, args.fsi_dsp_root))

    if not drift:
        print("OK: canon <-> fsi-dsp parity confirmed (no drift, no strays)")
        return 0

    print("DRIFT DETECTED:", file=sys.stderr)
    for item in drift:
        print(f"  {item}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
