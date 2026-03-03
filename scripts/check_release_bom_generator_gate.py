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
        # contract_versions is required; ensure the dist artifact exists early.
        arts = tmp_obj.get("artifacts") or {}
        if isinstance(arts, dict) and "contract_versions" in arts:
            a = arts["contract_versions"]
            rel = a.get("path") if isinstance(a, dict) else None
            p = (ROOT / rel).resolve() if isinstance(rel, str) else None
            if p is None or not p.exists():
                issues.append(_issue(
                    "missing_dist_artifact",
                    "release_bom.json:artifacts.contract_versions.path",
                    "existing dist/contracts/versions.json",
                    str(p) if p is not None else "<missing>",
                ))

    if not issues:
        # rules_registry and rule_versions are required; ensure dist artifacts exist early.
        arts = tmp_obj.get("artifacts") or {}
        for key, expect in (
            ("rules_registry", "existing dist/contracts/rules_registry.json"),
            ("rule_versions", "existing dist/contracts/rule_versions.json"),
        ):
            if isinstance(arts, dict) and key in arts:
                a = arts[key]
                rel = a.get("path") if isinstance(a, dict) else None
                p = (ROOT / rel).resolve() if isinstance(rel, str) else None
                if p is None or not p.exists():
                    issues.append(_issue(
                        "missing_dist_artifact",
                        f"release_bom.json:artifacts.{key}.path",
                        expect,
                        str(p) if p is not None else "<missing>",
                    ))

    if not issues:
        # Full consistency check
        from scripts.check_release_bom_consistency import check_release_bom_consistency
        try:
            check_release_bom_consistency(tmp_obj)
        except AssertionError as exc:
            issues.append(_issue(
                "consistency_failure",
                "release_bom.json",
                "consistent BOM",
                str(exc),
            ))

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
