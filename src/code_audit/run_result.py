"""code_audit.run_result

Convenience wrapper that builds and returns the run-result dict
for programmatic (non-CLI) callers.

Promotion (signals_v5): ``enable_js_ts`` defaults to ``True``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from code_audit.core.runner import run_scan


def build_run_result(
    root: str,
    project_id: str = "",
    *,
    config: dict[str, Any] | None = None,
    enable_js_ts: bool = True,
    # Testing hooks for golden-fixture determinism
    _run_id: str | None = None,
    _created_at: str | None = None,
) -> dict[str, Any]:
    """Run a scan and return the result as a plain dict."""
    result = run_scan(
        root=Path(root),
        analyzers=[],
        project_id=project_id,
        config=config,
        enable_js_ts=enable_js_ts,
        _run_id=_run_id,
        _created_at=_created_at,
    )
    return result.to_dict()
