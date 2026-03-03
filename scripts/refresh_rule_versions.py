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
        prev_hist: list[str] = []
        if isinstance(prev, dict):
            h = prev.get("history")
            if isinstance(h, list) and all(isinstance(x, str) and x for x in h):
                prev_hist = list(h)
            elif isinstance(prev.get("semantic_hash"), str) and prev.get("semantic_hash"):
                # Back-compat: schema_v1 had no history; seed from semantic_hash.
                prev_hist = [str(prev["semantic_hash"])]

        if prev_hist and prev_hist[-1] == sem_hash:
            # unchanged: keep history, keep version == len(history)
            out_rules[rule_id] = {
                "rule_logic_version": len(prev_hist),
                "semantic_hash": sem_hash,
                "history": prev_hist,
            }
        else:
            # changed or new: append new semantic hash; version == len(history)
            new_hist = (prev_hist or []) + [sem_hash]
            out_rules[rule_id] = {
                "rule_logic_version": len(new_hist),
                "semantic_hash": sem_hash,
                "history": new_hist,
            }

    return {
        "schema_version": 2,
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
