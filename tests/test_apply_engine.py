"""Unit tests for apply_engine.py (ACTA-02, ACTA-03, ACTA-04, ACTA-05)."""
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.apply_engine import (
    load_profile,
    check_profile_permits,
    check_tool_permitted,
    load_tool_classification,
    emit_activity_log_apply,
    write_incident_article,
)


# ---------------------------------------------------------------------------
# TestProfileLoading (ACTA-03)
# ---------------------------------------------------------------------------


class TestProfileLoading:
    def test_load_known_profiles(self):
        """All three known profiles load without error."""
        for name in ("read-only", "engineer", "break-glass"):
            profile = load_profile(name)
            assert isinstance(profile, dict), f"load_profile({name!r}) must return dict"
            assert profile["name"] == name, f"name field mismatch for {name!r}"
            assert "allowed_operations" in profile, f"missing allowed_operations for {name!r}"

    def test_load_read_only_returns_empty_operations(self):
        """read-only profile has empty allowed_operations list."""
        profile = load_profile("read-only")
        assert profile["allowed_operations"] == []

    def test_load_engineer_contains_standard_modules(self):
        """engineer profile contains module/topic, module/flink, role/cp_schema."""
        profile = load_profile("engineer")
        ops = profile["allowed_operations"]
        assert "module/topic" in ops
        assert "module/flink" in ops
        assert "role/cp_schema" in ops
        assert "role/cp_rbac" in ops
        assert "role/cp_connect" in ops

    def test_load_break_glass_has_explicit_operations(self):
        """break-glass profile has explicit allowed_operations (wildcard replaced per ACTG-01)."""
        profile = load_profile("break-glass")
        ops = profile["allowed_operations"]
        assert "*" not in ops, "Wildcard must be replaced with explicit operations per ACTG-01"
        assert len(ops) > 0, "break-glass must have at least one explicit operation"
        assert "module/topic" in ops

    def test_unknown_profile_raises(self):
        """Unknown profile name raises ValueError mentioning 'Unknown profile'."""
        with pytest.raises(ValueError, match="Unknown profile"):
            load_profile("admin")

    def test_empty_profile_raises(self):
        """Empty string profile name raises ValueError."""
        with pytest.raises(ValueError):
            load_profile("")

    def test_none_profile_raises(self):
        """None profile name raises ValueError or TypeError."""
        with pytest.raises((ValueError, TypeError)):
            load_profile(None)


# ---------------------------------------------------------------------------
# TestProfileFiles (ACTA-03 — files on disk)
# ---------------------------------------------------------------------------


class TestProfileFiles:
    def test_readonly_permits_nothing(self):
        """read-only profile denies all artifact operations."""
        profile = load_profile("read-only")
        assert not check_profile_permits(profile, "module/topic")
        assert not check_profile_permits(profile, "module/flink")
        assert not check_profile_permits(profile, "script/fsi-dr")

    def test_engineer_permits_standard_modules(self):
        """engineer profile permits standard non-destructive modules."""
        profile = load_profile("engineer")
        assert check_profile_permits(profile, "module/topic")
        assert check_profile_permits(profile, "module/flink")
        assert check_profile_permits(profile, "role/cp_schema")
        assert check_profile_permits(profile, "role/cp_rbac")
        assert check_profile_permits(profile, "role/cp_connect")

    def test_engineer_denies_destructive(self):
        """engineer profile denies destructive/non-standard operations.

        Note: scenario/cc-{aws,azure,gcp} were explicitly added to engineer
        during Phase F.1 smoke testing (they're the Confluent Cloud starter
        kits and FRANZ's primary apply target). Negative-space asserts now
        target the on-prem CFK/CP scenarios and the DR script — those
        remain destructive-adjacent and only break-glass should run them.
        """
        profile = load_profile("engineer")
        assert not check_profile_permits(profile, "script/fsi-dr")
        assert not check_profile_permits(profile, "scenario/cfk-openshift")
        assert not check_profile_permits(profile, "scenario/cp-rhel")
        assert not check_profile_permits(profile, "scenario/private-cloud")

    def test_break_glass_permits_explicit_operations(self):
        """break-glass permits explicit operations in its allowed_operations list (ACTG-01: wildcard replaced)."""
        profile = load_profile("break-glass")
        assert check_profile_permits(profile, "module/topic")
        assert check_profile_permits(profile, "script/fsi-dr")
        assert check_profile_permits(profile, "scenario/cc-aws")
        # Unknown operation not in explicit list is denied (wildcard removed)
        assert not check_profile_permits(profile, "anything/at/all")

    def test_engineer_denies_script(self):
        """engineer profile does not permit script/fsi-dr."""
        profile = load_profile("engineer")
        assert not check_profile_permits(profile, "script/fsi-dr")


