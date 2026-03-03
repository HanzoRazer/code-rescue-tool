"""Allow running as ``python -m code_audit``."""
from __future__ import annotations

from code_audit.main import cli_main

if __name__ == "__main__":
    raise SystemExit(cli_main())
