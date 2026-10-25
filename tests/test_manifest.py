"""Tests for MANIFEST.yaml completeness and structure (CNTR-01, CNTR-03)."""
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def manifest(fsi_dsp_root):
    """Load MANIFEST.yaml data."""
    manifest_path = fsi_dsp_root / "MANIFEST.yaml"
    if not manifest_path.exists():
        pytest.skip("MANIFEST.yaml not found")
    return yaml.safe_load(manifest_path.read_text())


@pytest.fixture
def manifest_ids(manifest):
    """Return set of all capability IDs."""
    return {cap["id"] for cap in manifest.get("capabilities", [])}


class TestManifestStructure:
    """CNTR-01: MANIFEST.yaml has correct schema."""

    def test_version_is_1_4_0(self, manifest):
        # Bumped to 1.1.0 in Phase 9 — upstream fsi-dsp main introduced
        # the confluent-on-linuxone accelerator + reference/*-low-latency-azure
        # additions; MANIFEST is a non-breaking 1.0.0 -> 1.1.0 minor bump.
        # 1.2.0: fsi-dsp module/cc-cluster-basic; 1.3.0: scenario/mq-quickstart;
        # 1.4.0: adr/013 (the duplicate ADR-009 renumbered).
        assert manifest["version"] == "1.4.0"

    def test_schema_is_v1(self, manifest):
        assert manifest["schema"] == "fsi-dsp/manifest/v1"

    def test_capabilities_is_list(self, manifest):
        assert isinstance(manifest["capabilities"], list)
        assert len(manifest["capabilities"]) >= 47

    def test_each_capability_has_required_fields(self, manifest):
        for cap in manifest["capabilities"]:
            assert "id" in cap, f"Missing id in capability: {cap.get('name', 'unknown')}"
            assert "type" in cap, f"Missing type in capability: {cap['id']}"
            assert "name" in cap, f"Missing name in capability: {cap['id']}"
            assert "path" in cap, f"Missing path in capability: {cap['id']}"


class TestManifestCompleteness:
    """CNTR-01: All fsi-dsp assets are present."""

    EXPECTED_ROLES = [
        "role/cp_topic", "role/cp_schema", "role/cp_rbac",
        "role/cp_connect", "role/cp_dr_mm2", "role/cp_dr_mrc",
        "role/cp_observability", "role/cfk_operator", "role/cfk_topic",
    ]

    EXPECTED_MODULES = ["module/topic", "module/flink"]

    EXPECTED_SCENARIOS = [
        "scenario/cc-aws", "scenario/cc-azure", "scenario/cc-gcp",
        "scenario/cfk-openshift", "scenario/cp-rhel", "scenario/private-cloud",
    ]

    EXPECTED_ADRS = [f"adr/{str(i).zfill(3)}" for i in range(1, 11)] + ["adr/013"]

    EXPECTED_REFERENCES = [
        "reference/java-producer", "reference/java-consumer",
        "reference/dotnet-producer", "reference/dotnet-consumer",
        "reference/python-producer", "reference/python-consumer",
        "reference/flink-sql", "reference/connect-configs",
        "reference/integration-test", "reference/local-dev",
    ]

    EXPECTED_SCRIPTS = [
        "script/mirror-failover", "script/mirror-failback",
        "script/fsi-dr", "script/consul-flip-region",
        "script/connect-pause-all", "script/validate-apply",
        "script/validate-fips",
    ]

    # MAN-01: type: accelerator landed in Phase 10. List grows with each new accelerator.
    # All IDs MUST start with the "accelerator/" prefix (see test_ids_have_type_prefix).
    EXPECTED_ACCELERATORS = ["accelerator/confluent-on-linuxone"]

    def test_all_roles_present(self, manifest_ids):
        for role_id in self.EXPECTED_ROLES:
            assert role_id in manifest_ids, f"Missing role: {role_id}"

    def test_all_modules_present(self, manifest_ids):
        for mod_id in self.EXPECTED_MODULES:
            assert mod_id in manifest_ids, f"Missing module: {mod_id}"

    def test_all_scenarios_present(self, manifest_ids):
        for scen_id in self.EXPECTED_SCENARIOS:
            assert scen_id in manifest_ids, f"Missing scenario: {scen_id}"

    def test_all_adrs_present(self, manifest_ids):
        for adr_id in self.EXPECTED_ADRS:
            assert adr_id in manifest_ids, f"Missing ADR: {adr_id}"

    def test_all_references_present(self, manifest_ids):
        for ref_id in self.EXPECTED_REFERENCES:
            assert ref_id in manifest_ids, f"Missing reference: {ref_id}"

    def test_all_scripts_present(self, manifest_ids):
        for script_id in self.EXPECTED_SCRIPTS:
            assert script_id in manifest_ids, f"Missing script: {script_id}"

    def test_all_accelerators_present(self, manifest_ids):
        for acc_id in self.EXPECTED_ACCELERATORS:
            assert acc_id in manifest_ids, f"Missing accelerator: {acc_id}"

    def test_ids_are_unique(self, manifest):
        ids = [cap["id"] for cap in manifest["capabilities"]]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {[i for i in ids if ids.count(i) > 1]}"

    def test_ids_have_type_prefix(self, manifest):
        """IDs must include type prefix to avoid ambiguity (Pitfall 2)."""
        valid_prefixes = {
            "role/", "module/", "scenario/", "adr/", "reference/",
            "script/", "observability/", "accelerator/",
        }
        for cap in manifest["capabilities"]:
            has_prefix = any(cap["id"].startswith(p) for p in valid_prefixes)
            assert has_prefix, f"ID '{cap['id']}' missing type prefix"


