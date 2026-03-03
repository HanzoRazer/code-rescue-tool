"""tests/test_language_discovery_js_ts_flag.py

Verifies that ``discover_source_files()`` respects the ``enable_js_ts``
flag and that default-on scanning picks up JS/TS files automatically.
"""
from __future__ import annotations

from pathlib import Path

from code_audit.core.runner import discover_source_files


def _touch(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_discover_source_files_js_ts_flag_controls_visibility(tmp_path: Path) -> None:
    _touch(tmp_path / "app.py", "print('hi')\n")
    _touch(tmp_path / "web" / "index.js", "console.log('hi')\n")
    _touch(tmp_path / "web" / "utils.ts", "const x: number = 1\n")
    _touch(tmp_path / "node_modules" / "lib.js", "/* vendored */\n")

    # Flag on: JS/TS are discovered, but excluded directories are still honored.
    res2 = discover_source_files(tmp_path, enable_js_ts=True)
    assert set(res2.keys()) == {"py", "js", "ts"}
    assert (tmp_path / "app.py").resolve() in res2["py"]

    # node_modules is excluded by default
    assert (tmp_path / "node_modules" / "lib.js").resolve() not in res2["js"]


def test_run_scan_default_includes_js_ts_when_present(tmp_path: Path) -> None:
    """
    Promotion step: default-on JS/TS scanning.
    If JS/TS files exist, the JS/TS analyzer path should run without requiring a flag.
    """
    from code_audit.core.runner import run_scan

    _touch(tmp_path / "app.py", "print('hi')\n")
    _touch(tmp_path / "web" / "main.js", "eval('1+1')\n")

    class _NoopPyAnalyzer:
        name = "noop_py"
        version = "0.0.0"

        def analyze(self, files: list[Path], sink) -> None:  # pragma: no cover
            return

    res = run_scan(root=tmp_path, analyzers=[_NoopPyAnalyzer()])
    d = res.to_dict() if hasattr(res, "to_dict") else dict(res)
    findings = d.get("findings") or []
    assert any(f.get("rule_id") == "SEC_EVAL_JS_001" for f in findings)
