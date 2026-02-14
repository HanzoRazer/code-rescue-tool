"""Rescue action model - represents a fix to be applied."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(Enum):
    """Type of rescue action."""

    REMOVE = "remove"           # Delete code (dead code, unreachable)
    REPLACE = "replace"         # Replace with safer alternative
    EXTRACT = "extract"         # Extract to variable/function/env
    REFACTOR = "refactor"       # Structural change
    FLAG = "flag"               # Flag for manual review


class SafetyLevel(Enum):
    """Safety level of the rescue action."""

    SAFE = "safe"               # Guaranteed safe, can auto-apply
    SEMI_AUTO = "semi_auto"     # Usually safe, recommend review
    MANUAL = "manual"           # Requires human decision


@dataclass(slots=True)
class RescueAction:
    """A single rescue action to fix a finding."""

    action_id: str
    finding_id: str
    rule_id: str
    action_type: ActionType
    safety_level: SafetyLevel
    description: str
    file_path: str
    line_start: int
    line_end: int
    original_code: str | None = None
    replacement_code: str | None = None
    rationale: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "action_id": self.action_id,
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "action_type": self.action_type.value,
            "safety_level": self.safety_level.value,
            "description": self.description,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "original_code": self.original_code,
            "replacement_code": self.replacement_code,
            "rationale": self.rationale,
            "metadata": self.metadata,
        }


# Rule ID to action type/safety mapping
RULE_ACTION_MAP: dict[str, tuple[ActionType, SafetyLevel]] = {
    # Dead code - safe to remove
    "DC_UNREACHABLE_001": (ActionType.REMOVE, SafetyLevel.SAFE),
    "DC_IF_FALSE_001": (ActionType.REMOVE, SafetyLevel.SAFE),
    "DC_ASSERT_FALSE_001": (ActionType.FLAG, SafetyLevel.MANUAL),

    # Global state - refactoring needed
    "GST_MUTABLE_DEFAULT_001": (ActionType.REPLACE, SafetyLevel.SAFE),
    "GST_MUTABLE_MODULE_001": (ActionType.FLAG, SafetyLevel.MANUAL),
    "GST_GLOBAL_KEYWORD_001": (ActionType.REFACTOR, SafetyLevel.MANUAL),

    # Security - extraction or replacement
    "SEC_HARDCODED_SECRET_001": (ActionType.EXTRACT, SafetyLevel.SEMI_AUTO),
    "SEC_EVAL_001": (ActionType.REPLACE, SafetyLevel.MANUAL),
    "SEC_SUBPROCESS_SHELL_001": (ActionType.REPLACE, SafetyLevel.SEMI_AUTO),
    "SEC_SQL_INJECTION_001": (ActionType.REPLACE, SafetyLevel.SEMI_AUTO),
    "SEC_PICKLE_LOAD_001": (ActionType.FLAG, SafetyLevel.MANUAL),
    "SEC_YAML_UNSAFE_001": (ActionType.REPLACE, SafetyLevel.SAFE),

    # Exceptions - flag for review
    "EXC_SWALLOW_001": (ActionType.FLAG, SafetyLevel.MANUAL),
    "EXC_BROAD_LOGGED_001": (ActionType.FLAG, SafetyLevel.MANUAL),
}


def get_action_mapping(rule_id: str) -> tuple[ActionType, SafetyLevel]:
    """Get action type and safety level for a rule_id."""
    return RULE_ACTION_MAP.get(
        rule_id,
        (ActionType.FLAG, SafetyLevel.MANUAL),
    )
