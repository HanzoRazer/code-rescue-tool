"""Base check class with auto-registry, caching, and shared utilities.

All concrete checkers inherit from :class:`BaseCheck`.  Setting a non-empty
``name`` class attribute auto-registers the checker for discovery by the
orchestrator.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .analyzer import CodeQualityAnalyzer

# ---------------------------------------------------------------------------
# Global checker registry (populated by __init_subclass__)
# ---------------------------------------------------------------------------
_CHECKER_REGISTRY: List[type["BaseCheck"]] = []


class BaseCheck:
    """Base class for all code quality checks.

    Subclasses are **auto-registered** when they define a non-empty
    ``name`` class attribute.  The orchestrator discovers them via
    :func:`get_registered_checkers`.
    """

    # Override in concrete checkers -----------------------------------------
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    fixable: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            _CHECKER_REGISTRY.append(cls)

    def __init__(self, analyzer: "CodeQualityAnalyzer") -> None:
        self.analyzer = analyzer

    # -- Public API ---------------------------------------------------------

    def run(self, files: List[Path]) -> None:
        """Run the check on *files*.  Override in subclasses."""

    def fix(self, file_path: Path, issue: Dict[str, Any]) -> Optional[str]:
        """Return the fixed file content for an auto-fixable issue, or *None*."""
        return None

    # -- File helpers (cached) ----------------------------------------------

    def read_file(self, file_path: Path) -> List[str]:
        """Return file lines from the analyser cache."""
        return self.analyzer.get_file_lines(file_path)

    def read_content(self, file_path: Path) -> str:
        """Return full file content from the analyser cache."""
        return self.analyzer.get_file_content(file_path)

    # -- Position helpers ---------------------------------------------------

    def _find_line_number(self, lines: List[str], position: int) -> int:
        """Map a character offset to a 1-based line number."""
        char_count = 0
        for i, line in enumerate(lines, 1):
            char_count += len(line)
            if char_count > position:
                return i
        return max(len(lines), 1)

    # -- Context helpers (rough) --------------------------------------------

    @staticmethod
    def _is_in_comment(line: str, col: int) -> bool:
        """Quick check whether *col* falls inside a ``//`` or ``/*`` comment."""
        slash = line.find("//")
        if slash != -1 and col >= slash:
            return True
        block = line.find("/*")
        if block != -1 and col >= block:
            return True
        return False

    @staticmethod
    def _is_in_string(line: str, col: int) -> bool:
        """Quick check whether *col* falls inside a JS string literal."""
        in_sq = in_dq = in_tpl = False
        for i, ch in enumerate(line[:col]):
            if ch == "'" and not in_dq and not in_tpl:
                in_sq = not in_sq
            elif ch == '"' and not in_sq and not in_tpl:
                in_dq = not in_dq
            elif ch == "`" and not in_sq and not in_dq:
                in_tpl = not in_tpl
        return in_sq or in_dq or in_tpl

    # -- Vue SFC helpers ----------------------------------------------------

    @staticmethod
    def parse_vue_sections(content: str) -> Dict[str, Tuple[int, int]]:
        """Return ``{section: (start_line, end_line)}`` for a ``.vue`` SFC.

        *section* is one of ``"template"``, ``"script"``, ``"style"``.
        Lines are 1-based.
        """
        sections: Dict[str, Tuple[int, int]] = {}
        lines = content.splitlines(keepends=True)
        current: Optional[str] = None
        start = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for tag in ("template", "script", "style"):
                if re.match(rf"<{tag}(\s|>)", stripped):
                    current = tag
                    start = i
                    break
                if stripped.startswith(f"</{tag}>") and current == tag:
                    sections[tag] = (start, i)
                    current = None
                    break
        return sections

    @staticmethod
    def _is_js_file(path: Path) -> bool:
        return path.suffix in {".js", ".ts", ".jsx", ".tsx"}

    @staticmethod
    def _is_vue_file(path: Path) -> bool:
        return path.suffix == ".vue"

    @staticmethod
    def _is_frontend_file(path: Path) -> bool:
        return path.suffix in {".js", ".ts", ".jsx", ".tsx", ".vue"}

    @staticmethod
    def _is_react_file(path: Path) -> bool:
        return path.suffix in {".jsx", ".tsx"}


def get_registered_checkers() -> List[type["BaseCheck"]]:
    """Return a snapshot of all registered checker classes."""
    return list(_CHECKER_REGISTRY)
