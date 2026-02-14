"""Tests for rescue plan generation."""

from __future__ import annotations

import pytest

from code_rescue.ingest.run_result_loader import load_run_result
from code_rescue.planner.rescue_planner import create_rescue_plan
from code_rescue.model.rescue_action import ActionType, SafetyLevel


SAMPLE_RUN_RESULT = {
    "schema_version": "run_result_v1",
    "run": {
        "run_id": "test-run-001",
        "signal_logic_version": "signals_v1",
        "engine_version": "engine_v1",
        "tool_version": "0.1.0",
    },
    "findings_raw": [
        {
            "finding_id": "F0000",
            "type": "dead_code",
            "severity": "high",
            "message": "Unreachable code after return",
            "location": {"path": "src/app.py", "line_start": 10, "line_end": 11},
            "confidence": 0.98,
            "metadata": {"rule_id": "DC_UNREACHABLE_001"},
        },
        {
            "finding_id": "F0001",
            "type": "dead_code",
            "severity": "high",
            "message": "if False block",
            "location": {"path": "src/app.py", "line_start": 20, "line_end": 23},
            "confidence": 0.95,
            "metadata": {"rule_id": "DC_IF_FALSE_001"},
        },
        {
            "finding_id": "F0002",
            "type": "global_state",
            "severity": "medium",
            "message": "Mutable default argument",
            "location": {"path": "src/utils.py", "line_start": 5, "line_end": 5},
            "confidence": 0.99,
            "metadata": {"rule_id": "GST_MUTABLE_DEFAULT_001"},
        },
    ],
    "signals_snapshot": [],
    "summary": {"confidence_score": 70},
}


def test_create_rescue_plan():
    """Test creating a rescue plan from findings."""
    run_result = load_run_result(SAMPLE_RUN_RESULT)
    assert run_result is not None

    plan = create_rescue_plan(run_result)

    assert plan.schema_version == "rescue_plan_v1"
    assert plan.source_run_id == "test-run-001"
    assert plan.source_signal_logic_version == "signals_v1"
    assert len(plan.actions) == 3


def test_plan_action_mapping():
    """Test that actions are mapped correctly to rules."""
    run_result = load_run_result(SAMPLE_RUN_RESULT)
    plan = create_rescue_plan(run_result)

    # Find actions by rule
    dc_unreachable = [a for a in plan.actions if a.rule_id == "DC_UNREACHABLE_001"]
    assert len(dc_unreachable) == 1
    assert dc_unreachable[0].action_type == ActionType.REMOVE
    assert dc_unreachable[0].safety_level == SafetyLevel.SAFE

    gst_mutable = [a for a in plan.actions if a.rule_id == "GST_MUTABLE_DEFAULT_001"]
    assert len(gst_mutable) == 1
    assert gst_mutable[0].action_type == ActionType.REPLACE
    assert gst_mutable[0].safety_level == SafetyLevel.SAFE


def test_plan_summary():
    """Test that plan summary is computed correctly."""
    run_result = load_run_result(SAMPLE_RUN_RESULT)
    plan = create_rescue_plan(run_result)

    assert plan.summary["total_actions"] == 3
    assert plan.summary["auto_fixable"] == 3  # All three are safe
    assert plan.summary["manual_review"] == 0


def test_plan_priority_ordering():
    """Test that actions are ordered by severity (high first)."""
    run_result = load_run_result(SAMPLE_RUN_RESULT)
    plan = create_rescue_plan(run_result)

    # High severity findings should come before medium
    severities = []
    for action in plan.actions:
        finding = next(
            f for f in run_result.findings if f.finding_id == action.finding_id
        )
        severities.append(finding.severity)

    # First two should be high, last should be medium
    assert severities[0] == "high"
    assert severities[1] == "high"
    assert severities[2] == "medium"


def test_plan_to_dict():
    """Test JSON serialization of rescue plan."""
    run_result = load_run_result(SAMPLE_RUN_RESULT)
    plan = create_rescue_plan(run_result)

    plan_dict = plan.to_dict()

    assert plan_dict["schema_version"] == "rescue_plan_v1"
    assert len(plan_dict["actions"]) == 3
    assert all(isinstance(a, dict) for a in plan_dict["actions"])
    assert "total_actions" in plan_dict["summary"]