# ---------------------------------------------------------------------------
# TestProfileEnforcement (ACTA-03)
# ---------------------------------------------------------------------------


class TestProfileEnforcement:
    def test_permit_exact_match(self):
        """Exact match on allowed_operations returns True."""
        profile = {"name": "custom", "allowed_operations": ["module/topic"]}
        assert check_profile_permits(profile, "module/topic") is True

    def test_deny_unknown_artifact(self):
        """Artifact not in allowed_operations returns False."""
        profile = {"name": "custom", "allowed_operations": ["module/topic"]}
        assert check_profile_permits(profile, "module/flink") is False

    def test_wildcard_permits_all(self):
        """Wildcard '*' in allowed_operations permits any artifact."""
        profile = {"name": "custom", "allowed_operations": ["*"]}
        assert check_profile_permits(profile, "module/topic") is True
        assert check_profile_permits(profile, "anything") is True

    def test_empty_list_denies_all(self):
        """Empty allowed_operations list denies all operations."""
        profile = {"name": "custom", "allowed_operations": []}
        assert check_profile_permits(profile, "module/topic") is False
        assert check_profile_permits(profile, "script/fsi-dr") is False


# ---------------------------------------------------------------------------
# TestActivityLog (ACTA-04)
# ---------------------------------------------------------------------------


class TestActivityLog:
    def test_emit_creates_file(self, tmp_path, monkeypatch):
        """emit_activity_log_apply creates the log file when it does not exist."""
        import tools.apply_engine as ae
        monkeypatch.setattr(ae, "PROJECT_ROOT", tmp_path)

        activity_dir = tmp_path / "wiki" / "activity"
        activity_dir.mkdir(parents=True)

        emit_activity_log_apply(
            overlay="base",
            plan_path="plans/trade-topic-plan.md",
            artifact_id="module/topic",
            profile_name="engineer",
            confirmation_status="confirmed",
            execution_result="success",
            duration_seconds=3.2,
            gate_results=[],
            operator="test-operator",
        )

        # File should now exist — YYYY-MM.md
        log_files = list(activity_dir.glob("*.md"))
        assert len(log_files) == 1, f"Expected 1 log file, found: {log_files}"

    def test_emit_appends_to_existing(self, tmp_path, monkeypatch):
        """emit_activity_log_apply appends to an existing log file."""
        import tools.apply_engine as ae
        monkeypatch.setattr(ae, "PROJECT_ROOT", tmp_path)

        activity_dir = tmp_path / "wiki" / "activity"
        activity_dir.mkdir(parents=True)

        # Create a pre-existing log file with a dummy entry
        from datetime import datetime
        month_key = datetime.utcnow().strftime("%Y-%m")
        log_file = activity_dir / f"{month_key}.md"
        log_file.write_text("# Activity Log\n\n## 2026-04-01T00:00:00Z\n**Skill:** /dsp:plan\n")

        emit_activity_log_apply(
            overlay="base",
            plan_path="plans/trade-topic-plan.md",
            artifact_id="module/topic",
            profile_name="engineer",
            confirmation_status="confirmed",
            execution_result="success",
            duration_seconds=1.0,
            gate_results=[],
            operator="test-operator",
        )

        content = log_file.read_text()
        # Both entries must be present
        assert "/dsp:plan" in content
        assert "/dsp:apply" in content

    def test_entry_contains_apply_fields(self, tmp_path, monkeypatch):
        """Activity log entry contains all required /dsp:apply fields."""
        import tools.apply_engine as ae
        monkeypatch.setattr(ae, "PROJECT_ROOT", tmp_path)

        activity_dir = tmp_path / "wiki" / "activity"
        activity_dir.mkdir(parents=True)

        emit_activity_log_apply(
            overlay="fsi",
            plan_path="plans/flink-pool-plan.md",
            artifact_id="module/flink",
            profile_name="break-glass",
            confirmation_status="confirmed",
            execution_result="success",
            duration_seconds=5.7,
            gate_results=[],
            operator="ops-lead",
        )

        log_files = list(activity_dir.glob("*.md"))
        content = log_files[0].read_text()

        assert "**Skill:** /dsp:apply" in content
        assert "**Operator:**" in content
        assert "**Profile:**" in content
        assert "**Confirmation status:**" in content
        assert "**Execution result:**" in content
        assert "**Duration seconds:**" in content


