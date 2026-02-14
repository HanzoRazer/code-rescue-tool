#!/usr/bin/env python3
"""Check that vendored contracts match upstream producer repo."""
from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

# Source-of-truth repo + branch (or use UPSTREAM_REF env var to pin to a tag)
UPSTREAM_REF = os.environ.get("UPSTREAM_REF", "main")
UPSTREAM_RAW_BASE = f"https://raw.githubusercontent.com/HanzoRazer/code-analysis-tool/{UPSTREAM_REF}"

# (upstream_path, local_path)
PAIRS = [
    ("schemas/run_result.schema.json", "contracts/run_result.schema.json"),
]

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []

    print(f"Checking contracts against upstream ref: {UPSTREAM_REF}")

    for upstream_rel, local_rel in PAIRS:
        upstream_url = f"{UPSTREAM_RAW_BASE}/{upstream_rel}"
        local_path = root / local_rel

        if not local_path.exists():
            failures.append(f"Missing local contract file: {local_rel}")
            continue

        upstream = fetch(upstream_url)
        local = local_path.read_bytes()

        if upstream != local:
            failures.append(
                f"Contract mismatch: {local_rel}\n"
                f"  upstream: {upstream_url}\n"
                f"  local:    {local_path}\n"
                f"  sha256 upstream: {sha256_bytes(upstream)}\n"
                f"  sha256 local:    {sha256_bytes(local)}\n"
                f"Fix: copy upstream file into {local_rel} and commit."
            )
        else:
            print(f"  [OK] {local_rel}")

    if failures:
        print("\n" + "\n\n".join(failures), file=sys.stderr)
        return 1

    print("\nOK: contracts match upstream producer repo.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
