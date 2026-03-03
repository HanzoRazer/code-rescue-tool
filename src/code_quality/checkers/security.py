"""Security checkers.

Checkers:
    SecurityVulnerabilityDetector  — common XSS / eval / crypto patterns
    HardcodedUrlDetector           — hardcoded URLs / IPs / secrets  [NEW]
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from ..base import BaseCheck


# ═══════════════════════════════════════════════════════════════════════════════
# SecurityVulnerabilityDetector  (improved context awareness)
# ═══════════════════════════════════════════════════════════════════════════════

class SecurityVulnerabilityDetector(BaseCheck):
    name = "SecurityVulnerabilityDetector"
    description = "Detect common security vulnerabilities"

    _PATTERNS: list[Tuple[str, str, str, str]] = [
        (r"\beval\s*\(",
         "eval() usage detected",
         "Avoid eval() — use JSON.parse or Function constructor if absolutely needed",
         "critical"),
        (r"\bdocument\.write\s*\(",
         "document.write() usage",
         "Can cause XSS — use DOM manipulation methods instead",
         "critical"),
        (r"\.innerHTML\s*=\s*(?!['\"]\s*['\"]\s*;)",
         "innerHTML assignment with non-empty value",
         "Use textContent, innerText, or a sanitiser library",
         "warning"),
        (r"\bnew\s+Function\s*\(",
         "new Function() — implicit eval",
         "Avoid dynamic code generation",
         "critical"),
        (r"\bMath\.random\s*\(\)",
         "Math.random() is not cryptographically secure",
         "Use crypto.getRandomValues() for security-sensitive randomness",
         "warning"),
        (r"\bdangerouslySetInnerHTML\b",
         "dangerouslySetInnerHTML in React",
         "Ensure content is sanitised before rendering",
         "warning"),
        (r"\bv-html\s*=",
         "v-html directive in Vue template",
         "Can cause XSS — sanitise content or use v-text",
         "warning"),
    ]

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)

            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                    continue

                for pattern, message, suggestion, severity in self._PATTERNS:
                    m = re.search(pattern, line)
                    if m and not self._is_in_string(line, m.start()) and not self._is_in_comment(line, m.start()):
                        self.analyzer.add_issue(
                            check_name=self.name,
                            file_path=fp,
                            line=i,
                            message=message,
                            severity=severity,
                            suggestion=suggestion,
                        )


# ═══════════════════════════════════════════════════════════════════════════════
# HardcodedUrlDetector  [NEW — Enhancement #14]
# ═══════════════════════════════════════════════════════════════════════════════

class HardcodedUrlDetector(BaseCheck):
    name = "HardcodedUrlDetector"
    description = "Detect hardcoded URLs, IPs, and potential secrets"

    _URL_PATTERN = re.compile(
        r"""['"]https?://(?!localhost|127\.0\.0\.1|example\.com|schema\.org|json-schema\.org)[^'"]{8,}['"]"""
    )
    _IP_PATTERN = re.compile(
        r"""['"](\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::\d+)?['"]"""
    )
    _SECRET_PATTERN = re.compile(
        r"""(?:api[_-]?key|secret|token|password|auth)\s*[:=]\s*['"][^'"]{6,}['"]""",
        re.IGNORECASE,
    )

    # Lines that are clearly config / env are OK
    _SKIP_LINE = re.compile(
        r"^\s*(?://|/\*|\*|import\b|require\b|process\.env)", re.IGNORECASE
    )

    def run(self, files: List[Path]) -> None:
        for fp in files:
            if not self._is_frontend_file(fp):
                continue
            lines = self.read_file(fp)

            for i, line in enumerate(lines, 1):
                if self._SKIP_LINE.match(line):
                    continue

                if self._URL_PATTERN.search(line):
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=i,
                        message="Hardcoded URL detected",
                        severity="warning",
                        suggestion="Move to an environment variable or config file",
                    )

                m = self._IP_PATTERN.search(line)
                if m:
                    ip = m.group(1)
                    if ip not in {"127.0.0.1", "0.0.0.0"}:
                        self.analyzer.add_issue(
                            check_name=self.name,
                            file_path=fp,
                            line=i,
                            message=f"Hardcoded IP address: {ip}",
                            severity="warning",
                            suggestion="Use environment variables for host addresses",
                        )

                if self._SECRET_PATTERN.search(line):
                    self.analyzer.add_issue(
                        check_name=self.name,
                        file_path=fp,
                        line=i,
                        message="Possible hardcoded secret/API key",
                        severity="critical",
                        suggestion="Use environment variables or a secrets manager",
                    )
