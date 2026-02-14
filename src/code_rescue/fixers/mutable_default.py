"""Mutable default argument fixer - fixes GST_MUTABLE_DEFAULT_001.

Transforms:
    def foo(items: List[str] = []):     →  def foo(items: List[str] = None):
        ...                                     if items is None:
                                                    items = []
                                                ...
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from code_rescue.fixers.base import AbstractFixer, FixResult, FixStatus
from code_rescue.model.rescue_action import RescueAction


class MutableDefaultFixer(AbstractFixer):
    """Fixer for GST_MUTABLE_DEFAULT_001 - mutable default arguments."""

    SUPPORTED_RULES = ["GST_MUTABLE_DEFAULT_001"]

    @property
    def supported_rules(self) -> list[str]:
        return self.SUPPORTED_RULES

    def can_fix(self, action: RescueAction) -> bool:
        return action.rule_id in self.SUPPORTED_RULES

    def generate_fix(
        self,
        action: RescueAction,
        source_code: str,
    ) -> tuple[str | None, str | None]:
        """Generate fix by replacing mutable default with None pattern."""
        params = find_mutable_default_params(source_code, action.line_start)
        if not params:
            return None, None

        fixed = apply_mutable_default_fix(source_code, action.line_start, params)
        if fixed is None:
            return None, None

        param_names = [p[0] for p in params]
        rationale = (
            f"Replaced mutable default(s) for {', '.join(param_names)} with None pattern. "
            "Mutable defaults are shared across calls, causing subtle bugs."
        )
        return fixed, rationale

    def apply(
        self,
        action: RescueAction,
        source_code: str,
        dry_run: bool = True,
    ) -> FixResult:
        """Apply the mutable default fix."""
        if not self.can_fix(action):
            return FixResult(
                status=FixStatus.SKIPPED,
                action=action,
                message=f"Fixer does not support rule: {action.rule_id}",
            )

        fixed_code, rationale = self.generate_fix(action, source_code)
        if fixed_code is None:
            return FixResult(
                status=FixStatus.FAILED,
                action=action,
                message="Could not generate fix - no mutable defaults found at location",
            )

        action.replacement_code = fixed_code
        if rationale:
            action.rationale = rationale

        return FixResult(
            status=FixStatus.SUCCESS,
            action=action,
            original_content=source_code,
            modified_content=fixed_code,
            message="Mutable default(s) replaced with None pattern",
        )


def find_mutable_default_params(
    source: str, line_start: int
) -> list[tuple[str, str, str]]:
    """Find parameters with mutable defaults on the given line.

    Returns list of (param_name, default_repr, mutable_type) tuples.
    """
    results = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno == line_start:
                # Check defaults
                defaults = node.args.defaults
                args = node.args.args

                # defaults align to the END of args
                offset = len(args) - len(defaults)

                for i, default in enumerate(defaults):
                    if isinstance(default, ast.List):
                        param = args[offset + i]
                        # Get the actual list content for reconstruction
                        list_repr = _reconstruct_list(default, source)
                        results.append((param.arg, list_repr, "list"))
                    elif isinstance(default, ast.Dict):
                        param = args[offset + i]
                        results.append((param.arg, "{}", "dict"))
                    elif isinstance(default, ast.Set):
                        param = args[offset + i]
                        results.append((param.arg, "set()", "set"))
                    elif isinstance(default, ast.Call):
                        # Handle list(), dict(), set() calls
                        if isinstance(default.func, ast.Name):
                            if default.func.id == "list" and not default.args:
                                param = args[offset + i]
                                results.append((param.arg, "[]", "list"))
                            elif default.func.id == "dict" and not default.args:
                                param = args[offset + i]
                                results.append((param.arg, "{}", "dict"))
                            elif default.func.id == "set" and not default.args:
                                param = args[offset + i]
                                results.append((param.arg, "set()", "set"))
                            elif default.func.id == "list" and default.args:
                                # list(range(...)) etc
                                param = args[offset + i]
                                call_repr = _get_source_segment(source, default)
                                results.append((param.arg, call_repr, "list"))

                # Also check kwonlyargs
                kw_defaults = node.args.kw_defaults
                kwonly = node.args.kwonlyargs
                for i, default in enumerate(kw_defaults):
                    if default is None:
                        continue
                    if isinstance(default, ast.List):
                        param = kwonly[i]
                        list_repr = _reconstruct_list(default, source)
                        results.append((param.arg, list_repr, "list"))
                    elif isinstance(default, ast.Dict):
                        param = kwonly[i]
                        results.append((param.arg, "{}", "dict"))
                    elif isinstance(default, ast.Set):
                        param = kwonly[i]
                        results.append((param.arg, "set()", "set"))

    return results


def _reconstruct_list(node: ast.List, source: str) -> str:
    """Reconstruct list literal from AST node."""
    if not node.elts:
        return "[]"
    # Try to get from source
    segment = _get_source_segment(source, node)
    if segment:
        return segment
    # Fallback
    return "[]"


def _get_source_segment(source: str, node: ast.AST) -> str | None:
    """Get source code segment for an AST node."""
    try:
        return ast.get_source_segment(source, node)
    except (AttributeError, TypeError):
        return None


def get_function_body_indent(lines: list[str], func_line: int) -> str:
    """Get the indentation of the function body."""
    func_line_idx = func_line - 1

    # Find the first line of the function body (after signature ends with :)
    in_signature = True
    for i in range(func_line_idx, len(lines)):
        line = lines[i]
        if in_signature:
            if line.rstrip().endswith(':'):
                in_signature = False
            continue
        # First non-empty, non-comment line after signature
        stripped = line.lstrip()
        if stripped and not stripped.startswith('#'):
            return line[:len(line) - len(line.lstrip())]

    # Fallback: function indent + 4 spaces
    func_indent = lines[func_line_idx][:len(lines[func_line_idx]) - len(lines[func_line_idx].lstrip())]
    return func_indent + "    "


def apply_mutable_default_fix(
    source: str,
    line_start: int,
    params: list[tuple[str, str, str]],
) -> str | None:
    """Apply the mutable default fix to source code.

    Args:
        source: Full source code of the file
        line_start: Line number where the function starts
        params: List of (param_name, default_repr, mutable_type) tuples

    Returns:
        Modified source code, or None if fix couldn't be applied
    """
    if not params:
        return None

    lines = source.splitlines(keepends=True)
    if line_start < 1 or line_start > len(lines):
        return None

    func_start_idx = line_start - 1

    # Find where the signature ends (the line with ':')
    sig_end_idx = func_start_idx
    paren_depth = 0
    found_open = False
    for i in range(func_start_idx, len(lines)):
        line = lines[i]
        for char in line:
            if char == '(':
                paren_depth += 1
                found_open = True
            elif char == ')':
                paren_depth -= 1
        if found_open and paren_depth == 0 and ':' in line:
            sig_end_idx = i
            break

    # Get the body indent
    body_indent = get_function_body_indent(lines, line_start)

    # Replace mutable defaults with None in signature
    for i in range(func_start_idx, sig_end_idx + 1):
        line = lines[i]
        for param_name, default_repr, mutable_type in params:
            # Escape special regex chars in default_repr
            escaped_default = re.escape(default_repr)

            # With type annotation: param: Type = [...]
            pattern1 = rf'(\b{re.escape(param_name)}\s*:\s*[^=]+\s*=\s*){escaped_default}'
            line = re.sub(pattern1, r'\1None', line)

            # Without type annotation: param = [...]
            pattern2 = rf'(\b{re.escape(param_name)}\s*=\s*){escaped_default}'
            line = re.sub(pattern2, r'\1None', line)

        lines[i] = line

    # Find the first line of the function body (after docstring if any)
    body_start_idx = sig_end_idx + 1

    # Skip docstrings
    if body_start_idx < len(lines):
        first_body_line = lines[body_start_idx].strip()
        if first_body_line.startswith('"""') or first_body_line.startswith("'''"):
            quote = first_body_line[:3]
            if first_body_line.count(quote) >= 2 and len(first_body_line) > 6:
                # Single-line docstring
                body_start_idx += 1
            else:
                # Multi-line docstring
                for i in range(body_start_idx + 1, len(lines)):
                    if quote in lines[i]:
                        body_start_idx = i + 1
                        break

    # Build the initialization lines
    init_lines = []
    for param_name, default_repr, mutable_type in params:
        init_lines.append(f"{body_indent}if {param_name} is None:\n")
        init_lines.append(f"{body_indent}    {param_name} = {default_repr}\n")

    # Insert initialization at the start of the function body
    new_lines = lines[:body_start_idx] + init_lines + lines[body_start_idx:]

    return ''.join(new_lines)


