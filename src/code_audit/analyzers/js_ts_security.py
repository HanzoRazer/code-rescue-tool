"""code_audit.analyzers.js_ts_security

JS/TS security preview analyzer.  Uses tree-sitter queries defined in
``data/treesitter/queries/js_ts_security.scm`` to detect:

  SEC_EVAL_JS_001              — eval(...)
  SEC_NEW_FUNCTION_JS_001      — new Function(...)
  EXC_EMPTY_CATCH_JS_001       — empty catch block
  GST_GLOBAL_THIS_MUTATION_001 — globalThis/window property mutation
  SEC_DYNAMIC_MODULE_LOAD_JS_001 — require/import with non-literal arg

Performance note (signals_v5):
  Captures are grouped in a single O(n) pass into ``by_name`` so each
  rule check is a dict lookup rather than a full-list rescan.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from code_audit.contracts.rules import rule_logic_version, Protocol


# ---------------------------------------------------------------------------
# Protocols / lightweight types used by the analyzer
# ---------------------------------------------------------------------------

class FindingSink(Protocol):
    """Minimal interface for collecting findings."""

    def add(self, finding: dict[str, Any]) -> None: ...  # pragma: no cover


@dataclass
class SourceFile:
    path: Path
    language: str  # "js" | "ts"


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------

def node_text(source_bytes: bytes, node: object) -> str:
    """Extract UTF-8 text from a tree-sitter node."""
    start = getattr(node, "start_byte", 0)
    end = getattr(node, "end_byte", 0)
    return source_bytes[start:end].decode("utf-8", errors="replace")


def node_start_line_col(source_bytes: bytes, node: object) -> tuple[int, int]:
    """Return (line, col) — both 1-indexed."""
    sp = getattr(node, "start_point", (0, 0))
    return (sp[0] + 1, sp[1] + 1)


def _first_arg_node(args_node: object) -> Optional[object]:
    """Return the first named child of an arguments node, or None."""
    children = getattr(args_node, "named_children", [])
    return children[0] if children else None


def _is_literal_module_spec(node: Optional[object]) -> bool:
    """True when *node* is a string literal (safe static module specifier)."""
    if node is None:
        return False
    node_type = getattr(node, "type", "")
    return node_type in ("string", "template_string")


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

_QUERY_PATH = Path(__file__).resolve().parent.parent / "data" / "treesitter" / "queries" / "js_ts_security.scm"


class JsTsSecurityPreviewAnalyzer:
    """JS/TS security preview analyzer (tree-sitter backed)."""

    name = "js_ts_security_preview"
    version = "0.2.0"

    def __init__(self) -> None:
        self._query_text: Optional[str] = None

    def _load_query(self) -> str:
        if self._query_text is None:
            self._query_text = _QUERY_PATH.read_text(encoding="utf-8")
        return self._query_text

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def analyze_multilang(self, files_by_lang: dict[str, list[SourceFile]], sink: FindingSink) -> None:
        from code_audit.parsers.tree_sitter_js import parse_file as ts_parse, query as ts_query

        query_text = self._load_query()

        for lang_key in ("js", "ts"):
            files = files_by_lang.get(lang_key, [])
            # Compile query once per run (tree-sitter compile is expensive).
            # query() also caches, but we avoid re-reading/rehashing per file here.
            for sf in files:
                if sf.language == "js":
                    lang = "javascript"
                else:
                    # Treat ts + tsx as "typescript" grammar for now.
                    lang = "typescript"

                try:
                    parsed = ts_parse(sf.path, language=lang)
                except Exception:
                    continue

                try:
                    caps = ts_query(parsed.tree, query_text, language=lang)
                except Exception:
                    continue

                # Single-pass grouping of captures for O(n) rule checks.
                by_name: dict[str, list[object]] = {}
                for cap_name, node in caps:
                    by_name.setdefault(cap_name, []).append(node)

                # ----------------------------------------------------------
                # SEC_EVAL_JS_001 — eval(...)
                # ----------------------------------------------------------
                for node in by_name.get("sec_eval.callee", []):
                    if node_text(parsed.source_bytes, node) != "eval":
                        continue
                    line, col = node_start_line_col(parsed.source_bytes, node)
                    sink.add(
                        {
                            "rule_id": "SEC_EVAL_JS_001",
                            "path": str(parsed.path),
                            "message": "Use of eval(...) detected (JS/TS).",
                            "location": {"line": line, "col": col},
                            "evidence": {"callee": "eval"},
                            "rule_logic_version": rule_logic_version("SEC_EVAL_JS_001"),
                        }
                    )

                # ----------------------------------------------------------
                # SEC_NEW_FUNCTION_JS_001 — new Function(...)
                # ----------------------------------------------------------
                for node in by_name.get("sec_new_function.ctor", []):
                    if node_text(parsed.source_bytes, node) != "Function":
                        continue
                    line, col = node_start_line_col(parsed.source_bytes, node)
                    sink.add(
                        {
                            "rule_id": "SEC_NEW_FUNCTION_JS_001",
                            "path": str(parsed.path),
                            "message": "Use of new Function(...) detected (JS/TS).",
                            "location": {"line": line, "col": col},
                            "evidence": {"callee": "Function"},
                            "rule_logic_version": rule_logic_version("SEC_NEW_FUNCTION_JS_001"),
                        }
                    )

                # ----------------------------------------------------------
                # EXC_EMPTY_CATCH_JS_001 — empty catch block
                # ----------------------------------------------------------
                for node in by_name.get("exc_empty_catch.body", []):
                    # Empty block = no named children inside
                    children = getattr(node, "named_children", [])
                    if children:
                        continue
                    line, col = node_start_line_col(parsed.source_bytes, node)
                    sink.add(
                        {
                            "rule_id": "EXC_EMPTY_CATCH_JS_001",
                            "path": str(parsed.path),
                            "message": "Empty catch block detected (JS/TS).",
                            "location": {"line": line, "col": col},
                            "evidence": {},
                            "rule_logic_version": rule_logic_version("EXC_EMPTY_CATCH_JS_001"),
                        }
                    )

                # ----------------------------------------------------------
                # GST_GLOBAL_THIS_MUTATION_001 — globalThis/window mutation
                # ----------------------------------------------------------
                for node in by_name.get("gst_global_mutation.obj", []):
                    obj_name = node_text(parsed.source_bytes, node)
                    if obj_name not in ("globalThis", "window"):
                        continue
                    line, col = node_start_line_col(parsed.source_bytes, node)
                    sink.add(
                        {
                            "rule_id": "GST_GLOBAL_THIS_MUTATION_001",
                            "path": str(parsed.path),
                            "message": f"Mutation of {obj_name} properties detected (JS/TS).",
                            "location": {"line": line, "col": col},
                            "evidence": {"object": obj_name},
                            "rule_logic_version": rule_logic_version("GST_GLOBAL_THIS_MUTATION_001"),
                        }
                    )

                # ----------------------------------------------------------
                # SEC_DYNAMIC_MODULE_LOAD_JS_001 — require/import(<non-lit>)
                # ----------------------------------------------------------
                dyn_fns = by_name.get("sec_dyn_load.fn", [])
                dyn_args = by_name.get("sec_dyn_load.args", [])

                # Conservative pairing: evaluate each args node independently; if any
                # fn is require/import in the file and there exists a non-literal args,
                # we emit on the callee position (best-effort).
                for fn_node in dyn_fns:
                    fn_name = node_text(parsed.source_bytes, fn_node)
                    if fn_name not in ("require", "import"):
                        continue
                    for args_node in dyn_args:
                        arg0 = _first_arg_node(args_node)
                        if _is_literal_module_spec(arg0):
                            continue
                        line, col = node_start_line_col(parsed.source_bytes, fn_node)
                        sink.add(
                            {
                                "rule_id": "SEC_DYNAMIC_MODULE_LOAD_JS_001",
                                "path": str(parsed.path),
                                "message": f"Dynamic module load detected via {fn_name}(<non-literal>) (JS/TS).",
                                "location": {"line": line, "col": col},
                                "evidence": {"callee": fn_name},
                                "rule_logic_version": rule_logic_version("SEC_DYNAMIC_MODULE_LOAD_JS_001"),
                            }
                        )
                        break
