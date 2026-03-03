"""scripts.check_release_bom_generator_gate

Pre-release gate: generates a temporary BOM and validates it against the
release_bom schema and consistency checks.  Designed to run in CI before
the real release BOM is cut.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
BOM_SCHEMA = ROOT / "schemas" / "release_bom.schema.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _issue(code: str, location: str, expected: str, actual: str) -> dict[str, str]:
    return {
        "code": code,
        "location": location,
        "expected": expected,
        "actual": actual,
    }


def run_release_bom_consistency_check(*, bom_obj: dict[str, Any], root: Path) -> list[dict[str, str]]:
    """Wrapper: converts AssertionError-based consistency checks into issue dicts."""
    from scripts.check_release_bom_consistency import check_release_bom_consistency

    try:
        check_release_bom_consistency(bom_obj)
    except AssertionError as exc:
        return [_issue("consistency_failure", "release_bom.json", "consistent BOM", str(exc))]
    return []


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

def check_release_bom_generator_gate() -> list[dict[str, str]]:
    """Generate a temporary BOM and validate it.  Returns list of issues (empty = pass)."""
    issues: list[dict[str, str]] = []

    # Import here to avoid circular imports at module level
    from scripts.generate_release_bom import generate_release_bom

    try:
        tmp_obj = generate_release_bom(write=False)
    except SystemExit as exc:
        issues.append(_issue(
            "generator_failure",
            "scripts/generate_release_bom.py",
            "successful generation",
            str(exc),
        ))
        return issues

    # Schema validation
    if BOM_SCHEMA.exists():
        schema = json.loads(BOM_SCHEMA.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(instance=tmp_obj, schema=schema)
        except jsonschema.ValidationError as exc:
            issues.append(_issue(
                "schema_validation",
                "release_bom.json",
                "valid against release_bom.schema.json",
                str(exc.message),
            ))
    else:
        issues.append(_issue(
            "missing_schema",
            "schemas/release_bom.schema.json",
            "existing schema file",
            "<missing>",
        ))

    if not issues:
        # Defense-in-depth (even though schema + generator enforce required keys):
        # Validate types for required artifacts and ensure their dist paths exist.
        arts = tmp_obj.get("artifacts")
        if not isinstance(arts, dict):
            issues.append(_issue(
                "invalid_required_artifact",
                "release_bom.json:artifacts",
                "object",
                type(arts).__name__,
            ))
        else:
            # js_ts_surface required boolean
            js_ts_surface = arts.get("js_ts_surface")
            if not isinstance(js_ts_surface, bool):
                issues.append(_issue(
                    "invalid_required_artifact",
                    "release_bom.json:artifacts.js_ts_surface",
                    "boolean",
                    js_ts_surface,
                ))

            def _require_dist_path(key: str, expected_rel: str) -> None:
                a = arts.get(key)
                if not isinstance(a, dict):
                    issues.append(_issue(
                        "invalid_required_artifact",
                        f"release_bom.json:artifacts.{key}",
                        "object",
                        type(a).__name__,
                    ))
                    return
                rel = a.get("path")
                if not isinstance(rel, str) or rel != expected_rel:
                    issues.append(_issue(
                        "invalid_required_artifact",
                        f"release_bom.json:artifacts.{key}.path",
                        expected_rel,
                        rel,
                    ))
                    return
                p = (ROOT / rel).resolve()
                if not p.exists():
                    issues.append(_issue(
                        "missing_dist_artifact",
                        f"release_bom.json:artifacts.{key}.path",
                        f"existing {expected_rel}",
                        str(p),
                    ))

            # Required by schema motif
            _require_dist_path("contract_versions", "dist/contracts/versions.json")
            _require_dist_path("rules_registry", "dist/contracts/rules_registry.json")
            _require_dist_path("rule_versions", "dist/contracts/rule_versions.json")

            # Tighten: if js_ts_surface=true, treesitter_manifest must exist and be valid.
            if js_ts_surface is True:
                a = arts.get("treesitter_manifest")
                if not isinstance(a, dict):
                    issues.append(_issue(
                        "invalid_required_artifact",
                        "release_bom.json:artifacts.treesitter_manifest",
                        "object (required when js_ts_surface=true)",
                        type(a).__name__,
                    ))
                else:
                    rel = a.get("path")
                    if not isinstance(rel, str) or rel != "dist/contracts/treesitter_manifest.json":
                        issues.append(_issue(
                            "invalid_required_artifact",
                            "release_bom.json:artifacts.treesitter_manifest.path",
                            "dist/contracts/treesitter_manifest.json",
                            rel,
                        ))
                    else:
                        p = (ROOT / rel).resolve()
                        if not p.exists():
                            issues.append(_issue(
                                "missing_dist_artifact",
                                "release_bom.json:artifacts.treesitter_manifest.path",
                                "existing dist/contracts/treesitter_manifest.json",
                                str(p),
                            ))
                        else:
                            # Align treesitter_manifest.signal_logic_version to contract_versions.
                            try:
                                ts_obj = json.loads(p.read_text(encoding="utf-8"))
                            except Exception:
                                ts_obj = None
                            cv_art = arts.get("contract_versions")
                            cv_rel = cv_art.get("path") if isinstance(cv_art, dict) else None
                            cv_obj = None
                            if isinstance(cv_rel, str):
                                cvp = (ROOT / cv_rel).resolve()
                                try:
                                    if cvp.exists():
                                        cv_obj = json.loads(cvp.read_text(encoding="utf-8"))
                                except Exception:
                                    cv_obj = None
                            if isinstance(ts_obj, dict) and isinstance(cv_obj, dict):
                                if ts_obj.get("signal_logic_version") != cv_obj.get("signal_logic_version"):
                                    issues.append(_issue(
                                        "invalid_required_artifact",
                                        "dist/contracts/treesitter_manifest.json:signal_logic_version",
                                        cv_obj.get("signal_logic_version"),
                                        ts_obj.get("signal_logic_version"),
                                    ))

            # ----------------------------------------------------------
            # Defense-in-depth: cross-artifact invariants (rule governance)
            # - rules_registry.signal_logic_version must match versions.json
            # - rule_versions.signal_logic_version must match versions.json
            # - rule_versions must cover all rule_ids in rules_registry
            # - rule_versions entries must be internally consistent:
            #     rule_logic_version == len(history)
            #     semantic_hash == history[-1]
            # ----------------------------------------------------------
            def _load_dist_json(rel: str) -> dict | None:
                p = (ROOT / rel).resolve()
                try:
                    if not p.exists():
                        return None
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    return None

            cv_art = arts.get("contract_versions")
            rr_art = arts.get("rules_registry")
            rv_art = arts.get("rule_versions")
            cv_rel = cv_art.get("path") if isinstance(cv_art, dict) else None
            rr_rel = rr_art.get("path") if isinstance(rr_art, dict) else None
            rv_rel = rv_art.get("path") if isinstance(rv_art, dict) else None

            if isinstance(cv_rel, str) and isinstance(rr_rel, str) and isinstance(rv_rel, str):
                cv_obj = _load_dist_json(cv_rel)
                rr_obj = _load_dist_json(rr_rel)
                rv_obj = _load_dist_json(rv_rel)

                if not isinstance(cv_obj, dict):
                    issues.append(_issue(
                        "invalid_required_artifact",
                        "release_bom.json:artifacts.contract_versions.path",
                        "valid JSON object",
                        "<unreadable>",
                    ))
                if not isinstance(rr_obj, dict):
                    issues.append(_issue(
                        "invalid_required_artifact",
                        "release_bom.json:artifacts.rules_registry.path",
                        "valid JSON object",
                        "<unreadable>",
                    ))
                if not isinstance(rv_obj, dict):
                    issues.append(_issue(
                        "invalid_required_artifact",
                        "release_bom.json:artifacts.rule_versions.path",
                        "valid JSON object",
                        "<unreadable>",
                    ))

                if isinstance(cv_obj, dict) and isinstance(rr_obj, dict) and isinstance(rv_obj, dict):
                    cv_slv = cv_obj.get("signal_logic_version")
                    rr_slv = rr_obj.get("signal_logic_version")
                    rv_slv = rv_obj.get("signal_logic_version")

                    if rr_slv != cv_slv:
                        issues.append(_issue(
                            "invalid_required_artifact",
                            "dist/contracts/rules_registry.json:signal_logic_version",
                            cv_slv,
                            rr_slv,
                        ))
                    if rv_slv != cv_slv:
                        issues.append(_issue(
                            "invalid_required_artifact",
                            "dist/contracts/rule_versions.json:signal_logic_version",
                            cv_slv,
                            rv_slv,
                        ))

                    rr_rules = rr_obj.get("rules")
                    rv_rules = rv_obj.get("rules")

                    if not isinstance(rr_rules, list):
                        issues.append(_issue(
                            "invalid_required_artifact",
                            "dist/contracts/rules_registry.json:rules",
                            "array",
                            type(rr_rules).__name__,
                        ))
                    if not isinstance(rv_rules, dict):
                        issues.append(_issue(
                            "invalid_required_artifact",
                            "dist/contracts/rule_versions.json:rules",
                            "object",
                            type(rv_rules).__name__,
                        ))

                    if isinstance(rr_rules, list) and isinstance(rv_rules, dict):
                        # Tighten: rules_count fields must match actual contents.
                        rr_count_decl = rr_art.get("rules_count") if isinstance(rr_art, dict) else None
                        rv_count_decl = rv_art.get("rules_count") if isinstance(rv_art, dict) else None
                        if isinstance(rr_count_decl, int) and rr_count_decl != len(rr_rules):
                            issues.append(_issue(
                                "invalid_required_artifact",
                                "release_bom.json:artifacts.rules_registry.rules_count",
                                len(rr_rules),
                                rr_count_decl,
                            ))
                        if isinstance(rv_count_decl, int) and rv_count_decl != len(rv_rules.keys()):
                            issues.append(_issue(
                                "invalid_required_artifact",
                                "release_bom.json:artifacts.rule_versions.rules_count",
                                len(rv_rules.keys()),
                                rv_count_decl,
                            ))

                        rr_ids: list[str] = []
                        rr_hash_by_id: dict[str, str] = {}
                        for r in rr_rules:
                            if isinstance(r, dict) and isinstance(r.get("rule_id"), str):
                                rr_ids.append(r["rule_id"])
                                if isinstance(r.get("semantic_hash"), str):
                                    rr_hash_by_id[r["rule_id"]] = r["semantic_hash"]
                        rr_ids = sorted(set(rr_ids))

                        for rid in rr_ids:
                            if rid not in rv_rules:
                                issues.append(_issue(
                                    "invalid_required_artifact",
                                    "dist/contracts/rule_versions.json:rules",
                                    f"contains rule_id {rid}",
                                    "<missing>",
                                ))
                                continue
                            ent = rv_rules.get(rid)
                            if not isinstance(ent, dict):
                                issues.append(_issue(
                                    "invalid_required_artifact",
                                    f"dist/contracts/rule_versions.json:rules.{rid}",
                                    "object",
                                    type(ent).__name__,
                                ))
                                continue
                            v = ent.get("rule_logic_version")
                            h = ent.get("semantic_hash")
                            hist = ent.get("history")
                            if not isinstance(v, int) or v < 1:
                                issues.append(_issue(
                                    "invalid_required_artifact",
                                    f"dist/contracts/rule_versions.json:rules.{rid}.rule_logic_version",
                                    "integer>=1",
                                    v,
                                ))
                            if not isinstance(h, str) or not h:
                                issues.append(_issue(
                                    "invalid_required_artifact",
                                    f"dist/contracts/rule_versions.json:rules.{rid}.semantic_hash",
                                    "non-empty string",
                                    h,
                                ))
                            if not isinstance(hist, list) or len(hist) < 1:
                                issues.append(_issue(
                                    "invalid_required_artifact",
                                    f"dist/contracts/rule_versions.json:rules.{rid}.history",
                                    "array (minItems=1)",
                                    hist,
                                ))
                            elif isinstance(v, int) and v == len(hist) and isinstance(h, str):
                                if hist[-1] != h:
                                    issues.append(_issue(
                                        "invalid_required_artifact",
                                        f"dist/contracts/rule_versions.json:rules.{rid}",
                                        "semantic_hash==history[-1]",
                                        "mismatch",
                                    ))
                                # no adjacent duplicates
                                for i in range(1, len(hist)):
                                    if hist[i] == hist[i - 1]:
                                        issues.append(_issue(
                                            "invalid_required_artifact",
                                            f"dist/contracts/rule_versions.json:rules.{rid}.history",
                                            "no adjacent duplicates",
                                            "duplicate",
                                        ))
                                        break

                            # semantic_hash must match rules_registry for same rule_id
                            reg_h = rr_hash_by_id.get(rid)
                            if isinstance(reg_h, str) and isinstance(h, str) and reg_h != h:
                                issues.append(_issue(
                                    "invalid_required_artifact",
                                    f"dist/contracts/rule_versions.json:rules.{rid}.semantic_hash",
                                    f"matches rules_registry ({reg_h})",
                                    h,
                                ))

            # If treesitter_manifest is present (js_ts_surface can be false in legacy releases),
            # require the shipped dist copy exists.
            arts = tmp_obj.get("artifacts") or {}
            if isinstance(arts, dict) and "treesitter_manifest" in arts:
                a = arts["treesitter_manifest"]
                rel = a.get("path") if isinstance(a, dict) else None
                p = (ROOT / rel).resolve() if isinstance(rel, str) else None
                if p is None or not p.exists():
                    issues.append(_issue(
                        "missing_dist_artifact",
                        "release_bom.json:artifacts.treesitter_manifest.path",
                        "existing dist/contracts/treesitter_manifest.json",
                        str(p) if p is not None else "<missing>",
                    ))

    if not issues:
        issues.extend(run_release_bom_consistency_check(bom_obj=tmp_obj, root=ROOT))

    return issues


def main() -> int:
    issues = check_release_bom_generator_gate()
    if issues:
        print(f"[release-bom-gate] FAILED with {len(issues)} issue(s):")
        for i, iss in enumerate(issues, 1):
            print(f"  {i}. [{iss['code']}] {iss['location']}: expected={iss['expected']} actual={iss['actual']}")
        return 1
    print("[release-bom-gate] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
