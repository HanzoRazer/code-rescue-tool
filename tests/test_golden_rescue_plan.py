"""Golden rescue plan tests.

Adapted from template_golden_fixtures.py for code-rescue-tool.

Validates that:
- Rescue plan generation is deterministic
- Plans can be regenerated identically from same input
- Plan structure matches expected schema
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code_rescue.ingest.run_result_loader import load_run_result
from code_rescue.planner.rescue_planner import create_rescue_plan


def _sample_run_result_with_findings() -> dict:
    """Create a run_result with findings that generate actions."""
    return {
        "schema_version": "run_result_v1",
        "run": {
            "run_id": "golden-test-001",
            "created_at": "2026-01-01T00:00:00+00:00",
            "tool_version": "1.0.0",
            "engine_version": "1.0.0",
            "signal_logic_version": "v1",
            "copy_version": "v1",
        },
        "summary": {
            "vibe_tier": "yellow",
            "confidence_score": 75,
            "counts": {
                "findings_total": 2,
                "by_severity": {"medium": 1, "low": 1},
                "by_type": {"global_state": 2},
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
            {
                "signal_id": "sig-002",
                "type": "global_state",
                "risk_level": "yellow",
                "urgency": "optional",
                "evidence": {
                    "finding_ids": ["f-002"],
                    "summary": {"global_keyword_count": 1},
                },
            },
        ],
        "findings_raw": [
            {
                "finding_id": "f-001",
                "type": "GST_MUTABLE_DEFAULT_001",
                "severity": "medium",
                "confidence": 0.95,
                "fingerprint": "md5-abc123",
                "message": "Mutable default argument",
                "location": {
                    "path": "src/utils.py",
                    "line_start": 10,
                    "line_end": 10,
                },
                "metadata": {
                    "param_name": "items",
                    "default_value": "[]",
                },
            },
            {
                "finding_id": "f-002",
                "type": "GST_GLOBAL_KEYWORD_001",
                "severity": "low",
                "confidence": 0.90,
                "fingerprint": "md5-def456",
                "message": "Global keyword usage",
                "location": {
                    "path": "src/config.py",
                    "line_start": 25,
                    "line_end": 25,
                },
            },
        ],
    }


def _normalize_plan(plan: dict) -> dict:
    """Normalize plan for deterministic comparison.

    Removes or normalizes volatile fields while preserving semantics.
    """
    normalized = json.loads(json.dumps(plan, sort_keys=True))

    # Sort actions by (file_path, line_start, rule_id) for stable order
    actions = normalized.get("actions", [])
    actions.sort(key=lambda a: (
        a.get("file_path", ""),
        a.get("line_start", 0),
        a.get("rule_id", ""),
    ))

    # Reassign action_ids to be deterministic
    for i, action in enumerate(actions):
        action["action_id"] = f"action-{i:04d}"

    normalized["actions"] = actions
    return normalized


class TestRescuePlanDeterminism:
    """Test that rescue plan generation is deterministic."""

    def test_same_input_produces_same_plan(self) -> None:
        """Running planner twice on same input should produce identical plans."""
        run_result_data = _sample_run_result_with_findings()

        # First run
        rr1 = load_run_result(run_result_data)
        plan1 = create_rescue_plan(rr1)

        # Second run
        rr2 = load_run_result(run_result_data)
        plan2 = create_rescue_plan(rr2)

        # Normalize and compare
        norm1 = _normalize_plan(plan1.to_dict())
        norm2 = _normalize_plan(plan2.to_dict())

        assert norm1 == norm2, (
            "Rescue plan generation is not deterministic.\n"
            "Same input should always produce identical output."
        )

    def test_plan_has_required_structure(self) -> None:
        """Plan must have actions and summary."""
        run_result_data = _sample_run_result_with_findings()
        rr = load_run_result(run_result_data)
        plan = create_rescue_plan(rr)
        plan_dict = plan.to_dict()

        assert "actions" in plan_dict
        assert "summary" in plan_dict
        assert isinstance(plan_dict["actions"], list)
        assert isinstance(plan_dict["summary"], dict)

    def test_plan_actions_have_required_fields(self) -> None:
        """Each action must have required fields."""
        run_result_data = _sample_run_result_with_findings()
        rr = load_run_result(run_result_data)
        plan = create_rescue_plan(rr)
        plan_dict = plan.to_dict()

        required_fields = {
            "action_id",
            "finding_id",
            "rule_id",
            "file_path",
            "line_start",
            "line_end",
            "action_type",
            "safety_level",
            "description",
        }

        for action in plan_dict["actions"]:
            missing = required_fields - set(action.keys())
            assert not missing, f"Action missing fields: {missing}"

    def test_plan_safety_levels_valid(self) -> None:
        """All actions must have valid safety levels."""
        run_result_data = _sample_run_result_with_findings()
        rr = load_run_result(run_result_data)
        plan = create_rescue_plan(rr)
        plan_dict = plan.to_dict()

        valid_levels = {"safe", "review", "manual"}

        for action in plan_dict["actions"]:
            assert action["safety_level"] in valid_levels, (
                f"Invalid safety_level: {action['safety_level']}"
            )

    def test_empty_findings_produces_empty_plan(self) -> None:
        """Run result with no findings should produce empty plan."""
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

        rr = load_run_result(run_result_data)
        plan = create_rescue_plan(rr)
        plan_dict = plan.to_dict()

        assert len(plan_dict["actions"]) == 0
