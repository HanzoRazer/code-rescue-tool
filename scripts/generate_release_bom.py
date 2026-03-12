"""scripts.generate_release_bom

Generates a release BOM (Bill of Materials) that attests all contract
artifacts shipped in dist/.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

# Environment-driven JS/TS surface toggle (default: enabled)
RELEASE_ENABLE_JS_TS = os.environ.get("RELEASE_ENABLE_JS_TS", "1") not in ("0", "false", "no", "")

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
RULE_PACK_DIST = DIST / "contracts" / "rule_pack.json"
RULE_PACK_SIG_DIST = DIST / "contracts" / "rule_pack.sig.json"
BOM_SIG_DIST = DIST / "release_bom.sig.json"
TRUSTED_KEYS_SRC = ROOT / "src" / "code_audit" / "contracts" / "trusted_signing_keys.json"
TRUSTED_KEYS_DIST = DIST / "contracts" / "trusted_signing_keys.json"

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
    js_ts_surface = bool(RELEASE_ENABLE_JS_TS)
    artifacts["js_ts_surface"] = js_ts_surface

    # Supply-chain signing declaration (canonical, schema-governed).
    # This must reflect whether signature artifacts are present in the BOM.
    artifacts["supply_chain_signed"] = False
    artifacts["signing_key_id"] = ""

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

    # Schema-level requirement (now conditional on js_ts_surface=true):
    # Fail early if the BOM declares JS/TS surface but cannot attest treesitter.
    if artifacts.get("js_ts_surface") is True and "treesitter_manifest" not in artifacts:
        raise SystemExit(
            "[release-bom] js_ts_surface=true requires artifacts.treesitter_manifest, but "
            "tests/contracts/treesitter_manifest.json is missing.\n"
            "Fix: generate it (python scripts/refresh_treesitter_manifest.py), commit it, and re-run."
        )

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
    # Optional but recommended: ship an immutable rule pack for downstream consumers.
    # This is derived from already-required artifacts; if generation fails, fail closed.
    try:
        import subprocess
        subprocess.run(
            ["python", "scripts/generate_rule_pack.py"],
            check=True,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
    except Exception as e:
        raise SystemExit(f"[release-bom] failed to generate rule pack: {e}")

    if not RULE_PACK_DIST.exists():
        raise SystemExit("[release-bom] rule pack generation succeeded but dist/contracts/rule_pack.json is missing")

    rp_sha = _sha256_file(RULE_PACK_DIST)
    rp_obj = _load_json(RULE_PACK_DIST)
    artifacts["rule_pack"] = {
        "path": RULE_PACK_DIST.relative_to(ROOT).as_posix(),
        "sha256": rp_sha,
        "schema_version": int(rp_obj.get("schema_version", 0) or 0),
        "signal_logic_version": str(rp_obj.get("signal_logic_version", "") or ""),
        "pack_hash": str(rp_obj.get("pack_hash", "") or ""),
        "rules_count": int(len(rp_obj.get("rules") or [])),
    }
    # ---------------------------------------------------------------------
    # Hard requirement motif: these must always exist in release BOM.
    # (Schema now requires them; fail early with a clear error if missing.)
    # ---------------------------------------------------------------------
    required_keys = ("js_ts_surface", "contract_versions", "rules_registry", "rule_versions")
    missing = [k for k in required_keys if k not in artifacts]
    if missing:
        raise SystemExit(f"[release-bom] missing required artifacts: {', '.join(missing)}")

    # Build final BOM
    bom: dict[str, Any] = {
        "bom_version": 1,
        "artifacts": artifacts,
    }

    if write:
        BOM_PATH.parent.mkdir(parents=True, exist_ok=True)
        BOM_PATH.write_text(json.dumps(bom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[release-bom] wrote {BOM_PATH.relative_to(ROOT)}")

        # Supply-chain: sign rule_pack + release_bom when signing key is available.
        # Fail-closed in release contexts by setting CODE_AUDIT_REQUIRE_SIGNATURES=1.
        import os as _os

        require = (_os.environ.get("CODE_AUDIT_REQUIRE_SIGNATURES", "") or "").strip().lower() in ("1", "true", "yes", "on")
        from code_audit.contracts.signing import SigningConfig
        cfg = SigningConfig()
        have_key = cfg.have_any_key_material()
        if require and not have_key:
            raise SystemExit(
                "[release-bom] CODE_AUDIT_REQUIRE_SIGNATURES=1 but no signing key material is available.\n"
                "Provide one of:\n"
                "  - CODE_AUDIT_SIGNING_KEYS_JSON_B64 (preferred, rotation)\n"
                "  - CODE_AUDIT_SIGNING_KEY_B64 (legacy)\n"
            )
        if have_key:
            bom["artifacts"]["supply_chain_signed"] = True

            # IMPORTANT: sign in a non-self-referential order so the attested BOM is what gets signed.
            #
            # Desired invariant:
            # - rule_pack_signature signs dist/contracts/rule_pack.json
            # - release_bom_signature signs the canonical BOM payload:
            #     dist/release_bom.json with artifacts.release_bom_signature removed
            #   (but including artifacts.rule_pack_signature)
            from code_audit.contracts.signing import canonical_payload_for_artifact, sign_payload, verify_payload

            # Tighten: enforce key_id is governed + active (unless explicitly allowed).
            allow_retired = (_os.environ.get("CODE_AUDIT_ALLOW_RETIRED_SIGNATURE_KEYS", "") or "").strip().lower() in ("1", "true", "yes", "on")
            if not TRUSTED_KEYS_SRC.exists():
                raise SystemExit("[release-bom] supply_chain_signed=true requires src/code_audit/contracts/trusted_signing_keys.json")
            try:
                tk_obj = json.loads(TRUSTED_KEYS_SRC.read_text(encoding="utf-8"))
            except Exception as e:
                raise SystemExit(f"[release-bom] unable to read trusted_signing_keys.json: {e}")
            keys = tk_obj.get("keys") or []
            if not isinstance(keys, list) or not keys:
                raise SystemExit("[release-bom] trusted_signing_keys.json invalid: keys must be a non-empty list")
            status_by_id: dict[str, str] = {}
            for k in keys:
                if not isinstance(k, dict):
                    continue
                kid = k.get("key_id")
                st = k.get("status")
                if isinstance(kid, str) and isinstance(st, str):
                    status_by_id[kid] = st
            signing_kid = cfg.key_id()
            st = status_by_id.get(signing_kid)
            if st is None:
                raise SystemExit(f"[release-bom] signing key_id={signing_kid!r} not present in trusted_signing_keys.json")
            if st != "active" and not allow_retired:
                raise SystemExit(
                    f"[release-bom] signing key_id={signing_kid!r} is {st!r}. "
                    "Set CODE_AUDIT_ALLOW_RETIRED_SIGNATURE_KEYS=1 to permit."
                )

            bom["artifacts"]["signing_key_id"] = signing_kid

            def _write_json(path: Path, obj: dict[str, Any]) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            def _sig_obj_from_file(path: Path) -> dict[str, Any]:
                o = _load_json(path)
                return {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": _sha256_file(path),
                    "algorithm": str(o.get("algorithm") or ""),
                    "key_id": str(o.get("key_id") or ""),
                    "payload_sha256": str(o.get("payload_sha256") or ""),
                    "signature": str(o.get("signature") or ""),
                }

            # 0) Ship trusted signing key registry + attest it in the BOM BEFORE BOM signing.
            # This ensures release_bom_signature covers the trusted key registry attestation.
            # Also fail-closed if the registry is not schema-valid.
            try:
                import jsonschema  # type: ignore
            except Exception as e:
                raise SystemExit(f"[release-bom] missing dependency: jsonschema (required to validate trusted_signing_keys): {e}")
            schema_path = ROOT / "schemas" / "trusted_signing_keys.schema.json"
            if not schema_path.exists():
                raise SystemExit("[release-bom] missing schemas/trusted_signing_keys.schema.json")
            try:
                jsonschema.validate(instance=tk_obj, schema=json.loads(schema_path.read_text(encoding="utf-8")))
            except Exception as e:
                raise SystemExit(f"[release-bom] trusted_signing_keys.json failed schema validation: {e}")
            TRUSTED_KEYS_DIST.parent.mkdir(parents=True, exist_ok=True)
            TRUSTED_KEYS_DIST.write_bytes(TRUSTED_KEYS_SRC.read_bytes())
            tk_dist_obj = _load_json(TRUSTED_KEYS_DIST)
            tk_keys = tk_dist_obj.get("keys") or []
            bom["artifacts"]["trusted_signing_keys"] = {
                "path": str(TRUSTED_KEYS_DIST.relative_to(ROOT)),
                "sha256": _sha256_file(TRUSTED_KEYS_DIST),
                "schema_version": int(tk_dist_obj.get("schema_version", 0) or 0),
                "keys_count": int(len(tk_keys) if isinstance(tk_keys, list) else 0),
            }

            # 1) Sign rule_pack.json
            if not RULE_PACK_DIST.exists():
                raise SystemExit("[release-bom] missing dist/contracts/rule_pack.json prior to signing")
            rp_obj = _load_json(RULE_PACK_DIST)
            rp_payload = canonical_payload_for_artifact(str(RULE_PACK_DIST), rp_obj)
            _write_json(RULE_PACK_SIG_DIST, sign_payload(rp_payload, cfg=cfg))
            # Self-verify (fail-closed) to prevent emitting broken signatures.
            verify_payload(rp_payload, _load_json(RULE_PACK_SIG_DIST), cfg=cfg)

            # 2) Inject rule_pack_signature into BOM and write BOM (unsigned-self)
            bom["artifacts"]["rule_pack_signature"] = _sig_obj_from_file(RULE_PACK_SIG_DIST)
            _write_json(DIST / "release_bom.json", bom)

            # 3) Sign canonical BOM payload (which strips release_bom_signature only)
            bom_on_disk = _load_json(DIST / "release_bom.json")
            bom_payload = canonical_payload_for_artifact(str(DIST / "release_bom.json"), bom_on_disk)
            _write_json(BOM_SIG_DIST, sign_payload(bom_payload, cfg=cfg))
            verify_payload(bom_payload, _load_json(BOM_SIG_DIST), cfg=cfg)

            # 4) Inject release_bom_signature and rewrite BOM (final)
            bom["artifacts"]["release_bom_signature"] = _sig_obj_from_file(BOM_SIG_DIST)

            # Tighten: the two signature artifacts must never collide.
            rp_sig_obj = bom["artifacts"].get("rule_pack_signature")
            rb_sig_obj = bom["artifacts"].get("release_bom_signature")
            if isinstance(rp_sig_obj, dict) and isinstance(rb_sig_obj, dict):
                if rp_sig_obj.get("payload_sha256") == rb_sig_obj.get("payload_sha256"):
                    raise SystemExit(
                        "[release-bom] rule_pack_signature.payload_sha256 must differ from "
                        "release_bom_signature.payload_sha256"
                    )
                if rp_sig_obj.get("signature") == rb_sig_obj.get("signature"):
                    raise SystemExit(
                        "[release-bom] rule_pack_signature.signature must differ from "
                        "release_bom_signature.signature"
                    )
            _write_json(DIST / "release_bom.json", bom)

        else:
            # No key: ensure we do not accidentally emit signature artifacts while claiming unsigned.
            bom["artifacts"]["supply_chain_signed"] = False
            bom["artifacts"]["signing_key_id"] = ""
            bom["artifacts"].pop("rule_pack_signature", None)
            bom["artifacts"].pop("release_bom_signature", None)
            bom["artifacts"].pop("trusted_signing_keys", None)
            # Tighten: clean stale signature files from dist so unsigned releases cannot
            # accidentally ship prior signed artifacts.
            for stale in (RULE_PACK_SIG_DIST, BOM_SIG_DIST, TRUSTED_KEYS_DIST):
                try:
                    if stale.exists():
                        stale.unlink()
                except OSError:
                    raise SystemExit(f"[release-bom] failed to remove stale signed artifact: {stale.relative_to(ROOT)}")
            (DIST / "release_bom.json").write_text(json.dumps(bom, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return bom


def main() -> int:
    generate_release_bom(write=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
