"""tests/test_semantic_surface_requires_signal_logic_bump.py

CI gate: ensures that all semantic-surface manifests and governance
artifacts declare the same signal_logic_version as the canonical
versions.json anchor.  If any file drifts, the test fails with
instructions to run the appropriate refresh scripts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

TS_MANIFEST = ROOT / "tests" / "contracts" / "treesitter_manifest.json"
GOLDEN_MANIFEST = ROOT / "tests" / "contracts" / "golden_fixtures_manifest.json"
VERSIONS = ROOT / "src" / "code_audit" / "contracts" / "versions.json"
RULES_REGISTRY = ROOT / "src" / "code_audit" / "contracts" / "rules_registry.json"
RULE_VERSIONS = ROOT / "src" / "code_audit" / "contracts" / "rule_versions.json"


def _load_json(p: Path) -> dict[str, Any]:
    assert p.exists(), f"Missing file: {p.relative_to(ROOT)}"
    return json.loads(p.read_text(encoding="utf-8"))


def _signal_logic_version() -> str:
    obj = _load_json(VERSIONS)
    v = obj.get("signal_logic_version")
    assert isinstance(v, str) and v.startswith("signals_v"), \
        "Invalid signal_logic_version in versions.json"
    return v


def _manifest_hashes(manifest_path: Path) -> dict[str, str]:
    obj = _load_json(manifest_path)
    files = obj.get("files") or {}
    assert isinstance(files, dict)
    return files


def test_semantic_surface_requires_signal_logic_bump():
    ts = _load_json(TS_MANIFEST)
    golden = _load_json(GOLDEN_MANIFEST)
    rr = _load_json(RULES_REGISTRY)
    rv = _load_json(RULE_VERSIONS)

    current_signal = _signal_logic_version()

    ts_recorded = ts.get("signal_logic_version")
    golden_recorded = golden.get("signal_logic_version")
    rr_recorded = rr.get("signal_logic_version")
    rv_recorded = rv.get("signal_logic_version")

    ts_hashes = _manifest_hashes(TS_MANIFEST)
    golden_hashes = _manifest_hashes(GOLDEN_MANIFEST)

    # If any manifest/artifact declares a different version than the current
    # anchor, enforce explicit bump alignment.
    if (
        ts_recorded != current_signal
        or golden_recorded != current_signal
        or rr_recorded != current_signal
        or rv_recorded != current_signal
    ):
        raise AssertionError(
            "Semantic surface signal_logic_version mismatch.\n"
            "All of the following must match versions.json:\n"
            "  - treesitter_manifest.json\n"
            "  - golden_fixtures_manifest.json\n"
            "  - rules_registry.json\n"
            "  - rule_versions.json\n"
            "Run appropriate refresh scripts and align versions."
        )
