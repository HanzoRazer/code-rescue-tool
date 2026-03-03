from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuleVersion:
    rule_logic_version: int
    semantic_hash: str
    history: tuple[str, ...] = ()


def load_rule_versions() -> dict[str, RuleVersion]:
    """
    Load rule_versions.json shipped with the package (source tree in repo).
    """
    repo_root = Path(__file__).resolve().parents[2]
    p = repo_root / "contracts" / "rule_versions.json"
    obj = json.loads(p.read_text(encoding="utf-8"))
    rules = obj.get("rules") or {}
    if not isinstance(rules, dict):
        return {}
    out: dict[str, RuleVersion] = {}
    for rid, v in rules.items():
        if not isinstance(rid, str) or not isinstance(v, dict):
            continue
        hist = v.get("history")
        if isinstance(hist, list) and all(isinstance(x, str) for x in hist):
            history = tuple(hist)
        else:
            history = ()
        out[rid] = RuleVersion(
            rule_logic_version=int(v.get("rule_logic_version") or 1),
            semantic_hash=str(v.get("semantic_hash") or ""),
            history=history,
        )
    return out


def rule_logic_version(rule_id: str) -> int:
    return load_rule_versions().get(rule_id, RuleVersion(1, "")).rule_logic_version
