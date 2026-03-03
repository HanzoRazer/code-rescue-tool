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


def test_rule_evolution_policy_version_equals_history_len_and_hash_is_last() -> None:
    """
    Rule evolution policy (granular governance):
    * rule_logic_version MUST equal len(history)
    * semantic_hash MUST equal history[-1]
    * history MUST not contain duplicates back-to-back (no "fake bump")
    """
    rv = _load(RULE_VERSIONS).get("rules") or {}
    assert isinstance(rv, dict)
    for rid, ent in rv.items():
        assert isinstance(ent, dict), f"{rid} entry must be object"
        v = ent.get("rule_logic_version")
        h = ent.get("semantic_hash")
        hist = ent.get("history")
        assert isinstance(v, int) and v >= 1, f"{rid} invalid rule_logic_version"
        assert isinstance(h, str) and h, f"{rid} invalid semantic_hash"
        assert isinstance(hist, list) and len(hist) >= 1, f"{rid} invalid history"
        assert v == len(hist), f"{rid} rule_logic_version must equal len(history)"
        assert h == hist[-1], f"{rid} semantic_hash must equal history[-1]"
        for i in range(1, len(hist)):
            assert hist[i] != hist[i - 1], f"{rid} history has duplicate adjacent hashes (fake bump)"