# ---------------------------------------------------------------------------
# TestIncidentArticle (ACTA-05)
# ---------------------------------------------------------------------------


class TestIncidentArticle:
    def test_creates_file(self, tmp_path, monkeypatch):
        """write_incident_article creates a file in wiki/incidents/."""
        import tools.apply_engine as ae
        monkeypatch.setattr(ae, "PROJECT_ROOT", tmp_path)

        incidents_dir = tmp_path / "wiki" / "incidents"
        incidents_dir.mkdir(parents=True)

        result_path = write_incident_article(
            slug="trade-topic-create",
            artifact_id="module/topic",
            operator="test-operator",
            profile_name="engineer",
            outcome="success",
            canon_hash="abc1234def56789",
            plan_path="plans/trade-topic-plan.md",
            gate_results=[],
            execution_result="success",
        )

        assert result_path.exists(), f"Incident article not found at {result_path}"
        # File should be inside wiki/incidents/
        assert "wiki/incidents" in str(result_path) or "wiki" in result_path.parts

    def test_frontmatter_keys(self, tmp_path, monkeypatch):
        """Incident article frontmatter contains required keys."""
        import tools.apply_engine as ae
        monkeypatch.setattr(ae, "PROJECT_ROOT", tmp_path)

        incidents_dir = tmp_path / "wiki" / "incidents"
        incidents_dir.mkdir(parents=True)

        result_path = write_incident_article(
            slug="flink-pool-provision",
            artifact_id="module/flink",
            operator="sre-01",
            profile_name="break-glass",
            outcome="success",
            canon_hash="deadbeef12345678",
            plan_path="plans/flink-pool-plan.md",
            gate_results=[],
            execution_result="success",
        )

        content = result_path.read_text()
        # YAML frontmatter must contain all 7 required keys
        assert "artifact:" in content
        assert "operator:" in content
        assert "profile:" in content
        assert "outcome:" in content
        assert "canon_hash:" in content
        assert "plan_ref:" in content
        assert "timestamp:" in content

    def test_incident_sections(self, tmp_path, monkeypatch):
        """Incident article contains the four required sections."""
        import tools.apply_engine as ae
        monkeypatch.setattr(ae, "PROJECT_ROOT", tmp_path)

        incidents_dir = tmp_path / "wiki" / "incidents"
        incidents_dir.mkdir(parents=True)

        result_path = write_incident_article(
            slug="schema-update",
            artifact_id="role/cp_schema",
            operator="test-operator",
            profile_name="engineer",
            outcome="success",
            canon_hash="cafe1234cafe5678",
            plan_path="plans/schema-plan.md",
            gate_results=[],
            execution_result="success",
        )

        content = result_path.read_text()
        assert "## What Changed" in content
        assert "## Why" in content
        assert "## Gate Results" in content
        assert "## Provenance" in content

    def test_gate_results_table(self, tmp_path, monkeypatch):
        """Gate Results section contains a markdown table with Gate/Status/Detail columns."""
        import tools.apply_engine as ae
        monkeypatch.setattr(ae, "PROJECT_ROOT", tmp_path)

        incidents_dir = tmp_path / "wiki" / "incidents"
        incidents_dir.mkdir(parents=True)

        gate_results = [
            {"gate": "canon_compliance", "status": "pass", "detail": "Canon compliant", "evidence": []},
            {"gate": "fsi_dsp_coverage", "status": "pass", "detail": "Matched module/topic", "evidence": ["module/topic"]},
        ]

        result_path = write_incident_article(
            slug="topic-with-gates",
            artifact_id="module/topic",
            operator="test-operator",
            profile_name="engineer",
            outcome="success",
            canon_hash="abcd1234abcd5678",
            plan_path="plans/topic-plan.md",
            gate_results=gate_results,
            execution_result="success",
        )

        content = result_path.read_text()
        # Table must have header row with Gate, Status, Detail columns
        assert "Gate" in content
        assert "Status" in content
        assert "Detail" in content
        # Table separator row
        assert "---" in content
        # Gate names from gate_results
        assert "canon_compliance" in content
        assert "fsi_dsp_coverage" in content

    def test_file_naming_convention(self, tmp_path, monkeypatch):
        """Incident file name follows <slug>-<YYYY-MM-DD>.md convention."""
        import tools.apply_engine as ae
        monkeypatch.setattr(ae, "PROJECT_ROOT", tmp_path)

        incidents_dir = tmp_path / "wiki" / "incidents"
        incidents_dir.mkdir(parents=True)

        result_path = write_incident_article(
            slug="my-slug",
            artifact_id="module/topic",
            operator="test-operator",
            profile_name="engineer",
            outcome="success",
            canon_hash="aaaa1111aaaa2222",
            plan_path="plans/plan.md",
            gate_results=[],
            execution_result="success",
        )

        filename = result_path.name
        assert filename.startswith("my-slug-")
        assert filename.endswith(".md")
        # Date portion: 4 digits dash 2 digits dash 2 digits
        import re
        assert re.search(r"\d{4}-\d{2}-\d{2}", filename), f"Date not in filename: {filename}"


