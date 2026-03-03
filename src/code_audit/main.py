"""code_audit.main — CLI entry point.

Run as:
    python -m code_audit scan --root .
    python -m code_audit scan --root . --disable-js-ts

Promotion (signals_v5): JS/TS scanning is default-on.
Use ``--disable-js-ts`` to restrict to Python-only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from code_audit.core.runner import run_scan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enable_js_ts_from_args(args: argparse.Namespace) -> bool:
    """Return True if JS/TS discovery should be enabled for this invocation."""
    # Default-on. Users can explicitly disable.
    return bool(getattr(args, "enable_js_ts", True))


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _add_js_ts_flags(parser: argparse.ArgumentParser) -> None:
    """Add the --enable-js-ts / --disable-js-ts mutually exclusive group."""
    g = parser.add_mutually_exclusive_group()
    g.add_argument(
        "--enable-js-ts",
        dest="enable_js_ts",
        action="store_true",
        default=True,
        help="Enable JS/TS scanning (default: on).",
    )
    g.add_argument(
        "--disable-js-ts",
        dest="enable_js_ts",
        action="store_false",
        help="Disable JS/TS scanning (Python-only).",
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="code_audit", description="Multi-language static analysis toolkit.")

    _add_js_ts_flags(p)

    sub = p.add_subparsers(dest="command")

    # -- scan subcommand ---------------------------------------------------
    scan_p = sub.add_parser("scan", help="Run a code audit scan.")
    scan_p.add_argument("--root", type=str, required=True, help="Root directory to scan.")
    scan_p.add_argument("--project-id", type=str, default="", help="Optional project identifier.")
    scan_p.add_argument("--out", type=str, default=None, help="Output directory for results.")
    _add_js_ts_flags(scan_p)

    return p


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _handle_scan(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory.", file=sys.stderr)
        return 1

    enable_js_ts = _enable_js_ts_from_args(args)
    result = run_scan(
        root=root,
        analyzers=[],
        project_id=getattr(args, "project_id", ""),
        enable_js_ts=enable_js_ts,
    )
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def cli_main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        return _handle_scan(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
