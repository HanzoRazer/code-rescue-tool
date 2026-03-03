"""Configuration loading, baseline support, and suppression logic."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_CONFIG: Dict[str, Any] = {
    # Thresholds
    "threshold": 5,
    "min_lines": 400,
    "max_params": 4,
    "max_methods": 15,
    "max_file_size_kb": 100,
    "duplicate_block_size": 5,
    # File discovery
    "file_patterns": [
        "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx",
        "**/*.vue", "**/*.html", "**/*.css",
    ],
    "exclude_dirs": [
        "node_modules", "dist", "build", ".git", "__pycache__",
        ".nuxt", ".next", "coverage", ".nyc_output",
        ".venv", "venv", "env", ".env",
    ],
    # Checker selection
    "checks": [],          # empty → all
    "exclude_checks": [],
    # Suppressions (list of {check, file, line?, message?} dicts)
    "suppressions": [],
}


def load_config(project_path: Path, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load ``.codequalityrc.json`` from *project_path* and merge with defaults.

    *overrides* (typically CLI args) take highest priority.
    """
    config: Dict[str, Any] = dict(DEFAULT_CONFIG)

    rc = project_path / ".codequalityrc.json"
    if rc.exists():
        try:
            user = json.loads(rc.read_text(encoding="utf-8"))
            # Merge lists additively, scalars by override
            for key, val in user.items():
                if key == "exclude_dirs" and isinstance(val, list):
                    config["exclude_dirs"] = list(set(config["exclude_dirs"]) | set(val))
                elif key == "file_patterns" and isinstance(val, list):
                    config["file_patterns"] = list(set(config["file_patterns"]) | set(val))
                else:
                    config[key] = val
        except (json.JSONDecodeError, ValueError):
            pass  # ignore malformed config

    if overrides:
        for key, val in overrides.items():
            if val is not None:
                config[key] = val

    return config


# ── Baseline / suppression ────────────────────────────────────────────────────

def load_baseline(path: Path) -> List[Dict[str, Any]]:
    """Load a previous report JSON and return its issues list."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("issues", [])
    except (json.JSONDecodeError, ValueError):
        return []


def is_suppressed(
    issue: Dict[str, Any],
    baseline_issues: List[Dict[str, Any]],
    inline_suppressions: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """Return *True* if *issue* matches a baseline entry or an inline suppression."""
    candidates = list(baseline_issues)
    if inline_suppressions:
        candidates.extend(inline_suppressions)

    for bi in candidates:
        if bi.get("check") != issue.get("check"):
            continue
        # file must match
        if bi.get("file") and bi["file"] != issue.get("file"):
            continue
        # optional line match
        if bi.get("line") is not None and bi["line"] != issue.get("line"):
            continue
        # optional message substring match
        if bi.get("message") and bi["message"] not in issue.get("message", ""):
            continue
        return True
    return False
