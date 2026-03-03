"""Tests for DeadCodeFixer."""

from __future__ import annotations

import pytest

from code_rescue.fixers.dead_code import DeadCodeFixer
from code_rescue.fixers.base import FixStatus
from code_rescue.model.rescue_action import RescueAction, ActionType, SafetyLevel


def _make_action(rule_id: str, line_start: int, line_end: int) -> RescueAction:
    return RescueAction(
        action_id="A0001",
        finding_id="f-001",
        rule_id=rule_id,
        action_type=ActionType.REMOVE,
        safety_level=SafetyLevel.SAFE,
        description="Dead code",
        file_path="src/example.py",
        line_start=line_start,
        line_end=line_end,
    )


class TestDeadCodeFixerProtocol:
    """Test DeadCodeFixer adherence to AbstractFixer protocol."""

    def test_supported_rules(self) -> None:
        fixer = DeadCodeFixer()
        assert "DC_UNREACHABLE_001" in fixer.supported_rules
        assert "DC_IF_FALSE_001" in fixer.supported_rules

    def test_can_fix_supported_rule(self) -> None:
        fixer = DeadCodeFixer()
        action = _make_action("DC_UNREACHABLE_001", 5, 6)
        assert fixer.can_fix(action) is True

    def test_cannot_fix_unsupported_rule(self) -> None:
        fixer = DeadCodeFixer()
        action = _make_action("SEC_EVAL_001", 5, 6)
        assert fixer.can_fix(action) is False

    def test_class_name_follows_convention(self) -> None:
        assert DeadCodeFixer.__name__.endswith("Fixer")


class TestDeadCodeFixerGenerateFix:
    """Test generate_fix for dead-code rules."""

    def test_unreachable_returns_empty_replacement(self) -> None:
        fixer = DeadCodeFixer()
        action = _make_action("DC_UNREACHABLE_001", 3, 4)
        code = "line1\nline2\nline3\nline4\nline5\n"
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        assert "unreachable" in rationale.lower()

    def test_if_false_returns_empty_replacement(self) -> None:
        fixer = DeadCodeFixer()
        action = _make_action("DC_IF_FALSE_001", 2, 3)
        code = "line1\nline2\nline3\n"
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        assert "if False" in rationale or "if false" in rationale.lower()

    def test_invalid_line_start_returns_none(self) -> None:
        fixer = DeadCodeFixer()
        action = _make_action("DC_UNREACHABLE_001", 0, 2)
        code = "line1\nline2\n"
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement is None
        assert rationale is None

    def test_line_end_exceeds_file_returns_none(self) -> None:
        fixer = DeadCodeFixer()
        action = _make_action("DC_UNREACHABLE_001", 1, 100)
        code = "line1\nline2\n"
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement is None
        assert rationale is None

    def test_unsupported_rule_returns_none(self) -> None:
        fixer = DeadCodeFixer()
        action = _make_action("DC_ASSERT_FALSE_001", 1, 1)
        code = "line1\n"
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement is None
        assert rationale is None


class TestDeadCodeFixerApply:
    """Test apply() method for dead-code removal."""

    def test_apply_removes_unreachable_lines(self) -> None:
        fixer = DeadCodeFixer()
        code = "def foo():\n    return 1\n    x = 2\n    y = 3\n"
        action = _make_action("DC_UNREACHABLE_001", 3, 4)
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert result.modified_content == "def foo():\n    return 1\n"

    def test_apply_removes_if_false_block(self) -> None:
        fixer = DeadCodeFixer()
        code = "x = 1\nif False:\n    pass\ny = 2\n"
        action = _make_action("DC_IF_FALSE_001", 2, 3)
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert result.modified_content == "x = 1\ny = 2\n"

    def test_apply_skips_unsupported_rule(self) -> None:
        fixer = DeadCodeFixer()
        action = _make_action("SEC_EVAL_001", 1, 1)
        result = fixer.apply(action, "code\n")
        assert result.status == FixStatus.SKIPPED

    def test_apply_fails_invalid_range(self) -> None:
        fixer = DeadCodeFixer()
        action = _make_action("DC_UNREACHABLE_001", 0, 1)
        result = fixer.apply(action, "code\n")
        assert result.status == FixStatus.FAILED

    def test_apply_preserves_surrounding_code(self) -> None:
        fixer = DeadCodeFixer()
        code = "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n"
        action = _make_action("DC_UNREACHABLE_001", 3, 3)
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert result.modified_content == "a = 1\nb = 2\nd = 4\ne = 5\n"

    def test_apply_single_line_removal(self) -> None:
        fixer = DeadCodeFixer()
        code = "x = 1\n"
        action = _make_action("DC_IF_FALSE_001", 1, 1)
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert result.modified_content == ""

    def test_apply_includes_original_content(self) -> None:
        fixer = DeadCodeFixer()
        code = "line1\nline2\n"
        action = _make_action("DC_UNREACHABLE_001", 2, 2)
        result = fixer.apply(action, code)
        assert result.original_content == code
