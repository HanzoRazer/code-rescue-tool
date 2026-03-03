"""code_audit.core.runner

Scan orchestration: discovers source files, wires analyzers, and produces
a ``RunResult``.

Promotion (signals_v5): JS/TS scanning is **default-on**.
Pass ``enable_js_ts=False`` to restrict to Python-only.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from code_audit.analyzers.js_ts_security import (
    FindingSink,
    JsTsSecurityPreviewAnalyzer,
    SourceFile,
)


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

class Analyzer:
    """Minimal duck-type for analyzer objects."""
    name: str = ""
    version: str = ""

    def analyze(self, files: list[Path], sink: Any) -> None: ...  # pragma: no cover


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

_DEFAULT_EXCLUDES = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}


def discover_py_files(
    root: Path,
    *,
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
) -> list[Path]:
    """Return all ``*.py`` files under *root*, respecting include/exclude globs."""
    exclude_dirs = _DEFAULT_EXCLUDES | set(exclude or [])
    files: list[Path] = []
    for p in root.rglob("*.py"):
        if any(part in exclude_dirs for part in p.parts):
            continue
        files.append(p.resolve())
    return sorted(files)


def discover_source_files(
    root: Path,
    *,
    enable_js_ts: bool = True,
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
) -> dict[str, list[Path]]:
    """Multi-language file discovery.

    Returns ``{"py": [...], "js": [...], "ts": [...]}`` when JS/TS is enabled,
    otherwise ``{"py": [...]}``.
    """
    exclude_dirs = _DEFAULT_EXCLUDES | set(exclude or [])
    result: dict[str, list[Path]] = {"py": []}

    if enable_js_ts:
        result["js"] = []
        result["ts"] = []

    ext_map = {".py": "py"}
    if enable_js_ts:
        ext_map.update({".js": "js", ".jsx": "js", ".ts": "ts", ".tsx": "ts"})

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in exclude_dirs for part in p.parts):
            continue
        lang = ext_map.get(p.suffix)
        if lang and lang in result:
            result[lang].append(p.resolve())

    for lang in result:
        result[lang].sort()

    return result


# ---------------------------------------------------------------------------
# Finding sink (concrete)
# ---------------------------------------------------------------------------

class _DefaultSink:
    """Collects findings as plain dicts."""

    def __init__(self) -> None:
        self._findings: list[dict[str, Any]] = []

    def add(self, finding: dict[str, Any]) -> None:
        self._findings.append(finding)

    @property
    def findings(self) -> list[dict[str, Any]]:
        return list(self._findings)


# ---------------------------------------------------------------------------
# Finding normalizer
# ---------------------------------------------------------------------------

def _normalize_finding_for_contract(f: dict) -> dict:
    """Strip unknown keys so output matches the finding contract."""
    allowed = {
        "rule_id",
        "path",
        "message",
        "location",
        "evidence",
        "rule_logic_version",
        "severity",
        "confidence",
        "category",
    }
    return {k: v for k, v in f.items() if k in allowed}


# ---------------------------------------------------------------------------
# RunResult (lightweight dict wrapper)
# ---------------------------------------------------------------------------

class RunResult:
    """Thin wrapper around the result dict for ergonomic access."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


# ---------------------------------------------------------------------------
# run_scan — main entry point
# ---------------------------------------------------------------------------

def run_scan(
    root: Path,
    analyzers: list[Any],
    *,
    project_id: str = "",
    config: dict[str, Any] | None = None,
    out_dir: Path | None = None,
    emit_signals_path: str | None = None,
    enable_js_ts: bool = True,
    # Testing hooks for golden-fixture determinism
    _run_id: str | None = None,
    _created_at: str | None = None,
) -> RunResult:
    """Execute a full scan of *root* and return a ``RunResult``."""
    scan_config = config or {}
    run_id = _run_id or uuid.uuid4().hex[:12]
    created_at = _created_at or datetime.now(timezone.utc).isoformat()

    # --- File discovery ---------------------------------------------------
    discovered: dict[str, list[Path]] | None = discover_source_files(
        root,
        enable_js_ts=bool(enable_js_ts),
        include=scan_config.get("include"),
        exclude=scan_config.get("exclude"),
    )
    files = discovered.get("py", []) if discovered else []

    # --- Python analyzers -------------------------------------------------
    sink = _DefaultSink()
    for analyzer in analyzers:
        if hasattr(analyzer, "analyze"):
            analyzer.analyze(files, sink)

    # --- JS/TS analyzer (promotion: default-on) ---------------------------
    if enable_js_ts:
        js_ts_analyzers = list(analyzers) + [JsTsSecurityPreviewAnalyzer()]
        for a in js_ts_analyzers:
            if hasattr(a, "analyze_multilang") and discovered:
                source_files_by_lang: dict[str, list[SourceFile]] = {}
                for lang_key in ("js", "ts"):
                    source_files_by_lang[lang_key] = [
                        SourceFile(path=p, language=lang_key)
                        for p in discovered.get(lang_key, [])
                    ]
                a.analyze_multilang(source_files_by_lang, sink)

    findings = [_normalize_finding_for_contract(f) for f in sink.findings]

    # Strict contract validation (hard fail on invalid finding shape).
    try:
        from code_audit.contracts.validate import validate_finding
    except Exception as e:
        raise RuntimeError(f"Unable to import finding validator: {e}") from e

    for f in findings:
        if isinstance(f, dict):
            validate_finding(f)

    # ------------------------------------------------------------------
    # Granular governance guard:
    # - If a finding's rule_id exists in rule_versions.json, it MUST emit
    #   rule_logic_version and it MUST match the authoritative value.
    # - If a finding emits rule_logic_version, it must match authoritative value
    #   (even if the rule_id is unknown to rule_versions, this will resolve to 1).
    # This prevents analyzers from lying (accidentally or otherwise) about the
    # rule-level semantic version they are emitting.
    # ------------------------------------------------------------------
    try:
        from code_audit.contracts.rules import load_rule_versions as _load_rv
        from code_audit.contracts.rules import rule_logic_version as _rlv
    except Exception as e:
        raise RuntimeError(f"Unable to import rule version resolver: {e}") from e

    _rv = _load_rv()

    for f in findings:
        if not isinstance(f, dict):
            continue
        rid = f.get("rule_id")
        if not isinstance(rid, str) or not rid:
            continue
        # If the rule is governed, the finding must carry the governed version.
        if rid in _rv and "rule_logic_version" not in f:
            raise RuntimeError(
                f"Missing rule_logic_version for governed rule_id={rid}. "
                "Findings for governed rules must emit rule_logic_version."
            )
        if "rule_logic_version" in f:
            expected = int(_rlv(rid))
            got = int(f.get("rule_logic_version") or 0)
            if got != expected:
                raise RuntimeError(
                    f"Invalid rule_logic_version for rule_id={rid}: got={got} expected={expected}. "
                    "Refresh rule versions or fix analyzer emission."
                )

    # Deterministic output: findings order must be stable across platforms and
    # independent of tree-sitter capture ordering or filesystem traversal.

    return RunResult(
        {
            "run_id": run_id,
            "created_at": created_at,
            "project_id": project_id,
            "root": str(root),
            "enable_js_ts": enable_js_ts,
            "file_counts": {k: len(v) for k, v in (discovered or {}).items()},
            "findings": findings,
        }
    )
