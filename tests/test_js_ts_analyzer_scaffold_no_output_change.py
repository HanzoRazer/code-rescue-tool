"""tests/test_js_ts_analyzer_scaffold_no_output_change.py

Asserts that when JS/TS scanning is explicitly **disabled**, no JS/TS
findings are emitted — even when JS/TS files are present.

Post-promotion (signals_v5): JS/TS is default-on elsewhere.  This test
validates the "disable" path still produces zero JS/TS findings.
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


def test_enable_js_ts_scaffold_produces_no_findings(tmp_path: Path) -> None:
    _touch(tmp_path / "app.py", "print('hi')\n")
    _touch(tmp_path / "web" / "main.js", "eval('1+1')\n")
    _touch(tmp_path / "web" / "main.ts", "const x: number = 1\n")

    # Promotion change: JS/TS is default-on elsewhere. This test asserts the
    # "disable" path still produces no JS/TS findings.
    res = run_scan(root=tmp_path, analyzers=[_NoopPyAnalyzer()], enable_js_ts=False)
    d = res.to_dict() if hasattr(res, "to_dict") else dict(res)  # tolerate older RunResult shapes

    findings = d.get("findings") or []
    assert findings == [] or len(findings) == 0
