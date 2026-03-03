"""Front-end template & framework checkers.

Checkers:
    MissingKeyPropsDetector      — v-for / .map() without key
    MissingDependencyArrayDetector — React hooks missing deps
    AccessibilityDetector        — basic a11y issues    [NEW #17]
    CSSDeadSelectorDetector      — CSS selectors unused in template [NEW #16]
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..base import BaseCheck


# ═══════════════════════════════════════════════════════════════════════════════
# MissingKeyPropsDetector  (FIX: also handle multi-line v-for)
# ═══════════════════════════════════════════════════════════════════════════════

class MissingKeyPropsDetector(BaseCheck):
    name = "MissingKeyPropsDetector"
    description = "Detect v-for / .map() without a key prop"
    fixable = True

    _VFOR = re.compile(r"v-for\s*=")
    _KEY  = re.compile(r":key\s*=|v-bind:key\s*=")
    _MAP  = re.compile(r"\.map\s*\(")
    _KEY_JSX = re.compile(r"\bkey\s*=")

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if self._is_vue_file(fp):
                self._check_vue(fp)
            elif self._is_react_file(fp):
                self._check_react(fp)

    def _check_vue(self, fp: Path) -> None:
        lines = self.read_file(fp)
        i = 0
        while i < len(lines):
            line = lines[i]
            if self._VFOR.search(line):
                # Look for :key on same element — may span several lines
                tag_text = line
                j = i + 1
                while j < len(lines) and ">" not in tag_text:
                    tag_text += lines[j]
                    j += 1
                if not self._KEY.search(tag_text):
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=i + 1,
                        message="v-for without :key",
                        severity="warning",
                        suggestion="Add :key to prevent rendering issues",
                    )
            i += 1

    def _check_react(self, fp: Path) -> None:
        lines = self.read_file(fp)
        content = self.read_content(fp)
        for m in self._MAP.finditer(content):
            lineno = self._find_line_number(lines, m.start())
            # Look ahead ~10 lines from .map( for <tag key= or key=
            snippet = content[m.start(): m.start() + 600]
            if not self._KEY_JSX.search(snippet):
                self.analyzer.add_issue(
                    check_name=self.name,
                    file_path=fp,
                    line=lineno,
                    message=".map() without key prop",
                    severity="warning",
                    suggestion="Add key prop to the returned element",
                )

    def fix(self, file_path: Path, issue: Dict[str, Any]) -> Optional[str]:
        """Insert :key='index' when missing on v-for."""
        if "v-for" not in issue.get("message", ""):
            return None
        lines = list(self.read_file(file_path))
        idx = issue["line"] - 1
        line = lines[idx]
        m = re.search(r'v-for\s*=\s*"([^"]*)"', line)
        if m:
            # Heuristic: use (item, index) variable or plain index
            loop_var = m.group(1)
            index_var = "index"
            im = re.search(r",\s*(\w+)\)", loop_var)
            if im:
                index_var = im.group(1)
            insert_pos = m.end()
            line = line[:insert_pos] + f' :key="{index_var}"' + line[insert_pos:]
            lines[idx] = line
        return "".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MissingDependencyArrayDetector
# ═══════════════════════════════════════════════════════════════════════════════

class MissingDependencyArrayDetector(BaseCheck):
    name = "MissingDependencyArrayDetector"
    description = "Detect React hooks missing dependency arrays"

    _HOOK_PATTERN = re.compile(
        r"\b(useEffect|useCallback|useMemo|useLayoutEffect)\s*\("
    )

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_react_file(fp) and not self._is_js_file(fp):
                continue
            content = self.read_content(fp)
            lines = self.read_file(fp)

            for m in self._HOOK_PATTERN.finditer(content):
                hook = m.group(1)
                # Extract full hook call (find matching close paren)
                start = m.end()
                depth, pos = 1, start
                while pos < len(content) and depth > 0:
                    ch = content[pos]
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                    pos += 1
                call_body = content[start:pos - 1]

                # Check if the last argument before closing ) is an array
                # Simple heuristic: look for , [...] at the end
                stripped = call_body.rstrip()
                if not stripped.endswith("]"):
                    lineno = self._find_line_number(lines, m.start())
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=lineno,
                        message=f"{hook}() without dependency array",
                        severity="warning",
                        suggestion=f"Add a dependency array to {hook}() to control re-runs",
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# AccessibilityDetector  [NEW — Enhancement #17]
# ═══════════════════════════════════════════════════════════════════════════════

class AccessibilityDetector(BaseCheck):
    name = "AccessibilityDetector"
    description = "Detect basic accessibility issues (a11y)"

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("*"):
                    continue

                # img without alt
                if re.search(r"<img\b", line):
                    # Gather the full tag (may span lines)
                    tag = line
                    j = i
                    while ">" not in tag and j < len(lines):
                        tag += lines[j]
                        j += 1
                    if not re.search(r"\balt\s*=", tag):
                        self.analyzer.add_issue(
                            check_name=self.name,
                            file_path=fp,
                            line=i,
                            message="<img> without alt attribute",
                            severity="warning",
                            suggestion="Add alt text for screen readers",
                        )

                # button without accessible label
                if re.search(r"<button\b", line):
                    tag = line
                    j = i
                    while ">" not in tag and j < len(lines):
                        tag += lines[j]
                        j += 1
                    if (not re.search(r"aria-label\s*=", tag) and
                            not re.search(r">.+</button>", tag)):
                        self.analyzer.add_issue(
                            check_name=self.name,
                            file_path=fp,
                            line=i,
                            message="<button> may lack accessible label",
                            severity="info",
                            suggestion="Add aria-label or visible text content",
                        )

                # Missing role or aria-label on interactive elements
                if re.search(r"<div\b[^>]*\b(onClick|@click|v-on:click)", line):
                    if not re.search(r"\brole\s*=", line):
                        self.analyzer.add_issue(
                            check_name=self.name,
                            file_path=fp,
                            line=i,
                            message="Clickable <div> without role attribute",
                            severity="warning",
                            suggestion='Add role="button" or use a <button> element',
                        )

                # anchor without href
                if re.search(r"<a\b", line) and not re.search(r"\bhref\s*=", line):
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=i,
                        message="<a> tag without href attribute",
                        severity="info",
                        suggestion="Add href or use a <button> if it triggers an action",
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# CSSDeadSelectorDetector  [NEW — Enhancement #16]
# ═══════════════════════════════════════════════════════════════════════════════

class CSSDeadSelectorDetector(BaseCheck):
    name = "CSSDeadSelectorDetector"
    description = "Detect CSS selectors with no matching template element (Vue SFC)"

    _SELECTOR = re.compile(r"^\s*([.#]?[\w-]+)\s*\{", re.MULTILINE)

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_vue_file(fp):
                continue
            content = self.read_content(fp)
            sections = self.parse_vue_sections(content)
            template = sections.get("template", "")
            style = sections.get("style", "")
            lines = self.read_file(fp)

            if not template or not style:
                continue

            for m in self._SELECTOR.finditer(style):
                selector = m.group(1).strip()
                if not selector:
                    continue

                used = False
                if selector.startswith("."):
                    # Class selector → look in template for class="...name..."
                    class_name = selector[1:]
                    if re.search(rf'\bclass\s*=\s*"[^"]*\b{re.escape(class_name)}\b',
                                 template):
                        used = True
                    elif re.search(rf":class\s*=.*\b{re.escape(class_name)}\b",
                                   template):
                        used = True
                elif selector.startswith("#"):
                    # ID selector
                    id_name = selector[1:]
                    if re.search(rf'\bid\s*=\s*"{re.escape(id_name)}"', template):
                        used = True
                else:
                    # Element selector (div, span, etc.)
                    if re.search(rf"<{re.escape(selector)}[\s>]", template):
                        used = True

                if not used:
                    # Find absolute line number
                    style_start = content.find("<style")
                    abs_pos = style_start + m.start() if style_start > 0 else m.start()
                    lineno = self._find_line_number(lines, abs_pos)
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=lineno,
                        message=f"CSS selector '{selector}' not used in template",
                        severity="info",
                        suggestion="Remove unused CSS to reduce bundle size",
                    )