# ---------------------------------------------------------------------------
# TestBypassPrevention (ACTA-02)
# ---------------------------------------------------------------------------


class TestBypassPrevention:
    def test_no_input_call(self):
        """apply_engine.py source does not contain input() call."""
        source_path = PROJECT_ROOT / "tools" / "apply_engine.py"
        source_text = source_path.read_text()
        assert "input(" not in source_text, (
            "apply_engine.py must not contain input() — no interactive prompts allowed"
        )

    def test_no_skip_confirmation(self):
        """apply_engine.py source does not contain skip_confirmation pattern."""
        source_path = PROJECT_ROOT / "tools" / "apply_engine.py"
        source_text = source_path.read_text()
        assert "skip_confirmation" not in source_text, (
            "apply_engine.py must not contain skip_confirmation"
        )

    def test_no_bypass_confirmation(self):
        """apply_engine.py source does not contain bypass_confirmation pattern."""
        source_path = PROJECT_ROOT / "tools" / "apply_engine.py"
        source_text = source_path.read_text()
        assert "bypass_confirmation" not in source_text, (
            "apply_engine.py must not contain bypass_confirmation"
        )


# ---------------------------------------------------------------------------
# TestToolClassification (ACTG-01)
# ---------------------------------------------------------------------------


class TestToolClassification:
    def test_load_tool_classification_returns_dict(self):
        """load_tool_classification() returns dict with 'tools' and 'unclassified_policy'."""
        classification = load_tool_classification()
        assert isinstance(classification, dict)
        assert "tools" in classification
        assert "unclassified_policy" in classification

    def test_read_only_profile_permits_read_only_tool(self):
        """read-only profile permits a read-only classified tool."""
        assert check_tool_permitted("read-only", "list-topics") is True

    def test_read_only_profile_denies_engineer_tool(self):
        """read-only profile denies an engineer-tier tool."""
        assert check_tool_permitted("read-only", "create-topics") is False

    def test_engineer_profile_permits_engineer_tool(self):
        """engineer profile permits an engineer-tier tool."""
        assert check_tool_permitted("engineer", "create-topics") is True

    def test_engineer_profile_denies_break_glass_tool(self):
        """engineer profile denies a break-glass-tier tool."""
        assert check_tool_permitted("engineer", "delete-schema") is False

    def test_break_glass_profile_permits_break_glass_tool(self):
        """break-glass profile permits a break-glass-tier tool."""
        assert check_tool_permitted("break-glass", "delete-schema") is True

    def test_unclassified_tool_denied_fail_closed(self):
        """Unclassified tool is denied (fail-closed) regardless of profile."""
        assert check_tool_permitted("engineer", "nonexistent_tool_xyz") is False


