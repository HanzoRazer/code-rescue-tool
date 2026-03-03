"""Tests for UnusedImportFixer."""

from __future__ import annotations

import pytest

from code_rescue.fixers.unused_import import UnusedImportFixer
from code_rescue.fixers.base import FixStatus
from code_rescue.model.rescue_action import RescueAction, ActionType, SafetyLevel


def _make_action(
    line_start: int,
    line_end: int,
    full_name: str = "typing.List",
    rule_id: str = "SKY_UNUSED_IMPORT_001",
) -> RescueAction:
    return RescueAction(
        action_id="SKY0001",
        finding_id="skylos-unused_imports-3-app.py",
        rule_id=rule_id,
        action_type=ActionType.REMOVE,
        safety_level=SafetyLevel.SAFE,
        description=f"Unused import: {full_name.rsplit('.', 1)[-1]}",
        file_path="src/app.py",
        line_start=line_start,
        line_end=line_end,
        metadata={"full_name": full_name, "confidence": 100},
    )


class TestUnusedImportFixerProtocol:
    """Test adherence to AbstractFixer protocol."""

    def test_supported_rules(self) -> None:
        fixer = UnusedImportFixer()
        assert "SKY_UNUSED_IMPORT_001" in fixer.supported_rules

    def test_can_fix_supported(self) -> None:
        fixer = UnusedImportFixer()
        action = _make_action(1, 1)
        assert fixer.can_fix(action) is True

    def test_cannot_fix_other_rule(self) -> None:
        fixer = UnusedImportFixer()
        action = _make_action(1, 1, rule_id="DC_UNREACHABLE_001")
        assert fixer.can_fix(action) is False

    def test_class_name_follows_convention(self) -> None:
        assert UnusedImportFixer.__name__.endswith("Fixer")


class TestUnusedImportFixerGenerateFix:
    """Test generate_fix for unused imports."""

    def test_removes_simple_import(self) -> None:
        fixer = UnusedImportFixer()
        code = "import os\nimport sys\n\nx = 1\n"
        action = _make_action(1, 1, full_name="os")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        assert "os" in rationale

    def test_removes_from_import(self) -> None:
        fixer = UnusedImportFixer()
        code = "from typing import List\nimport os\n"
        action = _make_action(1, 1, full_name="typing.List")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement == ""
        assert "List" in rationale

    def test_trims_multi_name_import(self) -> None:
        fixer = UnusedImportFixer()
        code = "from typing import List, Dict, Optional\n"
        action = _make_action(1, 1, full_name="typing.Dict")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement is not None
        assert "Dict" not in replacement or "Removed" in rationale
        assert "List" in replacement
        assert "Optional" in replacement

    def test_syntax_error_returns_none(self) -> None:
        fixer = UnusedImportFixer()
        code = "from typing import (\n"  # Incomplete
        action = _make_action(1, 1, full_name="typing.List")
        replacement, rationale = fixer.generate_fix(action, code)
        assert replacement is None


class TestUnusedImportFixerApply:
    """Test apply() method for import removal."""

    def test_apply_removes_import_line(self) -> None:
        fixer = UnusedImportFixer()
        code = "import os\nimport sys\n\nx = 1\n"
        action = _make_action(1, 1, full_name="os")
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert "import os" not in result.modified_content
        assert "import sys" in result.modified_content
        assert "x = 1" in result.modified_content

    def test_apply_removes_from_import(self) -> None:
        fixer = UnusedImportFixer()
        code = "from typing import List\nimport os\nx = 1\n"
        action = _make_action(1, 1, full_name="typing.List")
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert "List" not in result.modified_content
        assert "import os" in result.modified_content

    def test_apply_preserves_surrounding_code(self) -> None:
        fixer = UnusedImportFixer()
        code = "# header\nimport os\nimport sys\n\ndef main():\n    pass\n"
        action = _make_action(2, 2, full_name="os")
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert "# header" in result.modified_content
        assert "import sys" in result.modified_content
        assert "def main" in result.modified_content

    def test_apply_skips_unsupported_rule(self) -> None:
        fixer = UnusedImportFixer()
        action = _make_action(1, 1, rule_id="DC_UNREACHABLE_001")
        result = fixer.apply(action, "import os\n")
        assert result.status == FixStatus.SKIPPED

    def test_apply_includes_original_content(self) -> None:
        fixer = UnusedImportFixer()
        code = "import os\n"
        action = _make_action(1, 1, full_name="os")
        result = fixer.apply(action, code)
        assert result.original_content == code

    def test_apply_multi_name_keeps_others(self) -> None:
        fixer = UnusedImportFixer()
        code = "from typing import List, Dict, Optional\nx = 1\n"
        action = _make_action(1, 1, full_name="typing.Dict")
        result = fixer.apply(action, code)
        assert result.status == FixStatus.SUCCESS
        assert "List" in result.modified_content
        assert "Optional" in result.modified_content
        assert "x = 1" in result.modified_content
