from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "src" / "code_audit" / "contracts" / "versions.json"
REGISTRY = ROOT / "src" / "code_audit" / "contracts" / "rules_registry.json"


def _load_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    return _sha256_bytes(p.read_bytes())


def _stable_join_hash(parts: list[str]) -> str:
    """
    Combine already-hex strings deterministically.
    """
    h = hashlib.sha256()
    for x in parts:
        h.update(x.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _signal_logic_version() -> str:
    v = _load_json(VERSIONS).get("signal_logic_version")
    if not isinstance(v, str) or not v.startswith("signals_v"):
        raise SystemExit("Invalid signal_logic_version in versions.json")
    return v


def _repo_path(rel: str) -> Path:
    p = (ROOT / rel).resolve()
    # Harden: inputs must remain within repo root (no absolute paths, no .. escape).
    try:
        p.relative_to(ROOT.resolve())
    except Exception:
        raise SystemExit(f"semantic_inputs path escapes repo root: {rel}")
    return p


def _validate_semantic_input_path(rel: str) -> None:
    # Harden: ban absolute paths and traversal patterns.
    if rel.startswith(("/", "\\")) or (len(rel) > 1 and rel[1] == ":"):
        raise SystemExit(f"semantic_inputs must be repo-relative (not absolute): {rel}")
    if ".." in Path(rel).parts:
        raise SystemExit(f"semantic_inputs must not contain '..' traversal: {rel}")
    if "\\" in rel:
        raise SystemExit(f"semantic_inputs must use forward slashes: {rel}")


def _semantic_hash_for_rule(rule: dict[str, Any]) -> str:
    """
    Compute semantic_hash for a rule from declared semantic_inputs.

    semantic_inputs: list of repo-relative file paths.

     - Analyzer module(s)
     - Query file(s)
     - Any other explicit semantic levers for that rule
    """
    inputs = rule.get("semantic_inputs") or []
    if not isinstance(inputs, list) or not inputs:
        raise SystemExit(f"Rule {rule.get('rule_id')} missing semantic_inputs")

    # Deterministic ordering: sort paths; hash content; then hash the list of hashes.
    rels: list[str] = []
    for x in inputs:
        if not isinstance(x, str) or not x:
            raise SystemExit(f"Rule {rule.get('rule_id')} has invalid semantic_inputs entry: {x!r}")
        _validate_semantic_input_path(x)
        rels.append(x)

    rels = sorted(set(rels))

    file_hashes: list[str] = []
    for rel in rels:
        p = _repo_path(rel)
        if not p.exists() or not p.is_file():
            raise SystemExit(f"Rule {rule.get('rule_id')} semantic input missing: {rel}")
        file_hashes.append(f"{rel}:{_sha256_file(p)}")

    # Also bind the rule_id itself to avoid cross-rule collisions if inputs match.
    return _stable_join_hash([str(rule.get("rule_id") or "")] + file_hashes)


def build_rules_registry() -> dict[str, Any]:
    obj = _load_json(REGISTRY)
    rules = obj.get("rules") or []
    if not isinstance(rules, list):
        raise SystemExit("Invalid rules_registry.json: rules must be a list")

    out_rules: list[dict[str, Any]] = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("rule_id")
        if not isinstance(rid, str) or not rid:
            raise SystemExit("Invalid rules_registry.json: rule_id missing")
        rr = dict(r)
        # Canonicalize semantic_inputs for determinism
        sin = rr.get("semantic_inputs") or []
        if not isinstance(sin, list) or not sin:
            raise SystemExit(f"Rule {rid} missing semantic_inputs")
        canon: list[str] = []
        for x in sin:
            if isinstance(x, str) and x:
                _validate_semantic_input_path(x)
                canon.append(x)
        rr["semantic_inputs"] = sorted(set(canon))
        rr["semantic_hash"] = _semantic_hash_for_rule(rr)
        out_rules.append(rr)

    out_rules = sorted(out_rules, key=lambda d: str(d.get("rule_id") or ""))

    # Harden: refuse to proceed if there are any duplicate rule_ids after canonicalization.
    ids = [str(x.get("rule_id") or "") for x in out_rules]
    if any(not rid for rid in ids):
        raise SystemExit("rules_registry contains an empty rule_id after processing")
    if len(ids) != len(set(ids)):
        dups = sorted({rid for rid in ids if ids.count(rid) > 1})
        raise SystemExit("Duplicate rule_id entries detected in rules_registry:\n" + "\n".join(dups))

    return {
        "schema_version": int(obj.get("schema_version") or 1),
        "generated_by": "scripts/refresh_rules_registry.py",
        "signal_logic_version": _signal_logic_version(),
        "rules": out_rules,
    }


def main() -> int:
    out = build_rules_registry()
    REGISTRY.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[code-audit] wrote {REGISTRY.relative_to(ROOT)} ({len(out['rules'])} rules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
