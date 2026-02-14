"""Dead code fixer - removes unreachable and dead code."""

from __future__ import annotations

from code_rescue.fixers.base import AbstractFixer
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

        # For removal, replacement is empty string
        # But we need to preserve indentation context

        if action.rule_id == "DC_UNREACHABLE_001":
            # Remove lines after terminator (return/raise/break/continue)
            # The finding points to the unreachable lines
            rationale = (
                f"Removed {action.line_end - action.line_start + 1} unreachable "
                f"line(s) after control flow terminator."
            )
            return "", rationale

        elif action.rule_id == "DC_IF_FALSE_001":
            # Remove the entire if False: block
            rationale = "Removed 'if False:' block that never executes."
            return "", rationale

        return None, None
