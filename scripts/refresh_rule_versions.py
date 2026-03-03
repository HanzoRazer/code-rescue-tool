from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "src" / "code_audit" / "contracts" / "versions.json"
REGISTRY = ROOT / "src" / "code_audit" / "contracts" / "rules_registry.json"
OUT = ROOT / "src" / "code_audit" / "contracts" / "rule_versions.json"


def _load_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _signal_logic_version() -> str:
    obj = _load_json(VERSIONS)
    v = obj.get("signal_logic_version")
    if not isinstance(v, str) or not v.startswith("signals_v"):
        raise SystemExit("Invalid signal_logic_version in versions.json")
    return v


def build_rule_versions() -> dict[str, Any]:
    reg = _load_json(REGISTRY)
    rules = reg.get("rules") or []
    if not isinstance(rules, list):
        raise SystemExit("Invalid rules_registry.json: rules must be a list")

    # If rule_versions already exists, carry forward version counters.
    prior: dict[str, Any] = {}
    if OUT.exists():
        prior = _load_json(OUT).get("rules") or {}
        if not isinstance(prior, dict):
            prior = {}

    out_rules: Dict[str, Any] = {}
    for r in rules:
        rule_id = r.get("rule_id")
        sem_hash = r.get("semantic_hash")
        if not isinstance(rule_id, str) or not isinstance(sem_hash, str) or not sem_hash:
            raise SystemExit("Invalid rules_registry.json: missing rule_id/semantic_hash")
        prev = prior.get(rule_id) if isinstance(prior, dict) else None
        if isinstance(prev, dict) and prev.get("semantic_hash") == sem_hash:
            # unchanged: keep prior version
            out_rules[rule_id] = {
                "rule_logic_version": int(prev.get("rule_logic_version") or 1),
                "semantic_hash": sem_hash,
            }
        else:
            # changed or new: bump (or initialize)
            prev_ver = int(prev.get("rule_logic_version") or 0) if isinstance(prev, dict) else 0
            out_rules[rule_id] = {
                "rule_logic_version": max(prev_ver + 1, 1),
                "semantic_hash": sem_hash,
            }

    return {
        "schema_version": 1,
        "generated_by": "scripts/refresh_rule_versions.py",
        "signal_logic_version": _signal_logic_version(),
        "rules": dict(sorted(out_rules.items(), key=lambda kv: kv[0])),
    }


def main() -> int:
    obj = build_rule_versions()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[code-audit] wrote {OUT.relative_to(ROOT)} ({len(obj['rules'])} rules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
