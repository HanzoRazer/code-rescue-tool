from __future__ import annotations

import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "src" / "code_audit" / "contracts" / "trusted_signing_keys.json"
SCHEMA = ROOT / "schemas" / "trusted_signing_keys.schema.json"


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_trusted_signing_keys_schema_valid() -> None:
    assert REG.exists()
    assert SCHEMA.exists()
    jsonschema.validate(instance=_load_json(REG), schema=_load_json(SCHEMA))


def test_trusted_signing_keys_unique_sorted_and_has_active() -> None:
    obj = _load_json(REG)
    keys = obj.get("keys") or []
    assert isinstance(keys, list) and keys
    ids: list[str] = []
    active = 0
    for k in keys:
        assert isinstance(k, dict)
        kid = k.get("key_id")
        st = k.get("status")
        assert isinstance(kid, str) and kid.strip()
        assert isinstance(st, str) and st in ("active", "retired")
        ids.append(kid)
        if st == "active":
            active += 1
    assert ids == sorted(ids), "trusted_signing_keys.keys must be sorted by key_id"
    assert len(ids) == len(set(ids)), "Duplicate key_id in trusted_signing_keys"
    assert active >= 1, "trusted_signing_keys must include at least one active key"
