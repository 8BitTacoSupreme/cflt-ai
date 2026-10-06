"""Tests for canon overlay stack structure and resolution."""
import re
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def canon_root(project_root):
    return project_root / "canon"


class TestCanonStructure:
    """CANST-01: Verify directory structure exists."""

    def test_base_layer_exists(self, canon_root):
        assert (canon_root / "base").is_dir()
        assert (canon_root / "base" / "defaults.yaml").is_file()
        assert (canon_root / "base" / "README.md").is_file()

    def test_industry_fsi_layer_exists(self, canon_root):
        assert (canon_root / "industry" / "fsi").is_dir()
        assert (canon_root / "industry" / "fsi" / "overrides.yaml").is_file()
        assert (canon_root / "industry" / "fsi" / "README.md").is_file()

    def test_industry_fsi_adrs_exists(self, canon_root):
        assert (canon_root / "industry" / "fsi" / "adrs").is_dir()
        assert (canon_root / "industry" / "fsi" / "adrs" / "README.md").is_file()

    def test_customer_layer_exists(self, canon_root):
        assert (canon_root / "customer").is_dir()
        assert (canon_root / "customer" / "README.md").is_file()

    def test_engagement_layer_exists(self, canon_root):
        assert (canon_root / "engagement").is_dir()
        assert (canon_root / "engagement" / "README.md").is_file()


class TestCanonDefaults:
    """Verify base defaults match CLAUDE.md canonical values."""

    @pytest.fixture
    def defaults(self, canon_root):
        return yaml.safe_load((canon_root / "base" / "defaults.yaml").read_text())

    def test_producer_acks_all(self, defaults):
        assert defaults["producer"]["acks"] == "all"

    def test_replication_factor_3(self, defaults):
        assert defaults["topic_design"]["replication_factor"] == 3

    def test_min_insync_replicas_2(self, defaults):
        assert defaults["topic_design"]["min_insync_replicas"] == 2

    def test_consumer_auto_commit_disabled(self, defaults):
        assert defaults["consumer"]["enable_auto_commit"] is False

    def test_compression_lz4(self, defaults):
        assert defaults["producer"]["compression_type"] == "lz4"

    def test_idempotence_enabled(self, defaults):
        assert defaults["producer"]["enable_idempotence"] is True

    def test_schema_format_avro(self, defaults):
        assert defaults["schema_registry"]["format"] == "avro"


class TestCanonOverrides:
    """CANST-02: Verify override semantics work."""

    @pytest.fixture
    def overrides(self, canon_root):
        return yaml.safe_load(
            (canon_root / "industry" / "fsi" / "overrides.yaml").read_text()
        )

    def test_fsi_overrides_have_adr_sources(self, overrides):
        """CANST-03: Every override references an ADR."""
        content = yaml.dump(overrides)
        assert "override_source:" in content
        assert "fsi-dsp://adr/" in content

    def test_fsi_references_adr_001(self, overrides):
        assert overrides["schema_registry"]["override_source"] == "fsi-dsp://adr/001"

    def test_fsi_references_adr_005(self, overrides):
        assert overrides["cluster_linking"]["override_source"] == "fsi-dsp://adr/005"

    def test_fsi_has_latency_tiers(self, overrides):
        assert "latency_tiers" in overrides
        assert overrides["latency_tiers"]["market_data"] == "sub-millisecond"


class TestCanonStackResolution:
    """CANST-02 + CANST-04: Verify stack resolution and hash."""

    def test_resolve_stack_returns_tuple(self, project_root):
        import sys
        sys.path.insert(0, str(project_root))
        from canon.stack import resolve_stack
        config, stack_hash = resolve_stack()
        assert isinstance(config, dict)
        assert isinstance(stack_hash, str)
        assert len(stack_hash) == 16  # SHA-256 truncated to 16 hex chars

    def test_resolve_stack_merges_layers(self, project_root):
        import sys
        sys.path.insert(0, str(project_root))
        from canon.stack import resolve_stack
        config, _ = resolve_stack()
        # Base producer.acks should survive merge
        assert config["producer"]["acks"] == "all"
        # FSI latency_tiers should be present from override
        assert "latency_tiers" in config

    def test_provenance_footer_format(self, project_root):
        import sys
        sys.path.insert(0, str(project_root))
        from canon.stack import provenance_footer
        footer = provenance_footer()
        assert "Canon stack:" in footer
        assert "Hash:" in footer
        assert "base" in footer

    def test_active_layers(self, project_root):
        import sys
        sys.path.insert(0, str(project_root))
        from canon.stack import active_layers
        layers = active_layers()
        assert "base" in layers
        assert "industry/fsi" in layers

    def test_deep_merge_override_wins(self, project_root):
        import sys
        sys.path.insert(0, str(project_root))
        from canon.stack import _deep_merge
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"b": 99}}
        result = _deep_merge(base, override)
        assert result["a"]["b"] == 99  # Override wins
        assert result["a"]["c"] == 2   # Base preserved


