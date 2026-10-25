"""Unit tests for check-canon-parity.py (ACT-08)."""
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.check_canon_parity import ALLOWED_STRAY, MODULE_TO_CANON_KEY, check_parity, check_strays


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(path: Path, data: dict) -> Path:
    """Write a YAML file and return its path."""
    path.write_text(yaml.dump(data))
    return path


def _make_manifest(modules: list) -> dict:
    """Build a minimal MANIFEST.yaml structure with given terraform-module capability IDs."""
    capabilities = []
    for mod_id in modules:
        capabilities.append({
            "id": mod_id,
            "type": "terraform-module",
            "name": mod_id.split("/")[-1],
            "path": f"modules/{mod_id.split('/')[-1]}",
            "description": f"Test module {mod_id}",
        })
    return {"version": "1.0.0", "capabilities": capabilities}


def _make_defaults(keys: list) -> dict:
    """Build a minimal defaults.yaml with the given top-level keys.

    Tests treat defaults.yaml as the union set for canon-key resolution:
    production splits across canon/base/defaults.yaml + canon/industry/fsi/overrides.yaml,
    but check_parity() unions both into one canon_keys set. For test fixtures we
    write all required keys into one defaults file and skip overrides — same effect.
    """
    return {k: {"_placeholder": True} for k in keys}


def _make_accelerator_manifest(acc_id: str, layers: list) -> dict:
    """Build a MANIFEST.yaml with one accelerator entry whose apply_sequence has the given layers.

    Each layer is a dict: {"layer": str, "canon_key": str}.
    """
    return {
        "version": "1.1.0",
        "capabilities": [{
            "id": acc_id,
            "type": "accelerator",
            "name": acc_id.split("/")[-1],
            "path": f"accelerators/{acc_id.split('/')[-1]}",
            "apply_sequence": [
                {
                    "layer": layer["layer"],
                    "path": f"layers/{layer['layer']}",
                    "canon_key": layer["canon_key"],
                }
                for layer in layers
            ],
        }],
    }


# ---------------------------------------------------------------------------
# TestCheckParity
# ---------------------------------------------------------------------------

class TestCheckParity:
    """Tests for the check_parity() function."""

    def test_no_drift_on_current_state(self):
        """Current MANIFEST and defaults should be in parity — no drift expected."""
        manifest_path = PROJECT_ROOT / "raw" / "repos" / "fsi-dsp" / "MANIFEST.yaml"
        defaults_path = PROJECT_ROOT / "canon" / "base" / "defaults.yaml"

        drift = check_parity(manifest_path, defaults_path)
        assert drift == [], (
            f"Expected no drift on current state, but got:\n" +
            "\n".join(drift)
        )

    def test_no_strays_on_current_state(self):
        """Every governed asset on disk is registered in MANIFEST or allowlisted."""
        fsi_dsp_root = PROJECT_ROOT / "raw" / "repos" / "fsi-dsp"
        strays = check_strays(fsi_dsp_root / "MANIFEST.yaml", fsi_dsp_root)
        assert strays == [], "\n".join(strays)

    def test_allowed_stray_entries_exist_on_disk(self):
        """An allowlist entry for a path that no longer exists is dead debt: remove it."""
        fsi_dsp_root = PROJECT_ROOT / "raw" / "repos" / "fsi-dsp"
        gone = sorted(p for p in ALLOWED_STRAY if not (fsi_dsp_root / p).exists())
        assert gone == [], f"ALLOWED_STRAY entries with no file on disk: {gone}"

    def test_detects_missing_canon_key(self):
        """Drift detected when defaults.yaml is missing a key required by a terraform-module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # MANIFEST has module/topic (which requires topic_design) and module/flink
            manifest_path = _write_yaml(
                tmp / "MANIFEST.yaml",
                _make_manifest(["module/topic", "module/flink"]),
            )

            # defaults.yaml only has flink_sql — topic_design is missing
            defaults_path = _write_yaml(
                tmp / "defaults.yaml",
                _make_defaults(["flink_sql", "schema_registry", "producer", "consumer"]),
            )

            # Skip the real fsi overrides so the synthetic fixture is the only canon source.
            drift = check_parity(manifest_path, defaults_path, tmp / "no-overrides.yaml")

            # Must report drift for module/topic -> topic_design
            assert len(drift) >= 1
            drift_text = "\n".join(drift)
            assert "module/topic" in drift_text
            assert "[DRIFT-1]" in drift_text

    def test_parity_function_returns_list(self):
        """check_parity() always returns a list (never None or other type)."""
        manifest_path = PROJECT_ROOT / "raw" / "repos" / "fsi-dsp" / "MANIFEST.yaml"
        defaults_path = PROJECT_ROOT / "canon" / "base" / "defaults.yaml"

        result = check_parity(manifest_path, defaults_path)
        assert isinstance(result, list)

    def test_parity_with_empty_manifest(self):
        """Empty capabilities list returns no drift — no terraform-modules to check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # MANIFEST with no capabilities
            manifest_path = _write_yaml(
                tmp / "MANIFEST.yaml",
                {"version": "1.0.0", "capabilities": []},
            )

            defaults_path = _write_yaml(
                tmp / "defaults.yaml",
                _make_defaults(["topic_design", "flink_sql", "schema_registry"]),
            )

            drift = check_parity(manifest_path, defaults_path, tmp / "no-overrides.yaml")

            # No terraform-modules -> no DRIFT-1 violations
            drift_1_items = [d for d in drift if "[DRIFT-1]" in d]
            assert drift_1_items == [], (
                "Empty capabilities should produce no DRIFT-1 violations"
            )

    def test_detects_both_modules_missing_canon_keys(self):
        """Both module/topic and module/flink missing from defaults.yaml are both reported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            manifest_path = _write_yaml(
                tmp / "MANIFEST.yaml",
                _make_manifest(["module/topic", "module/flink"]),
            )

            # defaults.yaml has neither topic_design nor flink_sql
            defaults_path = _write_yaml(
                tmp / "defaults.yaml",
                _make_defaults(["schema_registry", "producer", "consumer", "security"]),
            )

            drift = check_parity(manifest_path, defaults_path, tmp / "no-overrides.yaml")
            drift_text = "\n".join(drift)

            # Both modules should be flagged
            assert "module/topic" in drift_text
            assert "module/flink" in drift_text

    def test_missing_manifest_file_returns_drift(self):
        """Missing MANIFEST.yaml produces a drift item (not an unhandled exception)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            defaults_path = _write_yaml(
                tmp / "defaults.yaml",
                _make_defaults(["topic_design"]),
            )
            missing_manifest = tmp / "NONEXISTENT.yaml"

            drift = check_parity(missing_manifest, defaults_path, tmp / "no-overrides.yaml")
            assert len(drift) >= 1
            assert any("not found" in d or "MANIFEST" in d for d in drift)


