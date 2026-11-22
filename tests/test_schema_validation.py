"""Schema validation contract tests.

Adapted from template_schema_validation.py for code-rescue-tool.

Validates that:
- Example payloads validate against schemas
- Invalid payloads are rejected
- Schema invariants hold
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


def _load_schema(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def run_result_schema():
    return _load_schema("run_result.schema.json")


@pytest.fixture
def valid_run_result():
    """Minimal valid run_result payload."""
    return {
        "schema_version": "run_result_v2",
        "run": {
            "run_id": "test-run-001",
            "created_at": "2026-01-01T00:00:00+00:00",
            "tool_version": "1.0.0",
            "engine_version": "1.0.0",
            "signal_logic_version": "v1",
            "copy_version": "v1",
        },
        "summary": {
            "vibe_tier": "green",
            "confidence_score": 85,
            "counts": {
                "findings_total": 1,
                "by_severity": {"low": 1},
                "by_type": {"dead_code": 1},
            },
        },
        "signals_snapshot": [
            {
                "signal_id": "sig-001",
                "type": "dead_code",
                "risk_level": "yellow",
                "urgency": "recommended",
                "evidence": {
                    "finding_ids": ["f-001"],
                    "summary": {"count": 1},
                },
            }
        ],
        "findings_raw": [
            {
                "finding_id": "f-001",
                "type": "dead_code",
                "severity": "low",
                "confidence": 0.9,
                "fingerprint": "abc123",
                "location": {
                    "path": "src/main.py",
                    "line_start": 10,
                    "line_end": 15,
                },
            }
        ],
        "scan_integrity": {
            "assessable": True,
            "files_scanned": 1,
            "analyzers_total": 1,
            "analyzers_ok": 1,
            "degraded": [],
            "reasons": [],
        },
    }


# ── positive tests: valid payloads ──────────────────────────────────


class TestRunResultSchema:
    """Tests for run_result.schema.json validation."""

    def test_valid_payload_passes(self, run_result_schema, valid_run_result):
        """Valid run_result should pass validation."""
        Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_schema_version_const(self, run_result_schema, valid_run_result):
        """The vendored schema pins schema_version to 'run_result_v2'."""
        assert run_result_schema["properties"]["schema_version"]["const"] == "run_result_v2"
        assert valid_run_result["schema_version"] == "run_result_v2"

    def test_vibe_tier_enum(self, run_result_schema, valid_run_result):
        """vibe_tier must be green, yellow, red, or inconclusive (v2)."""
        for tier in ["green", "yellow", "red", "inconclusive"]:
            valid_run_result["summary"]["vibe_tier"] = tier
            Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_confidence_score_range(self, run_result_schema, valid_run_result):
        """confidence_score must be 0-100."""
        for score in [0, 50, 100]:
            valid_run_result["summary"]["confidence_score"] = score
            Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_confidence_score_nullable(self, run_result_schema, valid_run_result):
        """v2: an inconclusive scan has no score."""
        valid_run_result["summary"]["vibe_tier"] = "inconclusive"
        valid_run_result["summary"]["confidence_score"] = None
        Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_scan_integrity_block_accepted(self, run_result_schema, valid_run_result):
        """v2: optional scan_integrity block validates."""
        valid_run_result["scan_integrity"] = {
            "assessable": False,
            "files_scanned": 0,
            "analyzers_total": 2,
            "analyzers_ok": 0,
            "degraded": [
                {"analyzer_id": "exceptions", "status": "failed", "is_critical": True}
            ],
            "reasons": ["no_files_scanned"],
        }
        Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_severity_enum(self, run_result_schema, valid_run_result):
        """severity must be info, low, medium, high, or critical."""
        for sev in ["info", "low", "medium", "high", "critical"]:
            valid_run_result["findings_raw"][0]["severity"] = sev
            Draft202012Validator(run_result_schema).validate(valid_run_result)


# ── negative tests: invalid payloads ────────────────────────────────


class TestNegativeCases:
    """Ensure schema rejects invalid payloads."""

    def test_rejects_missing_run(self, run_result_schema, valid_run_result):
        """Missing 'run' field should fail."""
        del valid_run_result["run"]
        with pytest.raises(ValidationError):
            Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_rejects_missing_summary(self, run_result_schema, valid_run_result):
        """Missing 'summary' field should fail."""
        del valid_run_result["summary"]
        with pytest.raises(ValidationError):
            Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_rejects_missing_scan_integrity(self, run_result_schema, valid_run_result):
        """v2 requires scan_integrity: no integrity-free GREEN."""
        del valid_run_result["scan_integrity"]
        with pytest.raises(ValidationError, match="scan_integrity"):
            Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_rejects_v1_schema_version(self, run_result_schema, valid_run_result):
        """The vendored schema is v2-only (the loader still accepts v1 input)."""
        valid_run_result["schema_version"] = "run_result_v1"
        with pytest.raises(ValidationError):
            Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_rejects_invalid_vibe_tier(self, run_result_schema, valid_run_result):
        """Invalid vibe_tier should fail."""
        valid_run_result["summary"]["vibe_tier"] = "purple"
        with pytest.raises(ValidationError):
            Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_rejects_confidence_out_of_range(self, run_result_schema, valid_run_result):
        """confidence_score > 100 should fail."""
        valid_run_result["summary"]["confidence_score"] = 150
        with pytest.raises(ValidationError):
            Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_rejects_invalid_severity(self, run_result_schema, valid_run_result):
        """Invalid severity should fail."""
        valid_run_result["findings_raw"][0]["severity"] = "extreme"
        with pytest.raises(ValidationError):
            Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_rejects_empty_run_id(self, run_result_schema, valid_run_result):
        """Empty run_id should fail (minLength: 1)."""
        valid_run_result["run"]["run_id"] = ""
        with pytest.raises(ValidationError):
            Draft202012Validator(run_result_schema).validate(valid_run_result)

    def test_rejects_negative_line_number(self, run_result_schema, valid_run_result):
        """Negative line numbers should fail."""
        valid_run_result["findings_raw"][0]["location"]["line_start"] = 0
        with pytest.raises(ValidationError):
            Draft202012Validator(run_result_schema).validate(valid_run_result)
