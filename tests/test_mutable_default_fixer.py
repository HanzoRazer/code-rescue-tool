"""Tests for MutableDefaultFixer."""

import pytest

from code_rescue.fixers.mutable_default import (
    MutableDefaultFixer,
    find_mutable_default_params,
    apply_mutable_default_fix,
    get_function_body_indent,
)
from code_rescue.model.rescue_action import RescueAction, ActionType, SafetyLevel


class TestFindMutableDefaultParams:
    """Tests for find_mutable_default_params function."""

    def test_finds_empty_list_default(self):
        source = "def foo(items=[]):\n    pass\n"
        params = find_mutable_default_params(source, 1)
        assert len(params) == 1
        assert params[0] == ("items", "[]", "list")

    def test_finds_empty_dict_default(self):
        source = "def foo(data={}):\n    pass\n"
        params = find_mutable_default_params(source, 1)
        assert len(params) == 1
        assert params[0] == ("data", "{}", "dict")

    def test_finds_empty_set_default(self):
        source = "def foo(items=set()):\n    pass\n"
        params = find_mutable_default_params(source, 1)
        assert len(params) == 1
        assert params[0] == ("items", "set()", "set")

    def test_finds_typed_list_default(self):
        source = "def foo(items: List[str] = []):\n    pass\n"
        params = find_mutable_default_params(source, 1)
        assert len(params) == 1
        assert params[0] == ("items", "[]", "list")

    def test_finds_multiple_mutable_defaults(self):
        source = "def foo(items=[], data={}, vals=set()):\n    pass\n"
        params = find_mutable_default_params(source, 1)
        assert len(params) == 3
        assert params[0][0] == "items"
        assert params[1][0] == "data"
        assert params[2][0] == "vals"

    def test_ignores_non_mutable_defaults(self):
        source = "def foo(x=None, y=0, z=\"\"):\n    pass\n"
        params = find_mutable_default_params(source, 1)
        assert len(params) == 0

    def test_handles_syntax_error(self):
        source = "def foo(items=[:\n    pass\n"
        params = find_mutable_default_params(source, 1)
        assert len(params) == 0

    def test_wrong_line_returns_empty(self):
        source = "def foo(items=[]):\n    pass\n"
        params = find_mutable_default_params(source, 5)
        assert len(params) == 0


class TestApplyMutableDefaultFix:
    """Tests for apply_mutable_default_fix function."""

    def test_fixes_simple_list_default(self):
        source = "def foo(items=[]):\n    return items\n"
        params = [("items", "[]", "list")]
        result = apply_mutable_default_fix(source, 1, params)
        
        assert result is not None
        assert "items=None" in result or "items = None" in result
        assert "if items is None:" in result
        assert "items = []" in result

    def test_fixes_dict_default(self):
        source = "def foo(data={}):\n    return data\n"
        params = [("data", "{}", "dict")]
        result = apply_mutable_default_fix(source, 1, params)
        
        assert result is not None
        assert "data=None" in result or "data = None" in result
        assert "if data is None:" in result
        assert "data = {}" in result

    def test_returns_none_for_invalid_line(self):
        source = "def foo(items=[]):\n    pass\n"
        params = [("items", "[]", "list")]
        result = apply_mutable_default_fix(source, 999, params)
        assert result is None

    def test_returns_none_for_empty_params(self):
        source = "def foo(items=[]):\n    pass\n"
        result = apply_mutable_default_fix(source, 1, [])
        assert result is None


class TestMutableDefaultFixer:
    """Tests for MutableDefaultFixer class."""

    def test_supported_rules(self):
        fixer = MutableDefaultFixer()
        assert "GST_MUTABLE_DEFAULT_001" in fixer.supported_rules

    def test_can_fix_supported_rule(self):
        fixer = MutableDefaultFixer()
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="GST_MUTABLE_DEFAULT_001",
            file_path="test.py",
            line_start=1,
            line_end=2,
            action_type=ActionType.REPLACE,
            safety_level=SafetyLevel.SAFE,
            description="Fix mutable default",
        )
        assert fixer.can_fix(action) is True

    def test_cannot_fix_unsupported_rule(self):
        fixer = MutableDefaultFixer()
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="SOME_OTHER_RULE",
            file_path="test.py",
            line_start=1,
            line_end=2,
            action_type=ActionType.REPLACE,
            safety_level=SafetyLevel.SAFE,
            description="Other fix",
        )
        assert fixer.can_fix(action) is False

    def test_apply_generates_fix(self):
        fixer = MutableDefaultFixer()
        source = "def foo(items=[]):\n    return items\n"
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="GST_MUTABLE_DEFAULT_001",
            file_path="test.py",
            line_start=1,
            line_end=2,
            action_type=ActionType.REPLACE,
            safety_level=SafetyLevel.SAFE,
            description="Fix mutable default",
        )
        
        result = fixer.apply(action, source, dry_run=True)
        
        assert result.status.value == "success"
        assert result.modified_content is not None
        assert "if items is None:" in result.modified_content

    def test_apply_skips_unsupported_rule(self):
        fixer = MutableDefaultFixer()
        action = RescueAction(
            action_id="test-1",
            finding_id="finding-1",
            rule_id="UNSUPPORTED_RULE",
            file_path="test.py",
            line_start=1,
            line_end=1,
            action_type=ActionType.REPLACE,
            safety_level=SafetyLevel.SAFE,
            description="Other fix",
        )
        
        result = fixer.apply(action, "def foo(): pass", dry_run=True)
        
        assert result.status.value == "skipped"


class TestGetFunctionBodyIndent:
    """Tests for get_function_body_indent function."""

    def test_simple_function(self):
        lines = ["def foo():\n", "    pass\n"]
        indent = get_function_body_indent(lines, 1)
        assert indent == "    "

    def test_class_method(self):
        lines = ["class Foo:\n", "    def bar(self):\n", "        pass\n"]
        indent = get_function_body_indent(lines, 2)
        assert indent == "        "
