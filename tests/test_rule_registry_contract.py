"""Rule registry contract tests.

Validates that:
- contracts/rule_registry.json is valid
- Every rule code-rescue binds to is registered (vendored upstream
  registry or contracts/local_rule_registry.json)
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

# Patterns accepted:
#   Underscore convention: 2-4 uppercase letters, underscore, uppercase word, underscore, 3 digits
#   Hyphen convention:     VUE-WORD-NNN (Vue fixer rules)
RULE_ID_PATTERN = re.compile(
    r"^(?:[A-Z]{2,4}_[A-Z][A-Z0-9_]*_[0-9]{3}|[A-Z]{2,4}(?:-[A-Z][A-Z0-9]*)*-[0-9]{3})$"
)


def _load_registry() -> dict:
    """Load rule registry from contracts."""
    return json.loads(RULE_REGISTRY_PATH.read_text(encoding="utf-8"))


def _discover_fixer_supported_rules() -> set[str]:
    """Discover all rule_ids supported by fixers via pkgutil discovery."""
    import inspect
    import pkgutil
    from types import ModuleType

    import code_rescue.fixers as fixers_pkg
    from code_rescue.fixers.base import AbstractFixer

    rules: set[str] = set()
    infos = sorted(pkgutil.iter_modules(fixers_pkg.__path__), key=lambda m: m.name)
    for info in infos:
        mod = __import__(f"{fixers_pkg.__name__}.{info.name}", fromlist=["_"])
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                obj is not AbstractFixer
                and issubclass(obj, AbstractFixer)
                and not inspect.isabstract(obj)
                and obj.__module__ == mod.__name__
            ):
                instance = obj()
                rules.update(instance.supported_rules)
    return rules


LOCAL_REGISTRY_PATH = CONTRACTS_DIR / "local_rule_registry.json"


def _load_local_registry() -> dict:
    """Load code-rescue's own (non-vendored) rule registry."""
    return json.loads(LOCAL_REGISTRY_PATH.read_text(encoding="utf-8"))


def _registered_rule_ids() -> set[str]:
    """Upstream (vendored) registry plus local owned and pending IDs."""
    local = _load_local_registry()
    return (
        set(_load_registry()["supported_rule_ids"])
        | set(local["supported_rule_ids"])
        | set(local["pending_upstream"])
    )


def _referenced_rule_ids() -> set[str]:
    """Every rule_id code-rescue binds behavior to."""
    from code_rescue.ingest.skylos_loader import SKYLOS_RULE_MAP
    from code_rescue.model.rescue_action import RULE_ACTION_MAP

    return (
        _discover_fixer_supported_rules()
        | set(RULE_ACTION_MAP)
        | set(SKYLOS_RULE_MAP.values())
    )


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
    """Referential integrity: every rule code-rescue acts on must be registered.

    contracts/rule_registry.json is a byte-parity copy of upstream's registry
    (ci/check_upstream_contracts.py). Rules code-rescue originates, and rules
    upstream emits but has not registered yet, live in
    contracts/local_rule_registry.json -- never in the vendored file.
    """

    def test_fixer_rules_in_registry(self) -> None:
        """Every rule a fixer, the action map, or an ingester binds to is registered."""
        known = _registered_rule_ids()
        referenced = _referenced_rule_ids()
        missing = referenced - known

        assert not missing, (
            "code-rescue references rules registered nowhere:\n"
            + "\n".join(f"  - {rid}" for rid in sorted(missing))
            + "\n\nIf upstream emits it, add it to pending_upstream in "
            "contracts/local_rule_registry.json; if code-rescue originates it, "
            "add it to supported_rule_ids there."
        )

    def test_local_registry_does_not_shadow_upstream(self) -> None:
        """Local and pending IDs must not duplicate upstream's registry.

        This is the forcing function on pending_upstream: once upstream
        registers a rule, it must be removed from the local file.
        """
        upstream = set(_load_registry()["supported_rule_ids"])
        local = _load_local_registry()
        shadowed = (
            set(local["supported_rule_ids"]) | set(local["pending_upstream"])
        ) & upstream

        assert not shadowed, (
            "Upstream now registers these; remove them from "
            "contracts/local_rule_registry.json:\n"
            + "\n".join(f"  - {rid}" for rid in sorted(shadowed))
        )

    def test_local_registry_lists_are_disjoint_sorted_and_well_formed(self) -> None:
        local = _load_local_registry()
        assert local.get("schema_version") == "local_rule_registry_v1"
        own, pending = local["supported_rule_ids"], local["pending_upstream"]
        for name, ids in (("supported_rule_ids", own), ("pending_upstream", pending)):
            assert ids == sorted(set(ids)), f"{name} must be sorted and unique"
            bad = [rid for rid in ids if not RULE_ID_PATTERN.match(rid)]
            assert not bad, f"{name} has malformed IDs: {bad}"
        assert not set(own) & set(pending), "an ID cannot be both owned and pending"

    def test_no_separator_collisions(self) -> None:
        """No two known IDs may differ only by '-' vs '_' or case.

        Upstream emits both EXC-SWALLOW-001 (supported scanner) and
        EXC_SWALLOW_001 (deprecated path); binding to the wrong spelling
        silently disables a rule.
        """
        seen: dict[str, str] = {}
        collisions = []
        for rid in sorted(_registered_rule_ids() | _referenced_rule_ids()):
            key = rid.replace("-", "_").upper()
            if key in seen and seen[key] != rid:
                collisions.append((seen[key], rid))
            seen.setdefault(key, rid)
        assert not collisions, f"Separator/case collisions: {collisions}"

    def test_local_entries_are_referenced(self) -> None:
        """No dead entries: every local/pending ID is used by code-rescue."""
        local = _load_local_registry()
        listed = set(local["supported_rule_ids"]) | set(local["pending_upstream"])
        unused = listed - _referenced_rule_ids()
        assert not unused, f"Unreferenced local registry entries: {sorted(unused)}"

    def test_registry_rules_have_prefix_categories(self) -> None:
        """Registry should have rules from expected categories."""
        registry = _load_registry()
        rule_ids = registry["supported_rule_ids"]

        prefixes = {rid.split("_")[0].split("-")[0] for rid in rule_ids}

        # code-analysis-tool emits these categories, plus VUE from rescue-tool
        expected_prefixes = {"DC", "EXC", "GST", "SEC", "VUE"}
        found = prefixes & expected_prefixes

        assert found, (
            f"Expected rule prefixes from {expected_prefixes}, "
            f"found: {prefixes}"
        )