def apply_fixes_to_file(
    file_path: Path,
    actions: list[RescueAction],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply all mutable default fixes to a single file.

    Args:
        file_path: Path to the file to fix
        actions: List of RescueAction for this file
        dry_run: If True, don't actually modify the file

    Returns:
        Dict with 'applied' count and 'errors' list
    """
    fixer = MutableDefaultFixer()
    result = {"applied": 0, "errors": []}

    if not file_path.exists():
        result["errors"].append(f"File not found: {file_path}")
        return result

    source = file_path.read_text(encoding='utf-8')
    modified = source

    # Sort actions by line number descending (so we don't shift line numbers)
    actions_sorted = sorted(actions, key=lambda a: -a.line_start)

    for action in actions_sorted:
        if not fixer.can_fix(action):
            continue

        params = find_mutable_default_params(modified, action.line_start)
        if not params:
            # Line numbers may have shifted, try nearby lines
            for offset in range(-3, 4):
                params = find_mutable_default_params(modified, action.line_start + offset)
                if params:
                    action.line_start += offset
                    break

        if params:
            new_source = apply_mutable_default_fix(modified, action.line_start, params)
            if new_source:
                modified = new_source
                result["applied"] += 1

    if modified != source and not dry_run:
        file_path.write_text(modified, encoding='utf-8')

    return result
