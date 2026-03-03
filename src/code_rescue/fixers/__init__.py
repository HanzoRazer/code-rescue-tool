"""Fixers module - rule-specific code transformations."""

from code_rescue.fixers.base import AbstractFixer, FixResult, FixStatus
from code_rescue.fixers.dead_code import DeadCodeFixer
from code_rescue.fixers.mutable_default import MutableDefaultFixer
from code_rescue.fixers.unused_class import UnusedClassFixer
from code_rescue.fixers.unused_function import UnusedFunctionFixer
from code_rescue.fixers.unused_import import UnusedImportFixer
from code_rescue.fixers.vue_component import VueComponentFixer
from code_rescue.fixers.vue_coupling import VueCouplingFixer

__all__ = [
    "AbstractFixer",
    "DeadCodeFixer",
    "FixResult",
    "FixStatus",
    "MutableDefaultFixer",
    "UnusedClassFixer",
    "UnusedFunctionFixer",
    "UnusedImportFixer",
    "VueComponentFixer",
    "VueCouplingFixer",
]
