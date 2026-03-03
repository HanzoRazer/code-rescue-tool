"""Unused import fixer - removes unused import lines detected by Skylos."""

from __future__ import annotations

import ast

from code_rescue.fixers.base import AbstractFixer, FixResult, FixStatus
from code_rescue.model.rescue_action import RescueAction


class UnusedImportFixer(AbstractFixer):
    """Fixer for SKY_UNUSED_IMPORT - removes unused import statements.

    Safety: SAFE — removing an unused import has no runtime effect.
    Handles both ``import X`` and ``from X import Y`` forms,
    including multi-name imports where only one name is unused.
    """

    SUPPORTED_RULES = ["SKY_UNUSED_IMPORT_001"]

    @property
    def supported_rules(self) -> list[str]:
        return self.SUPPORTED_RULES

    def can_fix(self, action: RescueAction) -> bool:
        return action.rule_id in self.SUPPORTED_RULES

    def generate_fix(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate fix by removing or trimming the import line.

        If the import has multiple names (``from X import A, B, C``) and
        only one is unused, remove just that name. Otherwise remove
        the entire import statement.
        """
        unused_name = action.metadata.get("full_name", "")
        simple_name = unused_name.rsplit(".", 1)[-1] if "." in unused_name else unused_name
        if not simple_name:
            # Fall back to description parsing
            desc = action.description or ""
            if ": " in desc:
                simple_name = desc.split(": ", 1)[1].strip()

        if not simple_name:
            return None, None

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return None, None

        # Find the import node at this line
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if node.lineno != action.line_start:
                continue

            names = node.names
            matching = [a for a in names if a.name == simple_name or (a.asname and a.asname == simple_name)]

            if not matching:
                # Name not found in this import — just delete the line
                return "", f"Removed unused import line (name '{simple_name}' not found in AST; deleting line)."

            if len(names) == 1:
                # Sole import — remove entire statement
                return "", f"Removed unused import '{simple_name}'."

            # Multi-name import — rebuild without the unused name
            remaining = [a for a in names if a not in matching]
            if not remaining:
                return "", f"Removed unused import (all names unused)."

            # Reconstruct import statement
            rebuilt = _rebuild_import(node, remaining)
            return rebuilt + "\n", f"Removed '{simple_name}' from multi-name import."

        # No AST match — fallback: delete the line
        return "", f"Removed unused import '{simple_name}' (line deletion)."

    def apply(
        self,
        action: RescueAction,
        source_code: str,
        dry_run: bool = True,
    ) -> FixResult:
        """Apply import removal."""
        if not self.can_fix(action):
            return FixResult(
                status=FixStatus.SKIPPED,
                action=action,
                message=f"Fixer does not support rule: {action.rule_id}",
            )

        replacement, rationale = self.generate_fix(action, source_code)
        if replacement is None:
            return FixResult(
                status=FixStatus.FAILED,
                action=action,
                message="Could not generate fix for unused import",
            )

        action.replacement_code = replacement
        if rationale:
            action.rationale = rationale

        # Apply removal: delete/replace lines in the specified range
        lines = source_code.splitlines(keepends=True)
        end = min(action.line_end, len(lines))
        before = "".join(lines[: action.line_start - 1])
        after = "".join(lines[end:])
        modified = before + replacement + after

        return FixResult(
            status=FixStatus.SUCCESS,
            action=action,
            original_content=source_code,
            modified_content=modified,
            message="Unused import removed" + (" (dry-run)" if dry_run else ""),
        )


def _rebuild_import(
    node: ast.Import | ast.ImportFrom,
    remaining: list[ast.alias],
) -> str:
    """Rebuild an import statement with only the remaining names."""
    name_parts = []
    for alias in remaining:
        if alias.asname:
            name_parts.append(f"{alias.name} as {alias.asname}")
        else:
            name_parts.append(alias.name)

    names_str = ", ".join(name_parts)

    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        dots = "." * (node.level or 0)
        return f"from {dots}{module} import {names_str}"
    else:
        return f"import {names_str}"
