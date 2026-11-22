"""The one-time semantic_hash LF re-measurement must stay consistent.

Full re-derivation needs git history (run
`python scripts/migrations/semantic_hash_lf_2026_11_21.py --verify`); CI's
shallow checkout lacks the base commit. These checks need no git history:
- each recorded `new` hash really is the rule hash of the recorded
  LF-normalized file hashes (the manifest cannot claim an arbitrary value);
- the ledger holds the corrected value, and the CRLF value it replaced is
  gone, i.e. history was corrected in place, not appended to.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "src" / "code_audit" / "contracts"
MANIFEST = CONTRACTS / "migrations" / "semantic_hash_lf_2026-11-21.json"
LEDGER = CONTRACTS / "rule_versions.json"

_spec = importlib.util.spec_from_file_location(
    "semantic_hash_lf_migration", ROOT / "scripts" / "migrations" / "semantic_hash_lf_2026_11_21.py"
)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_manifest_new_hashes_derive_from_recorded_inputs() -> None:
    manifest = _load(MANIFEST)
    assert manifest["base_commit"] == migration.BASE_COMMIT
    for rid, m in manifest["rules"].items():
        assert m["new"] == migration.rule_hash(rid, m["file_sha256_lf"]), rid
        assert m["new"] != m["old"], rid


def test_ledger_corrected_in_place_not_appended() -> None:
    manifest = _load(MANIFEST)
    ledger = _load(LEDGER)["rules"]
    for rid, m in manifest["rules"].items():
        history = ledger[rid]["history"]
        assert m["new"] in history, f"{rid}: corrected hash missing from history"
        assert m["old"] not in history, f"{rid}: CRLF measurement still in history"
        assert ledger[rid]["rule_logic_version"] == len(history), rid
