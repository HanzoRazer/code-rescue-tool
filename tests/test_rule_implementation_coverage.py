from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "src" / "code_audit" / "contracts" / "rules_registry.json"


def _load_registry_rule_ids() -> set[str]:
    import json
    obj = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rules = obj.get("rules") or []
    out: set[str] = set()
    for r in rules:
        if isinstance(r, dict) and isinstance(r.get("rule_id"), str):
            out.add(r["rule_id"])
    return out


def _scan_analyzer_rule_ids() -> set[str]:
    """
    Extract rule_id literals from analyzer modules.

    Handles two patterns:
      1. Variable assignment:  rule_id = "SOME_RULE_001"
      2. Dict literal key:    {"rule_id": "SOME_RULE_001", ...}
    """
    analyzers_dir = ROOT / "src" / "code_audit" / "analyzers"
    rule_ids: set[str] = set()

    for p in analyzers_dir.rglob("*.py"):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        for node in ast.walk(tree):
            # Pattern 1: rule_id = "..."
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "rule_id":
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            rule_ids.add(node.value.value)

            # Pattern 2: {"rule_id": "...", ...}  (dict literal)
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "rule_id"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                    ):
                        rule_ids.add(value.value)

    return rule_ids


def test_registry_rules_exist_in_code() -> None:
    registry_ids = _load_registry_rule_ids()
    code_ids = _scan_analyzer_rule_ids()

    missing = registry_ids - code_ids
    assert not missing, (
        "rules_registry contains rule_ids with no analyzer implementation:\n"
        + "\n".join(sorted(missing))
    )


def test_code_rules_exist_in_registry() -> None:
    registry_ids = _load_registry_rule_ids()
    code_ids = _scan_analyzer_rule_ids()

    extra = code_ids - registry_ids
    assert not extra, (
        "Analyzer code defines rule_ids missing from rules_registry:\n"
        + "\n".join(sorted(extra))
    )
