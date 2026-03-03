"""CLI entry point for code-rescue."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from collections import defaultdict

from code_rescue.ingest.run_result_loader import load_run_result
from code_rescue.ingest.skylos_loader import load_skylos_report, skylos_to_actions
from code_rescue.planner.rescue_planner import create_rescue_plan
from code_rescue.model.rescue_action import RescueAction, ActionType, SafetyLevel
from code_rescue.fixers import (
    DeadCodeFixer,
    MutableDefaultFixer,
    UnusedClassFixer,
    UnusedFunctionFixer,
    UnusedImportFixer,
)
from code_rescue.fixers.base import AbstractFixer
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

    # skylos command
    skylos_parser = subparsers.add_parser(
        "skylos",
        help="Fix dead code from a Skylos dead-code report",
    )
    skylos_parser.add_argument(
        "input",
        type=str,
        help="Path to Skylos dead-code JSON file",
    )
    skylos_parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Root directory of codebase (default: current directory)",
    )
    skylos_parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply the fixes (default: dry-run)",
    )
    skylos_parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backups before modifying files",
    )
    skylos_parser.add_argument(
        "--min-confidence",
        type=int,
        default=80,
        help="Minimum Skylos confidence to act on (default: 80)",
    )
    skylos_parser.add_argument(
        "--category",
        type=str,
        default=None,
        choices=["unused_imports", "unused_functions", "unused_classes"],
        help="Only fix a specific category",
    )
    skylos_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Write plan JSON to file instead of applying",
    )

    args = parser.parse_args()

    if args.command == "plan":
        return cmd_plan(args)
    elif args.command == "fix":
        return cmd_fix(args)
    elif args.command == "skylos":
        return cmd_skylos(args)

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
    mutable_fixer = MutableDefaultFixer()
    dead_code_fixer = DeadCodeFixer()
    fixers: dict[str, AbstractFixer] = {}
    for fixer in [mutable_fixer, dead_code_fixer]:
        for rule_id in fixer.supported_rules:
            fixers[rule_id] = fixer

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


def cmd_skylos(args: argparse.Namespace) -> int:
    """Fix dead code using a Skylos dead-code report."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        return 2

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Error: root directory not found: {root}", file=sys.stderr)
        return 2

    # Load Skylos report
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        return 2

    report = load_skylos_report(data)
    print(f"Loaded Skylos report: {len(report.symbols)} symbols")

    # Filter categories
    categories = None
    if args.category:
        categories = {args.category}

    # Convert to actions
    actions = skylos_to_actions(
        report,
        root=str(root),
        min_confidence=args.min_confidence,
        categories=categories,
    )
    print(f"Generated {len(actions)} actionable fixes")

    if not actions:
        print("No fixes to apply.")
        return 0

    # Print summary by rule
    by_rule: dict[str, int] = defaultdict(int)
    for a in actions:
        by_rule[a.rule_id] += 1
    for rule_id, count in sorted(by_rule.items()):
        print(f"  {rule_id}: {count}")

    # If --output, write plan JSON and exit
    if args.output:
        plan_data = {
            "source": "skylos",
            "total_actions": len(actions),
            "actions": [a.to_dict() for a in actions],
        }
        Path(args.output).write_text(
            json.dumps(plan_data, indent=2),
            encoding="utf-8",
        )
        print(f"\nPlan written to: {args.output}")
        return 0

    # Get available fixers
    import_fixer = UnusedImportFixer()
    func_fixer = UnusedFunctionFixer()
    class_fixer = UnusedClassFixer()
    dead_code_fixer = DeadCodeFixer()
    fixers: dict[str, AbstractFixer] = {}
    for fixer in [import_fixer, func_fixer, class_fixer, dead_code_fixer]:
        for rule_id in fixer.supported_rules:
            fixers[rule_id] = fixer

    # Group actions by file (process bottom-up by line to avoid offset drift)
    actions_by_file: dict[str, list[RescueAction]] = defaultdict(list)
    for action in actions:
        if action.rule_id in fixers:
            actions_by_file[action.file_path].append(action)

    if not actions_by_file:
        print("No fixes for supported rules.")
        return 0

    print(f"\n{'[DRY-RUN] ' if not args.apply else ''}Processing {len(actions_by_file)} files...")

    total_applied = 0
    total_errors = 0
    total_skipped = 0

    for rel_path, file_actions in sorted(actions_by_file.items()):
        # Try both relative and absolute paths
        full_path = root / rel_path
        if not full_path.exists():
            # Try the path as-is (might already be absolute in action)
            abs_candidate = Path(rel_path)
            if abs_candidate.exists():
                full_path = abs_candidate
            else:
                print(f"[SKIP] File not found: {rel_path}")
                total_skipped += len(file_actions)
                continue

        # Sort actions by line descending so removals don't shift later lines
        file_actions.sort(key=lambda a: -a.line_start)

        source = full_path.read_text(encoding="utf-8", errors="replace")

        # Create backup if requested
        if args.backup and args.apply:
            backup_path = full_path.with_suffix(full_path.suffix + ".bak")
            shutil.copy2(full_path, backup_path)

        modified = source
        file_applied = 0

        for action in file_actions:
            fixer = fixers.get(action.rule_id)
            if fixer is None:
                total_skipped += 1
                continue

            result = fixer.apply(action, modified, dry_run=not args.apply)

            if result.status.value == "success" and result.modified_content is not None:
                modified = result.modified_content
                file_applied += 1
            elif result.status.value == "failed":
                print(f"[FAIL] {rel_path}:{action.line_start} - {result.message}")
                total_errors += 1
            else:
                total_skipped += 1

        if file_applied > 0:
            if args.apply:
                full_path.write_text(modified, encoding="utf-8")
                print(f"[OK] {rel_path}: {file_applied} fix(es)")
            else:
                print(f"[DRY-RUN] {rel_path}: {file_applied} fix(es)")
            total_applied += file_applied

    print()
    print("=== SKYLOS FIX SUMMARY ===")
    print(f"Fixes applied: {total_applied}")
    print(f"Skipped:       {total_skipped}")
    print(f"Errors:        {total_errors}")

    if not args.apply and total_applied > 0:
        print()
        print("Run with --apply to actually make changes.")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
