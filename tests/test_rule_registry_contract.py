"""Rule registry contract tests.

Validates that:
- contracts/rule_registry.json is valid
- All fixer-supported rules are in the registry
- Rule IDs follow the naming convention
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from code_rescue.fixers.base import AbstractFixer

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"
RULE_REGISTRY_PATH = CONTRACTS_DIR / "rule_registry.json"

# Pattern: 2-4 uppercase letters, underscore, uppercase word, underscore, 3 digits
RULE_ID_PATTERN = re.compile(r"^[A-Z]{2,4}_[A-Z][A-Z0-9_]*_[0-9]{3}$")


def _load_registry() -> dict:
    """Load rule registry from contracts."""
    return json.loads(RULE_REGISTRY_PATH.read_text(encoding="utf-8"))


def _discover_fixer_supported_rules() -> set[str]:
    """Discover all rule_ids supported by fixers."""
    from code_rescue.fixers import MutableDefaultFixer

    fixers = [MutableDefaultFixer()]
    rules: set[str] = set()
    for fixer in fixers:
        rules.update(fixer.supported_rules)
    return rules


class TestRuleRegistryStructure:
    """Test rule_registry.json structure and format."""

    def test_registry_file_exists(self) -> None:
        """contracts/rule_registry.json must exist."""
        assert RULE_REGISTRY_PATH.exists(), (
            f"Rule registry not found: {RULE_REGISTRY_PATH}"
        )

    def test_registry_is_valid_json(self) -> None:
        """Registry must be valid JSON."""
        registry = _load_registry()
        assert isinstance(registry, dict)

    def test_registry_has_supported_rule_ids(self) -> None:
        """Registry must have supported_rule_ids array."""
        registry = _load_registry()
        assert "supported_rule_ids" in registry
        assert isinstance(registry["supported_rule_ids"], list)
        assert len(registry["supported_rule_ids"]) >= 1

    def test_rule_ids_follow_naming_convention(self) -> None:
        """All rule IDs must match pattern: PREFIX_NAME_NNN."""
        registry = _load_registry()
        bad_ids = []

        for rule_id in registry["supported_rule_ids"]:
            if not RULE_ID_PATTERN.match(rule_id):
                bad_ids.append(rule_id)

        assert not bad_ids, (
            f"Rule IDs don't match pattern {RULE_ID_PATTERN.pattern}:\n"
            + "\n".join(f"  - {rid}" for rid in bad_ids)
        )

    def test_rule_ids_are_unique(self) -> None:
        """All rule IDs must be unique."""
        registry = _load_registry()
        rule_ids = registry["supported_rule_ids"]
        duplicates = [rid for rid in rule_ids if rule_ids.count(rid) > 1]

        assert not duplicates, f"Duplicate rule IDs: {set(duplicates)}"

    def test_rule_ids_are_sorted(self) -> None:
        """Rule IDs should be sorted alphabetically."""
        registry = _load_registry()
        rule_ids = registry["supported_rule_ids"]
        sorted_ids = sorted(rule_ids)

        assert rule_ids == sorted_ids, (
            "Rule IDs are not sorted. Expected order:\n"
            + "\n".join(f"  {rid}" for rid in sorted_ids)
        )


class TestFixerRegistrySync:
    """Test that fixers are synced with rule registry."""

    def test_fixer_rules_in_registry(self) -> None:
        """All fixer-supported rules must be in the registry."""
        registry = _load_registry()
        registry_rules = set(registry["supported_rule_ids"])
        fixer_rules = _discover_fixer_supported_rules()

        missing = fixer_rules - registry_rules

        assert not missing, (
            "Fixer supports rules not in registry:\n"
            + "\n".join(f"  - {rid}" for rid in sorted(missing))
            + "\n\nAdd these to contracts/rule_registry.json"
        )

    def test_registry_rules_have_prefix_categories(self) -> None:
        """Registry should have rules from expected categories."""
        registry = _load_registry()
        rule_ids = registry["supported_rule_ids"]

        prefixes = {rid.split("_")[0] for rid in rule_ids}

        # code-analysis-tool emits these categories
        expected_prefixes = {"DC", "GST", "SEC"}
        found = prefixes & expected_prefixes

        assert found, (
            f"Expected rule prefixes from {expected_prefixes}, "
            f"found: {prefixes}"
        )
