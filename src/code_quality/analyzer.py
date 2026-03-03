"""Code-quality analyzer orchestrator.

Enhancements implemented:
    #6  — File content cache (``_file_cache``)
    #9  — .codequalityrc.json config support
    #10 — --fix mode (auto-fixable issues)
    #19 — --changed-only (git-diff mode)
    #20 — --baseline (suppress known issues)
    #21 — Parallel checker execution via ThreadPoolExecutor
"""
from __future__ import annotations

import fnmatch
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import BaseCheck, get_registered_checkers
from .config import load_config, load_baseline, is_suppressed

# Ensure all checker modules are imported (triggers __init_subclass__).
from . import checkers as _checkers  # noqa: F401


class CodeQualityAnalyzer:
    """Central orchestrator — discovers files, runs checkers, collects issues."""

    def __init__(
        self,
        project_path: str | Path,
        *,
        config_overrides: Optional[Dict[str, Any]] = None,
        baseline_path: Optional[Path] = None,
        changed_only: bool = False,
        fix: bool = False,
        workers: int = 4,
        verbose: bool = False,
    ) -> None:
        self.project_path = Path(project_path).resolve()
        self.config = load_config(self.project_path, config_overrides or {})
        self.baseline_issues = load_baseline(baseline_path) if baseline_path else []
        self.changed_only = changed_only
        self.fix = fix
        self.workers = max(1, workers)
        self.verbose = verbose

        # Results
        self.issues: List[Dict[str, Any]] = []

        # File content cache  (Enhancement #6)
        self._file_cache: Dict[Path, str] = {}

    # ── File caching ──────────────────────────────────────────────────────

    def get_file_content(self, file_path: Path) -> str:
        """Return full file content, cached."""
        fp = file_path.resolve()
        if fp not in self._file_cache:
            try:
                self._file_cache[fp] = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                self._file_cache[fp] = ""
        return self._file_cache[fp]

    def get_file_lines(self, file_path: Path) -> List[str]:
        """Return file content split into lines (with newlines)."""
        return self.get_file_content(file_path).splitlines(keepends=True)

    # ── Issue collection ──────────────────────────────────────────────────

    def add_issue(
        self,
        *,
        check_name: str,
        file_path: Path,
        line: int,
        message: str,
        severity: str = "warning",
        suggestion: str = "",
    ) -> None:
        """Append an issue (thread-safe — GIL protects list.append)."""
        issue: Dict[str, Any] = {
            "check": check_name,
            "file": str(file_path),
            "line": line,
            "message": message,
            "severity": severity,
            "suggestion": suggestion,
        }
        # Baseline suppression  (Enhancement #20)
        if self.baseline_issues and is_suppressed(issue, self.baseline_issues):
            return
        self.issues.append(issue)

    # ── File discovery ────────────────────────────────────────────────────

    def _get_files(self) -> List[Path]:
        """Gather files to analyse, respecting config patterns & exclusions."""
        exclude_dirs: Set[str] = set(self.config.get("exclude_dirs", []))
        patterns: List[str] = self.config.get("file_patterns", ["**/*"])

        all_files: List[Path] = []
        for pat in patterns:
            for fp in self.project_path.glob(pat):
                if fp.is_file():
                    # Exclude dirs
                    parts = fp.relative_to(self.project_path).parts
                    if any(d in exclude_dirs for d in parts):
                        continue
                    all_files.append(fp)

        # De-duplicate (glob patterns may overlap)
        seen: Set[Path] = set()
        unique: List[Path] = []
        for fp in all_files:
            rp = fp.resolve()
            if rp not in seen:
                seen.add(rp)
                unique.append(fp)

        return unique

    def _get_changed_files(self) -> List[Path]:
        """Return only files changed according to ``git diff --name-only``."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True, text=True,
                cwd=self.project_path,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["git", "diff", "--name-only"],
                    capture_output=True, text=True,
                    cwd=self.project_path,
                )
        except FileNotFoundError:
            return self._get_files()  # git not available — fall back

        names = {n.strip() for n in result.stdout.splitlines() if n.strip()}
        all_files = self._get_files()
        return [f for f in all_files
                if str(f.relative_to(self.project_path)) in names]

    # ── Checker instantiation & filtering ─────────────────────────────────

    def _active_checkers(self) -> List[BaseCheck]:
        """Instantiate only the checkers allowed by config."""
        allowed: List[str] = self.config.get("checks", [])
        excluded: List[str] = self.config.get("exclude_checks", [])

        instances: List[BaseCheck] = []
        for cls in get_registered_checkers():
            if allowed and cls.name not in allowed:
                continue
            if cls.name in excluded:
                continue
            instances.append(cls(self))
        return instances

    # ── Main entry ────────────────────────────────────────────────────────

    def analyze(self) -> List[Dict[str, Any]]:
        """Run all active checkers and return collected issues."""
        files = self._get_changed_files() if self.changed_only else self._get_files()

        if self.verbose:
            print(f"Analyzing {len(files)} file(s)…", file=sys.stderr)

        checkers = self._active_checkers()
        if self.verbose:
            print(f"Running {len(checkers)} checker(s)…", file=sys.stderr)

        # Enhancement #21 — parallel execution
        if self.workers > 1 and len(checkers) > 1:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                futures = {
                    pool.submit(checker.run, files): checker
                    for checker in checkers
                }
                for future in as_completed(futures):
                    exc = future.exception()
                    if exc:
                        checker = futures[future]
                        print(
                            f"[{checker.name}] failed: {exc}",
                            file=sys.stderr,
                        )
        else:
            for checker in checkers:
                try:
                    checker.run(files)
                except Exception as exc:
                    print(f"[{checker.name}] failed: {exc}", file=sys.stderr)

        # Enhancement #10 — auto-fix
        if self.fix:
            self._apply_fixes(checkers)

        # Sort by file then line
        self.issues.sort(key=lambda i: (i["file"], i["line"]))
        return self.issues

    def _apply_fixes(self, checkers: List[BaseCheck]) -> None:
        """Apply auto-fixes for fixable issues."""
        fixable_map = {c.name: c for c in checkers if c.fixable}
        applied: int = 0

        for issue in list(self.issues):
            checker = fixable_map.get(issue["check"])
            if not checker:
                continue
            fp = Path(issue["file"])
            result = checker.fix(fp, issue)
            if result is not None:
                try:
                    fp.write_text(result, encoding="utf-8")
                    applied += 1
                    # Invalidate cache
                    self._file_cache.pop(fp.resolve(), None)
                except OSError:
                    pass

        if applied and self.verbose:
            print(f"Applied {applied} auto-fix(es).", file=sys.stderr)
