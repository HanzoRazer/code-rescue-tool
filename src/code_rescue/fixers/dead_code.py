"""Dead code fixer - removes unreachable and dead code."""

from __future__ import annotations

from code_rescue.fixers.base import AbstractFixer, FixResult, FixStatus
from code_rescue.model.rescue_action import RescueAction


class DeadCodeFixer(AbstractFixer):
    """Fixer for dead code rules (DC_*)."""

    SUPPORTED_RULES = [
        "DC_UNREACHABLE_001",
        "DC_IF_FALSE_001",
    ]

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
        """Generate fix by removing the dead code lines.

        For DC_UNREACHABLE_001 and DC_IF_FALSE_001, the fix is simply
        to remove the offending lines.
        """
        lines = source_code.splitlines(keepends=True)

        # Validate line numbers
        if action.line_start < 1 or action.line_end > len(lines):
            return None, None

        if action.rule_id == "DC_UNREACHABLE_001":
            rationale = (
                f"Removed {action.line_end - action.line_start + 1} unreachable "
                f"line(s) after control flow terminator."
            )
            return "", rationale

        elif action.rule_id == "DC_IF_FALSE_001":
            rationale = "Removed 'if False:' block that never executes."
            return "", rationale

        return None, None

    def apply(
        self,
        action: RescueAction,
        source_code: str,
        dry_run: bool = True,
    ) -> FixResult:
        """Apply dead code removal.

        Removes the lines identified by the action's line range.
        """
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
                message="Could not generate fix (invalid line range)",
            )

        action.replacement_code = replacement
        if rationale:
            action.rationale = rationale

        # Apply removal: delete lines in the specified range
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
            message="Dead code removed" + (" (dry-run)" if dry_run else ""),
        )
