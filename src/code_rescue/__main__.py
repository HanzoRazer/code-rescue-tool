"""CLI entry point for code-rescue."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from collections import defaultdict

from code_rescue.ingest.run_result_loader import load_run_result
from code_rescue.planner.rescue_planner import create_rescue_plan
from code_rescue.model.rescue_action import RescueAction, ActionType, SafetyLevel
from code_rescue.fixers import MutableDefaultFixer
from code_rescue.fixers.mutable_default import apply_fixes_to_file


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

    # fix command
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
        "--root",
        type=str,
        default=".",
        help="Root directory of codebase (default: current directory)",
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
    fix_parser.add_argument(
        "--rule",
        type=str,
        default=None,
        help="Only fix specific rule (e.g., GST_MUTABLE_DEFAULT_001)",
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
    try:
        if args.input == "-":
            data = json.load(sys.stdin)
        else:
            path = Path(args.input)
            if not path.exists():
                print(f"Error: file not found: {path}", file=sys.stderr)
                return 2
            data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        return 2

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
    """Apply rescue actions from a plan."""
    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"Error: plan file not found: {plan_path}", file=sys.stderr)
        return 2

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Error: root directory not found: {root}", file=sys.stderr)
        return 2

    plan = json.loads(plan_path.read_text())
    actions = plan.get("actions", [])

    # Filter by rule if specified
    if args.rule:
        actions = [a for a in actions if a["rule_id"] == args.rule]

    # Filter to safe actions only (for now)
    safe_actions = [a for a in actions if a["safety_level"] == "safe"]

    # Get available fixers
    fixers = {
        "GST_MUTABLE_DEFAULT_001": MutableDefaultFixer(),
    }

    # Group actions by file
    actions_by_file: dict[str, list[dict]] = defaultdict(list)
    for action in safe_actions:
        rule_id = action["rule_id"]
        if rule_id in fixers:
            actions_by_file[action["file_path"]].append(action)

    if not actions_by_file:
        print("No safe fixes available for supported rules.")
        print(f"Total actions in plan: {len(actions)}")
        print(f"Safe actions: {len(safe_actions)}")
        print(f"Supported rules: {list(fixers.keys())}")
        return 0

    print(f"{'[DRY-RUN] ' if not args.apply else ''}Applying fixes...")
    print(f"Root: {root}")
    print(f"Files to fix: {len(actions_by_file)}")
    print()

    total_applied = 0
    total_errors = 0

    for rel_path, file_actions in sorted(actions_by_file.items()):
        full_path = root / rel_path
        if not full_path.exists():
            print(f"[SKIP] File not found: {rel_path}")
            total_errors += 1
            continue

        # Convert dict actions to RescueAction objects
        rescue_actions = []
        for a in file_actions:
            rescue_actions.append(RescueAction(
                action_id=a["action_id"],
                finding_id=a["finding_id"],
                rule_id=a["rule_id"],
                file_path=a["file_path"],
                line_start=a["line_start"],
                line_end=a["line_end"],
                action_type=ActionType(a["action_type"]),
                safety_level=SafetyLevel(a["safety_level"]),
                description=a["description"],
            ))

        # Create backup if requested
        if args.backup and args.apply:
            backup_path = full_path.with_suffix(full_path.suffix + ".bak")
            shutil.copy2(full_path, backup_path)

        # Apply fixes
        result = apply_fixes_to_file(
            full_path,
            rescue_actions,
            dry_run=not args.apply,
        )

        if result["applied"] > 0:
            status = "[OK]" if args.apply else "[DRY-RUN]"
            print(f"{status} {rel_path}: {result['applied']} fix(es)")
            total_applied += result["applied"]

        if result["errors"]:
            for err in result["errors"]:
                print(f"[ERROR] {rel_path}: {err}")
                total_errors += 1

    print()
    print("=== SUMMARY ===")
    print(f"Fixes applied: {total_applied}")
    print(f"Errors: {total_errors}")

    if not args.apply and total_applied > 0:
        print()
        print("Run with --apply to actually make changes.")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
