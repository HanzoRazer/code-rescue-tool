"""scripts.refresh_treesitter_manifest

Regenerates the treesitter_manifest.json that records SHA-256 hashes
of every file in the tree-sitter semantic surface (queries, parsers,
analyzers, version anchor, rule governance artifacts, vendored grammars).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
VERSIONS_PATH = ROOT / "src" / "code_audit" / "contracts" / "versions.json"
OUT = ROOT / "tests" / "contracts" / "treesitter_manifest.json"

VENDORED_DIR = ROOT / "src" / "code_audit" / "data" / "treesitter" / "vendor"
QUERIES_DIR = ROOT / "src" / "code_audit" / "data" / "treesitter" / "queries"
RULES_REGISTRY_PATH = ROOT / "src" / "code_audit" / "contracts" / "rules_registry.json"
RULE_VERSIONS_PATH = ROOT / "src" / "code_audit" / "contracts" / "rule_versions.json"
WRAPPER_FILES = [
    ROOT / "src" / "code_audit" / "parsers" / "tree_sitter_loader.py",
    ROOT / "src" / "code_audit" / "parsers" / "tree_sitter_js.py",
    ROOT / "src" / "code_audit" / "analyzers" / "js_ts_security.py",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _signal_logic_version() -> str:
    obj = _load_json(VERSIONS_PATH)
    v = obj.get("signal_logic_version")
    if not isinstance(v, str) or not v.startswith("signals_v"):
        raise SystemExit("Invalid signal_logic_version in versions.json")
    return v


def _iter_vendor_files(vendor_dir: Path):
    """Yield all files under the vendor directory (if it exists)."""
    if not vendor_dir.exists():
        return
    for p in sorted(vendor_dir.rglob("*")):
        if p.is_file():
            yield p


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------

def build_manifest() -> dict:
    files: Dict[str, str] = {}

    # Version anchor is part of semantic governance. If it changes, the gate
    # must force a manifest refresh + signal_logic_version bump decisions.
    if not VERSIONS_PATH.exists():
        raise SystemExit(f"Missing version anchor: {VERSIONS_PATH.relative_to(ROOT)}")
    files[VERSIONS_PATH.relative_to(ROOT).as_posix()] = _sha256_file(VERSIONS_PATH)

    # Rule governance artifacts are part of the semantic surface (they drive
    # per-rule versioning/attestation and must not drift silently).
    if not RULES_REGISTRY_PATH.exists():
        raise SystemExit(f"Missing rules registry: {RULES_REGISTRY_PATH.relative_to(ROOT)}")
    files[RULES_REGISTRY_PATH.relative_to(ROOT).as_posix()] = _sha256_file(RULES_REGISTRY_PATH)

    if not RULE_VERSIONS_PATH.exists():
        raise SystemExit(f"Missing rule versions: {RULE_VERSIONS_PATH.relative_to(ROOT)}")
    files[RULE_VERSIONS_PATH.relative_to(ROOT).as_posix()] = _sha256_file(RULE_VERSIONS_PATH)

    # Vendored grammars (if present)
    for p in _iter_vendor_files(VENDORED_DIR):
        rel = p.relative_to(ROOT).as_posix()
        files[rel] = _sha256_file(p)

    # Query files
    if QUERIES_DIR.exists():
        for p in sorted(QUERIES_DIR.rglob("*")):
            if p.is_file():
                rel = p.relative_to(ROOT).as_posix()
                files[rel] = _sha256_file(p)

    # Wrapper / analyzer files
    for wp in WRAPPER_FILES:
        if wp.exists():
            rel = wp.relative_to(ROOT).as_posix()
            files[rel] = _sha256_file(wp)

    return {
        "manifest_version": 1,
        "signal_logic_version": _signal_logic_version(),
        "generated_by": "scripts/refresh_treesitter_manifest.py",
        "files": dict(sorted(files.items())),
    }


def main() -> int:
    manifest = build_manifest()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"[treesitter-manifest] wrote {OUT.relative_to(ROOT)} ({len(manifest['files'])} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