class TestManifestPathsExist:
    """Verify MANIFEST.yaml paths reference real directories/files."""

    def test_paths_exist(self, manifest, fsi_dsp_root):
        missing = []
        for cap in manifest["capabilities"]:
            path = fsi_dsp_root / cap["path"]
            if not path.exists():
                missing.append(f"{cap['id']}: {cap['path']}")
        assert missing == [], f"Missing paths:\n" + "\n".join(missing)


class TestAdrNumbering:
    """fsi-dsp ADR numbers are unique, registered, and match their IDs and headings
    (two different ADR-009 files existed until fsi-dsp renumbered one to 013)."""

    @pytest.fixture
    def adr_files(self, fsi_dsp_root):
        files = sorted(p for p in (fsi_dsp_root / "docs" / "adr").glob("[0-9][0-9][0-9]-*.md")
                       if p.name != "000-template.md")
        assert len(files) >= 13, files
        return files

    def test_adr_file_numbers_unique(self, adr_files):
        numbers = [p.name[:3] for p in adr_files]
        duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
        assert duplicates == [], f"ADR numbers used more than once: {duplicates}"

    def test_every_adr_file_registered(self, manifest, adr_files):
        registered = {cap["path"] for cap in manifest["capabilities"] if cap["type"] == "adr"}
        unregistered = [f"docs/adr/{p.name}" for p in adr_files if f"docs/adr/{p.name}" not in registered]
        assert unregistered == [], f"ADR files missing from MANIFEST: {unregistered}"

    def test_adr_ids_match_file_numbers(self, manifest):
        for cap in manifest["capabilities"]:
            if cap["type"] == "adr":
                number = cap["id"].split("/", 1)[1][:3]
                assert cap["path"].startswith(f"docs/adr/{number}-"), f"{cap['id']} -> {cap['path']}"

    def test_adr_heading_matches_file_number(self, adr_files):
        for p in adr_files:
            heading = p.read_text().splitlines()[0]
            assert heading.startswith(f"# ADR-{p.name[:3]}:"), f"{p.name}: {heading}"


class TestCIWorkflowsExist:
    """CNTR-03: CI parity workflows exist in both repos."""

    def test_cflt_ai_citation_workflow(self, project_root):
        wf = project_root / ".github" / "workflows" / "manifest-citations.yml"
        assert wf.is_file(), "cflt-ai manifest-citations.yml missing"

    def test_fsi_dsp_stability_workflow(self, fsi_dsp_root):
        wf = fsi_dsp_root / ".github" / "workflows" / "manifest-stability.yml"
        assert wf.is_file(), "fsi-dsp manifest-stability.yml missing"

    def test_check_citations_script(self, project_root):
        script = project_root / "tools" / "check-citations.py"
        assert script.is_file(), "check-citations.py missing"

    def test_check_stability_script(self, fsi_dsp_root):
        script = fsi_dsp_root / "scripts" / "check-manifest-stability.py"
        assert script.is_file(), "check-manifest-stability.py missing"


