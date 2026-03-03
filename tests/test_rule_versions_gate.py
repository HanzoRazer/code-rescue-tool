from __future__ import annotations

import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
RULE_VERSIONS = ROOT / "src" / "code_audit" / "contracts" / "rule_versions.json"
SCHEMA = ROOT / "schemas" / "rule_versions.schema.json"
RULES_REGISTRY = ROOT / "src" / "code_audit" / "contracts" / "rules_registry.json"
VERSIONS = ROOT / "src" / "code_audit" / "contracts" / "versions.json"


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_rule_versions_schema_valid() -> None:
    assert RULE_VERSIONS.exists()
    assert SCHEMA.exists()
    jsonschema.validate(instance=_load(RULE_VERSIONS), schema=_load(SCHEMA))


def test_rule_versions_align_with_versions_json() -> None:
    rv = _load(RULE_VERSIONS)
    v = _load(VERSIONS)
    assert rv.get("signal_logic_version") == v.get("signal_logic_version")


def test_rule_versions_cover_registry_rules() -> None:
    rv = _load(RULE_VERSIONS).get("rules") or {}
    reg_rules = _load(RULES_REGISTRY).get("rules") or []
    reg_ids = sorted([r.get("rule_id") for r in reg_rules if isinstance(r, dict) and isinstance(r.get("rule_id"), str)])
    for rid in reg_ids:
        assert rid in rv, f"Missing rule_versions entry for {rid}. Run: python scripts/refresh_rule_versions.py"


def test_rule_versions_semantic_hash_matches_registry() -> None:
    """
    Granular governance invariant:
    rules_registry defines the semantic_hash per rule
    rule_versions MUST mirror that hash, so versioning is keyed to the same semantics
    """
    reg = _load(RULES_REGISTRY)
    rv = _load(RULE_VERSIONS)
    reg_rules = reg.get("rules") or []
    rv_rules = rv.get("rules") or {}
    assert isinstance(reg_rules, list)
    assert isinstance(rv_rules, dict)
    for r in reg_rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("rule_id")
        rh = r.get("semantic_hash")
        if not isinstance(rid, str) or not isinstance(rh, str):
            continue
        assert rid in rv_rules, f"rule_versions missing entry for {rid}"
        ent = rv_rules[rid]
        assert isinstance(ent, dict), f"rule_versions[{rid}] must be an object"
        assert ent.get("semantic_hash") == rh, (
            f"rule_versions semantic_hash mismatch for {rid}.\n"
            "Run: python scripts/refresh_rule_versions.py"
        )
