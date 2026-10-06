#!/usr/bin/env python3
"""Promote a generalized pattern from a client silo UP into industry/base canon.

This is the "cleanser": it lifts overrides from a client-scoped layer (customer/* or
engagement/*) into a shareable layer (industry/* or base), STRIPPING client
identifiers along the way, and emits a candidate file + diff for human review. It
never writes into canon/ and never commits — promotion is always a reviewed action.

Scrub rules:
  - Source citations (override_source / *_source) are replaced with a
    `TODO: ADR-xxx` placeholder — a promoted override needs its OWN industry/base ADR.
  - Every `--scrub` term (and the client name inferred from --from) is redacted from
    string values, case-insensitive.
  - Guard patterns like `examplebank-*-sandbox` generalize to `<owner>-*-sandbox`.
  - Any top-level key left without a source gets a TODO placeholder and the run is
    marked NOT READY until a human fills the ADRs and clears residual hits.

Usage:
  python tools/promote-canon.py --from customer/examplebank --to industry/fsi --scrub examplebank,acct-id
  python tools/promote-canon.py --from customer/acme-bank --to industry/fsi --scrub acme --keys producer,latency_tiers

Client silos resolve from CFLT_CANON_EXTERNAL_PATH (see canon/stack.py / CONTRIBUTING.md).
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import yaml  # noqa: E402

from canon.stack import _load_layer  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "promote"
SOURCE_KEYS = ("override_source", "_source")


def _client_name(from_layer: str) -> str:
    """Infer the client identifier from a 'customer/<name>' / 'engagement/<name>' path."""
    parts = from_layer.strip("/").split("/")
    return parts[1] if len(parts) >= 2 else parts[-1]


def _scrub_string(key: str, value: str, terms: list[str], from_layer: str) -> str:
    # Source citations always become a fresh-ADR placeholder. The placeholder is
    # deliberately client-free — from_layer is recorded in the file header only.
    if key in SOURCE_KEYS or key.endswith("_source"):
        return "TODO: ADR-xxx (replace with target-layer ADR)"
    return _redact(value, terms)


def _redact(text: str, terms: list[str]) -> str:
    """Replace every scrub term in a string with the literal <redacted> marker.

    No structural rewriting (no guard-pattern generalization) — any surviving
    <redacted> marker forces NOT READY so the operator resolves it by hand rather
    than the tool guessing a replacement and mangling prose.
    """
    for term in terms:
        if not term:
            continue
        text = re.sub(re.escape(term), "<redacted>", text, flags=re.IGNORECASE)
    return text


def _scrub(node, terms: list[str], from_layer: str, key: str = ""):
    if isinstance(node, dict):
        # Scrub keys too — a client identifier in a YAML key must not survive.
        return {_redact(k, terms): _scrub(v, terms, from_layer, key=k) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub(v, terms, from_layer, key=key) for v in node]
    if isinstance(node, str):
        return _scrub_string(key, node, terms, from_layer)
    return node


def _ensure_source(fragment: dict, from_layer: str) -> list[str]:
    """Inject a TODO source into any top-level dict key lacking one. Returns the names."""
    missing = []
    for key, value in fragment.items():
        if isinstance(value, dict) and not any(s in value for s in SOURCE_KEYS):
            value["override_source"] = "TODO: ADR-xxx (add target-layer ADR)"
            missing.append(key)
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description="Promote + scrub a client overlay into a shareable layer.")
    ap.add_argument("--from", dest="from_layer", required=True,
                    help="Source layer, e.g. customer/examplebank or engagement/examplebank-2026")
    ap.add_argument("--to", dest="to_layer", required=True,
                    help="Target shareable layer, e.g. industry/fsi or base")
    ap.add_argument("--scrub", default="",
                    help="Comma-separated identifiers to redact (client name is added automatically)")
    ap.add_argument("--keys", default="",
                    help="Comma-separated top-level keys to promote (default: all)")
    args = ap.parse_args()

    source = _load_layer(args.from_layer)
    if not source:
        print(f"error: source layer {args.from_layer!r} resolved to nothing — "
              f"check the name and CFLT_CANON_EXTERNAL_PATH.", file=sys.stderr)
        return 2

    # Select keys to promote.
    if args.keys:
        wanted = [k.strip() for k in args.keys.split(",") if k.strip()]
        missing_keys = [k for k in wanted if k not in source]
        if missing_keys:
            print(f"error: keys not in source: {missing_keys}", file=sys.stderr)
            return 2
        source = {k: source[k] for k in wanted}

    terms = [t.strip() for t in args.scrub.split(",") if t.strip()]
    terms.append(_client_name(args.from_layer))  # always redact the client name itself

    candidate = _scrub(source, terms, args.from_layer)
    needs_adr = _ensure_source(candidate, args.from_layer)

    candidate_yaml = yaml.safe_dump(candidate, sort_keys=False)

    # Residual-leak check: no scrub term should survive in the promoted content.
    residual = sorted({t for t in terms if re.search(re.escape(t), candidate_yaml, re.IGNORECASE)})
    # Any source scrubbed/injected from a client layer leaves a TODO ADR — never
    # auto-ready while those remain.
    todos = candidate_yaml.count("TODO: ADR")
    # A surviving <redacted> marker means a scrub landed mid-token (e.g. a guard
    # pattern) and needs a human to supply the generalized form — not paste-safe yet.
    orphaned = "<redacted>" in candidate_yaml
    ready = not residual and not needs_adr and todos == 0 and not orphaned

    # Write candidate.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe = args.from_layer.strip("/").replace("/", "__")
    out_path = OUTPUT_DIR / f"{safe}-candidate.yaml"
    # Header is deliberately client-free so the whole file is paste-safe into the
    # shareable layer. Source + scrub provenance goes to the operator console only.
    header = (
        f"# CANDIDATE promotion into canon/{args.to_layer}/overrides.yaml\n"
        f"# Generated by tools/promote-canon.py — review, fill TODO ADRs, then hand-apply.\n\n"
    )
    out_path.write_text(header + candidate_yaml)

    # Diff against the current target layer.
    current = _load_layer(args.to_layer)
    current_yaml = yaml.safe_dump(current, sort_keys=False) if current else ""
    diff = "".join(difflib.unified_diff(
        current_yaml.splitlines(keepends=True),
        candidate_yaml.splitlines(keepends=True),
        fromfile=f"canon/{args.to_layer}/overrides.yaml (current)",
        tofile=f"{args.from_layer} -> {args.to_layer} (candidate)",
    ))
    (OUTPUT_DIR / f"{safe}-candidate.diff").write_text(diff)

    print(f"promote:   {args.from_layer} -> {args.to_layer}  (scrubbed: {terms})")
    print(f"candidate: {out_path.relative_to(PROJECT_ROOT)}")
    print(f"diff:      {(OUTPUT_DIR / f'{safe}-candidate.diff').relative_to(PROJECT_ROOT)}")
    if diff:
        print("\n" + diff)
    if residual:
        print(f"\n[warn] residual scrub terms still present: {residual}")
    if needs_adr:
        print(f"[warn] keys needing a target-layer ADR (TODO placeholders inserted): {needs_adr}")
    if todos:
        print(f"[warn] {todos} TODO ADR placeholder(s) to fill before promoting.")
    if orphaned:
        print("[warn] '<redacted>' marker(s) survived — replace with a generalized "
              "value (e.g. a guard pattern) by hand before promoting.")
    print(f"\n{'READY' if ready else 'NOT READY'} - "
          f"{'review the diff, then hand-apply.' if ready else 'resolve the warnings above before promoting.'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
