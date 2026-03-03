"""Structural analysis checkers.

Checkers:
    RecursiveLinesDetector      — direct recursion & self-rendering Vue components
    CyclicDependencyDetector    — N-node import cycles via DFS
    DeepNestingDetector         — deeply nested control flow (brace-based)
    ComponentDepthAnalyzer      — deep HTML/template nesting
    CircularComponentDetector   — circular Vue component references
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..base import BaseCheck


# ═══════════════════════════════════════════════════════════════════════════════
# RecursiveLinesDetector  (FIX: re.DOTALL for multi-line bodies)
# ═══════════════════════════════════════════════════════════════════════════════

class RecursiveLinesDetector(BaseCheck):
    name = "RecursiveLinesDetector"
    description = "Detect recursive function calls and self-rendering Vue components"

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)
            content = self.read_content(fp)

            # Direct recursion: function foo(…) { … foo( … }
            # Use re.DOTALL so [^}]* can cross newlines inside the body.
            # Limit body scan to 2000 chars to avoid catastrophic backtracking.
            for m in re.finditer(
                r"function\s+(\w+)\s*\([^)]*\)\s*\{",
                content,
            ):
                fname = m.group(1)
                body_start = m.end()
                body_slice = content[body_start : body_start + 2000]
                # Find matching closing brace (simple depth tracker)
                depth = 1
                body_end = 0
                for i, ch in enumerate(body_slice):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            body_end = i
                            break
                body = body_slice[:body_end]
                # Check if the function calls itself
                if re.search(rf"\b{re.escape(fname)}\s*\(", body):
                    line_no = self._find_line_number(lines, m.start())
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=line_no,
                        message=f"Direct recursion detected in function '{fname}'",
                        severity="warning",
                        suggestion="Ensure there's a proper base case to prevent infinite recursion",
                    )

            # Vue self-rendering component
            if self._is_vue_file(fp):
                cname = fp.stem
                tag_open = f"<{cname}"
                if tag_open in content:
                    idx = content.find(tag_open)
                    # Check it's not in <script> or a comment
                    sections = self.parse_vue_sections(content)
                    tpl = sections.get("template")
                    if tpl:
                        tpl_start = sum(len(l) for l in lines[: tpl[0] - 1])
                        tpl_end = sum(len(l) for l in lines[: tpl[1]])
                        if tpl_start <= idx < tpl_end:
                            line_no = self._find_line_number(lines, idx)
                            self.analyzer.add_issue(
                                check_name=self.name,
                                file_path=fp,
                                line=line_no,
                                message=f"Component '{cname}' renders itself recursively",
                                severity="warning",
                                suggestion="Ensure recursive rendering has a stopping condition (v-if)",
                            )


# ═══════════════════════════════════════════════════════════════════════════════
# CyclicDependencyDetector  (FIX: full DFS for N-node cycles)
# ═══════════════════════════════════════════════════════════════════════════════

class CyclicDependencyDetector(BaseCheck):
    name = "CyclicDependencyDetector"
    description = "Detect circular import / dependency cycles of any length"

    def run(self, files: List[Path]) -> None:
        # Build import graph: node → set of (resolved_target, import_line)
        graph: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
        adj: Dict[str, Set[str]] = defaultdict(set)  # for cycle search

        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)
            key = str(fp)
            for i, line in enumerate(lines, 1):
                m = re.search(r"""import\s+.*\s+from\s+['"]([^'"]+)['"]""", line)
                if m:
                    raw = m.group(1)
                    resolved = self._resolve(fp, raw, files)
                    if resolved:
                        graph[key].append((resolved, i))
                        adj[key].add(resolved)

        # DFS cycle detection (colouring: 0=white, 1=grey, 2=black)
        colour: Dict[str, int] = defaultdict(int)
        parent: Dict[str, Optional[str]] = {}

        def dfs(node: str, path: List[str]) -> None:
            colour[node] = 1
            path.append(node)
            for neighbour in adj.get(node, set()):
                if colour[neighbour] == 0:
                    parent[neighbour] = node
                    dfs(neighbour, path)
                elif colour[neighbour] == 1:
                    # Back-edge → cycle found
                    cycle_start = path.index(neighbour)
                    cycle = path[cycle_start:]
                    # Report on the originating import line
                    for src, edges in graph.items():
                        if src != node:
                            continue
                        for target, lineno in edges:
                            if target == neighbour:
                                self.analyzer.add_issue(
                                    check_name=self.name,
                                    file_path=Path(node),
                                    line=lineno,
                                    message=f"Cyclic dependency: {' → '.join(Path(n).name for n in cycle)} → {Path(neighbour).name}",
                                    severity="critical",
                                    suggestion="Break the cycle by extracting shared logic to a third module",
                                )
                                break
            path.pop()
            colour[node] = 2

        for node in list(adj.keys()):
            if colour[node] == 0:
                dfs(node, [])

    @staticmethod
    def _resolve(source: Path, raw_import: str, all_files: List[Path]) -> Optional[str]:
        if not raw_import.startswith("."):
            return None  # skip bare-specifier / node_modules imports
        base = source.parent / raw_import
        for ext in ("", ".js", ".ts", ".jsx", ".tsx", ".vue", "/index.js", "/index.ts"):
            candidate = base.parent / (base.name + ext)
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            for fp in all_files:
                if fp.resolve() == resolved:
                    return str(fp)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# DeepNestingDetector  (FIX: brace-only depth, skip strings & comments)
# ═══════════════════════════════════════════════════════════════════════════════

class DeepNestingDetector(BaseCheck):
    name = "DeepNestingDetector"
    description = "Detect deeply nested code blocks (brace-based depth tracking)"

    def run(self, files: List[Path]) -> None:
        threshold = self.analyzer.config.get("threshold", 5)

        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)

            depth = 0
            in_block_comment = False
            reported_lines: List[Tuple[int, int]] = []

            for i, line in enumerate(lines, 1):
                stripped = line.strip()

                # Track block comments
                if in_block_comment:
                    if "*/" in stripped:
                        in_block_comment = False
                    continue
                if stripped.startswith("/*"):
                    if "*/" not in stripped:
                        in_block_comment = True
                    continue
                if stripped.startswith("//"):
                    continue

                # Count braces outside strings
                for col, ch in enumerate(line):
                    if self._is_in_string(line, col) or self._is_in_comment(line, col):
                        continue
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1

                if depth > threshold:
                    reported_lines.append((i, depth))

            for line_no, level in reported_lines:
                self.analyzer.add_issue(
                    check_name=self.name,
                    file_path=fp,
                    line=line_no,
                    message=f"Deep nesting detected (level: {level})",
                    severity="warning",
                    suggestion="Refactor with early returns, guard clauses, or extracted functions",
                )


# ═══════════════════════════════════════════════════════════════════════════════
# ComponentDepthAnalyzer  (FIX: skip self-closing, comments, script/style)
# ═══════════════════════════════════════════════════════════════════════════════

class ComponentDepthAnalyzer(BaseCheck):
    name = "ComponentDepthAnalyzer"
    description = "Analyse HTML template nesting depth"

    _SELF_CLOSING = frozenset({
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    })

    def run(self, files: List[Path]) -> None:
        threshold = self.analyzer.config.get("threshold", 5)

        for fp in files:
            if not self._is_vue_file(fp):
                continue
            content = self.read_content(fp)
            lines = self.read_file(fp)
            sections = self.parse_vue_sections(content)
            tpl = sections.get("template")
            if not tpl:
                continue

            depth = 0
            max_depth = 0
            worst_line = 0

            for i in range(tpl[0], tpl[1] + 1):
                if i - 1 >= len(lines):
                    break
                line = lines[i - 1]
                stripped = line.strip()

                # Skip HTML comments
                if stripped.startswith("<!--"):
                    continue

                # Count opening tags (not self-closing, not closing)
                opens = re.findall(r"<([a-zA-Z][\w-]*)", stripped)
                for tag in opens:
                    if tag.lower() not in self._SELF_CLOSING:
                        depth += 1

                # Self-closing tags like <img/> or <Component />
                self_closes = len(re.findall(r"/>", stripped))
                depth -= self_closes

                # Closing tags
                closes = len(re.findall(r"</[a-zA-Z][\w-]*\s*>", stripped))
                depth -= closes

                if depth > max_depth:
                    max_depth = depth
                    worst_line = i

            if max_depth > threshold:
                self.analyzer.add_issue(
                    check_name=self.name,
                    file_path=fp,
                    line=worst_line,
                    message=f"Deep component nesting detected (depth: {max_depth})",
                    severity="warning",
                    suggestion="Refactor into smaller, composable components",
                )


# ═══════════════════════════════════════════════════════════════════════════════
# CircularComponentDetector  (FIX: DFS for N-node circular refs)
# ═══════════════════════════════════════════════════════════════════════════════

class CircularComponentDetector(BaseCheck):
    name = "CircularComponentDetector"
    description = "Detect circular Vue component references"

    def run(self, files: List[Path]) -> None:
        vue_files = [f for f in files if self._is_vue_file(f)]
        # Build component import graph
        graph: Dict[str, List[Tuple[str, int]]] = {}
        adj: Dict[str, Set[str]] = defaultdict(set)

        for fp in vue_files:
            lines = self.read_file(fp)
            key = str(fp)
            graph[key] = []
            for i, line in enumerate(lines, 1):
                m = re.search(r"""import\s+(\w+)\s+from\s+['"]([^'"]+)['"]""", line)
                if m:
                    imp_path = m.group(2)
                    resolved = self._resolve_vue(fp, imp_path, vue_files)
                    if resolved:
                        graph[key].append((resolved, i))
                        adj[key].add(resolved)

        # DFS cycle detection
        colour: Dict[str, int] = defaultdict(int)

        def dfs(node: str, path: List[str]) -> None:
            colour[node] = 1
            path.append(node)
            for nbr in adj.get(node, set()):
                if colour[nbr] == 0:
                    dfs(nbr, path)
                elif colour[nbr] == 1:
                    cycle_start = path.index(nbr)
                    cycle = path[cycle_start:]
                    for target, lineno in graph.get(node, []):
                        if target == nbr:
                            self.analyzer.add_issue(
                                check_name=self.name,
                                file_path=Path(node),
                                line=lineno,
                                message=f"Circular component reference: {' → '.join(Path(n).stem for n in cycle)} → {Path(nbr).stem}",
                                severity="critical",
                                suggestion="Extract shared functionality to a third component",
                            )
                            break
            path.pop()
            colour[node] = 2

        for node in list(adj.keys()):
            if colour[node] == 0:
                dfs(node, [])

    @staticmethod
    def _resolve_vue(source: Path, raw: str, vue_files: List[Path]) -> Optional[str]:
        if not raw.startswith("."):
            return None
        base = source.parent / raw
        for ext in ("", ".vue"):
            candidate = (base.parent / (base.name + ext)).resolve()
            for fp in vue_files:
                if fp.resolve() == candidate:
                    return str(fp)
        return None
