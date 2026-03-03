"""Runtime / async checkers.

Checkers:
    MemoryLeakPatternDetector        — missing cleanup for intervals, listeners, etc.
                                       (FIX: whole-file scan for cleanup)
    UnhandledPromiseDetector         — .then() without .catch(), async without try/catch  [NEW]
    AwaitInLoopDetector              — await inside for/while loops  [NEW]
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from ..base import BaseCheck


# ═══════════════════════════════════════════════════════════════════════════════
# MemoryLeakPatternDetector  (FIX: whole-file cleanup scan)
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryLeakPatternDetector(BaseCheck):
    name = "MemoryLeakPatternDetector"
    description = "Detect common memory leak patterns (missing cleanup)"

    _PAIRS = [
        ("setInterval", "clearInterval",
         "setInterval without clearInterval",
         "Clear intervals in beforeDestroy / onUnmounted"),
        ("setTimeout", "clearTimeout",
         "setTimeout without clearTimeout (if stored)",
         "Clear timeouts when they may outlive the component"),
        ("addEventListener", "removeEventListener",
         "addEventListener without removeEventListener",
         "Remove listeners in beforeDestroy / onUnmounted"),
        ("new WebSocket", ".close(",
         "WebSocket opened without close()",
         "Close WebSocket connections when unmounting"),
        ("new MutationObserver", ".disconnect(",
         "MutationObserver without disconnect()",
         "Disconnect observers in cleanup hooks"),
        ("new IntersectionObserver", ".disconnect(",
         "IntersectionObserver without disconnect()",
         "Disconnect observers in cleanup hooks"),
    ]

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)
            content = self.read_content(fp)

            for opener, closer, message, suggestion in self._PAIRS:
                # Find all openers and check if the closer exists *anywhere* in file
                for m in re.finditer(re.escape(opener), content):
                    if closer not in content:
                        line_no = self._find_line_number(lines, m.start())
                        self.analyzer.add_issue(
                            check_name=self.name,
                            file_path=fp,
                            line=line_no,
                            message=message,
                            severity="critical",
                            suggestion=suggestion,
                        )
                        break  # one report per pattern per file


# ═══════════════════════════════════════════════════════════════════════════════
# UnhandledPromiseDetector  [NEW — Enhancement #11]
# ═══════════════════════════════════════════════════════════════════════════════

class UnhandledPromiseDetector(BaseCheck):
    name = "UnhandledPromiseDetector"
    description = "Detect Promises without error handling"

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)
            content = self.read_content(fp)

            # .then() without .catch()
            # Look for chains: .then(…) NOT followed by .catch(…) within ~200 chars
            for m in re.finditer(r"\.then\s*\(", content):
                # Scan forward for .catch within the chain
                after = content[m.end() : m.end() + 500]
                if ".catch(" not in after and ".catch (" not in after:
                    line_no = self._find_line_number(lines, m.start())
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=line_no,
                        message=".then() without .catch() — unhandled rejection",
                        severity="warning",
                        suggestion="Add .catch() or use async/await with try/catch",
                    )

            # async functions without try/catch
            for m in re.finditer(r"\basync\s+(?:function\s+\w+|(?:\w+|\([^)]*\))\s*=>)\s*\{", content):
                body_start = m.end()
                # Scan the function body for try{
                body_slice = content[body_start : body_start + 2000]
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
                has_await = "await " in body or "await(" in body
                has_try = "try" in body and "catch" in body
                if has_await and not has_try:
                    line_no = self._find_line_number(lines, m.start())
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=line_no,
                        message="Async function with await but no try/catch",
                        severity="warning",
                        suggestion="Wrap await calls in try/catch for error handling",
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# AwaitInLoopDetector  [NEW — Enhancement #12]
# ═══════════════════════════════════════════════════════════════════════════════

class AwaitInLoopDetector(BaseCheck):
    name = "AwaitInLoopDetector"
    description = "Detect await inside loops (sequential I/O that should be parallel)"

    _LOOP_START = re.compile(
        r"\b(?:for\s*\(|for\s+\w+\s+(?:of|in)|while\s*\(|do\s*\{)"
    )

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)
            content = self.read_content(fp)

            for loop_m in self._LOOP_START.finditer(content):
                # Find loop body
                body_start = content.find("{", loop_m.end())
                if body_start == -1:
                    continue
                body_slice = content[body_start + 1 : body_start + 3000]
                depth = 1
                body_end = 0
                for idx, ch in enumerate(body_slice):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            body_end = idx
                            break
                body = body_slice[:body_end]

                # Check for await in the loop body (not in nested async functions)
                # Simple approach: look for "await " not inside a nested async
                if re.search(r"\bawait\s", body):
                    line_no = self._find_line_number(lines, loop_m.start())
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=line_no,
                        message="await used inside a loop — sequential I/O",
                        severity="warning",
                        suggestion="Collect promises and use Promise.all() for parallel execution",
                    )
