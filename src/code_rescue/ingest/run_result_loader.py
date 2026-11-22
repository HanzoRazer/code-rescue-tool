"""Load run_result JSON (v1 or v2) from code-analysis-tool.

This module consumes the output of code-analysis-tool and converts it
into typed dataclasses for use by the rescue planner and fixers.

Compatibility policy:
- ``schema_version`` must be one of SUPPORTED_SCHEMA_VERSIONS. Upstream bumps
  it only for breaking changes, so an unknown version is rejected.
- Within a supported version the loader is forward-tolerant: unknown fields
  are ignored, unknown enum values (vibe tier, severity, risk level) are kept
  as raw strings, and missing or null containers parse as empty.
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


SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"run_result_v1", "run_result_v2"})


@dataclass(slots=True)
class RunResult:
    """Parsed run_result (v1 or v2) from code-analysis-tool."""

    schema_version: str
    run: RunMetadata
    findings: list[Finding]
    signals: list[Signal]
    summary: dict[str, Any]
    # v2 only: the producer's evidence about whether the scan could assess
    # the tree. None for v1 inputs (which carry no such evidence).
    scan_integrity: dict[str, Any] | None = None

    @property
    def vibe_tier(self) -> str | None:
        """Raw tier string; v2 adds "inconclusive", future values pass through."""
        tier = self.summary.get("vibe_tier")
        return tier if isinstance(tier, str) else None

    @property
    def confidence_score(self) -> int | None:
        """Score 0-100, or None when the producer could not score the scan (v2)."""
        score = self.summary.get("confidence_score")
        return score if isinstance(score, int) and not isinstance(score, bool) else None

    @property
    def is_inconclusive(self) -> bool:
        """True when the producer could not assess the tree, or did not prove it could.

        Findings are then partial: absence of a finding is not evidence of
        clean code, but the findings present are still real.

        A v2 result without scan_integrity is unverified (upstream makes the
        block required in v2, so only a malformed or truncated payload lacks
        it) and is treated as inconclusive. v1 predates integrity evidence
        and keeps its tier as-is.
        """
        if self.vibe_tier == "inconclusive":
            return True
        if self.scan_integrity is None:
            return self.schema_version != "run_result_v1"
        return self.scan_integrity.get("assessable") is not True

    def findings_by_rule(self, rule_id: str) -> list[Finding]:
        """Get all findings with a specific rule_id."""
        return [f for f in self.findings if f.rule_id == rule_id]

    def findings_by_type(self, finding_type: str) -> list[Finding]:
        """Get all findings of a specific type."""
        return [f for f in self.findings if f.type == finding_type]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _parse_location(data: dict[str, Any]) -> Location:
    data = _as_dict(data)
    return Location(
        path=data.get("path", ""),
        line_start=data.get("line_start", 0),
        line_end=data.get("line_end", 0),
    )


def _parse_finding(data: dict[str, Any]) -> Finding:
    data = _as_dict(data)
    return Finding(
        finding_id=data.get("finding_id", ""),
        type=data.get("type", ""),
        severity=data.get("severity", "info"),
        message=data.get("message", ""),
        location=_parse_location(data.get("location")),
        confidence=data.get("confidence", 0.0),
        snippet=data.get("snippet"),
        metadata=_as_dict(data.get("metadata")),
    )


def _parse_signal(data: dict[str, Any]) -> Signal:
    data = _as_dict(data)
    return Signal(
        signal_id=data.get("signal_id", ""),
        type=data.get("type", ""),
        risk_level=data.get("risk_level", "green"),
        urgency=data.get("urgency", "optional"),
        evidence=_as_dict(data.get("evidence")),
    )


def _parse_run_metadata(data: dict[str, Any]) -> RunMetadata:
    data = _as_dict(data)
    return RunMetadata(
        run_id=data.get("run_id", ""),
        signal_logic_version=data.get("signal_logic_version", ""),
        engine_version=data.get("engine_version", ""),
        tool_version=data.get("tool_version", ""),
    )


def load_run_result(data: dict[str, Any]) -> RunResult | None:
    """Parse a run_result dict (any of SUPPORTED_SCHEMA_VERSIONS).

    Returns None if the data is not a run_result of a supported version.
    """
    if not isinstance(data, dict):
        return None
    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        return None

    integrity = data.get("scan_integrity")

    return RunResult(
        schema_version=schema_version,
        run=_parse_run_metadata(data.get("run")),
        findings=[_parse_finding(f) for f in _as_list(data.get("findings_raw"))],
        signals=[_parse_signal(s) for s in _as_list(data.get("signals_snapshot"))],
        summary=_as_dict(data.get("summary")),
        scan_integrity=integrity if isinstance(integrity, dict) else None,
    )
