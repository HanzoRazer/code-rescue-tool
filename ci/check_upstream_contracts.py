#!/usr/bin/env python3
"""Check that vendored contracts match upstream producer repo."""
from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

OWNER = "HanzoRazer"
REPO = "code-analysis-tool"

# Allow pinning upstream ref (branch/tag/sha) via env var:
#   UPSTREAM_REF=main (default)
#   UPSTREAM_REF=v1.0.0
#   UPSTREAM_REF=fbf34e1
UPSTREAM_REF = os.environ.get("UPSTREAM_REF", "main").strip() or "main"

UPSTREAM_RAW_BASE = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{UPSTREAM_REF}"

# Optional: also enforce upstream rule registry parity.
# Default is enabled. Set CHECK_RULE_REGISTRY=0 to skip temporarily.
CHECK_RULE_REGISTRY = os.environ.get("CHECK_RULE_REGISTRY", "1").strip() not in {"0", "false", "False", "no", "NO"}

BASE_PAIRS = [
    ("schemas/run_result.schema.json", "contracts/run_result.schema.json"),
]

RULE_REGISTRY_PAIRS = [
    # Producer source-of-truth location (expected):
    #   code-analysis-tool/docs/rule_registry.json
    ("docs/rule_registry.json", "contracts/rule_registry.json"),
]

def pairs() -> list[tuple[str, str]]:
    if CHECK_RULE_REGISTRY:
        return BASE_PAIRS + RULE_REGISTRY_PAIRS
    return BASE_PAIRS

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            # Helps avoid occasional 403s from GitHub for requests without a UA.
            "User-Agent": f"{REPO}-contract-parity-check/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []

    for upstream_rel, local_rel in pairs():
        upstream_url = f"{UPSTREAM_RAW_BASE}/{upstream_rel}"
        local_path = root / local_rel

        if not local_path.exists():
            failures.append(f"Missing local contract file: {local_rel}")
            continue

        try:
            upstream = fetch(upstream_url)
        except Exception as e:
            extra = ""
            if upstream_rel == "docs/rule_registry.json":
                extra = (
                    "\nNote: rule registry parity is enabled.\n"
                    "  - Ensure upstream has docs/rule_registry.json\n"
                    "  - Or temporarily disable with CHECK_RULE_REGISTRY=0\n"
                )
            failures.append(
                f"Failed to fetch upstream contract\n"
                f"  upstream_ref: {UPSTREAM_REF}\n"
                f"  url: {upstream_url}\n"
                f"  error: {e!r}\n"
                f"Fix: set UPSTREAM_REF to a valid branch/tag/sha."
                f"{extra}"
            )
            continue

        local = local_path.read_bytes()

        if upstream != local:
            failures.append(
                f"Contract mismatch: {local_rel}\n"
                f"  upstream_ref: {UPSTREAM_REF}\n"
                f"  upstream: {upstream_url}\n"
                f"  local:    {local_path}\n"
                f"  sha256 upstream: {sha256_bytes(upstream)}\n"
                f"  sha256 local:    {sha256_bytes(local)}\n"
                f"Fix: copy upstream file into {local_rel} and commit.\n"
                f"Tip: run scripts/sync_contracts.sh after setting UPSTREAM_REF."
            )

    if failures:
        print("\n\n".join(failures), file=sys.stderr)
        return 1

    rr = "enabled" if CHECK_RULE_REGISTRY else "disabled"
    print(f"OK: contracts match upstream ({OWNER}/{REPO}@{UPSTREAM_REF}). rule_registry_check={rr}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