# ---------------------------------------------------------------------------
# TestCustomerOverlay (ACTG-04)
# ---------------------------------------------------------------------------


class TestCustomerOverlay:
    def test_acme_bank_engineer_missing_flink(self):
        """acme-bank engineer overlay does NOT have module/flink in allowed_operations."""
        profile = load_profile("engineer", customer="acme-bank")
        assert "module/flink" not in profile["allowed_operations"]

    def test_acme_bank_engineer_has_cp_audit(self):
        """acme-bank engineer overlay has role/cp_audit in allowed_operations."""
        profile = load_profile("engineer", customer="acme-bank")
        assert "role/cp_audit" in profile["allowed_operations"]

    def test_nonexistent_customer_falls_back_to_base(self):
        """load_profile() with nonexistent customer falls back to base engineer profile."""
        profile = load_profile("engineer", customer="nonexistent-customer-xyz")
        # base engineer has module/flink
        assert "module/flink" in profile["allowed_operations"]

    def test_no_customer_param_backward_compat(self):
        """load_profile() without customer param still works (backward compat)."""
        profile = load_profile("engineer")
        assert isinstance(profile, dict)
        assert profile["name"] == "engineer"


# ---------------------------------------------------------------------------
# TestOverrideReasonLogging (ACTG-03)
# ---------------------------------------------------------------------------


class TestOverrideReasonLogging:
    def test_emit_activity_log_includes_override_reason(self, tmp_path, monkeypatch):
        """emit_activity_log_apply with override_reason writes reason to log content."""
        import tools.apply_engine as ae
        monkeypatch.setattr(ae, "PROJECT_ROOT", tmp_path)

        activity_dir = tmp_path / "wiki" / "activity"
        activity_dir.mkdir(parents=True)

        emit_activity_log_apply(
            overlay="base",
            plan_path="plans/dr-failover.md",
            artifact_id="module/topic",
            profile_name="break-glass",
            confirmation_status="confirmed",
            execution_result="success",
            duration_seconds=2.5,
            gate_results=[],
            operator="ops-lead",
            override_reason="P0 incident",
        )

        log_files = list(activity_dir.glob("*.md"))
        content = log_files[0].read_text()
        assert "P0 incident" in content

    def test_write_incident_article_includes_override_reason_frontmatter(self, tmp_path, monkeypatch):
        """write_incident_article with override_reason writes it to frontmatter."""
        import tools.apply_engine as ae
        monkeypatch.setattr(ae, "PROJECT_ROOT", tmp_path)

        incidents_dir = tmp_path / "wiki" / "incidents"
        incidents_dir.mkdir(parents=True)

        result_path = write_incident_article(
            slug="dr-failover",
            artifact_id="module/topic",
            operator="ops-lead",
            profile_name="break-glass",
            outcome="success",
            canon_hash="abcd1234abcd5678",
            plan_path="plans/dr-failover.md",
            gate_results=[],
            execution_result="success",
            override_reason="DR failover",
        )

        content = result_path.read_text()
        assert "override_reason: DR failover" in content