# ---------------------------------------------------------------------------
# TestParityScript
# ---------------------------------------------------------------------------

class TestParityScript:
    """Tests for the check-canon-parity.py script importability and module constants."""

    def test_script_importable(self):
        """from tools.check_canon_parity import check_parity works (underscore alias)."""
        # This import was already done at the top of this file — if we got here, it works.
        assert callable(check_parity)

    def test_module_to_canon_key_mapping_present(self):
        """MODULE_TO_CANON_KEY mapping exists and covers the two terraform-modules."""
        assert "module/topic" in MODULE_TO_CANON_KEY
        assert "module/flink" in MODULE_TO_CANON_KEY
        assert MODULE_TO_CANON_KEY["module/topic"] == "topic_design"
        assert MODULE_TO_CANON_KEY["module/flink"] == "flink_sql"

    def test_cc_cluster_basic_maps_to_cluster_design(self):
        """module/cc-cluster-basic (fsi-dsp PR #2) is governed by the cluster_design canon key."""
        assert MODULE_TO_CANON_KEY.get("module/cc-cluster-basic") == "cluster_design"
        defaults_path = PROJECT_ROOT / "canon" / "base" / "defaults.yaml"
        assert "cluster_design" in yaml.safe_load(defaults_path.read_text())

    def test_module_to_canon_key_contains_accelerator_layers(self):
        """MODULE_TO_CANON_KEY includes all 5 accelerator/confluent-on-linuxone composite entries (Phase 11)."""
        assert len(MODULE_TO_CANON_KEY) >= 7, (
            f"Expected >= 7 entries (2 terraform-module + 5 accelerator layers), "
            f"got {len(MODULE_TO_CANON_KEY)}"
        )
        assert MODULE_TO_CANON_KEY["accelerator/confluent-on-linuxone:01-rbac"] == "fsi.security.mds-rbac"
        assert MODULE_TO_CANON_KEY["accelerator/confluent-on-linuxone:02-tls"] == "fsi.security.tls-fips"
        assert MODULE_TO_CANON_KEY["accelerator/confluent-on-linuxone:03-schema-governance"] == "fsi.schema.compatibility-full-transitive"
        assert MODULE_TO_CANON_KEY["accelerator/confluent-on-linuxone:04-audit"] == "fsi.audit.events-retention"
        assert MODULE_TO_CANON_KEY["accelerator/confluent-on-linuxone:05-flink"] == "fsi.flink.environment-mtls"

    def test_fsi_overrides_contains_accelerator_canon_keys(self):
        """canon/industry/fsi/overrides.yaml contains the 5 dotted-path keys consumed by accelerator parity."""
        overrides_path = PROJECT_ROOT / "canon" / "industry" / "fsi" / "overrides.yaml"
        overrides_data = yaml.safe_load(overrides_path.read_text())
        for key in [
            "fsi.security.mds-rbac",
            "fsi.security.tls-fips",
            "fsi.schema.compatibility-full-transitive",
            "fsi.audit.events-retention",
            "fsi.flink.environment-mtls",
        ]:
            assert key in overrides_data, (
                f"Expected '{key}' as a top-level key in canon/industry/fsi/overrides.yaml, "
                f"got: {list(overrides_data.keys())}"
            )

    def test_module_to_canon_key_values_present_in_defaults(self):
        """Every value in MODULE_TO_CANON_KEY exists as a top-level key in either
        canon/base/defaults.yaml (terraform-module canon keys) or
        canon/industry/fsi/overrides.yaml (accelerator dotted-path keys; Phase 11)."""
        defaults_path = PROJECT_ROOT / "canon" / "base" / "defaults.yaml"
        overrides_path = PROJECT_ROOT / "canon" / "industry" / "fsi" / "overrides.yaml"
        defaults_data = yaml.safe_load(defaults_path.read_text())
        overrides_data = yaml.safe_load(overrides_path.read_text()) or {}
        canon_keys = set(defaults_data.keys()) | set(overrides_data.keys())

        for module_id, canon_key in MODULE_TO_CANON_KEY.items():
            assert canon_key in canon_keys, (
                f"MODULE_TO_CANON_KEY['{module_id}'] = '{canon_key}' "
                f"but '{canon_key}' is not in defaults.yaml or fsi/overrides.yaml"
            )


