"""Load and normalize Skylos dead-code JSON into RescueAction lists.

Skylos outputs a flat JSON with category lists:
    {
      "unused_functions": [...],
      "unused_imports": [...],
      "unused_classes": [...],
      "unused_variables": [...],
      "unused_parameters": [...],
      ...
    }

Each entry has: name, full_name, simple_name, type, file, basename, line,
confidence, references, and optionally calls/decorators.

This module converts them into RescueAction objects consumable by fixers,
and uses Python's ast module to resolve line_end (Skylos only gives start).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from code_rescue.model.rescue_action import (
    RescueAction,
    ActionType,
    SafetyLevel,
)


# Rule IDs for Skylos dead-code categories
SKYLOS_RULE_MAP: dict[str, str] = {
    "unused_functions": "SKY_UNUSED_FUNC_001",
    "unused_imports": "SKY_UNUSED_IMPORT_001",
    "unused_classes": "SKY_UNUSED_CLASS_001",
    "unused_variables": "SKY_UNUSED_VAR_001",
    "unused_parameters": "SKY_UNUSED_PARAM_001",
}

# Safety classification per category
SKYLOS_SAFETY_MAP: dict[str, tuple[ActionType, SafetyLevel]] = {
    "SKY_UNUSED_IMPORT_001": (ActionType.REMOVE, SafetyLevel.SAFE),
    "SKY_UNUSED_FUNC_001": (ActionType.REMOVE, SafetyLevel.SEMI_AUTO),
    "SKY_UNUSED_CLASS_001": (ActionType.REMOVE, SafetyLevel.MANUAL),
    "SKY_UNUSED_VAR_001": (ActionType.FLAG, SafetyLevel.MANUAL),
    "SKY_UNUSED_PARAM_001": (ActionType.FLAG, SafetyLevel.MANUAL),
}

# Categories we can auto-fix (have fixers for)
FIXABLE_CATEGORIES = {"unused_functions", "unused_imports", "unused_classes"}


@dataclass(frozen=True, slots=True)
class SkylosSymbol:
    """A single dead symbol from Skylos output."""

    name: str
    full_name: str
    simple_name: str
    symbol_type: str          # function, method, class, import, variable
    file: str
    basename: str
    line: int
    confidence: int           # 0-100
    references: int
    category: str             # unused_functions, unused_imports, etc.
    calls: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SkylosReport:
    """Parsed Skylos dead-code report."""

    symbols: list[SkylosSymbol]
    grade: dict[str, Any] = field(default_factory=dict)
    analysis_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def by_category(self) -> dict[str, list[SkylosSymbol]]:
        result: dict[str, list[SkylosSymbol]] = {}
        for sym in self.symbols:
            result.setdefault(sym.category, []).append(sym)
        return result

    @property
    def fixable(self) -> list[SkylosSymbol]:
        return [s for s in self.symbols if s.category in FIXABLE_CATEGORIES]


def _parse_symbol(entry: dict[str, Any], category: str) -> SkylosSymbol:
    """Parse a single Skylos symbol entry."""
    return SkylosSymbol(
        name=entry.get("name", ""),
        full_name=entry.get("full_name", ""),
        simple_name=entry.get("simple_name", ""),
        symbol_type=entry.get("type", ""),
        file=entry.get("file", ""),
        basename=entry.get("basename", ""),
        line=entry.get("line", 0),
        confidence=entry.get("confidence", 0),
        references=entry.get("references", 0),
        category=category,
        calls=entry.get("calls", []),
        decorators=entry.get("decorators", []),
    )


def load_skylos_report(data: dict[str, Any]) -> SkylosReport:
    """Parse Skylos dead-code JSON into a SkylosReport."""
    symbols: list[SkylosSymbol] = []

    for category, rule_id in SKYLOS_RULE_MAP.items():
        entries = data.get(category, [])
        if isinstance(entries, list):
            for entry in entries:
                symbols.append(_parse_symbol(entry, category))

    return SkylosReport(
        symbols=symbols,
        grade=data.get("grade", {}),
        analysis_summary=data.get("analysis_summary", {}),
    )


def resolve_line_end(file_path: str, line_start: int, symbol_type: str) -> int:
    """Use Python AST to find the end line of a symbol.

    Args:
        file_path: Absolute path to the Python file
        line_start: 1-based start line of the symbol
        symbol_type: 'function', 'method', 'class', or 'import'

    Returns:
        1-based end line, or line_start if resolution fails
    """
    if symbol_type == "import":
        # Imports are single-line (or we find the actual end via AST)
        return _resolve_import_end(file_path, line_start)

    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return line_start

    # Walk AST for matching node
    for node in ast.walk(tree):
        if not hasattr(node, "lineno"):
            continue

        if node.lineno != line_start:
            continue

        if symbol_type in ("function", "method") and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            return node.end_lineno or line_start

        if symbol_type == "class" and isinstance(node, ast.ClassDef):
            return node.end_lineno or line_start

    return line_start


def _resolve_import_end(file_path: str, line_start: int) -> int:
    """Resolve end line for an import statement (may be multi-line)."""
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return line_start

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if node.lineno == line_start:
                return node.end_lineno or line_start

    return line_start


def skylos_to_actions(
    report: SkylosReport,
    root: str = "",
    min_confidence: int = 80,
    categories: set[str] | None = None,
) -> list[RescueAction]:
    """Convert SkylosReport into a list of RescueAction objects.

    Args:
        report: Parsed Skylos report
        root: Root directory to make paths relative to (optional)
        min_confidence: Minimum confidence threshold (0-100)
        categories: Set of categories to include (default: all fixable)

    Returns:
        List of RescueAction objects, prioritized by confidence desc
    """
    allowed = categories or FIXABLE_CATEGORIES
    actions: list[RescueAction] = []
    action_num = 0

    for sym in sorted(report.symbols, key=lambda s: -s.confidence):
        if sym.category not in allowed:
            continue
        if sym.confidence < min_confidence:
            continue
        if sym.references > 0:
            continue  # Skip symbols that still have references

        rule_id = SKYLOS_RULE_MAP[sym.category]
        action_type, safety_level = SKYLOS_SAFETY_MAP[rule_id]

        # Normalize file path
        file_path = sym.file.replace("\\", "/")
        if root:
            root_norm = root.replace("\\", "/").rstrip("/") + "/"
            if file_path.startswith(root_norm):
                file_path = file_path[len(root_norm):]

        # Resolve end line via AST (only for files we can read)
        line_end = resolve_line_end(sym.file, sym.line, sym.symbol_type)

        action_num += 1
        actions.append(RescueAction(
            action_id=f"SKY{action_num:04d}",
            finding_id=f"skylos-{sym.category}-{sym.line}-{sym.basename}",
            rule_id=rule_id,
            action_type=action_type,
            safety_level=safety_level,
            description=f"Unused {sym.symbol_type}: {sym.simple_name}",
            file_path=file_path,
            line_start=sym.line,
            line_end=line_end,
            original_code=None,
            rationale=_rationale(sym),
            metadata={
                "full_name": sym.full_name,
                "confidence": sym.confidence,
                "decorators": sym.decorators,
                "skylos_category": sym.category,
            },
        ))

    return actions


def _rationale(sym: SkylosSymbol) -> str:
    """Generate human-readable rationale for removing a symbol."""
    templates = {
        "unused_imports": (
            f"Import '{sym.simple_name}' has {sym.references} references. "
            "Removing unused imports improves readability and startup time."
        ),
        "unused_functions": (
            f"Function '{sym.simple_name}' has {sym.references} references "
            f"(confidence: {sym.confidence}%). "
            "Removing dead functions reduces maintenance burden."
        ),
        "unused_classes": (
            f"Class '{sym.simple_name}' has {sym.references} references "
            f"(confidence: {sym.confidence}%). "
            "Flag for review — may be used via dynamic dispatch or external callers."
        ),
        "unused_variables": (
            f"Variable '{sym.simple_name}' is assigned but never read."
        ),
        "unused_parameters": (
            f"Parameter '{sym.simple_name}' is never used in the function body."
        ),
    }
    return templates.get(sym.category, f"Dead code: {sym.full_name}")
