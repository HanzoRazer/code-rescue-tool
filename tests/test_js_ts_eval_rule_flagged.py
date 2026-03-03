"""tests/test_js_ts_eval_rule_flagged.py

Verifies that the JS/TS eval rule (SEC_EVAL_JS_001) fires when JS/TS
scanning is enabled and does NOT fire when explicitly disabled.

Post-promotion (signals_v5): JS/TS is default-on.
"""
from __future__ import annotations

from pathlib import Path

from code_audit.core.runner import run_scan


def _touch(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class _NoopPyAnalyzer:
    name = "noop_py"
    version = "0.0.0"

    def analyze(self, files: list[Path], sink) -> None:  # pragma: no cover
        return


def test_eval_rule_emits_finding_only_when_flag_enabled(tmp_path: Path) -> None:
    _touch(tmp_path / "app.py", "print('hi')\n")
    _touch(tmp_path / "web" / "main.js", "eval('1+1')\n")

    # Explicit disable: JS not scanned, so no findings.
    res0 = run_scan(root=tmp_path, analyzers=[_NoopPyAnalyzer()], enable_js_ts=False)
    d0 = res0.to_dict()
    assert not any(f.get("rule_id") == "SEC_EVAL_JS_001" for f in (d0.get("findings") or []))

    # Default-on (or explicit enable): JS is scanned by JS/TS analyzer.
    res1 = run_scan(root=tmp_path, analyzers=[_NoopPyAnalyzer()], enable_js_ts=True)
    d1 = res1.to_dict()
    findings = d1.get("findings") or []
    assert any(f.get("rule_id") == "SEC_EVAL_JS_001" for f in findings)
