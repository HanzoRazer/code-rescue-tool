"""Unused class fixer - removes dead classes detected by Skylos."""

from __future__ import annotations

import ast

from code_rescue.fixers.base import AbstractFixer, FixResult, FixStatus
from code_rescue.model.rescue_action import RescueAction


class UnusedClassFixer(AbstractFixer):
    """Fixer for SKY_UNUSED_CLASS - removes unused class definitions.

    Safety: MANUAL — classes may be used via dynamic dispatch, metaclasses,
    plugin registries or external imports that static analysis cannot detect.
    Flags for review by default; will remove if explicitly invoked.
    """

    SUPPORTED_RULES = ["SKY_UNUSED_CLASS_001"]

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
        """Generate fix by identifying the full class span via AST.

        Returns empty replacement (deletion) with rationale.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return None, None

        class_node = _find_class_at_line(tree, action.line_start)
        if class_node is None:
            # Fallback: trust the line range in the action
            if action.line_start >= 1 and action.line_end >= action.line_start:
                name = action.description.split(": ", 1)[-1] if ": " in action.description else "unknown"
                rationale = (
                    f"Removed unused class '{name}' "
                    f"(lines {action.line_start}-{action.line_end}, AST fallback)."
                )
                return "", rationale
            return None, None

        # Update action line range to cover decorators through end
        decorator_start = _decorator_start(class_node)
        if decorator_start < action.line_start:
            action.line_start = decorator_start
        if class_node.end_lineno and class_node.end_lineno > action.line_end:
            action.line_end = class_node.end_lineno

        name = class_node.name
        span = action.line_end - action.line_start + 1
        rationale = (
            f"Removed unused class '{name}' ({span} lines). "
            "Verify no dynamic/plugin usage before committing."
        )
        return "", rationale

    def apply(
        self,
        action: RescueAction,
        source_code: str,
        dry_run: bool = True,
    ) -> FixResult:
        """Apply class removal."""
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
                message="Could not locate class in AST",
            )

        action.replacement_code = replacement
        if rationale:
            action.rationale = rationale

        # Apply removal
        lines = source_code.splitlines(keepends=True)
        end = min(action.line_end, len(lines))
        before = "".join(lines[: action.line_start - 1])
        after = "".join(lines[end:])
        modified = before + after

        return FixResult(
            status=FixStatus.SUCCESS,
            action=action,
            original_content=source_code,
            modified_content=modified,
            message="Unused class removed" + (" (dry-run)" if dry_run else ""),
        )


def _find_class_at_line(tree: ast.Module, line: int) -> ast.ClassDef | None:
    """Find a class definition starting at the given line.

    Also checks decorator lines.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        dec_start = _decorator_start(node)
        if dec_start <= line <= node.lineno:
            return node

    return None


def _decorator_start(node: ast.ClassDef) -> int:
    """Return the first line of decorators, or the class line if none."""
    if node.decorator_list:
        return min(d.lineno for d in node.decorator_list)
    return node.lineno
