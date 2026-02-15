"""CLI/API parity tests.

Adapted from template_cli_api_parity_*.py for code-rescue-tool.

Validates that:
- CLI 'plan' command produces identical output to programmatic API
- Both paths use the same underlying logic
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from code_rescue.ingest.run_result_loader import load_run_result
from code_rescue.planner.rescue_planner import create_rescue_plan

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(args: list[str], *, input_data: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run code-rescue CLI."""
    env = {**os.environ}
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "code_rescue", *args],
        capture_output=True,
        text=True,
        env=env,
        input=input_data,
    )


def _sample_run_result() -> dict:
    """Create a sample run_result with findings."""
    return {
        "schema_version": "run_result_v1",
        "run": {
            "run_id": "parity-test-001",
            "created_at": "2026-01-01T00:00:00+00:00",
            "tool_version": "1.0.0",
            "engine_version": "1.0.0",
            "signal_logic_version": "v1",
            "copy_version": "v1",
        },
        "summary": {
            "vibe_tier": "yellow",
            "confidence_score": 80,
            "counts": {
                "findings_total": 1,
                "by_severity": {"medium": 1},
                "by_type": {"global_state": 1},
            },
        },
        "signals_snapshot": [
            {
                "signal_id": "sig-001",
                "type": "mutable_default",
                "risk_level": "yellow",
                "urgency": "recommended",
                "evidence": {
                    "finding_ids": ["f-001"],
                    "summary": {"mutable_default_count": 1},
                },
            },
        ],
        "findings_raw": [
            {
                "finding_id": "f-001",
                "type": "GST_MUTABLE_DEFAULT_001",
                "severity": "medium",
                "confidence": 0.95,
                "fingerprint": "abc123",
                "message": "Mutable default argument",
                "location": {
                    "path": "src/module.py",
                    "line_start": 15,
                    "line_end": 15,
                },
            },
        ],
    }


def _normalize_plan(plan: dict) -> dict:
    """Normalize plan for comparison.

    Removes volatile fields and sorts for deterministic comparison.
    """
    normalized = json.loads(json.dumps(plan, sort_keys=True))

    # Sort actions deterministically
    actions = normalized.get("actions", [])
    actions.sort(key=lambda a: (
        a.get("file_path", ""),
        a.get("line_start", 0),
        a.get("rule_id", ""),
    ))

    # Normalize action_ids
    for i, action in enumerate(actions):
        action["action_id"] = f"normalized-{i:04d}"

    normalized["actions"] = actions
    return normalized


class TestPlanCommandParity:
    """Test that CLI 'plan' matches API output."""

    def test_cli_plan_matches_api(self, tmp_path: Path) -> None:
        """CLI 'plan' output should match programmatic API."""
        run_result_data = _sample_run_result()

        # Write input file
        input_file = tmp_path / "run_result.json"
        input_file.write_text(json.dumps(run_result_data))

        # Get CLI output
        r = _run_cli(["plan", str(input_file)])
        assert r.returncode == 0, f"CLI failed:\nstdout: {r.stdout}\nstderr: {r.stderr}"
        cli_plan = json.loads(r.stdout)

        # Get API output
        rr = load_run_result(run_result_data)
        api_plan = create_rescue_plan(rr).to_dict()

        # Normalize both for comparison
        cli_normalized = _normalize_plan(cli_plan)
        api_normalized = _normalize_plan(api_plan)

        assert cli_normalized == api_normalized, (
            "CLI 'plan' output differs from API.\n"
            "This indicates two different compute paths.\n\n"
            f"CLI actions: {len(cli_plan.get('actions', []))}\n"
            f"API actions: {len(api_plan.get('actions', []))}"
        )

    def test_cli_plan_deterministic(self, tmp_path: Path) -> None:
        """Running CLI 'plan' twice should produce identical output."""
        run_result_data = _sample_run_result()
        input_file = tmp_path / "run_result.json"
        input_file.write_text(json.dumps(run_result_data))

        # Run twice
        r1 = _run_cli(["plan", str(input_file)])
        r2 = _run_cli(["plan", str(input_file)])

        assert r1.returncode == 0
        assert r2.returncode == 0

        plan1 = _normalize_plan(json.loads(r1.stdout))
        plan2 = _normalize_plan(json.loads(r2.stdout))

        assert plan1 == plan2, "CLI 'plan' is not deterministic"

    def test_cli_plan_empty_findings(self, tmp_path: Path) -> None:
        """Empty findings should produce empty plan via both CLI and API."""
        run_result_data = {
            "schema_version": "run_result_v1",
            "run": {
                "run_id": "empty-test",
                "created_at": "2026-01-01T00:00:00+00:00",
                "tool_version": "1.0.0",
                "engine_version": "1.0.0",
                "signal_logic_version": "v1",
                "copy_version": "v1",
            },
            "summary": {
                "vibe_tier": "green",
                "confidence_score": 100,
                "counts": {"findings_total": 0, "by_severity": {}, "by_type": {}},
            },
            "signals_snapshot": [],
            "findings_raw": [],
        }

        input_file = tmp_path / "run_result.json"
        input_file.write_text(json.dumps(run_result_data))

        # CLI
        r = _run_cli(["plan", str(input_file)])
        assert r.returncode == 0
        cli_plan = json.loads(r.stdout)

        # API
        rr = load_run_result(run_result_data)
        api_plan = create_rescue_plan(rr).to_dict()

        assert len(cli_plan["actions"]) == 0
        assert len(api_plan["actions"]) == 0

    def test_cli_stdout_is_valid_json(self, tmp_path: Path) -> None:
        """CLI stdout must be valid, parseable JSON."""
        run_result_data = _sample_run_result()
        input_file = tmp_path / "run_result.json"
        input_file.write_text(json.dumps(run_result_data))

        r = _run_cli(["plan", str(input_file)])
        assert r.returncode == 0

        # Should not raise
        plan = json.loads(r.stdout)
        assert isinstance(plan, dict)
