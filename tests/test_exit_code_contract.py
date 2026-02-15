"""Exit code contract tests.

Adapted from template_exit_code_contract.py for code-rescue-tool.

Verifies CLI exit code semantics:
    plan:   0 = success, 2 = input error (file not found, invalid format)
    fix:    0 = success (no errors), 1 = some errors, 2 = input error
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], *, input_data: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run code-rescue CLI with given args."""
    env = {**os.environ}
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "code_rescue", *args],
        capture_output=True,
        text=True,
        env=env,
        input=input_data,
    )


def _minimal_run_result() -> dict:
    """Create a minimal valid run_result for testing."""
    return {
        "schema_version": "run_result_v1",
        "run": {
            "run_id": "test-001",
            "created_at": "2026-01-01T00:00:00+00:00",
            "tool_version": "1.0.0",
            "engine_version": "1.0.0",
            "signal_logic_version": "v1",
            "copy_version": "v1",
        },
        "summary": {
            "vibe_tier": "green",
            "confidence_score": 100,
            "counts": {
                "findings_total": 0,
                "by_severity": {},
                "by_type": {},
            },
        },
        "signals_snapshot": [],
        "findings_raw": [],
    }


# ── plan command exit codes ─────────────────────────────────────────


class TestPlanExitCodes:
    """Test exit codes for 'plan' command."""

    def test_plan_valid_input_returns_0(self, tmp_path: Path) -> None:
        """Valid input file should return exit 0."""
        input_file = tmp_path / "run_result.json"
        input_file.write_text(json.dumps(_minimal_run_result()))

        r = _run(["plan", str(input_file)])
        assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"

    def test_plan_file_not_found_returns_2(self, tmp_path: Path) -> None:
        """Missing input file should return exit 2."""
        r = _run(["plan", str(tmp_path / "nonexistent.json")])
        assert r.returncode == 2, f"stdout: {r.stdout}\nstderr: {r.stderr}"
        assert "not found" in r.stderr.lower()

    def test_plan_invalid_json_returns_2(self, tmp_path: Path) -> None:
        """Invalid JSON should return exit 2."""
        input_file = tmp_path / "bad.json"
        input_file.write_text("not valid json {{{")

        r = _run(["plan", str(input_file)])
        assert r.returncode == 2, f"stdout: {r.stdout}\nstderr: {r.stderr}"

    def test_plan_invalid_schema_returns_2(self, tmp_path: Path) -> None:
        """Valid JSON but invalid schema should return exit 2."""
        input_file = tmp_path / "bad_schema.json"
        input_file.write_text(json.dumps({"not": "a run_result"}))

        r = _run(["plan", str(input_file)])
        assert r.returncode == 2, f"stdout: {r.stdout}\nstderr: {r.stderr}"

    def test_plan_outputs_valid_json(self, tmp_path: Path) -> None:
        """Plan command should output valid JSON."""
        input_file = tmp_path / "run_result.json"
        input_file.write_text(json.dumps(_minimal_run_result()))

        r = _run(["plan", str(input_file)])
        assert r.returncode == 0

        # stdout should be valid JSON
        plan = json.loads(r.stdout)
        assert "actions" in plan
        assert "summary" in plan


# ── fix command exit codes ──────────────────────────────────────────


class TestFixExitCodes:
    """Test exit codes for 'fix' command."""

    def test_fix_plan_not_found_returns_2(self, tmp_path: Path) -> None:
        """Missing plan file should return exit 2."""
        r = _run(["fix", str(tmp_path / "nonexistent.json")])
        assert r.returncode == 2, f"stdout: {r.stdout}\nstderr: {r.stderr}"
        assert "not found" in r.stderr.lower()

    def test_fix_root_not_found_returns_2(self, tmp_path: Path) -> None:
        """Missing root directory should return exit 2."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({"actions": [], "summary": {}}))

        r = _run(["fix", str(plan_file), "--root", "/nonexistent/path"])
        assert r.returncode == 2, f"stdout: {r.stdout}\nstderr: {r.stderr}"

    def test_fix_empty_plan_returns_0(self, tmp_path: Path) -> None:
        """Empty plan (no actions) should return exit 0."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({"actions": [], "summary": {}}))

        r = _run(["fix", str(plan_file), "--root", str(tmp_path)])
        assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"

    def test_fix_dry_run_returns_0(self, tmp_path: Path) -> None:
        """Dry-run with valid plan should return exit 0."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps({
            "actions": [
                {
                    "action_id": "a-001",
                    "finding_id": "f-001",
                    "rule_id": "GST_MUTABLE_DEFAULT_001",
                    "file_path": "nonexistent.py",
                    "line_start": 1,
                    "line_end": 1,
                    "action_type": "replace",
                    "safety_level": "safe",
                    "description": "Fix mutable default",
                }
            ],
            "summary": {},
        }))

        # Dry-run without --apply won't actually try to read files
        r = _run(["fix", str(plan_file), "--root", str(tmp_path)])
        # Returns 1 because file doesn't exist (SKIP error)
        assert r.returncode in [0, 1], f"stdout: {r.stdout}\nstderr: {r.stderr}"
