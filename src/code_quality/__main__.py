"""CLI entry-point for the Code Quality Analyzer Suite.

Usage
-----
    python -m code_quality /path/to/project [options]

All flags are wired to config overrides (FIX for P0 #1 — previously unwired args).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .analyzer import CodeQualityAnalyzer
from .output import emit_human, emit_json, emit_sarif, emit_html


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="code_quality",
        description="Code Quality Analyzer Suite v2.0 — static analysis for JS / Vue / React",
    )
    p.add_argument("path", type=Path, help="Root directory of the project to analyse")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose stderr output")

    # Output format (mutually exclusive)
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="fmt_json", action="store_true",
                     help="Machine-readable JSON output")
    fmt.add_argument("--sarif", dest="fmt_sarif", action="store_true",
                     help="SARIF 2.1.0 output (GitHub / VS Code compatible)")

    p.add_argument("--html", dest="html_path", type=Path, default=None,
                   metavar="FILE", help="Write an HTML report to FILE")

    # Filtering
    p.add_argument("--checks", nargs="*", default=[],
                   help="Run only these checkers (space-separated names)")
    p.add_argument("--exclude-checks", nargs="*", default=[],
                   help="Exclude these checkers")
    p.add_argument("--exclude-dirs", nargs="*", default=[],
                   help="Additional directories to exclude")

    # Thresholds — FIX: these are now actually wired to config
    p.add_argument("--threshold", type=int, default=None,
                   help="Nesting-depth threshold (default 5)")
    p.add_argument("--min-lines", type=int, default=None,
                   help="Min lines for recursive-function checker (default 400)")
    p.add_argument("--max-params", type=int, default=None,
                   help="Max params before flagging (default 4)")
    p.add_argument("--max-methods", type=int, default=None,
                   help="Max methods in a component (default 15)")
    p.add_argument("--max-file-size-kb", type=int, default=None,
                   help="Max file size in KB (default 100)")

    # Modes
    p.add_argument("--changed-only", action="store_true",
                   help="Only analyse files changed in git (git diff HEAD)")
    p.add_argument("--fix", action="store_true",
                   help="Auto-fix fixable issues in-place")
    p.add_argument("--baseline", type=Path, default=None,
                   metavar="FILE", help="JSON baseline — suppress known issues")
    p.add_argument("--workers", type=int, default=4,
                   help="Parallel worker threads (default 4)")

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not args.path.is_dir():
        print(f"Error: {args.path} is not a directory", file=sys.stderr)
        return 2

    # Build config overrides from CLI flags
    overrides: dict = {}
    if args.checks:
        overrides["checks"] = args.checks
    if args.exclude_checks:
        overrides["exclude_checks"] = args.exclude_checks
    if args.exclude_dirs:
        overrides["exclude_dirs"] = args.exclude_dirs
    for key in ("threshold", "min_lines", "max_params", "max_methods", "max_file_size_kb"):
        val = getattr(args, key.replace("-", "_"), None)
        if val is not None:
            overrides[key] = val

    analyzer = CodeQualityAnalyzer(
        args.path,
        config_overrides=overrides,
        baseline_path=args.baseline,
        changed_only=args.changed_only,
        fix=args.fix,
        workers=args.workers,
        verbose=args.verbose,
    )

    issues = analyzer.analyze()

    # Build the results envelope expected by output formatters
    critical = sum(1 for i in issues if i["severity"] == "critical")
    warning = sum(1 for i in issues if i["severity"] == "warning")
    info = sum(1 for i in issues if i["severity"] == "info")
    results = {
        "target_path": str(args.path.resolve()),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "summary": {
            "total_files": len({i["file"] for i in issues}),
            "total_issues": len(issues),
            "critical_issues": critical,
            "warning_issues": warning,
            "info_issues": info,
        },
        "issues": issues,
    }

    # Output
    if args.fmt_sarif:
        print(emit_sarif(results))
    elif args.fmt_json:
        print(emit_json(results))
    else:
        print(emit_human(results))

    if args.html_path:
        emit_html(results, args.html_path)
        if args.verbose:
            print(f"HTML report written to {args.html_path}", file=sys.stderr)

    # Exit code: 2 = critical, 1 = warnings, 0 = clean
    severities = {i["severity"] for i in issues}
    if "critical" in severities or "error" in severities:
        return 2
    if "warning" in severities:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