class TestManifestSchemaValidator:
    """MAN-01: tools/check_manifest.py validates the v1 schema including the accelerator type.

    Coverage:
      - 2 positive (real MANIFEST, synthetic fixture)
      - 4 negative-space (each invariant from 10-CONTEXT.md locked decisions)
      - 1 regression (existing types unchanged by accelerator branch)
      - 1 type-enum gate (unknown type rejected with clear error)
      - 1 KNOWN_TYPES constant-shape lock (drift fails fast, forces doc+code lockstep)
    """

    def test_validator_accepts_real_manifest(self, fsi_dsp_root):
        """Positive: the live post-Phase-10 MANIFEST has zero schema errors."""
        from tools.check_manifest import validate_manifest
        errors = validate_manifest(fsi_dsp_root / "MANIFEST.yaml")
        assert errors == [], f"Real MANIFEST produced schema errors: {errors}"

    def test_validator_accepts_accelerator_fixture(self, project_root):
        """Positive: a well-formed accelerator fixture validates cleanly."""
        from tools.check_manifest import validate_manifest
        fixture = project_root / "tests" / "fixtures" / "manifest_accelerator_valid.yaml"
        errors = validate_manifest(fixture)
        assert errors == [], f"Valid accelerator fixture rejected: {errors}"

    @pytest.fixture
    def invalid_fixtures(self, project_root):
        path = project_root / "tests" / "fixtures" / "manifest_accelerator_invalid.yaml"
        return yaml.safe_load(path.read_text())

    def test_validator_rejects_accelerator_missing_apply_sequence(self, invalid_fixtures):
        from tools.check_manifest import validate_capability
        errors = validate_capability(invalid_fixtures["missing_apply_sequence"])
        assert any("apply_sequence" in e for e in errors), (
            f"Expected apply_sequence error, got {errors}"
        )

    def test_validator_rejects_accelerator_empty_apply_sequence(self, invalid_fixtures):
        from tools.check_manifest import validate_capability
        errors = validate_capability(invalid_fixtures["empty_apply_sequence"])
        assert any("empty" in e for e in errors), (
            f"Expected 'empty' error, got {errors}"
        )

    def test_validator_rejects_accelerator_layer_missing_canon_key(self, invalid_fixtures):
        from tools.check_manifest import validate_capability
        errors = validate_capability(invalid_fixtures["layer_missing_canon_key"])
        assert any("canon_key" in e for e in errors), (
            f"Expected canon_key error, got {errors}"
        )

    def test_validator_rejects_accelerator_missing_apply_command(self, invalid_fixtures):
        from tools.check_manifest import validate_capability
        errors = validate_capability(invalid_fixtures["missing_apply_command"])
        assert any("apply_command" in e for e in errors), (
            f"Expected apply_command error, got {errors}"
        )

    def test_validator_accepts_all_existing_types(self):
        """Regression: every pre-accelerator type validates with just base fields.

        Locks the no-bleed property: the accelerator branch must not impose
        accelerator-specific fields on other types. If a future change adds
        per-type required fields, this test will start failing for that type
        and the relevant fixture must be updated explicitly.
        """
        from tools.check_manifest import validate_capability
        for type_name, id_prefix in [
            ("ansible-role", "role/"),
            ("terraform-module", "module/"),
            ("scenario", "scenario/"),
            ("adr", "adr/"),
            ("reference", "reference/"),
            ("script", "script/"),
            ("observability", "observability/"),
        ]:
            cap = {
                "id": f"{id_prefix}fixture",
                "type": type_name,
                "name": "fixture",
                "path": f"{id_prefix}fixture",
            }
            errors = validate_capability(cap)
            assert errors == [], f"Existing type {type_name} regressed: {errors}"

    def test_validator_rejects_unknown_type(self):
        """Type enum gate: any type outside KNOWN_TYPES is rejected with a clear error."""
        from tools.check_manifest import validate_capability
        cap = {"id": "x/y", "type": "frobnicator", "name": "y", "path": "x/y"}
        errors = validate_capability(cap)
        assert any("unknown type" in e.lower() for e in errors), (
            f"Expected unknown-type error, got {errors}"
        )

    def test_known_types_constant_shape(self):
        """KNOWN_TYPES must match exactly the documented set.

        Drift here forces a tools/manifest-schema.md update in the same PR.
        """
        from tools.check_manifest import KNOWN_TYPES
        assert KNOWN_TYPES == {
            "ansible-role", "terraform-module", "scenario", "adr",
            "reference", "script", "observability", "accelerator",
        }
