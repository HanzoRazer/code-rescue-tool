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


# ── run_result_v2 (code-analysis-tool 0.2.0, fail-closed scan integrity) ──

import copy  # noqa: E402

from code_rescue.ingest.run_result_loader import SUPPORTED_SCHEMA_VERSIONS  # noqa: E402


def _v2(**summary_overrides):
    data = copy.deepcopy(SAMPLE_RUN_RESULT)
    data["schema_version"] = "run_result_v2"
    data["summary"].update(summary_overrides)
    return data


def test_supported_versions_are_v1_and_v2():
    assert SUPPORTED_SCHEMA_VERSIONS == {"run_result_v1", "run_result_v2"}


def test_v1_still_loads_without_integrity():
    result = load_run_result(SAMPLE_RUN_RESULT)
    assert result is not None
    assert result.scan_integrity is None
    assert result.confidence_score == 65
    assert result.is_inconclusive is False


def test_v2_loads_with_scan_integrity():
    data = _v2()
    data["scan_integrity"] = {
        "assessable": True,
        "files_scanned": 3,
        "analyzers_total": 2,
        "analyzers_ok": 2,
        "degraded": [],
        "reasons": [],
    }
    result = load_run_result(data)
    assert result is not None
    assert result.schema_version == "run_result_v2"
    assert result.scan_integrity["files_scanned"] == 3
    assert result.is_inconclusive is False
    assert len(result.findings) == len(SAMPLE_RUN_RESULT["findings_raw"])


def test_v2_inconclusive_has_null_score_and_keeps_findings():
    data = _v2(vibe_tier="inconclusive", confidence_score=None)
    result = load_run_result(data)
    assert result is not None
    assert result.is_inconclusive is True
    assert result.confidence_score is None
    assert result.findings, "partial findings from an inconclusive scan are still real"


def test_v2_not_assessable_integrity_marks_inconclusive():
    data = _v2()
    data["scan_integrity"] = {"assessable": False}
    result = load_run_result(data)
    assert result is not None
    assert result.is_inconclusive is True


def test_unknown_schema_version_rejected():
    """Upstream bumps schema_version only for breaking changes."""
    assert load_run_result(_v2() | {"schema_version": "run_result_v3"}) is None
    assert load_run_result(["not", "a", "dict"]) is None  # type: ignore[arg-type]


def test_forward_tolerant_within_supported_version():
    """Unknown fields/enum values pass through; null containers parse as empty."""
    data = _v2(vibe_tier="ultraviolet", confidence_score=None, future_field={"x": 1})
    data["brand_new_top_level"] = [1, 2, 3]
    data["signals_snapshot"] = None
    data["findings_raw"][0]["location"] = None
    data["findings_raw"][0]["metadata"] = None
    data["findings_raw"][0]["severity"] = "catastrophic"
    data["run"] = None
    result = load_run_result(data)
    assert result is not None
    assert result.vibe_tier == "ultraviolet"
    assert result.signals == []
    assert result.findings[0].location.path == ""
    assert result.findings[0].metadata == {}
    assert result.findings[0].severity == "catastrophic"
    assert result.run.run_id == ""


def test_bool_score_is_not_a_score():
    assert load_run_result(_v2(confidence_score=True)).confidence_score is None
