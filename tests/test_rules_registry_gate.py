"""tests/test_rules_registry_gate.py

CI gate: validates that rules_registry.json conforms to its JSON Schema
and stays aligned with the versions.json anchor.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "src" / "code_audit" / "contracts" / "rules_registry.json"
SCHEMA = ROOT / "schemas" / "rules_registry.schema.json"
VERSIONS = ROOT / "src" / "code_audit" / "contracts" / "versions.json"


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _signal_logic_version() -> str:
    obj = _load_json(VERSIONS)
    v = obj.get("signal_logic_version")
    assert isinstance(v, str) and v.startswith("signals_v")
    return v


def test_rules_registry_validates_schema() -> None:
    assert REGISTRY.exists(), "Missing src/code_audit/contracts/rules_registry.json"
    assert SCHEMA.exists(), "Missing schemas/rules_registry.schema.json"
    jsonschema.validate(instance=_load_json(REGISTRY), schema=_load_json(SCHEMA))


def test_rules_registry_aligns_with_version_anchor() -> None:
    reg = _load_json(REGISTRY)
    assert reg.get("signal_logic_version") == _signal_logic_version(), (
        "rules_registry.json signal_logic_version must match versions.json.\n"
        "Run: python scripts/refresh_rules_registry.py"
    )


def test_rules_registry_has_no_empty_hashes() -> None:
    reg = _load_json(REGISTRY)
    rules = reg.get("rules") or []
    for r in rules:
        h = r.get("semantic_hash")
        assert isinstance(h, str) and h.strip(), f"Empty semantic_hash for rule {r.get('rule_id')}"
        assert h != "REPLACE_WITH_REAL_HASH"
        assert len(h) == 64 and all(c in "0123456789abcdef" for c in h), (
            f"semantic_hash must be sha256 hex for rule {r.get('rule_id')}.\n"
            "Run: python scripts/refresh_rules_registry.py"
        )


def test_rules_registry_rule_ids_unique_and_sorted() -> None:
    reg = _load_json(REGISTRY)
    rules = reg.get("rules") or []
    assert isinstance(rules, list)
    ids: list[str] = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("rule_id")
        assert isinstance(rid, str) and rid, "rules_registry rule_id must be non-empty string"
        ids.append(rid)
    assert len(ids) == len(set(ids)), "Duplicate rule_id entries in rules_registry.json"
    assert ids == sorted(ids), "rules_registry.json rules must be sorted by rule_id (stable contract)"


def test_rules_registry_schema_valid() -> None:
    assert REGISTRY.exists()
    assert SCHEMA.exists()
    jsonschema.validate(instance=_load_json(REGISTRY), schema=_load_json(SCHEMA))


def test_rules_registry_semantic_inputs_sorted_unique_and_exist() -> None:
    """
    Tighten the semantic lever surface:
      semantic_inputs must be sorted + unique (stable hash inputs)
      each path must exist (no dangling semantic levers)
    """
    reg = _load_json(REGISTRY)
    rules = reg.get("rules") or []
    assert isinstance(rules, list)
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("rule_id")
        inputs = r.get("semantic_inputs")
        assert isinstance(rid, str) and rid
        assert isinstance(inputs, list) and inputs, f"{rid} missing semantic_inputs"
        assert all(isinstance(x, str) and x for x in inputs), f"{rid} invalid semantic_inputs entries"
        assert inputs == sorted(inputs), f"{rid} semantic_inputs must be sorted"
        assert len(inputs) == len(set(inputs)), f"{rid} semantic_inputs must be unique"
        for rel in inputs:
            assert "\\" not in rel, f"{rid} semantic_inputs must use forward slashes: {rel}"
            assert not rel.startswith(("/", "\\")), f"{rid} semantic_inputs must be repo-relative: {rel}"
            assert not (len(rel) > 1 and rel[1] == ":"), f"{rid} semantic_inputs must not be drive-absolute: {rel}"
            assert ".." not in Path(rel).parts, f"{rid} semantic_inputs must not contain '..': {rel}"
            p = (ROOT / rel).resolve()
            assert p.exists() and p.is_file(), f"{rid} semantic_input missing or not a file: {rel}"
            # Must not escape repo root
            p.relative_to(ROOT.resolve())


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _stable_join_hash(parts: list[str]) -> str:
    h = hashlib.sha256()
    for x in parts:
        h.update(x.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _recompute_rule_semantic_hash(rule_id: str, semantic_inputs: list[str]) -> str:
    rels = sorted(set(semantic_inputs))
    file_hashes = [f"{rel}:{_sha256_file((ROOT / rel).resolve())}" for rel in rels]
    return _stable_join_hash([rule_id] + file_hashes)


def test_rules_registry_semantic_hash_matches_recomputed() -> None:
    """
    Tighten: semantic_hash is not just "well-formed" — it must equal the
    deterministic recomputation from semantic_inputs.
    This prevents hand-edits to semantic_hash and ensures refresh script is
    the only valid update path.
    """
    reg = _load_json(REGISTRY)
    rules = reg.get("rules") or []
    assert isinstance(rules, list)
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("rule_id")
        inputs = r.get("semantic_inputs")
        h = r.get("semantic_hash")
        assert isinstance(rid, str) and rid
        assert isinstance(inputs, list) and inputs and all(isinstance(x, str) and x for x in inputs)
        assert isinstance(h, str) and h
        expected = _recompute_rule_semantic_hash(rid, inputs)
        assert h == expected, (
            f"semantic_hash mismatch for {rid}.\n"
            "Run: python scripts/refresh_rules_registry.py"
        )
