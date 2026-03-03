"""Component-level checkers (Vue & framework-specific).

Checkers:
    GodComponentDetector       — oversized components (brace-tracking for methods)
    PropsDrillingAnalyzer      — props drilled without local use
    PropMutationDetector       — direct prop mutation (FIX: variable scope)
    InlineFunctionDetector     — inline arrow fns in templates / JSX
    VueCompositionApiDetector  — Options API patterns that should migrate  [NEW]
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Set

from ..base import BaseCheck


# ═══════════════════════════════════════════════════════════════════════════════
# GodComponentDetector  (FIX: brace-depth method counting)
# ═══════════════════════════════════════════════════════════════════════════════

class GodComponentDetector(BaseCheck):
    name = "GodComponentDetector"
    description = "Detect oversized components (God objects)"

    def run(self, files: List[Path]) -> None:
        min_lines = self.analyzer.config.get("min_lines", 400)
        max_methods = self.analyzer.config.get("max_methods", 15)

        for fp in files:
            if fp.suffix not in {".vue", ".jsx", ".tsx"}:
                continue
            lines = self.read_file(fp)

            if len(lines) > min_lines:
                self.analyzer.add_issue(
                    check_name=self.name,
                    file_path=fp,
                    line=1,
                    message=f"Component is very large ({len(lines)} lines)",
                    severity="warning",
                    suggestion="Break into smaller, focused components",
                )

            # Method count via brace tracking (Vue Options API)
            if self._is_vue_file(fp):
                content = self.read_content(fp)
                method_count = self._count_methods_brace(content)
                if method_count > max_methods:
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=1,
                        message=f"Component has many methods ({method_count})",
                        severity="info",
                        suggestion="Extract into composables or mixins",
                    )

    @staticmethod
    def _count_methods_brace(content: str) -> int:
        """Count methods inside ``methods: { … }`` by tracking brace depth."""
        m = re.search(r"\bmethods\s*:\s*\{", content)
        if not m:
            return 0

        depth = 1
        pos = m.end()
        method_count = 0
        expecting_name = True

        while pos < len(content) and depth > 0:
            ch = content[pos]
            if ch == "{":
                depth += 1
                if depth == 2:
                    # Entering a method body at depth 2
                    method_count += 1
            elif ch == "}":
                depth -= 1
            pos += 1

        return method_count


# ═══════════════════════════════════════════════════════════════════════════════
# PropsDrillingAnalyzer  (FIX: supports both array & object props syntax)
# ═══════════════════════════════════════════════════════════════════════════════

class PropsDrillingAnalyzer(BaseCheck):
    name = "PropsDrillingAnalyzer"
    description = "Detect props drilled through components without local use"

    def run(self, files: List[Path]) -> None:
        prop_passthrough: Dict[str, List[str]] = {}

        for fp in files:
            if not self._is_vue_file(fp):
                continue
            content = self.read_content(fp)
            props = self._extract_props(content)

            for prop in props:
                # Is prop only used as a child binding?
                child_bind = re.findall(rf":{re.escape(prop)}\b", content)
                # Is prop used in JS expressions (this.prop or just prop in template)?
                direct_use = re.findall(rf"\bthis\.{re.escape(prop)}\b", content)
                template_use = re.findall(
                    rf"(?<![:])\b{re.escape(prop)}\b(?!\s*=)", content
                )
                # Subtract the props declaration itself
                decl_count = len(re.findall(rf'["\']?{re.escape(prop)}["\']?\s*[,:\]}}]', content))

                uses = len(direct_use) + max(0, len(template_use) - decl_count - len(child_bind))
                if child_bind and uses <= 0:
                    prop_passthrough.setdefault(prop, []).append(str(fp))

        for prop, file_list in prop_passthrough.items():
            if len(file_list) >= 2:
                for fpath in file_list:
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=Path(fpath),
                        line=1,
                        message=f"Prop '{prop}' is drilled through without local use",
                        severity="info",
                        suggestion="Use provide/inject, Pinia, or Vuex for deeply shared state",
                    )

    @staticmethod
    def _extract_props(content: str) -> List[str]:
        """Extract prop names from both array and object syntax, plus defineProps."""
        props: List[str] = []
        # Array syntax: props: ['foo', 'bar']
        arr = re.search(r"\bprops\s*:\s*\[([^\]]+)\]", content)
        if arr:
            props.extend(re.findall(r"""['"](\w+)['"]""", arr.group(1)))
        # Object syntax: props: { foo: { … }, bar: String }
        obj = re.search(r"\bprops\s*:\s*\{", content)
        if obj:
            depth = 1
            pos = obj.end()
            current_key = ""
            while pos < len(content) and depth > 0:
                ch = content[pos]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                pos += 1
            block = content[obj.end() : pos - 1]
            # Top-level keys are the prop names
            for key_m in re.finditer(r"""(?:^|,)\s*['"]?(\w+)['"]?\s*:""", block):
                props.append(key_m.group(1))
        # Composition API: defineProps<{ foo: string }>() or defineProps({ foo: … })
        dp = re.search(r"\bdefineProps\s*[<(]", content)
        if dp:
            chunk = content[dp.end() : dp.end() + 500]
            for key_m in re.finditer(r"""['"]?(\w+)['"]?\s*[?:]""", chunk):
                props.append(key_m.group(1))
        return props


