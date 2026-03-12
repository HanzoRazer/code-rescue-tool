from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

VERSIONS = ROOT / "src" / "code_audit" / "contracts" / "versions.json"
REGISTRY = ROOT / "src" / "code_audit" / "contracts" / "rules_registry.json"
RULE_VERSIONS = ROOT / "src" / "code_audit" / "contracts" / "rule_versions.json"

OUT = DIST / "contracts" / "rule_pack.json"


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _stable_join_hash(parts: list[str]) -> str:
    h = hashlib.sha256()
    for x in parts:
        h.update(x.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _load_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def generate_rule_pack() -> dict[str, Any]:
    v = _load_json(VERSIONS)
    rr = _load_json(REGISTRY)
    rv = _load_json(RULE_VERSIONS)

    slv = v.get("signal_logic_version")
    if not isinstance(slv, str) or not slv.startswith("signals_v"):
        raise SystemExit("Invalid versions.json signal_logic_version")

    rules = rr.get("rules") or []
    versions = (rv.get("rules") or {})
    if not isinstance(rules, list) or not isinstance(versions, dict):
        raise SystemExit("Invalid registry or rule_versions shape")

    out_rules: list[dict[str, Any]] = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("rule_id")
        sh = r.get("semantic_hash")
        ins = r.get("semantic_inputs")
        if not isinstance(rid, str) or not isinstance(sh, str) or not isinstance(ins, list):
            raise SystemExit("Invalid rule entry in registry")
        ent = versions.get(rid)
        if not isinstance(ent, dict):
            raise SystemExit(f"Missing rule_versions entry for {rid}")
        rlv = ent.get("rule_logic_version")
        if not isinstance(rlv, int) or rlv < 1:
            raise SystemExit(f"Invalid rule_logic_version for {rid}")
        out_rules.append(
            {
                "rule_id": rid,
                "semantic_hash": sh,
                "rule_logic_version": rlv,
                "semantic_inputs": list(ins),
            }
        )

    out_rules = sorted(out_rules, key=lambda d: d["rule_id"])

    pack_hash = _stable_join_hash(
        [slv] + [f"{r['rule_id']}@{r['semantic_hash']}@{r['rule_logic_version']}" for r in out_rules]
    )

    return {
        "schema_version": 1,
        "generated_by": "scripts/generate_rule_pack.py",
        "signal_logic_version": slv,
        "pack_hash": pack_hash,
        "rules": out_rules,
    }


def main() -> int:
    obj = generate_rule_pack()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[code-audit] wrote {OUT.relative_to(ROOT)} ({len(obj['rules'])} rules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
