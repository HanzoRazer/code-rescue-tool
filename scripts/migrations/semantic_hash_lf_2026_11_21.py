#!/usr/bin/env python3
"""One-time migration: re-measure pinned semantic hashes with LF-normalized input.

Why: semantic_hash was sha256 over raw file bytes, and the pinned values were
refreshed on a Windows (CRLF) checkout. Linux CI checks the same source out
with LF, so the hashes could never be reproduced there. The hashing now
normalizes CRLF -> LF (scripts/refresh_rules_registry.py). The pinned values
must be re-measured under that rule.

This is a CORRECTION OF MEASUREMENT, not a logic change, so it does not
append history or bump rule_logic_version (that would record a change that
never happened). It is the one sanctioned exception to the append-only
ledger, and is scoped tightly:

- It applies only to BASE_COMMIT's source, read from git, never the working
  tree. A real source change made afterwards cannot ride along; it must go
  through refresh_rules_registry.py / refresh_rule_versions.py as usual.
- Before rewriting anything it proves that the pinned hash equals the CRLF
  measurement of that same source, i.e. the only difference is line endings.
- It rewrites only semantic_hash and history[-1]; earlier history entries
  are left as recorded.
- It writes MANIFEST listing every rewritten value and its inputs.
- It has no flags for other commits or rules. It cannot be reused.

Usage:
  python scripts/migrations/semantic_hash_lf_2026_11_21.py           # apply
  python scripts/migrations/semantic_hash_lf_2026_11_21.py --verify  # re-derive and compare with MANIFEST
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = "95bbd445c1a1243b16e030da9e6da74c1b8cae4f"
CONTRACTS = ROOT / "src" / "code_audit" / "contracts"
REGISTRY = CONTRACTS / "rules_registry.json"
LEDGER = CONTRACTS / "rule_versions.json"
MANIFEST = CONTRACTS / "migrations" / "semantic_hash_lf_2026-11-21.json"
REG_REL = "src/code_audit/contracts/rules_registry.json"
LEDGER_REL = "src/code_audit/contracts/rule_versions.json"


def _git_blob(path: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", f"{BASE_COMMIT}:{path}"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _lf(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def _crlf(b: bytes) -> bytes:
    return _lf(b).replace(b"\n", b"\r\n")


def stable_join_hash(parts: list[str]) -> str:
    h = hashlib.sha256()
    for x in parts:
        h.update(x.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def rule_hash(rule_id: str, file_sha256: dict[str, str]) -> str:
    """Same construction as refresh_rules_registry.py, from per-file hashes."""
    return stable_join_hash([rule_id] + [f"{p}:{file_sha256[p]}" for p in sorted(file_sha256)])


def derive() -> dict:
    base_registry = json.loads(_git_blob(REG_REL))
    base_ledger = json.loads(_git_blob(LEDGER_REL))["rules"]
    rules: dict[str, dict] = {}
    for r in base_registry["rules"]:
        rid = r["rule_id"]
        inputs = sorted(set(r["semantic_inputs"]))
        blobs = {p: _git_blob(p) for p in inputs}
        old = base_ledger[rid]["semantic_hash"]
        crlf_measure = rule_hash(rid, {p: _sha(_crlf(b)) for p, b in blobs.items()})
        if crlf_measure != old:
            raise SystemExit(
                f"{rid}: pinned hash is not the CRLF measurement of {BASE_COMMIT[:7]}'s "
                "source -- the difference is not only line endings. Refusing."
            )
        lf_files = {p: _sha(_lf(b)) for p, b in blobs.items()}
        rules[rid] = {"old": old, "new": rule_hash(rid, lf_files), "file_sha256_lf": lf_files}
    return {
        "migration": "semantic_hash_lf_2026-11-21",
        "base_commit": BASE_COMMIT,
        "reason": (
            "semantic_hash was sha256 over raw bytes, pinned from a CRLF checkout; "
            "re-measured over CRLF->LF normalized content. Measurement correction "
            "only: no source change, so no history append or rule_logic_version bump."
        ),
        "rewrites": ["rules_registry.json: semantic_hash", "rule_versions.json: semantic_hash, history[-1]"],
        "rules": rules,
    }


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def main() -> int:
    manifest = derive()
    if "--verify" in sys.argv[1:]:
        recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if recorded != manifest:
            print("MANIFEST does not match re-derivation from git", file=sys.stderr)
            return 1
        print(f"OK: {MANIFEST.relative_to(ROOT)} re-derives from {BASE_COMMIT[:7]}")
        return 0

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    for r in registry["rules"]:
        m = manifest["rules"][r["rule_id"]]
        if r["semantic_hash"] != m["old"]:
            raise SystemExit(f"{r['rule_id']}: registry no longer at the migrated value; refusing")
        r["semantic_hash"] = m["new"]
    for rid, m in manifest["rules"].items():
        ent = ledger["rules"][rid]
        if ent["semantic_hash"] != m["old"] or ent["history"][-1] != m["old"]:
            raise SystemExit(f"{rid}: ledger no longer at the migrated value; refusing")
        ent["semantic_hash"] = m["new"]
        ent["history"][-1] = m["new"]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(_dump(registry), encoding="utf-8")
    LEDGER.write_text(_dump(ledger), encoding="utf-8")
    MANIFEST.write_text(_dump(manifest), encoding="utf-8")
    print(f"Migrated {len(manifest['rules'])} rules; manifest: {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
