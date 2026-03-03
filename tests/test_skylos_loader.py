"""Tests for Skylos dead-code report loader."""

from __future__ import annotations

import pytest

from code_rescue.ingest.skylos_loader import (
    SkylosReport,
    SkylosSymbol,
    load_skylos_report,
    resolve_line_end,
    skylos_to_actions,
    SKYLOS_RULE_MAP,
    FIXABLE_CATEGORIES,
)
from code_rescue.model.rescue_action import ActionType, SafetyLevel


# ── Fixtures ────────────────────────────────────────────────────────

MINIMAL_REPORT: dict = {
    "unused_imports": [
        {
            "name": "List",
            "full_name": "typing.List",
            "simple_name": "List",
            "type": "import",
            "file": "/project/src/app.py",
            "basename": "app.py",
            "line": 3,
            "confidence": 100,
            "references": 0,
        },
    ],
    "unused_functions": [
        {
            "name": "old_helper",
            "full_name": "app.helpers.old_helper",
            "simple_name": "old_helper",
            "type": "function",
            "file": "/project/src/helpers.py",
            "basename": "helpers.py",
            "line": 10,
            "confidence": 95,
            "references": 0,
            "calls": [],
            "decorators": [],
        },
    ],
    "unused_classes": [
        {
            "name": "OldMixin",
            "full_name": "app.mixins.OldMixin",
            "simple_name": "OldMixin",
            "type": "class",
            "file": "/project/src/mixins.py",
            "basename": "mixins.py",
            "line": 5,
            "confidence": 90,
            "references": 0,
        },
    ],
    "unused_variables": [
        {
            "name": "DEBUG",
            "full_name": "app.config.DEBUG",
            "simple_name": "DEBUG",
            "type": "variable",
            "file": "/project/src/config.py",
            "basename": "config.py",
            "line": 1,
            "confidence": 80,
            "references": 0,
        },
    ],
    "unused_parameters": [],
}


