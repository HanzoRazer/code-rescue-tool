"""scripts.check_release_bom_consistency

Post-generation consistency checker: validates that a release BOM's
attestations match the actual dist/ artifacts on disk.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _req(obj: dict, key: str, ctx: str) -> Any:
    """Return obj[key] or raise with a clear message."""
    if key not in obj:
        raise AssertionError(f"{ctx} missing required key: {key}")
    return obj[key]


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------

def check_release_bom_consistency(bom: dict[str, Any]) -> None:
    """Raise AssertionError on any inconsistency."""
    artifacts = bom.get("artifacts")
    assert isinstance(artifacts, dict), "BOM must contain 'artifacts' object"

    # -----------------------------------------------------------------
    # Contract versions attestation must always exist and be self-consistent.
    # -----------------------------------------------------------------
    if "contract_versions" not in artifacts:
        raise AssertionError("artifacts.contract_versions is required in the BOM.")

    cv = artifacts["contract_versions"]
    ctx = "artifacts.contract_versions"
    relp = _req(cv, "path", ctx)
    expected_sha = _req(cv, "sha256", ctx)
    expected_schema_v = _req(cv, "schema_version", ctx)
    expected_slv = _req(cv, "signal_logic_version", ctx)

    assert isinstance(relp, str) and relp.endswith("dist/contracts/versions.json"), \
        f"{ctx}.path invalid: {relp}"

    p = (ROOT / relp).resolve()
    assert p.exists(), f"{ctx}.path does not exist: {relp}"
    got = _sha256_file(p)
    assert got == expected_sha, f"{ctx}.sha256 mismatch: expected={expected_sha} got={got}"

    obj = json.loads(p.read_text(encoding="utf-8"))
    assert obj.get("schema_version") == expected_schema_v, f"{ctx}.schema_version mismatch vs file"
    assert obj.get("signal_logic_version") == expected_slv, f"{ctx}.signal_logic_version mismatch vs file"

    # -----------------------------------------------------------------
    # Rule governance artifacts must exist and align with the version anchor.
    # -----------------------------------------------------------------
    def _check_rule_artifact(key: str, expected_path_suffix: str) -> dict:
        if key not in artifacts:
            raise AssertionError(f"artifacts.{key} is required in the BOM.")
        a = artifacts[key]
        assert isinstance(a, dict), f"artifacts.{key} must be an object"
        ctx2 = f"artifacts.{key}"
        relp = _req(a, "path", ctx2)
        ex_sha = _req(a, "sha256", ctx2)
        ex_sv = _req(a, "schema_version", ctx2)
        ex_slv2 = _req(a, "signal_logic_version", ctx2)
        _req(a, "rules_count", ctx2)
        assert isinstance(relp, str) and relp.endswith(expected_path_suffix), f"{ctx2}.path invalid: {relp}"
        fp = (ROOT / relp).resolve()
        assert fp.exists(), f"{ctx2}.path does not exist: {relp}"
        got = _sha256_file(fp)
        assert got == ex_sha, f"{ctx2}.sha256 mismatch: expected={ex_sha} got={got}"
        o = json.loads(fp.read_text(encoding="utf-8"))
        assert o.get("schema_version") == ex_sv, f"{ctx2}.schema_version mismatch vs file"
        assert o.get("signal_logic_version") == ex_slv2, f"{ctx2}.signal_logic_version mismatch vs file"
        # Must align to contract version anchor signal logic version
        assert ex_slv2 == expected_slv, f"{ctx2}.signal_logic_version must match contract_versions"
        return o

    rr_obj = _check_rule_artifact("rules_registry", "dist/contracts/rules_registry.json")
    rv_obj = _check_rule_artifact("rule_versions", "dist/contracts/rule_versions.json")

    # Tighten: BOM-declared rule counts must match file contents.
    rr_art = artifacts.get("rules_registry")
    rv_art = artifacts.get("rule_versions")
    if isinstance(rr_art, dict):
        declared = rr_art.get("rules_count")
        actual = len(rr_obj.get("rules") or []) if isinstance(rr_obj.get("rules"), list) else None
        assert declared == actual, f"artifacts.rules_registry.rules_count mismatch: declared={declared} actual={actual}"
    if isinstance(rv_art, dict):
        declared = rv_art.get("rules_count")
        actual = len((rv_obj.get("rules") or {}).keys()) if isinstance(rv_obj.get("rules"), dict) else None
        assert declared == actual, f"artifacts.rule_versions.rules_count mismatch: declared={declared} actual={actual}"

    # Cross-check: rule_versions must cover all rule_ids in rules_registry.
    rr_rules = rr_obj.get("rules") or []
    rv_rules = rv_obj.get("rules") or {}
    if isinstance(rr_rules, list) and isinstance(rv_rules, dict):
        rr_ids = sorted([r.get("rule_id") for r in rr_rules if isinstance(r, dict) and isinstance(r.get("rule_id"), str)])
        for rid in rr_ids:
            assert rid in rv_rules, f"rule_versions missing entry for {rid}"

        # Cross-check: semantic_hash must match registry per rule, and rule_versions
        # entries must satisfy evolution policy invariants.
        reg_hash_by_id: dict[str, str] = {}
        for r in rr_rules:
            if not isinstance(r, dict):
                continue
            rid = r.get("rule_id")
            rh = r.get("semantic_hash")
            if isinstance(rid, str) and isinstance(rh, str):
                reg_hash_by_id[rid] = rh
        for rid, rh in reg_hash_by_id.items():
            ent = rv_rules.get(rid)
            assert isinstance(ent, dict), f"rule_versions[{rid}] must be an object"
            assert ent.get("semantic_hash") == rh, f"rule_versions[{rid}].semantic_hash must match rules_registry"
            v = ent.get("rule_logic_version")
            hist = ent.get("history")
            assert isinstance(v, int) and v >= 1, f"rule_versions[{rid}].rule_logic_version must be integer>=1"
            assert isinstance(hist, list) and len(hist) >= 1, f"rule_versions[{rid}].history must be non-empty array"
            assert v == len(hist), f"rule_versions[{rid}] rule_logic_version must equal len(history)"
            assert ent.get("semantic_hash") == hist[-1], f"rule_versions[{rid}] semantic_hash must equal history[-1]"
            for i in range(1, len(hist)):
                assert hist[i] != hist[i - 1], f"rule_versions[{rid}].history must not contain adjacent duplicates"

    # -----------------------------------------------------------------
    # Absolute strictest rule in consistency checker:
    # - artifacts.js_ts_surface is canonical declaration.
    # - If true, treesitter_manifest is required (mirrors schema).
    # - Defense-in-depth: RELEASE_ENABLE_JS_TS=true requires js_ts_surface=true.
    # -----------------------------------------------------------------
    rel_enable = (os.environ.get("RELEASE_ENABLE_JS_TS", "") or "").strip().lower() in ("1", "true", "yes", "y", "on")
    assert isinstance(artifacts, dict), "release_bom.artifacts must be an object"
    js_ts_surface = artifacts.get("js_ts_surface")
    if rel_enable and js_ts_surface is not True:
        raise AssertionError("RELEASE_ENABLE_JS_TS=true requires artifacts.js_ts_surface=true in the BOM.")

    if js_ts_surface is True and ("treesitter_manifest" not in artifacts):
        raise AssertionError("artifacts.js_ts_surface=true requires artifacts.treesitter_manifest.")

    # -----------------------------------------------------------------
    # Tree-sitter manifest attestation
    # - If js_ts_surface=true, it is required (already enforced above)
    # - If present, dist artifact must exist and sha256 must match
    # - If present, its signal_logic_version must match contract_versions
    # -----------------------------------------------------------------
    if "treesitter_manifest" in artifacts:
        tm = artifacts["treesitter_manifest"]
        ctx3 = "artifacts.treesitter_manifest"
        tm_relp = _req(tm, "path", ctx3)
        tm_sha = _req(tm, "sha256", ctx3)
        expected_mv = _req(tm, "manifest_version", ctx3)
        tm_slv = _req(tm, "signal_logic_version", ctx3)

        assert isinstance(tm_relp, str) and tm_relp.endswith("dist/contracts/treesitter_manifest.json"), \
            f"{ctx3}.path invalid: {tm_relp}"
        tm_p = (ROOT / tm_relp).resolve()
        assert tm_p.exists(), f"{ctx3}.path does not exist: {tm_relp}"
        tm_got = _sha256_file(tm_p)
        assert tm_got == tm_sha, f"{ctx3}.sha256 mismatch: expected={tm_sha} got={tm_got}"

        # Lightweight sanity: ensure the file is JSON and has required fields.
        tm_obj = json.loads(tm_p.read_text(encoding="utf-8"))
        assert tm_obj.get("manifest_version") == expected_mv, f"{ctx3}.manifest_version mismatch vs file"
        assert tm_obj.get("signal_logic_version") == tm_slv, f"{ctx3}.signal_logic_version mismatch vs file"

        # Align tree-sitter manifest to the contract version anchor.
        # contract_versions is required by schema motif.
        cv = artifacts.get("contract_versions")
        assert isinstance(cv, dict), "artifacts.contract_versions must be an object"
        cv_slv = _req(cv, "signal_logic_version", "artifacts.contract_versions")
        assert tm_slv == cv_slv, f"{ctx3}.signal_logic_version must match artifacts.contract_versions.signal_logic_version"


def main() -> int:
    bom_path = ROOT / "dist" / "release_bom.json"
    if not bom_path.exists():
        raise SystemExit(f"[check-bom] missing BOM: {bom_path.relative_to(ROOT)}")
    bom = json.loads(bom_path.read_text(encoding="utf-8"))
    check_release_bom_consistency(bom)
    print("[check-bom] all consistency checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
