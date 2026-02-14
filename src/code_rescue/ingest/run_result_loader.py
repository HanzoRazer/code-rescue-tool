"""Load and validate run_result_v1 JSON from code-analysis-tool.

This module consumes the output of code-analysis-tool and converts it
into typed dataclasses for use by the rescue planner and fixers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Location:
    """Source code location."""

    path: str
    line_start: int
    line_end: int


@dataclass(frozen=True, slots=True)
class Finding:
    """A single finding from code-analysis-tool."""

    finding_id: str
    type: str
    severity: str
    message: str
    location: Location
    confidence: float
    snippet: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def rule_id(self) -> str | None:
        """Extract rule_id from metadata if present."""
        return self.metadata.get("rule_id")


@dataclass(frozen=True, slots=True)
class Signal:
    """A signal (aggregated findings) from code-analysis-tool."""

    signal_id: str
    type: str
    risk_level: str
    urgency: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunMetadata:
    """Metadata about the analysis run."""

    run_id: str
    signal_logic_version: str
    engine_version: str
    tool_version: str


@dataclass(slots=True)
class RunResult:
    """Parsed run_result_v1 from code-analysis-tool."""

    schema_version: str
    run: RunMetadata
    findings: list[Finding]
    signals: list[Signal]
    summary: dict[str, Any]

    def findings_by_rule(self, rule_id: str) -> list[Finding]:
        """Get all findings with a specific rule_id."""
        return [f for f in self.findings if f.rule_id == rule_id]

    def findings_by_type(self, finding_type: str) -> list[Finding]:
        """Get all findings of a specific type."""
        return [f for f in self.findings if f.type == finding_type]


def _parse_location(data: dict[str, Any]) -> Location:
    return Location(
        path=data.get("path", ""),
        line_start=data.get("line_start", 0),
        line_end=data.get("line_end", 0),
    )


def _parse_finding(data: dict[str, Any]) -> Finding:
    return Finding(
        finding_id=data.get("finding_id", ""),
        type=data.get("type", ""),
        severity=data.get("severity", "info"),
        message=data.get("message", ""),
        location=_parse_location(data.get("location", {})),
        confidence=data.get("confidence", 0.0),
        snippet=data.get("snippet"),
        metadata=data.get("metadata", {}),
    )


def _parse_signal(data: dict[str, Any]) -> Signal:
    return Signal(
        signal_id=data.get("signal_id", ""),
        type=data.get("type", ""),
        risk_level=data.get("risk_level", "green"),
        urgency=data.get("urgency", "optional"),
        evidence=data.get("evidence", {}),
    )


def _parse_run_metadata(data: dict[str, Any]) -> RunMetadata:
    return RunMetadata(
        run_id=data.get("run_id", ""),
        signal_logic_version=data.get("signal_logic_version", ""),
        engine_version=data.get("engine_version", ""),
        tool_version=data.get("tool_version", ""),
    )


def load_run_result(data: dict[str, Any]) -> RunResult | None:
    """Parse and validate a run_result_v1 JSON dict.

    Returns None if the data is not a valid run_result.
    """
    schema_version = data.get("schema_version")
    if schema_version != "run_result_v1":
        return None

    run_data = data.get("run", {})
    findings_raw = data.get("findings_raw", [])
    signals_snapshot = data.get("signals_snapshot", [])
    summary = data.get("summary", {})

    return RunResult(
        schema_version=schema_version,
        run=_parse_run_metadata(run_data),
        findings=[_parse_finding(f) for f in findings_raw],
        signals=[_parse_signal(s) for s in signals_snapshot],
        summary=summary,
    )