# ═══════════════════════════════════════════════════════════════════════════════
# PropMutationDetector  (FIX: scoped flags, proper state tracking)
# ═══════════════════════════════════════════════════════════════════════════════

class PropMutationDetector(BaseCheck):
    name = "PropMutationDetector"
    description = "Detect direct mutation of Vue component props"

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_vue_file(fp):
                continue
            content = self.read_content(fp)
            lines = self.read_file(fp)

            props = PropsDrillingAnalyzer._extract_props(content)
            if not props:
                continue

            # Scan <script> section for this.<prop> = …
            sections = self.parse_vue_sections(content)
            script = sections.get("script")
            if not script:
                continue

            for i in range(script[0] - 1, min(script[1], len(lines))):
                line = lines[i]
                for prop in props:
                    if re.search(rf"\bthis\.{re.escape(prop)}\s*=", line):
                        self.analyzer.add_issue(
                            check_name=self.name,
                            file_path=fp,
                            line=i + 1,
                            message=f"Direct mutation of prop '{prop}'",
                            severity="critical",
                            suggestion="Emit an event to notify the parent component instead",
                        )


# ═══════════════════════════════════════════════════════════════════════════════
# InlineFunctionDetector
# ═══════════════════════════════════════════════════════════════════════════════

class InlineFunctionDetector(BaseCheck):
    name = "InlineFunctionDetector"
    description = "Detect inline arrow functions in templates / JSX"

    _PATTERNS = [
        (r"""@\w+=["']\s*\([^)]*\)\s*=>""", "Inline arrow function in Vue event handler", "Move to methods or <script setup>"),
        (r"""v-on:\w+=["']\s*\([^)]*\)\s*=>""", "Inline arrow function in v-on handler", "Move to methods"),
        (r"on[A-Z]\w*=\{\s*\([^)]*\)\s*=>", "Inline arrow function in React event handler", "Extract to a named function"),
    ]

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if fp.suffix not in {".vue", ".jsx", ".tsx"}:
                continue
            lines = self.read_file(fp)
            for i, line in enumerate(lines, 1):
                for pattern, message, suggestion in self._PATTERNS:
                    if re.search(pattern, line):
                        self.analyzer.add_issue(
                            check_name=self.name,
                            file_path=fp,
                            line=i,
                            message=message,
                            severity="info",
                            suggestion=suggestion,
                        )
                        break  # one issue per line


# ═══════════════════════════════════════════════════════════════════════════════
# VueCompositionApiDetector  [NEW — Enhancement #15]
# ═══════════════════════════════════════════════════════════════════════════════

class VueCompositionApiDetector(BaseCheck):
    name = "VueCompositionApiDetector"
    description = "Detect Options API patterns that could migrate to Composition API"

    _OPTIONS_KEYS = [
        ("data()", r"\bdata\s*\(\s*\)\s*\{", "Replace data() with reactive()/ref()"),
        ("computed:", r"\bcomputed\s*:\s*\{", "Replace computed properties with computed()"),
        ("watch:", r"\bwatch\s*:\s*\{", "Replace watchers with watch()/watchEffect()"),
        ("methods:", r"\bmethods\s*:\s*\{", "Move methods into <script setup> as plain functions"),
        ("mixins:", r"\bmixins\s*:\s*\[", "Replace mixins with composables (use…() functions)"),
        ("filters:", r"\bfilters\s*:\s*\{", "Filters removed in Vue 3 — use computed or methods"),
    ]

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_vue_file(fp):
                continue
            content = self.read_content(fp)
            lines = self.read_file(fp)

            # Only flag if Vue 3 is likely (check for defineComponent or <script setup>)
            has_setup = "<script setup" in content or "defineComponent" in content
            if has_setup:
                # Already using Composition API; skip
                continue

            for label, pattern, suggestion in self._OPTIONS_KEYS:
                m = re.search(pattern, content)
                if m:
                    line_no = self._find_line_number(lines, m.start())
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=line_no,
                        message=f"Options API pattern detected: {label}",
                        severity="info",
                        suggestion=suggestion,
                    )
