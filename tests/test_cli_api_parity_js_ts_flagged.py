"""tests/test_cli_api_parity_js_ts_flagged.py

Ensures CLI output (``python -m code_audit scan``) is structurally
identical to the programmatic ``build_run_result()`` API.

Post-promotion (signals_v5): JS/TS is default-on; --enable-js-ts is
no longer required on the CLI.  A separate test validates the
--disable-js-ts path.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _touch(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _normalize_for_parity(d: dict[str, Any], *, root: Path) -> dict[str, Any]:
    """Strip volatile fields so CLI vs API dicts are comparable."""
    out = dict(d)
    out.pop("run_id", None)
    out.pop("created_at", None)
    # Normalise root to a canonical form
    out["root"] = str(root.resolve())
    return out


_SRC_DIR = str(Path(__file__).resolve().parents[1] / "src")


def _cli_env() -> dict[str, str]:
    """Return env dict that ensures *our* src/code_audit is resolved first."""
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = _SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _run_cli_scan(root: Path) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "code_audit",
        "scan",
        "--root",
        str(root),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, env=_cli_env())
    assert p.returncode == 0, f"CLI failed.\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
    return json.loads(p.stdout)


def _run_api_scan(root: Path) -> dict:
    try:
        from code_audit.run_result import build_run_result
    except Exception:
        from code_audit.model.run_result import build_run_result  # type: ignore[import]

    return build_run_result(
        root=str(root),
        project_id="",
        enable_js_ts=True,
        # Determinism hooks (if supported by your build_run_result signature)
        _run_id="cli_api_parity",
        _created_at="1970-01-01T00:00:00Z",
    )


def test_cli_api_parity_enable_js_ts(tmp_path: Path) -> None:
    _touch(tmp_path / "app.py", "print('hi')\n")
    _touch(tmp_path / "web" / "main.js", "eval('1+1')\n")

    cli = _run_cli_scan(tmp_path)
    api = _run_api_scan(tmp_path)

    cli_n = _normalize_for_parity(cli, root=tmp_path)
    api_n = _normalize_for_parity(api, root=tmp_path)
    assert cli_n == api_n


def test_cli_api_parity_disable_js_ts(tmp_path: Path) -> None:
    """
    Parity contract for disable mode:
    CLI scan with --disable-js-ts must match API scan with enable_js_ts=False.
    """
    _touch(tmp_path / "app.py", "print('hi')\n")
    _touch(tmp_path / "web" / "main.js", "eval('1+1')\n")

    cmd = [
        sys.executable,
        "-m",
        "code_audit",
        "scan",
        "--root",
        str(tmp_path),
        "--disable-js-ts",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, env=_cli_env())
    assert p.returncode == 0, f"CLI failed.\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
    cli = json.loads(p.stdout)

    try:
        from code_audit.run_result import build_run_result
    except Exception:
        from code_audit.model.run_result import build_run_result  # type: ignore[import]

    api = build_run_result(
        root=str(tmp_path),
        project_id="",
        enable_js_ts=False,
        _run_id="cli_api_parity_disable",
        _created_at="1970-01-01T00:00:00Z",
    )

    cli_n = _normalize_for_parity(cli, root=tmp_path)
    api_n = _normalize_for_parity(api, root=tmp_path)
    assert cli_n == api_n