class TestLoadSkylosReport:
    """Test loading and parsing Skylos JSON."""

    def test_loads_all_categories(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        assert isinstance(report, SkylosReport)
        assert len(report.symbols) == 4

    def test_symbols_have_correct_categories(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        categories = {s.category for s in report.symbols}
        assert "unused_imports" in categories
        assert "unused_functions" in categories
        assert "unused_classes" in categories
        assert "unused_variables" in categories

    def test_fixable_returns_correct_subset(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        fixable = report.fixable
        # Variables are NOT fixable
        assert len(fixable) == 3
        fixable_cats = {s.category for s in fixable}
        assert "unused_variables" not in fixable_cats

    def test_by_category_groups_correctly(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        by_cat = report.by_category
        assert len(by_cat["unused_imports"]) == 1
        assert by_cat["unused_imports"][0].name == "List"

    def test_empty_report(self) -> None:
        report = load_skylos_report({})
        assert len(report.symbols) == 0

    def test_symbol_fields_populated(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        imp = next(s for s in report.symbols if s.category == "unused_imports")
        assert imp.name == "List"
        assert imp.full_name == "typing.List"
        assert imp.line == 3
        assert imp.confidence == 100
        assert imp.references == 0
        assert imp.symbol_type == "import"


class TestSkylosToActions:
    """Test conversion from SkylosReport to RescueAction list."""

    def test_produces_actions(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        actions = skylos_to_actions(report)
        assert len(actions) == 3  # import, function, class (not variable)

    def test_import_action_is_safe(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        actions = skylos_to_actions(report)
        import_action = next(a for a in actions if a.rule_id == "SKY_UNUSED_IMPORT_001")
        assert import_action.action_type == ActionType.REMOVE
        assert import_action.safety_level == SafetyLevel.SAFE

    def test_function_action_is_semi_auto(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        actions = skylos_to_actions(report)
        func_action = next(a for a in actions if a.rule_id == "SKY_UNUSED_FUNC_001")
        assert func_action.action_type == ActionType.REMOVE
        assert func_action.safety_level == SafetyLevel.SEMI_AUTO

    def test_class_action_is_manual(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        actions = skylos_to_actions(report)
        cls_action = next(a for a in actions if a.rule_id == "SKY_UNUSED_CLASS_001")
        assert cls_action.action_type == ActionType.REMOVE
        assert cls_action.safety_level == SafetyLevel.MANUAL

    def test_min_confidence_filters(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        # Set min_confidence to 96 — only import (100) passes
        actions = skylos_to_actions(report, min_confidence=96)
        assert len(actions) == 1
        assert actions[0].rule_id == "SKY_UNUSED_IMPORT_001"

    def test_category_filter(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        actions = skylos_to_actions(report, categories={"unused_imports"})
        assert all(a.rule_id == "SKY_UNUSED_IMPORT_001" for a in actions)

    def test_root_strips_prefix(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        actions = skylos_to_actions(report, root="/project")
        for a in actions:
            assert not a.file_path.startswith("/project/")
            assert a.file_path.startswith("src/")

    def test_actions_sorted_by_confidence_desc(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        actions = skylos_to_actions(report)
        confidences = [a.metadata["confidence"] for a in actions]
        assert confidences == sorted(confidences, reverse=True)

    def test_skips_symbols_with_references(self) -> None:
        data = {
            "unused_imports": [
                {
                    "name": "Used",
                    "full_name": "typing.Used",
                    "simple_name": "Used",
                    "type": "import",
                    "file": "/project/src/app.py",
                    "basename": "app.py",
                    "line": 1,
                    "confidence": 100,
                    "references": 3,  # Has references — shouldn't be acted on
                },
            ],
        }
        report = load_skylos_report(data)
        actions = skylos_to_actions(report)
        assert len(actions) == 0

    def test_action_ids_are_unique(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        actions = skylos_to_actions(report)
        ids = [a.action_id for a in actions]
        assert len(ids) == len(set(ids))

    def test_metadata_includes_full_name(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        actions = skylos_to_actions(report)
        for a in actions:
            assert "full_name" in a.metadata
            assert "confidence" in a.metadata

    def test_to_dict_roundtrip(self) -> None:
        report = load_skylos_report(MINIMAL_REPORT)
        actions = skylos_to_actions(report)
        for a in actions:
            d = a.to_dict()
            assert d["rule_id"].startswith("SKY_UNUSED_")
            assert isinstance(d["line_start"], int)
            assert isinstance(d["metadata"], dict)


class TestResolveLineEnd:
    """Test AST-based line_end resolution."""

    def test_function_end_line(self, tmp_path) -> None:
        code = "def foo():\n    x = 1\n    return x\n\ny = 2\n"
        f = tmp_path / "test.py"
        f.write_text(code)
        assert resolve_line_end(str(f), 1, "function") == 3

    def test_class_end_line(self, tmp_path) -> None:
        code = "class Foo:\n    x = 1\n    def bar(self):\n        pass\n\ny = 2\n"
        f = tmp_path / "test.py"
        f.write_text(code)
        assert resolve_line_end(str(f), 1, "class") == 4

    def test_import_end_line_single(self, tmp_path) -> None:
        code = "import os\nimport sys\n"
        f = tmp_path / "test.py"
        f.write_text(code)
        assert resolve_line_end(str(f), 1, "import") == 1

    def test_import_end_line_multiline(self, tmp_path) -> None:
        code = "from typing import (\n    List,\n    Dict,\n)\n"
        f = tmp_path / "test.py"
        f.write_text(code)
        assert resolve_line_end(str(f), 1, "import") == 4

    def test_missing_file_returns_start(self) -> None:
        assert resolve_line_end("/nonexistent/file.py", 5, "function") == 5

    def test_syntax_error_returns_start(self, tmp_path) -> None:
        f = tmp_path / "bad.py"
        f.write_text("def foo(:\n")
        assert resolve_line_end(str(f), 1, "function") == 1

    def test_no_match_returns_start(self, tmp_path) -> None:
        code = "x = 1\ny = 2\n"
        f = tmp_path / "test.py"
        f.write_text(code)
        assert resolve_line_end(str(f), 1, "function") == 1
