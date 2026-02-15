"""Fixer registry contract test.

Adapted from template_registry_contract.py for code-rescue-tool.

Ensures all concrete Fixer classes are discoverable and properly registered.
"""

from __future__ import annotations

import inspect
import pkgutil
from types import ModuleType
from typing import Iterable

import code_rescue.fixers as fixers_pkg
from code_rescue.fixers.base import AbstractFixer


def _iter_fixer_modules() -> Iterable[ModuleType]:
    """Import all modules under code_rescue.fixers.

    Deterministic order: sorted by module name.
    """
    infos = sorted(pkgutil.iter_modules(fixers_pkg.__path__), key=lambda m: m.name)
    for info in infos:
        yield __import__(f"{fixers_pkg.__name__}.{info.name}", fromlist=["_"])


def _is_concrete_fixer_class(cls: type, module: ModuleType) -> bool:
    """Check if cls is a concrete Fixer defined in module.

    Convention:
      - Defined in that module (not imported from elsewhere)
      - Subclass of AbstractFixer
      - Not abstract itself
      - Has required interface (supported_rules property)
    """
    if cls.__module__ != module.__name__:
        return False

    if not issubclass(cls, AbstractFixer):
        return False

    if inspect.isabstract(cls):
        return False

    # Must have supported_rules
    if not hasattr(cls, "supported_rules"):
        return False

    return True


def _discover_fixers() -> set[type]:
    """Discover all concrete Fixer classes under code_rescue.fixers."""
    found: set[type] = set()
    for module in _iter_fixer_modules():
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is AbstractFixer:
                continue
            try:
                if _is_concrete_fixer_class(obj, module):
                    found.add(obj)
            except TypeError:
                # issubclass fails for non-class objects
                continue
    return found


def test_all_fixers_are_discoverable() -> None:
    """Contract: All concrete Fixer classes can be discovered via pkgutil."""
    discovered = _discover_fixers()
    assert len(discovered) >= 1, (
        "Expected at least 1 concrete Fixer class, found none.\n"
        "Check that fixers are defined in code_rescue.fixers submodules."
    )


def test_all_fixers_have_supported_rules() -> None:
    """Contract: Every Fixer declares which rules it can handle."""
    discovered = _discover_fixers()
    for fixer_cls in discovered:
        instance = fixer_cls()
        rules = instance.supported_rules
        assert isinstance(rules, list), (
            f"{fixer_cls.__name__}.supported_rules must return a list, "
            f"got {type(rules).__name__}"
        )
        assert len(rules) >= 1, (
            f"{fixer_cls.__name__}.supported_rules is empty. "
            f"Every fixer must support at least one rule."
        )


def test_no_duplicate_rule_coverage() -> None:
    """Contract: Each rule_id is handled by at most one fixer (no conflicts)."""
    discovered = _discover_fixers()
    rule_to_fixer: dict[str, type] = {}
    conflicts: list[str] = []

    for fixer_cls in discovered:
        instance = fixer_cls()
        for rule_id in instance.supported_rules:
            if rule_id in rule_to_fixer:
                conflicts.append(
                    f"Rule {rule_id} claimed by both "
                    f"{rule_to_fixer[rule_id].__name__} and {fixer_cls.__name__}"
                )
            else:
                rule_to_fixer[rule_id] = fixer_cls

    assert not conflicts, (
        "Multiple fixers claim the same rule_id:\n" + "\n".join(conflicts)
    )


def test_fixer_names_follow_convention() -> None:
    """Contract: Fixer class names end with 'Fixer'."""
    discovered = _discover_fixers()
    bad_names = [
        cls.__name__ for cls in discovered if not cls.__name__.endswith("Fixer")
    ]
    assert not bad_names, (
        f"Fixer classes should end with 'Fixer': {bad_names}"
    )
