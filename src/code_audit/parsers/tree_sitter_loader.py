"""code_audit.parsers.tree_sitter_loader

Low-level tree-sitter bootstrapping: grammar loading, parser creation,
and configuration management.  All tree-sitter integration funnels
through this module so callers never touch the C FFI directly.

Compatible with **tree-sitter ≥ 0.25** (pip grammar packages expose
a ``language()`` function returning a PyCapsule).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class TreeSitterUnavailable(ImportError):
    """Raised when tree-sitter or a required grammar is not installed."""


@dataclass(frozen=True)
class TreeSitterConfig:
    """Paths and settings for the tree-sitter runtime."""

    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "code_audit" / "treesitter")
    library_name: str = "languages.so"

    @classmethod
    def default(cls) -> TreeSitterConfig:
        return cls()


# ---------------------------------------------------------------------------
# Grammar / Language loading  (tree-sitter ≥ 0.25 — pip grammar packages)
# ---------------------------------------------------------------------------

_LANGUAGE_CACHE: dict[str, object] = {}

# Map from our canonical grammar name → (pip_module, function_name)
_GRAMMAR_MAP: dict[str, tuple[str, str]] = {
    "javascript": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx":        ("tree_sitter_typescript", "language_tsx"),
}


def load_language(name: str, cfg: Optional[TreeSitterConfig] = None) -> object:
    """Return a tree-sitter ``Language`` object for *name*.

    Supported names: ``javascript``, ``typescript``, ``tsx``.
    """
    if name in _LANGUAGE_CACHE:
        return _LANGUAGE_CACHE[name]

    try:
        from tree_sitter import Language  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise TreeSitterUnavailable(
            "tree-sitter is not installed. Install extras: pip install .[treesitter]"
        ) from exc

    grammar_info = _GRAMMAR_MAP.get(name)
    if grammar_info is None:
        raise TreeSitterUnavailable(
            f"Unsupported grammar: {name!r}. "
            f"Supported: {sorted(_GRAMMAR_MAP)}"
        )

    mod_name, fn_name = grammar_info
    try:
        import importlib
        mod = importlib.import_module(mod_name)
        capsule = getattr(mod, fn_name)()
    except (ImportError, AttributeError) as exc:
        raise TreeSitterUnavailable(
            f"Grammar package {mod_name!r} is not installed. "
            f"Install it: pip install {mod_name.replace('_', '-')}"
        ) from exc

    lang = Language(capsule)
    _LANGUAGE_CACHE[name] = lang
    return lang


# ---------------------------------------------------------------------------
# Parser factory
# ---------------------------------------------------------------------------

def make_parser(language: str, cfg: Optional[TreeSitterConfig] = None) -> object:
    """Create a tree-sitter ``Parser`` configured for *language*."""
    try:
        from tree_sitter import Parser  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise TreeSitterUnavailable(
            "tree-sitter is not installed. Install extras: pip install .[treesitter]"
        ) from exc

    lang_obj = load_language(language, cfg)
    parser = Parser(lang_obj)
    return parser
