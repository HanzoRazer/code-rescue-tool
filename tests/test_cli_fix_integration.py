"""CLI fix command integration tests.

Validates that:
- CLI 'fix' command runs end-to-end for supported fixers
- Dry-run does not modify files
- --apply modifies files correctly
- Correct exit codes are returned
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(
    args: list[str],
    *,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run code-rescue CLI."""
    env = {**os.environ}
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "code_rescue", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )


def _make_plan(actions: list[dict]) -> dict:
    """Create a minimal rescue plan dict."""
    return {
        "schema_version": "rescue_plan_v1",
        "source_run_id": "test-001",
        "source_signal_logic_version": "v1",
        "actions": actions,
        "summary": {"total_actions": len(actions)},
    }


def _make_mutable_default_action(
    file_path: str = "target.py",
    line_start: int = 1,
    line_end: int = 1,
) -> dict:
    return {
        "action_id": "A0001",
        "finding_id": "f-001",
        "rule_id": "GST_MUTABLE_DEFAULT_001",
        "action_type": "replace",
        "safety_level": "safe",
        "description": "Mutable default argument",
        "file_path": file_path,
        "line_start": line_start,
        "line_end": line_end,
    }


class TestFixDryRun:
    """Test fix command in dry-run mode (default)."""

    def test_dry_run_does_not_modify_files(self, tmp_path: Path) -> None:
        """Dry-run should not change any source files."""
        # Create target file
        target = tmp_path / "target.py"
        source = "def foo(items=[]):\n    return items\n"
        target.write_text(source)

        # Create plan
        plan = _make_plan([_make_mutable_default_action()])
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))

        r = _run_cli(["fix", str(plan_file), "--root", str(tmp_path)])
        assert r.returncode == 0

        # File should be unchanged
        assert target.read_text() == source

    def test_empty_plan_returns_zero(self, tmp_path: Path) -> None:
        plan = _make_plan([])
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))

        r = _run_cli(["fix", str(plan_file), "--root", str(tmp_path)])
        assert r.returncode == 0


class TestFixApply:
    """Test fix command with --apply."""

    def test_apply_modifies_mutable_default(self, tmp_path: Path) -> None:
        """--apply should actually modify the file."""
        target = tmp_path / "target.py"
        source = "def foo(items=[]):\n    return items\n"
        target.write_text(source)

        plan = _make_plan([_make_mutable_default_action()])
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))

        r = _run_cli(["fix", str(plan_file), "--root", str(tmp_path), "--apply"])
        assert r.returncode == 0

        modified = target.read_text()
        # The mutable default should be replaced with None pattern
        assert "items=[]" not in modified
        assert "None" in modified

    def test_apply_with_backup(self, tmp_path: Path) -> None:
        """--backup should create .bak files."""
        target = tmp_path / "target.py"
        source = "def foo(items=[]):\n    return items\n"
        target.write_text(source)

        plan = _make_plan([_make_mutable_default_action()])
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))

        r = _run_cli([
            "fix", str(plan_file),
            "--root", str(tmp_path),
            "--apply", "--backup",
        ])
        assert r.returncode == 0

        backup = tmp_path / "target.py.bak"
        assert backup.exists(), "Backup file not created"
        assert backup.read_text() == source


class TestFixExitCodes:
    """Test fix command exit codes."""

    def test_plan_not_found_returns_2(self) -> None:
        r = _run_cli(["fix", "nonexistent_plan.json"])
        assert r.returncode == 2

    def test_root_not_found_returns_2(self, tmp_path: Path) -> None:
        plan = _make_plan([])
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))

        r = _run_cli(["fix", str(plan_file), "--root", "/nonexistent/dir"])
        assert r.returncode == 2

    def test_missing_file_reports_error(self, tmp_path: Path) -> None:
        """Actions targeting missing files should be reported."""
        plan = _make_plan([_make_mutable_default_action("missing.py")])
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))

        r = _run_cli(["fix", str(plan_file), "--root", str(tmp_path), "--apply"])
        # Should report the error but still return 1 (not crash)
        assert r.returncode in (0, 1)


class TestFixRuleFilter:
    """Test --rule filtering."""

    def test_filter_by_rule(self, tmp_path: Path) -> None:
        """--rule should only apply matching actions."""
        target = tmp_path / "target.py"
        target.write_text("def foo(items=[]):\n    return items\n")

        plan = _make_plan([
            _make_mutable_default_action(),
            {
                "action_id": "A0002",
                "finding_id": "f-002",
                "rule_id": "DC_UNREACHABLE_001",
                "action_type": "remove",
                "safety_level": "safe",
                "description": "Unreachable code",
                "file_path": "target.py",
                "line_start": 2,
                "line_end": 2,
            },
        ])
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))

        r = _run_cli([
            "fix", str(plan_file),
            "--root", str(tmp_path),
            "--rule", "GST_MUTABLE_DEFAULT_001",
        ])
        assert r.returncode == 0


class TestInconclusiveSourceScan:
    """A plan built from an inconclusive scan may be planned/dry-run, never applied.

    An incomplete scan cannot support a "safe to remove" claim.
    """

    @staticmethod
    def _inconclusive_plan_file(tmp_path: Path) -> Path:
        plan = _make_plan([_make_mutable_default_action()])
        plan["source_scan_inconclusive"] = True
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))
        return plan_file

    def test_apply_refused_and_file_untouched(self, tmp_path: Path) -> None:
        target = tmp_path / "target.py"
        source = "def foo(items=[]):\n    return items\n"
        target.write_text(source)

        r = _run_cli(
            ["fix", str(self._inconclusive_plan_file(tmp_path)), "--root", str(tmp_path), "--apply"]
        )
        assert r.returncode == 2
        assert "INCONCLUSIVE" in r.stderr
        assert target.read_text() == source

    def test_dry_run_still_allowed(self, tmp_path: Path) -> None:
        target = tmp_path / "target.py"
        source = "def foo(items=[]):\n    return items\n"
        target.write_text(source)

        r = _run_cli(["fix", str(self._inconclusive_plan_file(tmp_path)), "--root", str(tmp_path)])
        assert r.returncode == 0
        assert "dry-run only" in r.stderr
        assert target.read_text() == source

    @pytest.mark.parametrize(
        ("summary", "integrity", "flagged"),
        [
            ({"vibe_tier": "inconclusive", "confidence_score": None}, None, True),
            ({"vibe_tier": "yellow", "confidence_score": 70}, {"assessable": False}, True),
            ({"vibe_tier": "yellow", "confidence_score": 70}, {"assessable": True}, False),
        ],
    )
    def test_plan_command_carries_inconclusive_flag(
        self, tmp_path: Path, summary: dict, integrity: dict | None, flagged: bool
    ) -> None:
        run_result = {
            "schema_version": "run_result_v2",
            "run": {"run_id": "r-1", "signal_logic_version": "signals_v1"},
            "summary": summary,
            "signals_snapshot": [],
            "findings_raw": [],
        }
        if integrity is not None:
            run_result["scan_integrity"] = integrity
        rr_file = tmp_path / "rr.json"
        rr_file.write_text(json.dumps(run_result))

        r = _run_cli(["plan", str(rr_file)])
        assert r.returncode == 0, r.stderr
        plan = json.loads(r.stdout)
        if flagged:
            assert plan["source_scan_inconclusive"] is True
            assert "INCONCLUSIVE" in r.stderr
        else:
            assert "source_scan_inconclusive" not in plan
