#!/usr/bin/env python3
"""
canon/stack.py — Canon overlay stack resolution.

Loads base defaults, then merges industry/customer/engagement overrides
in order. Computes a SHA-256 hash of the resolved config for provenance.

Usage:
    from canon.stack import resolve_stack
    config, stack_hash = resolve_stack()
    # config is the merged dict, stack_hash is a hex string

H.4b: resolve_stack() now accepts `family` and `canon_layer` keyword args.
      Operator family (default) uses industry/fsi as before; developer family
      routes to the profile's canon_layer (default industry/fsi/developer-sandbox).
      v1.0 callers (resolve_stack() with no args, or with customer=...) are
      byte-compatible — the operator default preserves exact pre-H.4b behavior.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


CANON_ROOT = Path(__file__).resolve().parent


def _layer_roots() -> List[Path]:
    """Ordered roots to search for layer config files.

    The repo-internal canon dir is always searched first. Additional roots come
    from CFLT_CANON_EXTERNAL_PATH (os-pathsep separated, ~ expanded) — this is how
    client/engagement overlays live in a private repo that never enters the shared
    cflt-ai tree. External roots mirror the canon layer paths, e.g.
    ~/clients/examplebank-canon/customer/examplebank/overrides.yaml.
    """
    roots = [CANON_ROOT]
    for part in os.environ.get("CFLT_CANON_EXTERNAL_PATH", "").split(os.pathsep):
        part = part.strip()
        if part:
            roots.append(Path(part).expanduser().resolve())
    return roots


def _layer_order_for(family: str = "operator", canon_layer: Optional[str] = None) -> List[str]:
    """Compute the layer order for the canon stack (H.4b).

    Operator family uses the prod FSI overlay (industry/fsi) as the industry layer.
    Developer family uses `canon_layer` (defaults to industry/fsi/developer-sandbox)
    as the industry layer.

    Customer and engagement layers are appended last regardless of family.

    Args:
        family:      "operator" (default) or "developer".
        canon_layer: Optional explicit industry-layer path. When None, defaults are
                     operator → "industry/fsi"; developer → "industry/fsi/developer-sandbox".

    Returns:
        List of layer names in composition order.

    Raises:
        ValueError: If family is not a recognized canon family.
    """
    if family == "developer":
        industry_layer = canon_layer or "industry/fsi/developer-sandbox"
    elif family == "operator":
        industry_layer = canon_layer or "industry/fsi"
    else:
        raise ValueError(f"Unknown profile family for canon stack: {family!r}")
    return ["base", industry_layer, "customer", "engagement"]


# Module-level constant for back-compat — any code that imported LAYER_ORDER directly
# still gets the operator-family default order. H.4b: prefer _layer_order_for() in new code.
LAYER_ORDER = _layer_order_for()


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_layer(layer_name: str) -> dict:
    """Load a layer's YAML config. Returns empty dict if not found.

    Searches each root from _layer_roots() in order; first hit wins. This lets
    client/engagement overlays resolve from an external private repo while base
    and industry stay repo-internal.
    """
    # Base uses defaults.yaml; all others use overrides.yaml
    filename = "defaults.yaml" if layer_name == "base" else "overrides.yaml"
    for root in _layer_roots():
        config_file = root / layer_name / filename
        if config_file.exists():
            data = yaml.safe_load(config_file.read_text())
            return data if isinstance(data, dict) else {}
    return {}


def _resolve_layer_names(
    layers: Optional[List[str]] = None,
    customer: Optional[str] = None,
    engagement: Optional[str] = None,
    family: str = "operator",
    canon_layer: Optional[str] = None,
) -> List[str]:
    """Build the concrete layer-name list, substituting customer/engagement names.

    Shared by resolve_stack() and active_layers() so both agree on which layers
    are in play for a given selection.
    """
    if layers is None:
        layers = _layer_order_for(family=family, canon_layer=canon_layer)
    resolved = []
    for layer in layers:
        if layer == "customer" and customer:
            resolved.append(f"customer/{customer}")
        elif layer == "engagement" and engagement:
            resolved.append(f"engagement/{engagement}")
        else:
            resolved.append(layer)
    return resolved


def resolve_stack(
    layers: Optional[List[str]] = None,
    customer: Optional[str] = None,
    engagement: Optional[str] = None,
    family: str = "operator",
    canon_layer: Optional[str] = None,
) -> Tuple[Dict, str]:
    """Resolve the full canon stack by merging layers in order.

    Args:
        layers:      Override default layer order (for testing). When provided,
                     `family` and `canon_layer` are ignored — caller has full control.
        customer:    Customer name to load customer/{name}/overrides.yaml.
        engagement:  Engagement name to load engagement/{name}/overrides.yaml.
        family:      "operator" (default) or "developer" — selects industry-layer
                     routing when `layers` is not explicitly provided. Default
                     preserves byte-identical v1.0 behavior.
        canon_layer: Optional explicit industry-layer path (e.g.,
                     "industry/fsi/developer-sandbox"). Used when the profile JSON
                     specifies its own canon_layer field. If None, defaults are
                     operator → "industry/fsi"; developer → "industry/fsi/developer-sandbox".

    Returns:
        Tuple of (merged_config_dict, sha256_hex_hash).

    Raises:
        ValueError: If family is unknown (via _layer_order_for).
    """
    resolved_layers = _resolve_layer_names(
        layers=layers,
        customer=customer,
        engagement=engagement,
        family=family,
        canon_layer=canon_layer,
    )

    merged = {}

    for layer_name in resolved_layers:
        layer_data = _load_layer(layer_name)
        if layer_data:
            merged = _deep_merge(merged, layer_data)

    # Compute deterministic hash of resolved config
    canonical_json = json.dumps(merged, sort_keys=True, default=str)
    stack_hash = hashlib.sha256(canonical_json.encode()).hexdigest()[:16]

    return merged, stack_hash


def layer_has_overrides(layer_name: str) -> bool:
    """True if a layer resolves to an overrides.yaml in any canon root.

    Used to reject a selected industry/tier that would otherwise resolve to an
    empty layer and silently degrade to base-only canon.
    """
    return any((root / layer_name / "overrides.yaml").exists() for root in _layer_roots())


def available_industries() -> List[str]:
    """Industry names with a prod overrides.yaml, across all roots (repo + external).

    A bare directory with no overrides.yaml is not a usable industry — excluding it
    here means validate_industry() rejects it instead of resolving to empty canon.
    """
    found = set()
    for root in _layer_roots():
        industry_dir = root / "industry"
        if industry_dir.is_dir():
            found.update(
                p.name for p in industry_dir.iterdir()
                if p.is_dir() and (p / "overrides.yaml").exists()
            )
    return sorted(found)


def validate_industry(industry: Optional[str]) -> str:
    """Return the industry name (default 'fsi'), validating it exists across canon roots.

    Shared by the scaffold rail (tools/scaffold_engine.py) and the plan/apply act rail
    (tools/act_gates.py) so industry selection fails loudly on a typo in both places
    instead of silently falling back to base-only canon.
    """
    selected = industry or "fsi"
    available = available_industries()
    if selected not in available:
        raise ValueError(
            f"Unknown industry {selected!r} — available: {available}. "
            f"Add canon/industry/{selected}/ (or set CFLT_CANON_EXTERNAL_PATH)."
        )
    return selected


def active_layers(
    layers: Optional[List[str]] = None,
    customer: Optional[str] = None,
    engagement: Optional[str] = None,
    family: str = "operator",
    canon_layer: Optional[str] = None,
) -> List[str]:
    """Return list of layers that have config files present (searching all roots).

    With no args, reports the operator-default layers present in the repo
    (byte-compatible with the pre-external-path behavior). Pass the same selection
    args as resolve_stack() to reflect an active customer/engagement layer —
    including one resolved from CFLT_CANON_EXTERNAL_PATH.
    """
    names = _resolve_layer_names(
        layers=layers,
        customer=customer,
        engagement=engagement,
        family=family,
        canon_layer=canon_layer,
    )
    present = []
    for layer in names:
        filename = "defaults.yaml" if layer == "base" else "overrides.yaml"
        if any((root / layer / filename).exists() for root in _layer_roots()):
            present.append(layer)
    return present


def provenance_footer(
    customer: Optional[str] = None,
    engagement: Optional[str] = None,
    family: str = "operator",
    canon_layer: Optional[str] = None,
) -> str:
    """Generate a provenance footer string for artifact embedding."""
    _config, stack_hash = resolve_stack(
        customer=customer, engagement=engagement, family=family, canon_layer=canon_layer
    )
    layers = active_layers(
        customer=customer, engagement=engagement, family=family, canon_layer=canon_layer
    )
    return f"Canon stack: {' + '.join(layers)} | Hash: {stack_hash}"


if __name__ == "__main__":
    config, stack_hash = resolve_stack()
    layers = active_layers()
    print(f"Active layers: {', '.join(layers)}")
    print(f"Stack hash: {stack_hash}")
    print(f"Resolved keys: {list(config.keys())}")
    print(f"\nProvenance: {provenance_footer()}")
