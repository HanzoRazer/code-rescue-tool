"""Rescue planner - creates prioritized rescue plans from findings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from code_rescue.ingest.run_result_loader import RunResult, Finding
from code_rescue.model.rescue_action import (
    RescueAction,
    ActionType,
    SafetyLevel,
    get_action_mapping,
)


# Severity priority (higher = more urgent)
SEVERITY_PRIORITY: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "info": 0,
}


@dataclass(slots=True)
class RescuePlan:
    """A prioritized plan of rescue actions."""

    schema_version: str = "rescue_plan_v1"
    source_run_id: str = ""
    source_signal_logic_version: str = ""
    actions: list[RescueAction] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "schema_version": self.schema_version,
            "source_run_id": self.source_run_id,
            "source_signal_logic_version": self.source_signal_logic_version,
            "actions": [a.to_dict() for a in self.actions],
            "summary": self.summary,
        }


def _finding_priority(finding: Finding) -> tuple[int, int, str, int]:
    """Sort key for findings: severity (desc), confidence (desc), path, line."""
    return (
        -SEVERITY_PRIORITY.get(finding.severity, 0),
        -int(finding.confidence * 100),
        finding.location.path,
        finding.location.line_start,
    )


def _create_action_from_finding(finding: Finding, action_num: int) -> RescueAction:
    """Create a rescue action from a finding."""
    rule_id = finding.rule_id or f"{finding.type.upper()}_UNKNOWN"
    action_type, safety_level = get_action_mapping(rule_id)

    return RescueAction(
        action_id=f"A{action_num:04d}",
        finding_id=finding.finding_id,
        rule_id=rule_id,
        action_type=action_type,
        safety_level=safety_level,
        description=finding.message,
        file_path=finding.location.path,
        line_start=finding.location.line_start,
        line_end=finding.location.line_end,
        original_code=finding.snippet,
        replacement_code=None,  # Filled in by fixers
        rationale=_generate_rationale(rule_id, action_type),
        metadata=finding.metadata,
    )


def _generate_rationale(rule_id: str, action_type: ActionType) -> str:
    """Generate human-readable rationale for the action."""
    rationales = {
        "DC_UNREACHABLE_001": "Code after return/raise/break/continue never executes.",
        "DC_IF_FALSE_001": "Code inside 'if False:' block never executes.",
        "DC_ASSERT_FALSE_001": "assert False always fails - may be intentional placeholder.",
        "GST_MUTABLE_DEFAULT_001": "Mutable default arguments are shared across calls.",
        "GST_MUTABLE_MODULE_001": "Module-level mutable state can cause unexpected behavior.",
        "GST_GLOBAL_KEYWORD_001": "Global keyword creates hidden dependencies.",
        "SEC_HARDCODED_SECRET_001": "Hardcoded secrets should be extracted to environment variables.",
        "SEC_EVAL_001": "eval() can execute arbitrary code - use ast.literal_eval() if possible.",
        "SEC_SUBPROCESS_SHELL_001": "shell=True is vulnerable to command injection.",
        "SEC_SQL_INJECTION_001": "String formatting in SQL is vulnerable to injection.",
        "SEC_PICKLE_LOAD_001": "pickle.load() can execute arbitrary code from untrusted data.",
        "SEC_YAML_UNSAFE_001": "yaml.load() without SafeLoader can execute arbitrary code.",
    }
    return rationales.get(rule_id, f"Rule {rule_id} triggered - review recommended.")


def create_rescue_plan(run_result: RunResult) -> RescuePlan:
    """Create a prioritized rescue plan from analysis results."""
    # Sort findings by priority
    sorted_findings = sorted(run_result.findings, key=_finding_priority)

    # Create actions
    actions = [
        _create_action_from_finding(f, i)
        for i, f in enumerate(sorted_findings)
    ]

    # Build summary
    by_safety = {level.value: 0 for level in SafetyLevel}
    by_type = {atype.value: 0 for atype in ActionType}
    by_rule: dict[str, int] = {}

    for action in actions:
        by_safety[action.safety_level.value] += 1
        by_type[action.action_type.value] += 1
        by_rule[action.rule_id] = by_rule.get(action.rule_id, 0) + 1

    summary = {
        "total_actions": len(actions),
        "by_safety_level": by_safety,
        "by_action_type": by_type,
        "by_rule_id": by_rule,
        "auto_fixable": by_safety.get("safe", 0) + by_safety.get("semi_auto", 0),
        "manual_review": by_safety.get("manual", 0),
    }

    return RescuePlan(
        source_run_id=run_result.run.run_id,
        source_signal_logic_version=run_result.run.signal_logic_version,
        actions=actions,
        summary=summary,
    )
