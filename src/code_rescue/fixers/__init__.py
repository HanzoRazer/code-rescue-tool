"""Fixers module - rule-specific code transformations."""

from code_rescue.fixers.base import AbstractFixer, FixResult, FixStatus
from code_rescue.fixers.mutable_default import MutableDefaultFixer

__all__ = ["AbstractFixer", "FixResult", "FixStatus", "MutableDefaultFixer"]