class TestExternalCanonPath:
    """Client/engagement silos resolve from CFLT_CANON_EXTERNAL_PATH."""

    def _import(self, project_root):
        import sys
        sys.path.insert(0, str(project_root))
        import canon.stack as stack
        return stack

    def test_unset_env_is_backcompat(self, project_root, monkeypatch):
        """No external path → byte-identical to pre-external-path behavior."""
        stack = self._import(project_root)
        monkeypatch.delenv("CFLT_CANON_EXTERNAL_PATH", raising=False)
        _, h = stack.resolve_stack()
        assert stack.active_layers() == ["base", "industry/fsi"]
        # Re-resolving is deterministic.
        _, h2 = stack.resolve_stack()
        assert h == h2

    def test_external_customer_layer_merges_and_wins(
        self, project_root, tmp_path, monkeypatch
    ):
        stack = self._import(project_root)
        client = tmp_path / "customer" / "examplebank"
        client.mkdir(parents=True)
        (client / "overrides.yaml").write_text(
            "producer:\n"
            '  compression_type: "zstd"\n'
            '  override_source: "customer/examplebank/adr-001"\n'
            "cluster_linking:\n"
            '  preferred_over: "examplebank-override"\n'
        )
        monkeypatch.setenv("CFLT_CANON_EXTERNAL_PATH", str(tmp_path))

        cfg, h = stack.resolve_stack(customer="examplebank")
        # Client override wins over base (lz4) and over industry/fsi.
        assert cfg["producer"]["compression_type"] == "zstd"
        assert cfg["cluster_linking"]["preferred_over"] == "examplebank-override"
        # Non-overridden base keys survive.
        assert cfg["producer"]["acks"] == "all"
        # The active layer list reflects the external client layer.
        assert "customer/examplebank" in stack.active_layers(customer="examplebank")
        # Hash differs from the unselected stack.
        _, base_hash = stack.resolve_stack()
        assert h != base_hash

    def test_external_path_does_not_leak_without_selection(
        self, project_root, tmp_path, monkeypatch
    ):
        """Setting the path but not selecting the customer keeps client data out."""
        stack = self._import(project_root)
        client = tmp_path / "customer" / "examplebank"
        client.mkdir(parents=True)
        (client / "overrides.yaml").write_text('producer:\n  compression_type: "zstd"\n')
        monkeypatch.setenv("CFLT_CANON_EXTERNAL_PATH", str(tmp_path))

        cfg, _ = stack.resolve_stack()  # no customer= selection
        assert cfg["producer"]["compression_type"] == "lz4"  # base, not examplebank
        assert "customer/examplebank" not in stack.active_layers()


class TestIndustryRouting:
    """Industry overlays are selectable by directory via canon_layer."""

    def test_operator_routes_to_named_industry(self, project_root, tmp_path, monkeypatch):
        import sys
        sys.path.insert(0, str(project_root))
        from canon.stack import resolve_stack
        # Stand up a throwaway industry overlay (a name not present in the repo) in
        # an external root, to prove operator routing honors an arbitrary industry.
        telco = tmp_path / "industry" / "telco"
        telco.mkdir(parents=True)
        (telco / "overrides.yaml").write_text(
            "producer:\n"
            '  compression_type: "snappy"\n'
            '  override_source: "industry/telco/adr-001"\n'
        )
        monkeypatch.setenv("CFLT_CANON_EXTERNAL_PATH", str(tmp_path))
        cfg, _ = resolve_stack(family="operator", canon_layer="industry/telco")
        assert cfg["producer"]["compression_type"] == "snappy"

    def test_repo_industry_wins_over_external(self, project_root, tmp_path, monkeypatch):
        """Repo-internal layer is searched first; external can't shadow it."""
        import sys
        sys.path.insert(0, str(project_root))
        from canon.stack import resolve_stack
        shadow = tmp_path / "industry" / "retail"
        shadow.mkdir(parents=True)
        (shadow / "overrides.yaml").write_text(
            'producer:\n  compression_type: "snappy"\n'
        )
        monkeypatch.setenv("CFLT_CANON_EXTERNAL_PATH", str(tmp_path))
        cfg, _ = resolve_stack(canon_layer="industry/retail")
        # The committed retail overlay (zstd) wins; external cannot shadow repo IP.
        assert cfg["producer"]["compression_type"] == "zstd"
