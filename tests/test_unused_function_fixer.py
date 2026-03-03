"""Tests for UnusedFunctionFixer."""

from __future__ import annotations

import pytest

from code_rescue.fixers.unused_function import UnusedFunctionFixer
from code_rescue.fixers.base import FixStatus
from code_rescue.model.rescue_action import RescueAction, ActionType, SafetyLevel


def _make_action(
    line_start: int,
    line_end: int,
    name: str = "old_helper",
    rule_id: str = "SKY_UNUSED_FUNC_001",
) -> RescueAction:
    return RescueAction(
        action_id="SKY0001",
        finding_id="skylos-unused_functions-10-helpers.py",
        rule_id=rule_id,
        action_type=ActionType.REMOVE,
        safety_level=SafetyLevel.SEMI_AUTO,
        description=f"Unused function: {name}",
        file_path="src/helpers.py",
        line_start=line_start,
        line_end=line_end,
        metadata={"full_name": f"app.helpers.{name}", "confidence": 95},
    )


class TestUnusedFunctionFixerProtocol:
    """Test adherence to AbstractFixer protocol."""

    def test_supported_rules(self) -> None:
        fixer = UnusedFunctionFixer()
        assert "SKY_UNUSED_FUNC_001" in fixer.supported_rules

    def test_can_fix_supported(self) -> None:
        fixer = UnusedFunctionFixer()
        action = _make_action(1, 1)
        assert fixer.can_fix(action) is True

    def test_cannot_fix_other_rule(self) -> None:
        fixer = UnusedFunctionFixer()
        action = _make_action(1, 1, rule_id="DC_UNREACHABLE_001")
        assert fixer.can_fix(action) is False

    def test_class_name_follows_convention(self) -> None:
        assert UnusedFunctionFixer.__name__.endswith("Fixer")


class TestUnusedFunctionFixerGenerateFix:
    """Test generate_fix for unused functions."""

    def test_simple_function_removal(self) -> None:
        fixer = UnusedFunctionFixer()
        code = "def old_helper():\n    return 42\n\ndef main():\n    pass\n"
        action = _make_action(1, 1, name="old_helper")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        assert "old_helper" in rationale
        # Action line_end should be updated to cover full function
        assert action.line_end == 2

    def test_function_with_decorator(self) -> None:
        fixer = UnusedFunctionFixer()
        code = "@deprecated\ndef old_func():\n    pass\n\nx = 1\n"
        action = _make_action(2, 2, name="old_func")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        # Should expand to include decorator
        assert action.line_start == 1
        assert action.line_end == 3

    def test_multiline_function(self) -> None:
        fixer = UnusedFunctionFixer()
        code = (
            "def helper():\n"
            "    x = 1\n"
            "    y = 2\n"
            "    z = x + y\n"
            "    return z\n"
            "\n"
            "def main():\n"
            "    pass\n"
        )
        action = _make_action(1, 1, name="helper")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        assert action.line_end == 5

    def test_async_function(self) -> None:
        fixer = UnusedFunctionFixer()
        code = "async def old_async():\n    await something()\n\nx = 1\n"
        action = _make_action(1, 1, name="old_async")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        assert action.line_end == 2

    def test_syntax_error_returns_none(self) -> None:
        fixer = UnusedFunctionFixer()
        code = "def broken(:\n"
        action = _make_action(1, 1)
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement is None

    def test_no_match_uses_fallback(self) -> None:
        fixer = UnusedFunctionFixer()
        code = "x = 1\ny = 2\n"
        action = _make_action(1, 2)
        replacement, rationale = fixer.generate_fix(action, code)
        # Falls back to line range
        assert replacement == ""
        assert "AST fallback" in rationale


class TestUnusedFunctionFixerApply:
    """Test apply() method for function removal."""

    def test_apply_removes_function(self) -> None:
        fixer = UnusedFunctionFixer()
        code = "def old():\n    return 1\n\ndef main():\n    pass\n"
        action = _make_action(1, 1, name="old")
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert "def old" not in result.modified_content
        assert "def main" in result.modified_content

    def test_apply_removes_decorated_function(self) -> None:
        fixer = UnusedFunctionFixer()
        code = "@deprecated\ndef old():\n    pass\n\nx = 1\n"
        action = _make_action(2, 2, name="old")
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert "@deprecated" not in result.modified_content
        assert "def old" not in result.modified_content
        assert "x = 1" in result.modified_content

    def test_apply_preserves_surrounding(self) -> None:
        fixer = UnusedFunctionFixer()
        code = "x = 1\n\ndef unused():\n    pass\n\ny = 2\n"
        action = _make_action(3, 3, name="unused")
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert "x = 1" in result.modified_content
        assert "y = 2" in result.modified_content

    def test_apply_skips_unsupported_rule(self) -> None:
        fixer = UnusedFunctionFixer()
        action = _make_action(1, 1, rule_id="SEC_EVAL_001")
        result = fixer.apply(action, "def x(): pass\n")
        assert result.status == FixStatus.SKIPPED

    def test_apply_includes_original_content(self) -> None:
        fixer = UnusedFunctionFixer()
        code = "def old():\n    pass\n"
        action = _make_action(1, 1, name="old")
        result = fixer.apply(action, code)
        assert result.original_content == code
