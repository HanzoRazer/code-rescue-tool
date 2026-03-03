"""code_audit.parsers.tree_sitter_js

High-level helpers: parse a JS/TS file and run tree-sitter queries.
Query objects are compiled once and cached (LRU) to avoid the expensive
re-compilation per file that dominated profiling in large scans.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from code_audit.parsers.tree_sitter_loader import (
    TreeSitterConfig,
    TreeSitterUnavailable,
    load_language,
    make_parser,
)


@dataclass
class ParsedTree:
    language: str
    path: Path
    source_bytes: bytes
    tree: object


def parse_file(path: Path, *, language: str, cfg: Optional[TreeSitterConfig] = None) -> ParsedTree:
    """Parse a source file with Tree-sitter and return a ``ParsedTree``."""
    cfg = cfg or TreeSitterConfig.default()
    parser = make_parser(language, cfg)
    p = path.resolve()
    src = p.read_bytes()
    tree = parser.parse(src)  # type: ignore[attr-defined]
    return ParsedTree(language=language, path=p, source_bytes=src, tree=tree)


# ---------------------------------------------------------------------------
# Query compilation with LRU caching
# ---------------------------------------------------------------------------

def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@lru_cache(maxsize=64)
def _compile_query_cached(language: str, query_sha: str, query_text: str, lib_hint: str) -> object:
    """
    Cache compiled Query objects.

    Cache key includes:
     - language name
     - sha256(query_text)
     - lib_hint (path-ish) to avoid cross-library collisions
    """
    try:
        from tree_sitter import Query  # type: ignore
    except Exception as e:  # pragma: no cover
        raise TreeSitterUnavailable(
            "tree-sitter is not installed. Install extras: pip install .[treesitter]"
        ) from e

    # Compile against the governed Language object (not Parser.language).
    lang_obj = load_language(language)
    return Query(lang_obj, query_text)


def query(tree_obj: object, query_text: str, *, language: str, cfg: Optional[TreeSitterConfig] = None):
    """
    Run a Tree-sitter query against a parsed tree.

    Returns a list of capture tuples: ``(capture_name, node)``.

    tree-sitter ≥ 0.25 uses ``QueryCursor.matches()`` which returns
    ``[(pattern_idx, {name: [node, ...]})]``.  We flatten that into the
    legacy ``[(name, node)]`` format so downstream code is unchanged.
    """
    from tree_sitter import QueryCursor  # type: ignore

    cfg = cfg or TreeSitterConfig.default()
    # Use library path as a hint in the cache key (governed by manifest).
    lib_hint = str((cfg.cache_dir / cfg.library_name).resolve())
    q = _compile_query_cached(language, _sha256_text(query_text), query_text, lib_hint)

    cursor = QueryCursor(q)
    flat: list[tuple[str, object]] = []
    for _pattern_idx, captures_dict in cursor.matches(tree_obj.root_node):  # type: ignore[attr-defined]
        for cap_name, nodes in captures_dict.items():
            for node in nodes:
                flat.append((cap_name, node))
    return flat
