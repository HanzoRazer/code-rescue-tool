"""CLI entry point for code-rescue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from code_rescue.ingest.run_result_loader import load_run_result
from code_rescue.planner.rescue_planner import create_rescue_plan


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="code-rescue",
        description="Rescue spaghetti code using code-analysis-tool findings",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # plan command
    plan_parser = subparsers.add_parser(
        "plan",
        help="Generate a rescue plan from analysis results",
    )
    plan_parser.add_argument(
        "input",
        type=str,
        help="Path to run_result JSON file (use '-' for stdin)",
    )
    plan_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="-",
        help="Output path for rescue plan (default: stdout)",
    )
    plan_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes",
    )

    # fix command (placeholder)
    fix_parser = subparsers.add_parser(
        "fix",
        help="Apply rescue actions to codebase",
    )
    fix_parser.add_argument(
        "plan",
        type=str,
        help="Path to rescue plan JSON",
    )
    fix_parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply the fixes (default: dry-run)",
    )
    fix_parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backups before modifying files",
    )

    args = parser.parse_args()

    if args.command == "plan":
        return cmd_plan(args)
    elif args.command == "fix":
        return cmd_fix(args)

    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """Generate a rescue plan from analysis results."""
    # Load input
    if args.input == "-":
        data = json.load(sys.stdin)
    else:
        path = Path(args.input)
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            return 2
        data = json.loads(path.read_text())

    # Parse and validate
    run_result = load_run_result(data)
    if run_result is None:
        print("Error: invalid run_result format", file=sys.stderr)
        return 2

    # Create plan
    plan = create_rescue_plan(run_result)

    # Output
    output_json = json.dumps(plan.to_dict(), indent=2)
    if args.output == "-":
        print(output_json)
    else:
        Path(args.output).write_text(output_json)
        print(f"Rescue plan written to: {args.output}", file=sys.stderr)

    return 0


def cmd_fix(args: argparse.Namespace) -> int:
    """Apply rescue actions (placeholder)."""
    print("fix command not yet implemented", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
