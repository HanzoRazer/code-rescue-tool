"""General code-quality checkers.

Checkers:
    DeadCodeDetector         — unused declarations (FIX: exclude declaring file)
    TodoCommentDetector      — TODO / FIXME / HACK / XXX
    TestCoverageIndicator    — files without corresponding tests
    BundleSizeAnalyzer       — oversized files
    ConsoleLogDetector       — console.log left in production code  [NEW]
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

from ..base import BaseCheck


# ═══════════════════════════════════════════════════════════════════════════════
# DeadCodeDetector  (FIX: exclude declaring file from usage count)
# ═══════════════════════════════════════════════════════════════════════════════

class DeadCodeDetector(BaseCheck):
    name = "DeadCodeDetector"
    description = "Detect potentially unused code (cross-file analysis)"

    def run(self, files: List[Path]) -> None:
        js_files = [f for f in files if self._is_frontend_file(f)]

        # Phase 1: collect declarations
        declarations: Dict[str, List[str]] = defaultdict(list)  # name → [files]
        for fp in js_files:
            content = self.read_content(fp)
            # Named functions
            for m in re.finditer(r"\bfunction\s+(\w+)\s*\(", content):
                declarations[m.group(1)].append(str(fp))
            # Top-level const/let/var (only at indent ≤ 4)
            for m in re.finditer(r"^[ ]{0,4}(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=",
                                 content, re.MULTILINE):
                declarations[m.group(1)].append(str(fp))

        # Phase 2: scan for usage — name must appear in a DIFFERENT file
        for fp in js_files:
            content = self.read_content(fp)
            for name in list(declarations.keys()):
                if name in content:
                    # Mark as used if this is not the *only* file that declares it
                    declaring_files = declarations[name]
                    if str(fp) not in declaring_files:
                        declarations.pop(name, None)  # it's used elsewhere

        # Phase 3: report names that remain (declared but never used elsewhere)
        # Filter out common false positives (very short names, exports)
        for name, file_list in declarations.items():
            if len(name) <= 2:
                continue  # skip _, i, x, …
            for fpath in file_list:
                # Also check if it's exported (exports are API surface, not dead)
                fcontent = self.read_content(Path(fpath))
                if re.search(rf"\bexport\b.*\b{re.escape(name)}\b", fcontent):
                    continue
                self.analyzer.add_issue(
                    check_name=self.name,
                    file_path=Path(fpath),
                    line=1,
                    message=f"Potentially unused: '{name}'",
                    severity="info",
                    suggestion="Remove if not needed, or verify it's used via dynamic import",
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TodoCommentDetector  (extended: HACK, XXX, WARN)
# ═══════════════════════════════════════════════════════════════════════════════

class TodoCommentDetector(BaseCheck):
    name = "TodoCommentDetector"
    description = "Detect TODO, FIXME, HACK, XXX comments"

    _PATTERNS = [
        (re.compile(r"(?://|/\*|#|<!--)\s*TODO\b", re.IGNORECASE),
         "TODO comment found", "info",
         "Address pending tasks before production"),
        (re.compile(r"(?://|/\*|#|<!--)\s*FIXME\b", re.IGNORECASE),
         "FIXME comment found", "warning",
         "This indicates a known bug that needs fixing"),
        (re.compile(r"(?://|/\*|#|<!--)\s*HACK\b", re.IGNORECASE),
         "HACK comment found", "warning",
         "Refactor this workaround into a proper solution"),
        (re.compile(r"(?://|/\*|#|<!--)\s*XXX\b", re.IGNORECASE),
         "XXX comment found", "warning",
         "Review and resolve this marker"),
    ]

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)
            for i, line in enumerate(lines, 1):
                for pattern, message, severity, suggestion in self._PATTERNS:
                    if pattern.search(line):
                        self.analyzer.add_issue(
                            check_name=self.name,
                            file_path=fp,
                            line=i,
                            message=message,
                            severity=severity,
                            suggestion=suggestion,
                        )
                        break  # one per line


# ═══════════════════════════════════════════════════════════════════════════════
# TestCoverageIndicator  (improved matching)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoverageIndicator(BaseCheck):
    name = "TestCoverageIndicator"
    description = "Identify source files without corresponding test files"

    def run(self, files: List[Path]) -> None:
        sources: List[Path] = []
        test_stems: Set[str] = set()

        for fp in files:
            name_lower = fp.name.lower()
            if any(t in name_lower for t in (".test.", ".spec.", "_test.", "_spec.", "__test")):
                # Normalise test stem: MyComponent.test.js → mycomponent
                stem = re.sub(r"\.(test|spec)", "", fp.stem, flags=re.IGNORECASE).lower()
                test_stems.add(stem)
            elif self._is_frontend_file(fp):
                sources.append(fp)

        for src in sources:
            base = src.stem.lower()
            if base in test_stems:
                continue
            # Also accept camelCase → snake_case equivalents
            snake = re.sub(r"([a-z])([A-Z])", r"\1_\2", src.stem).lower()
            if snake in test_stems:
                continue
            self.analyzer.add_issue(
                check_name=self.name,
                file_path=src,
                line=1,
                message="No corresponding test file found",
                severity="info",
                suggestion=f"Create a test file for {src.name}",
            )


# ═══════════════════════════════════════════════════════════════════════════════
# BundleSizeAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════

class BundleSizeAnalyzer(BaseCheck):
    name = "BundleSizeAnalyzer"
    description = "Flag oversized files that may hurt bundle performance"

    def run(self, files: List[Path]) -> None:
        max_kb = self.analyzer.config.get("max_file_size_kb", 100)

        large: List[tuple[Path, float]] = []
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            try:
                size_kb = fp.stat().st_size / 1024
            except OSError:
                continue
            if size_kb > max_kb:
                large.append((fp, size_kb))

        large.sort(key=lambda x: x[1], reverse=True)
        for fp, size_kb in large[:10]:
            self.analyzer.add_issue(
                check_name=self.name,
                file_path=fp,
                line=1,
                message=f"Large file detected ({size_kb:.1f} KB)",
                severity="info",
                suggestion="Consider code splitting or lazy loading",
            )


# ═══════════════════════════════════════════════════════════════════════════════
# ConsoleLogDetector  [NEW — Enhancement #13]
# ═══════════════════════════════════════════════════════════════════════════════

class ConsoleLogDetector(BaseCheck):
    name = "ConsoleLogDetector"
    description = "Detect console.log / warn / error left in source"
    fixable = True

    _PATTERN = re.compile(r"\bconsole\.(log|warn|error|debug|info|trace|dir)\s*\(")

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("//"):
                    continue
                m = self._PATTERN.search(line)
                if m:
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=i,
                        message=f"console.{m.group(1)}() left in source",
                        severity="warning",
                        suggestion="Remove or replace with a proper logging framework",
                    )

    def fix(self, file_path: Path, issue: Dict[str, Any]) -> str | None:
        """Remove the console.* line."""
        lines = list(self.read_file(file_path))
        idx = issue["line"] - 1
        if 0 <= idx < len(lines):
            lines[idx] = ""
        return "".join(lines)
