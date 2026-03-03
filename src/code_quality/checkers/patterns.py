"""Code-pattern checkers.

Checkers:
    CallbackHellDetector       — deeply nested callbacks
    MagicNumberDetector        — magic numbers / strings (FIX: context-aware)
    LongParameterListDetector  — functions with too many params
    DuplicateCodeDetector      — duplicate code blocks (FIX: hash-based O(n))
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ..base import BaseCheck


# ═══════════════════════════════════════════════════════════════════════════════
# CallbackHellDetector  (improved brace-depth tracking)
# ═══════════════════════════════════════════════════════════════════════════════

class CallbackHellDetector(BaseCheck):
    name = "CallbackHellDetector"
    description = "Detect deeply nested callbacks (callback hell)"

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)

            # Track callback nesting by counting function(…){ and => {
            callback_depth = 0
            depths: List[Tuple[int, int]] = []  # (line, depth)
            brace_stack: List[str] = []  # 'cb' or 'other'

            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("/*"):
                    continue

                # Detect callback openers
                cb_opens = len(re.findall(
                    r"(?:function\s*\([^)]*\)|(?:\([^)]*\)|[\w$]+)\s*=>)\s*\{",
                    line,
                ))
                other_opens = line.count("{") - cb_opens
                closes = line.count("}")

                for _ in range(cb_opens):
                    callback_depth += 1
                    brace_stack.append("cb")
                for _ in range(max(0, other_opens)):
                    brace_stack.append("other")

                for _ in range(closes):
                    if brace_stack:
                        tag = brace_stack.pop()
                        if tag == "cb":
                            callback_depth -= 1

                if callback_depth >= 3:
                    depths.append((i, callback_depth))

            for line_no, depth in depths:
                self.analyzer.add_issue(
                    check_name=self.name,
                    file_path=fp,
                    line=line_no,
                    message=f"Deep callback nesting detected (depth: {depth})",
                    severity="warning",
                    suggestion="Use Promises or async/await to flatten the structure",
                )


# ═══════════════════════════════════════════════════════════════════════════════
# MagicNumberDetector  (FIX: skip consts, imports, comments)
# ═══════════════════════════════════════════════════════════════════════════════

class MagicNumberDetector(BaseCheck):
    name = "MagicNumberDetector"
    description = "Detect magic numbers (context-aware)"
    fixable = True

    _ALLOWED = frozenset({0, 1, -1, 2, 10, 100, 1000, 24, 60, 360, 255})
    _SKIP_LINE = re.compile(
        r"^\s*(?:import\b|export\b|const\b|let\b|var\b|//|/\*|\*)", re.IGNORECASE
    )

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)

            for i, line in enumerate(lines, 1):
                # Skip declarations, imports, and comments
                if self._SKIP_LINE.match(line):
                    continue

                for m in re.finditer(r"(?<![.\w])(-?\d{2,})(?!\.\w)", line):
                    col = m.start()
                    if self._is_in_string(line, col) or self._is_in_comment(line, col):
                        continue
                    try:
                        num = int(m.group(1))
                    except ValueError:
                        continue
                    if num in self._ALLOWED:
                        continue
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=i,
                        message=f"Magic number '{m.group(1)}' detected",
                        severity="info",
                        suggestion="Extract to a named constant",
                    )

    def fix(self, file_path: Path, issue: Dict[str, Any]) -> str | None:
        """Extract the magic number into a const at the top of the scope."""
        lines = self.read_file(file_path)
        line_idx = issue["line"] - 1
        if line_idx >= len(lines):
            return None
        line = lines[line_idx]
        m = re.search(r"(?<![.\w])(-?\d{2,})(?!\.\w)", line)
        if not m:
            return None
        num = m.group(1)
        const_name = f"MAGIC_{num}"
        declaration = f"const {const_name} = {num};\n"
        new_line = line[: m.start()] + const_name + line[m.end() :]
        lines[line_idx] = new_line
        # Insert const after any imports at top
        insert_at = 0
        for j, l in enumerate(lines):
            if l.strip().startswith("import "):
                insert_at = j + 1
        lines.insert(insert_at, declaration)
        return "".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# LongParameterListDetector  (also detects arrow functions & methods)
# ═══════════════════════════════════════════════════════════════════════════════

class LongParameterListDetector(BaseCheck):
    name = "LongParameterListDetector"
    description = "Detect functions with too many parameters"

    _FUNC_PATTERNS = [
        re.compile(r"function\s+\w+\s*\(([^)]*)\)"),                # named fn
        re.compile(r"(?:const|let|var)\s+\w+\s*=\s*\(([^)]*)\)\s*=>"),  # arrow
        re.compile(r"(\w+)\s*\(([^)]*)\)\s*\{"),                    # method
    ]

    def run(self, files: List[Path]) -> None:
        max_params = self.analyzer.config.get("max_params", 4)

        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)
            content = self.read_content(fp)

            for pattern in self._FUNC_PATTERNS:
                for m in pattern.finditer(content):
                    params_str = m.group(m.lastindex or 1)
                    params = [p.strip() for p in params_str.split(",") if p.strip()]
                    if len(params) > max_params:
                        line_no = self._find_line_number(lines, m.start())
                        self.analyzer.add_issue(
                            check_name=self.name,
                            file_path=fp,
                            line=line_no,
                            message=f"Function has {len(params)} parameters",
                            severity="info",
                            suggestion="Use an options object instead of many positional parameters",
                        )


# ═══════════════════════════════════════════════════════════════════════════════
# DuplicateCodeDetector  (FIX: hash-based fingerprinting ≈ O(n))
# ═══════════════════════════════════════════════════════════════════════════════

class DuplicateCodeDetector(BaseCheck):
    name = "DuplicateCodeDetector"
    description = "Detect duplicate code blocks via line-hash fingerprinting"

    def run(self, files: List[Path]) -> None:
        block_size = self.analyzer.config.get("duplicate_block_size", 5)

        # Map: (hash of normalised block) → list of (file, start_line)
        fingerprints: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
        reported: Set[str] = set()

        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)
            normalised = [l.strip() for l in lines]

            for start in range(len(normalised) - block_size + 1):
                block = "\n".join(normalised[start : start + block_size])
                # Skip trivial blocks (empty, braces-only)
                if len(block.replace("\n", "").strip()) < 20:
                    continue
                h = hashlib.md5(block.encode()).hexdigest()
                fingerprints[h].append((str(fp), start + 1))

        for h, locations in fingerprints.items():
            if len(locations) < 2:
                continue
            # Only report each (file1, file2) pair once
            for idx, (f1, l1) in enumerate(locations):
                for f2, l2 in locations[idx + 1 :]:
                    if f1 == f2 and abs(l1 - l2) < block_size:
                        continue  # overlapping in same file
                    key = f"{f1}:{l1}-{f2}:{l2}"
                    if key in reported:
                        continue
                    reported.add(key)
                    other = f2 if f1 != f2 else f"line {l2}"
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=Path(f1),
                        line=l1,
                        message="Duplicate code block detected",
                        severity="warning",
                        suggestion=f"Similar code found in {Path(other).name}. Extract to a shared utility.",
                    )
                    break  # one report per block per file
