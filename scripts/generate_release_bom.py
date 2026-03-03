"""scripts.generate_release_bom

Generates a release BOM (Bill of Materials) that attests all contract
artifacts shipped in dist/.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

# Producer-side semantic manifests that must be shipped into dist/ and attested in the BOM.
TREESITTER_MANIFEST_SRC = ROOT / "tests" / "contracts" / "treesitter_manifest.json"
TREESITTER_MANIFEST_DIST = DIST / "contracts" / "treesitter_manifest.json"

# Contract version anchor (single source of truth for signal logic version)
CONTRACT_VERSIONS_SRC = ROOT / "src" / "code_audit" / "contracts" / "versions.json"
CONTRACT_VERSIONS_DIST = DIST / "contracts" / "versions.json"

# Rule governance artifacts
RULES_REGISTRY_SRC = ROOT / "src" / "code_audit" / "contracts" / "rules_registry.json"
RULES_REGISTRY_DIST = DIST / "contracts" / "rules_registry.json"
RULE_VERSIONS_SRC = ROOT / "src" / "code_audit" / "contracts" / "rule_versions.json"
RULE_VERSIONS_DIST = DIST / "contracts" / "rule_versions.json"

BOM_PATH = DIST / "release_bom.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _copy_into_dist_path(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


# ---------------------------------------------------------------------------
# BOM generation
# ---------------------------------------------------------------------------

def generate_release_bom(*, write: bool = True) -> dict[str, Any]:
    """Generate and optionally write the release BOM."""
    artifacts: dict[str, Any] = {}

    # JS/TS surface flag
    artifacts["js_ts_surface"] = True

    # ---------------------------------------------------------------------
    # Treesitter manifest attestation
    # ---------------------------------------------------------------------
    if TREESITTER_MANIFEST_SRC.exists():
        _copy_into_dist_path(TREESITTER_MANIFEST_SRC, TREESITTER_MANIFEST_DIST)
        ts_sha = _sha256_file(TREESITTER_MANIFEST_DIST)
        ts_obj = _load_json(TREESITTER_MANIFEST_DIST)
        artifacts["treesitter_manifest"] = {
            "path": TREESITTER_MANIFEST_DIST.relative_to(ROOT).as_posix(),
            "sha256": ts_sha,
            "manifest_version": int(ts_obj.get("manifest_version", 0) or 0),
            "signal_logic_version": str(ts_obj.get("signal_logic_version", "") or ""),
        }

    # ---------------------------------------------------------------------
    # Contract versions attestation (version anchor)
    # ---------------------------------------------------------------------
    if not CONTRACT_VERSIONS_SRC.exists():
        raise SystemExit(f"[release-bom] missing contract versions: {CONTRACT_VERSIONS_SRC.relative_to(ROOT)}")

    _copy_into_dist_path(CONTRACT_VERSIONS_SRC, CONTRACT_VERSIONS_DIST)
    versions_sha = _sha256_file(CONTRACT_VERSIONS_DIST)
    versions_obj = _load_json(CONTRACT_VERSIONS_DIST)

    artifacts["contract_versions"] = {
        "path": CONTRACT_VERSIONS_DIST.relative_to(ROOT).as_posix(),
        "sha256": versions_sha,
        "schema_version": int(versions_obj.get("schema_version", 0) or 0),
        "signal_logic_version": str(versions_obj.get("signal_logic_version", "") or ""),
    }

    # ---------------------------------------------------------------------
    # Rule governance attestations (registry + per-rule versions)
    # ---------------------------------------------------------------------
    if not RULES_REGISTRY_SRC.exists():
        raise SystemExit(f"[release-bom] missing rules registry: {RULES_REGISTRY_SRC.relative_to(ROOT)}")

    _copy_into_dist_path(RULES_REGISTRY_SRC, RULES_REGISTRY_DIST)
    rr_sha = _sha256_file(RULES_REGISTRY_DIST)
    rr_obj = _load_json(RULES_REGISTRY_DIST)

    artifacts["rules_registry"] = {
        "path": RULES_REGISTRY_DIST.relative_to(ROOT).as_posix(),
        "sha256": rr_sha,
        "schema_version": int(rr_obj.get("schema_version", 0) or 0),
        "signal_logic_version": str(rr_obj.get("signal_logic_version", "") or ""),
        "rules_count": int(len(rr_obj.get("rules") or [])),
    }

    if not RULE_VERSIONS_SRC.exists():
        raise SystemExit(f"[release-bom] missing rule versions: {RULE_VERSIONS_SRC.relative_to(ROOT)}")

    _copy_into_dist_path(RULE_VERSIONS_SRC, RULE_VERSIONS_DIST)
    rv_sha = _sha256_file(RULE_VERSIONS_DIST)
    rv_obj = _load_json(RULE_VERSIONS_DIST)

    artifacts["rule_versions"] = {
        "path": RULE_VERSIONS_DIST.relative_to(ROOT).as_posix(),
        "sha256": rv_sha,
        "schema_version": int(rv_obj.get("schema_version", 0) or 0),
        "signal_logic_version": str(rv_obj.get("signal_logic_version", "") or ""),
        "rules_count": int(len((rv_obj.get("rules") or {}).keys())),
    }

    # Build final BOM
    bom: dict[str, Any] = {
        "bom_version": 1,
        "artifacts": artifacts,
    }

    if write:
        BOM_PATH.parent.mkdir(parents=True, exist_ok=True)
        BOM_PATH.write_text(json.dumps(bom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[release-bom] wrote {BOM_PATH.relative_to(ROOT)}")

    return bom


def main() -> int:
    generate_release_bom(write=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
