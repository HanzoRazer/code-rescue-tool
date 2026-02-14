"""Base fixer class - interface for rule-specific fixers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from code_rescue.model.rescue_action import RescueAction


class FixStatus(Enum):
    """Result status of a fix attempt."""

    SUCCESS = "success"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(slots=True)
class FixResult:
    """Result of applying a fixer."""

    status: FixStatus
    action: RescueAction
    original_content: str | None = None
    modified_content: str | None = None
    diff: str | None = None
    message: str | None = None


class AbstractFixer(ABC):
    """Base class for rule-specific fixers.

    Each fixer handles one or more rule_ids and knows how to
    generate replacement code for findings matching those rules.
    """

    @property
    @abstractmethod
    def supported_rules(self) -> list[str]:
        """Return list of rule_ids this fixer can handle."""
        ...

    @abstractmethod
    def can_fix(self, action: RescueAction) -> bool:
        """Return True if this fixer can handle the given action."""
        ...

    @abstractmethod
    def generate_fix(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate replacement code for the action.

        Args:
            action: The rescue action to fix
            source_code: Full source code of the file

        Returns:
            Tuple of (replacement_code, rationale) or (None, None) if no fix possible
        """
        ...

    def apply(
        self,
        action: RescueAction,
        source_code: str,
        dry_run: bool = True,
    ) -> FixResult:
        """Apply the fix to source code.

        Args:
            action: The rescue action to apply
            source_code: Full source code of the file
            dry_run: If True, don't actually modify anything

        Returns:
            FixResult with status and modified content
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
                message="Could not generate fix",
            )

        # Update action with replacement
        action.replacement_code = replacement
        if rationale:
            action.rationale = rationale

        # For now, just return the result without actually modifying
        # Full implementation would apply the fix and generate diff
        return FixResult(
            status=FixStatus.SUCCESS,
            action=action,
            original_content=source_code,
            modified_content=None,  # TODO: implement actual modification
            message="Fix generated (dry-run)",
        )
