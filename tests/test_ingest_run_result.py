"""Tests for run_result ingestion from code-analysis-tool."""

from __future__ import annotations

import pytest

from code_rescue.ingest.run_result_loader import load_run_result, RunResult


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
            "message": "2 statement(s) after 'return' will never execute",
            "location": {
                "path": "src/app.py",
                "line_start": 10,
                "line_end": 11,
            },
            "confidence": 0.98,
            "snippet": "# unreachable code",
            "metadata": {
                "rule_id": "DC_UNREACHABLE_001",
                "terminator": "return",
            },
        },
        {
            "finding_id": "F0001",
            "type": "security",
            "severity": "critical",
            "message": "Hardcoded secret detected",
            "location": {
                "path": "src/config.py",
                "line_start": 5,
                "line_end": 5,
            },
            "confidence": 0.95,
            "snippet": "API_KEY = 'sk-...'",
            "metadata": {
                "rule_id": "SEC_HARDCODED_SECRET_001",
            },
        },
    ],
    "signals_snapshot": [
        {
            "signal_id": "S0000",
            "type": "dead_code",
            "risk_level": "red",
            "urgency": "important",
            "evidence": {
                "finding_ids": ["F0000"],
            },
        },
    ],
    "summary": {
        "confidence_score": 65,
        "vibe_tier": "yellow",
    },
}


def test_load_run_result_valid():
    """Test loading a valid run_result_v1."""
    result = load_run_result(SAMPLE_RUN_RESULT)

    assert result is not None
    assert isinstance(result, RunResult)
    assert result.schema_version == "run_result_v1"
    assert result.run.run_id == "test-run-001"
    assert result.run.signal_logic_version == "signals_v1"


def test_load_run_result_findings():
    """Test that findings are parsed correctly."""
    result = load_run_result(SAMPLE_RUN_RESULT)

    assert result is not None
    assert len(result.findings) == 2

    # Check first finding
    f0 = result.findings[0]
    assert f0.finding_id == "F0000"
    assert f0.type == "dead_code"
    assert f0.severity == "high"
    assert f0.rule_id == "DC_UNREACHABLE_001"
    assert f0.location.path == "src/app.py"
    assert f0.location.line_start == 10


def test_load_run_result_signals():
    """Test that signals are parsed correctly."""
    result = load_run_result(SAMPLE_RUN_RESULT)

    assert result is not None
    assert len(result.signals) == 1

    s0 = result.signals[0]
    assert s0.signal_id == "S0000"
    assert s0.risk_level == "red"
    assert s0.urgency == "important"


def test_load_run_result_invalid_schema():
    """Test that invalid schema version returns None."""
    invalid = {"schema_version": "unknown_v99"}
    result = load_run_result(invalid)

    assert result is None


def test_findings_by_rule():
    """Test filtering findings by rule_id."""
    result = load_run_result(SAMPLE_RUN_RESULT)

    assert result is not None
    dc_findings = result.findings_by_rule("DC_UNREACHABLE_001")
    assert len(dc_findings) == 1
    assert dc_findings[0].finding_id == "F0000"


def test_findings_by_type():
    """Test filtering findings by type."""
    result = load_run_result(SAMPLE_RUN_RESULT)

    assert result is not None
    security_findings = result.findings_by_type("security")
    assert len(security_findings) == 1
    assert security_findings[0].rule_id == "SEC_HARDCODED_SECRET_001"
