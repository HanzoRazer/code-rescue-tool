"""Tests for UnusedClassFixer."""

from __future__ import annotations

import pytest

from code_rescue.fixers.unused_class import UnusedClassFixer
from code_rescue.fixers.base import FixStatus
from code_rescue.model.rescue_action import RescueAction, ActionType, SafetyLevel


def _make_action(
    line_start: int,
    line_end: int,
    name: str = "OldMixin",
    rule_id: str = "SKY_UNUSED_CLASS_001",
) -> RescueAction:
    return RescueAction(
        action_id="SKY0001",
        finding_id="skylos-unused_classes-5-mixins.py",
        rule_id=rule_id,
        action_type=ActionType.REMOVE,
        safety_level=SafetyLevel.MANUAL,
        description=f"Unused class: {name}",
        file_path="src/mixins.py",
        line_start=line_start,
        line_end=line_end,
        metadata={"full_name": f"app.mixins.{name}", "confidence": 90},
    )


class TestUnusedClassFixerProtocol:
    """Test adherence to AbstractFixer protocol."""

    def test_supported_rules(self) -> None:
        fixer = UnusedClassFixer()
        assert "SKY_UNUSED_CLASS_001" in fixer.supported_rules

    def test_can_fix_supported(self) -> None:
        fixer = UnusedClassFixer()
        action = _make_action(1, 1)
        assert fixer.can_fix(action) is True

    def test_cannot_fix_other_rule(self) -> None:
        fixer = UnusedClassFixer()
        action = _make_action(1, 1, rule_id="DC_UNREACHABLE_001")
        assert fixer.can_fix(action) is False

    def test_class_name_follows_convention(self) -> None:
        assert UnusedClassFixer.__name__.endswith("Fixer")


class TestUnusedClassFixerGenerateFix:
    """Test generate_fix for unused classes."""

    def test_simple_class_removal(self) -> None:
        fixer = UnusedClassFixer()
        code = "class OldMixin:\n    x = 1\n\nclass Active:\n    pass\n"
        action = _make_action(1, 1, name="OldMixin")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        assert "OldMixin" in rationale
        assert action.line_end == 2

    def test_class_with_methods(self) -> None:
        fixer = UnusedClassFixer()
        code = (
            "class Dead:\n"
            "    def __init__(self):\n"
            "        self.x = 1\n"
            "\n"
            "    def method(self):\n"
            "        return self.x\n"
            "\n"
            "y = 2\n"
        )
        action = _make_action(1, 1, name="Dead")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        assert action.line_end == 6

    def test_class_with_decorator(self) -> None:
        fixer = UnusedClassFixer()
        code = "@dataclass\nclass Config:\n    x: int = 0\n\ny = 1\n"
        action = _make_action(2, 2, name="Config")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        assert action.line_start == 1
        assert action.line_end == 3

    def test_rationale_includes_review_warning(self) -> None:
        fixer = UnusedClassFixer()
        code = "class Old:\n    pass\n"
        action = _make_action(1, 1, name="Old")
        _, rationale = fixer.generate_fix(action, code)
        assert "dynamic" in rationale.lower() or "plugin" in rationale.lower()

    def test_syntax_error_returns_none(self) -> None:
        fixer = UnusedClassFixer()
        code = "class Broken(:\n"
        action = _make_action(1, 1)
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement is None


class TestUnusedClassFixerApply:
    """Test apply() method for class removal."""

    def test_apply_removes_class(self) -> None:
        fixer = UnusedClassFixer()
        code = "class Old:\n    pass\n\nclass Active:\n    pass\n"
        action = _make_action(1, 1, name="Old")
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert "class Old" not in result.modified_content
        assert "class Active" in result.modified_content

    def test_apply_removes_decorated_class(self) -> None:
        fixer = UnusedClassFixer()
        code = "@dataclass\nclass Old:\n    x: int = 0\n\ny = 1\n"
        action = _make_action(2, 2, name="Old")
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert "@dataclass" not in result.modified_content
        assert "class Old" not in result.modified_content
        assert "y = 1" in result.modified_content

    def test_apply_preserves_surrounding(self) -> None:
        fixer = UnusedClassFixer()
        code = "x = 1\n\nclass Dead:\n    pass\n\ny = 2\n"
        action = _make_action(3, 3, name="Dead")
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert "x = 1" in result.modified_content
        assert "y = 2" in result.modified_content

    def test_apply_skips_unsupported_rule(self) -> None:
        fixer = UnusedClassFixer()
        action = _make_action(1, 1, rule_id="SEC_EVAL_001")
        result = fixer.apply(action, "class X: pass\n")
        assert result.status == FixStatus.SKIPPED

    def test_apply_includes_original_content(self) -> None:
        fixer = UnusedClassFixer()
        code = "class Old:\n    pass\n"
        action = _make_action(1, 1, name="Old")
        result = fixer.apply(action, code)
        assert result.original_content == code