# ---------------------------------------------------------------------------
# TestAcceleratorParity (Phase 11)
# ---------------------------------------------------------------------------

class TestAcceleratorParity:
    """Positive-path tests: each of the 5 accelerator layers maps to its canon key with no drift."""

    @staticmethod
    def _run_layer_parity(tmpdir: str, layer: str, canon_key: str) -> list:
        """Helper: write a single-layer accelerator manifest + matching defaults, return drift.

        Includes the 2 terraform-modules in the MANIFEST + their canon keys in defaults
        so WARN-2 reverse-lookup noise does not pollute the positive-path assertion.
        """
        tmp = Path(tmpdir)
        # Include every terraform-module currently in MODULE_TO_CANON_KEY so the
        # direction-2 reverse-lookup check finds a backing module for each canon
        # infra key. Keeps the fixture self-maintaining: any future module ID
        # added to MODULE_TO_CANON_KEY only needs the matching canon defaults
        # entry added below.
        terraform_module_ids = [k for k in MODULE_TO_CANON_KEY if ":" not in k]
        terraform_module_canon_keys = [MODULE_TO_CANON_KEY[k] for k in terraform_module_ids]
        manifest_data = {
            "version": "1.1.0",
            "capabilities": [
                {
                    "id": mid,
                    "type": "terraform-module",
                    "name": mid.split("/")[-1],
                    "path": f"modules/{mid.split('/')[-1]}",
                    "description": f"{mid} module",
                }
                for mid in terraform_module_ids
            ] + [
                {
                    "id": "accelerator/confluent-on-linuxone",
                    "type": "accelerator",
                    "name": "confluent-on-linuxone",
                    "path": "accelerators/confluent-on-linuxone",
                    "apply_sequence": [
                        {
                            "layer": layer,
                            "path": f"layers/{layer}",
                            "canon_key": canon_key,
                        },
                    ],
                },
            ],
        }
        manifest_path = _write_yaml(tmp / "MANIFEST.yaml", manifest_data)
        defaults_path = _write_yaml(
            tmp / "defaults.yaml",
            _make_defaults([canon_key, *terraform_module_canon_keys]),
        )
        # Skip the real fsi overrides — defaults fixture above is the union source.
        return check_parity(manifest_path, defaults_path, tmp / "no-overrides.yaml")

    def test_layer_01_rbac_maps_to_fsi_security_mds_rbac(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            drift = self._run_layer_parity(tmpdir, "01-rbac", "fsi.security.mds-rbac")
            assert drift == [], f"Expected no drift for 01-rbac, got: {drift}"

    def test_layer_02_tls_maps_to_fsi_security_tls_fips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            drift = self._run_layer_parity(tmpdir, "02-tls", "fsi.security.tls-fips")
            assert drift == [], f"Expected no drift for 02-tls, got: {drift}"

    def test_layer_03_schema_governance_maps_to_fsi_schema_compatibility_full_transitive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            drift = self._run_layer_parity(
                tmpdir, "03-schema-governance", "fsi.schema.compatibility-full-transitive"
            )
            assert drift == [], f"Expected no drift for 03-schema-governance, got: {drift}"

    def test_layer_04_audit_maps_to_fsi_audit_events_retention(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            drift = self._run_layer_parity(tmpdir, "04-audit", "fsi.audit.events-retention")
            assert drift == [], f"Expected no drift for 04-audit, got: {drift}"

    def test_layer_05_flink_maps_to_fsi_flink_environment_mtls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            drift = self._run_layer_parity(tmpdir, "05-flink", "fsi.flink.environment-mtls")
            assert drift == [], f"Expected no drift for 05-flink, got: {drift}"


# ---------------------------------------------------------------------------
# TestAcceleratorNegativeSpace (Phase 11)
# ---------------------------------------------------------------------------

class TestAcceleratorNegativeSpace:
    """Negative-path tests: unknown layer, canon_key mismatch, terraform-module regression."""

    def test_unknown_layer_produces_drift_1(self):
        """A layer whose composite key is not in MODULE_TO_CANON_KEY produces a blocking DRIFT-1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest_path = _write_yaml(
                tmp / "MANIFEST.yaml",
                _make_accelerator_manifest(
                    "accelerator/confluent-on-linuxone",
                    [{"layer": "99-unknown", "canon_key": "fsi.unknown.key"}],
                ),
            )
            defaults_path = _write_yaml(
                tmp / "defaults.yaml",
                _make_defaults(["fsi.unknown.key"]),
            )

            drift = check_parity(manifest_path, defaults_path, tmp / "no-overrides.yaml")
            drift_text = "\n".join(drift)

            assert "[DRIFT-1]" in drift_text
            assert "accelerator/confluent-on-linuxone:99-unknown" in drift_text
            assert "no entry in MODULE_TO_CANON_KEY" in drift_text

    def test_canon_key_mismatch_produces_drift_1(self):
        """A layer whose MANIFEST canon_key disagrees with MODULE_TO_CANON_KEY produces a DRIFT-1
        mentioning both keys for unambiguous CI output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest_path = _write_yaml(
                tmp / "MANIFEST.yaml",
                _make_accelerator_manifest(
                    "accelerator/confluent-on-linuxone",
                    [{"layer": "01-rbac", "canon_key": "wrong.key"}],
                ),
            )
            defaults_path = _write_yaml(
                tmp / "defaults.yaml",
                _make_defaults(["fsi.security.mds-rbac", "wrong.key"]),
            )

            drift = check_parity(manifest_path, defaults_path, tmp / "no-overrides.yaml")
            drift_text = "\n".join(drift)

            assert "[DRIFT-1]" in drift_text
            assert "'wrong.key'" in drift_text
            assert "'fsi.security.mds-rbac'" in drift_text

    def test_terraform_module_parity_unchanged(self):
        """Regression: terraform-module DRIFT-1 still fires when canon key missing,
        even with a clean accelerator entry present in the same MANIFEST."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # MANIFEST with module/topic (canon key missing) + accelerator (clean)
            manifest_data = {
                "version": "1.1.0",
                "capabilities": [
                    {
                        "id": "module/topic",
                        "type": "terraform-module",
                        "name": "topic",
                        "path": "modules/topic",
                        "description": "Test topic module",
                    },
                    {
                        "id": "accelerator/confluent-on-linuxone",
                        "type": "accelerator",
                        "name": "confluent-on-linuxone",
                        "path": "accelerators/confluent-on-linuxone",
                        "apply_sequence": [
                            {
                                "layer": "01-rbac",
                                "path": "layers/01-rbac",
                                "canon_key": "fsi.security.mds-rbac",
                            },
                        ],
                    },
                ],
            }
            manifest_path = _write_yaml(tmp / "MANIFEST.yaml", manifest_data)
            # defaults has the accelerator key but NOT topic_design — terraform-module
            # drift should fire; accelerator drift should NOT.
            defaults_path = _write_yaml(
                tmp / "defaults.yaml",
                _make_defaults(["fsi.security.mds-rbac", "schema_registry"]),
            )

            drift = check_parity(manifest_path, defaults_path, tmp / "no-overrides.yaml")
            drift_text = "\n".join(drift)

            # Terraform-module drift fires
            assert "module/topic" in drift_text
            assert "topic_design" in drift_text
            assert "[DRIFT-1]" in drift_text
            # No accidental accelerator-related drift
            assert "accelerator/confluent-on-linuxone:01-rbac" not in drift_text
