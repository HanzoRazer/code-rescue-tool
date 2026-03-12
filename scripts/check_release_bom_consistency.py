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


def _canonical_json_bytes(obj: Any) -> bytes:
    # Must match signing canonicalization: stable keys, no whitespace variance.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex_of_json(obj: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(obj)).hexdigest()


def _validate_jsonschema(*, instance: dict[str, Any], schema_path: Path, ctx: str) -> None:
    try:
        import jsonschema  # type: ignore
    except Exception as e:
        raise AssertionError(f"{ctx}: jsonschema dependency missing: {e}")
    if not schema_path.exists():
        raise AssertionError(f"{ctx}: missing schema file: {schema_path.relative_to(ROOT)}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=instance, schema=schema)


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
    # Supply-chain declaration must match artifact presence.
    # - supply_chain_signed=true => both signature artifacts must exist
    # - if any signature artifact exists => supply_chain_signed must be true
    # -----------------------------------------------------------------
    scs = artifacts.get("supply_chain_signed")
    assert isinstance(scs, bool), "artifacts.supply_chain_signed must be boolean"
    signing_kid = artifacts.get("signing_key_id")
    if scs is True:
        assert isinstance(signing_kid, str) and signing_kid, "artifacts.signing_key_id required when supply_chain_signed=true"
    else:
        assert isinstance(signing_kid, str), "artifacts.signing_key_id must be string"
    has_rp_sig = "rule_pack_signature" in artifacts
    has_bom_sig = "release_bom_signature" in artifacts
    has_tk = "trusted_signing_keys" in artifacts
    if (has_rp_sig or has_bom_sig) and scs is not True:
        raise AssertionError("Signature artifacts present but artifacts.supply_chain_signed is not true.")
    if scs is True and not (has_rp_sig and has_bom_sig and has_tk):
        raise AssertionError("artifacts.supply_chain_signed=true requires signature artifacts + trusted_signing_keys.")
    if scs is False:
        assert not has_rp_sig and not has_bom_sig and not has_tk, (
            "Unsigned BOM must not carry signature artifacts or trusted_signing_keys."
        )

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
        rr_ids = [r.get("rule_id") for r in rr_rules if isinstance(r, dict) and isinstance(r.get("rule_id"), str)]
        # Tighten: registry must be stable-ordered and contain unique rule_ids.
        assert rr_ids == sorted(rr_ids), "rules_registry rules must be sorted by rule_id"
        assert len(rr_ids) == len(set(rr_ids)), "rules_registry contains duplicate rule_id entries"
        rr_ids = sorted(rr_ids)
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
    # -----------------------------------------------------------------
    # Supply-chain signatures (if present)
    # - Signature artifact sha256 must match file on disk
    # - payload_sha256 must match canonical hash of the referenced payload
    # - If signing key is available, verify signature (HMAC)
    # - If CODE_AUDIT_REQUIRE_SIGNATURES=1, both signatures must exist
    # -----------------------------------------------------------------
    require_sigs = scs is True or (os.environ.get("CODE_AUDIT_REQUIRE_SIGNATURES", "") or "").strip().lower() in ("1", "true", "yes", "on")
    have_key = bool((os.environ.get("CODE_AUDIT_SIGNING_KEY_B64", "") or "").strip())

    allow_mixed_keys = (os.environ.get("CODE_AUDIT_ALLOW_MIXED_SIGNATURE_KEYS", "") or "").strip().lower() in ("1", "true", "yes", "on")

    def _check_sig_artifact(key: str, expected_path: str, payload_path: str) -> None:
        a = artifacts.get(key)
        ctx = f"artifacts.{key}"
        if a is None:
            if require_sigs:
                raise AssertionError(f"{ctx} missing but CODE_AUDIT_REQUIRE_SIGNATURES=1")
            return
        assert isinstance(a, dict), f"{ctx} must be an object"
        rel = _req(a, "path", ctx)
        assert rel == expected_path, f"{ctx}.path must be {expected_path}"
        p = (ROOT / rel).resolve()
        assert p.exists(), f"{ctx}.path does not exist: {rel}"
        got_sha = _sha256_file(p)
        exp_sha = _req(a, "sha256", ctx)
        assert got_sha == exp_sha, f"{ctx}.sha256 mismatch: expected={exp_sha} got={got_sha}"
        # Load signature file and sanity fields
        sig_obj = json.loads(p.read_text(encoding="utf-8"))
        alg = _req(a, "algorithm", ctx)
        kid = _req(a, "key_id", ctx)
        psha = _req(a, "payload_sha256", ctx)
        sig = _req(a, "signature", ctx)
        assert sig_obj.get("algorithm") == alg
        assert sig_obj.get("key_id") == kid
        assert sig_obj.get("payload_sha256") == psha
        assert sig_obj.get("signature") == sig

        # Tighten: ensure sha256 in BOM matches actual file digest.
        assert _req(a, "sha256", ctx) == _sha256_file(p), (
            f"{ctx}.sha256 does not match actual file hash"
        )
        # Tighten: payload_sha256 must be valid 64-char lowercase hex
        assert isinstance(psha, str) and len(psha) == 64 and all(c in "0123456789abcdef" for c in psha), (
            f"{ctx}.payload_sha256 must be 64-char lowercase hex"
        )
        # Tighten: signature must be valid 64-char lowercase hex
        assert isinstance(sig, str) and len(sig) == 64 and all(c in "0123456789abcdef" for c in sig), (
            f"{ctx}.signature must be 64-char lowercase hex"
        )

        # Bind payload_sha256 to the canonical JSON of the payload
        payload_file = (ROOT / payload_path).resolve()
        assert payload_file.exists(), f"{ctx} payload missing: {payload_path}"
        payload_obj = json.loads(payload_file.read_text(encoding="utf-8"))
        # Avoid self-referential signing cycles (e.g., BOM signature cannot cover itself).
        from code_audit.contracts.signing import canonical_payload_for_artifact
        canon_payload = canonical_payload_for_artifact(str(payload_file), payload_obj)
        expected_payload_sha = _sha256_hex_of_json(canon_payload)
        assert psha == expected_payload_sha, f"{ctx}.payload_sha256 mismatch vs payload canonical hash"

        # Tighten: signature artifact path must be canonical for its payload.
        # Prevent swapping signature files across artifact slots.
        if key == "rule_pack_signature":
            assert payload_path == "dist/contracts/rule_pack.json", (
                "rule_pack_signature must bind dist/contracts/rule_pack.json"
            )
        elif key == "release_bom_signature":
            assert payload_path == "dist/release_bom.json", (
                "release_bom_signature must bind dist/release_bom.json"
            )

        # Verify HMAC when key is available (or required).
        if have_key or require_sigs:
            from code_audit.contracts.signing import verify_payload, SigningConfig
            verify_payload(canon_payload, sig_obj, cfg=SigningConfig())

    def _load_trusted_keys() -> dict[str, str]:
        a = artifacts.get("trusted_signing_keys")
        if a is None:
            if require_sigs or scs is True:
                raise AssertionError("trusted_signing_keys missing but signatures are required/present")
            return {}
        assert isinstance(a, dict), "artifacts.trusted_signing_keys must be an object"
        ctx = "artifacts.trusted_signing_keys"
        rel = _req(a, "path", ctx)
        p = (ROOT / rel).resolve()
        assert p.exists(), f"trusted_signing_keys file missing: {rel}"
        # Tighten: sha256 must match the on-disk file
        exp_sha = _req(a, "sha256", ctx)
        assert isinstance(exp_sha, str) and len(exp_sha) == 64 and all(c in "0123456789abcdef" for c in exp_sha)
        got_sha = _sha256_file(p)
        assert got_sha == exp_sha, f"{ctx}.sha256 mismatch: expected={exp_sha} got={got_sha}"
        obj = json.loads(p.read_text(encoding="utf-8"))
        # Tighten: full schema validation (prevents ad-hoc fields / bad statuses).
        _validate_jsonschema(
            instance=obj,
            schema_path=ROOT / "schemas" / "trusted_signing_keys.schema.json",
            ctx="dist/contracts/trusted_signing_keys.json",
        )
        keys = obj.get("keys") or []
        assert isinstance(keys, list) and keys, "trusted_signing_keys.keys must be a non-empty list"
        # Tighten: schema_version present and sane
        sv = obj.get("schema_version")
        assert isinstance(sv, int) and sv >= 1, "trusted_signing_keys.schema_version must be >= 1"
        a_sv = a.get("schema_version")
        assert isinstance(a_sv, int) and a_sv == sv, "artifacts.trusted_signing_keys.schema_version must match file"
        # Tighten: keys_count must match
        a_kc = a.get("keys_count")
        assert isinstance(a_kc, int) and a_kc == len(keys), "artifacts.trusted_signing_keys.keys_count must match file"
        out: dict[str, str] = {}
        ids: list[str] = []
        active = 0
        for k in keys:
            if not isinstance(k, dict):
                continue
            kid = k.get("key_id")
            st = k.get("status")
            if isinstance(kid, str) and isinstance(st, str):
                out[kid] = st
                ids.append(kid)
                if st == "active":
                    active += 1
        assert out, "trusted_signing_keys must include at least one key_id"
        assert ids == sorted(ids), "trusted_signing_keys.keys must be sorted by key_id"
        assert len(ids) == len(set(ids)), "trusted_signing_keys contains duplicate key_id"
        assert active >= 1, "trusted_signing_keys must include at least one active key_id"
        return out

    trusted = _load_trusted_keys()

    _check_sig_artifact(
        "rule_pack_signature",
        "dist/contracts/rule_pack.sig.json",
        "dist/contracts/rule_pack.json",
    )
    _check_sig_artifact(
        "release_bom_signature",
        "dist/release_bom.sig.json",
        "dist/release_bom.json",
    )

    # Tighten: signature artifacts must not be byte-identical.
    # They sign different payloads and should therefore differ even if key_id matches.
    if has_rp_sig and has_bom_sig:
        rp_sig = artifacts.get("rule_pack_signature")
        bom_sig = artifacts.get("release_bom_signature")
        if isinstance(rp_sig, dict) and isinstance(bom_sig, dict):
            assert rp_sig.get("signature") != bom_sig.get("signature"), (
                "rule_pack_signature.signature and release_bom_signature.signature must differ"
            )
            assert rp_sig.get("payload_sha256") != bom_sig.get("payload_sha256"), (
                "rule_pack_signature.payload_sha256 and release_bom_signature.payload_sha256 must differ"
            )

    # Key rotation enforcement:
    # - signature.key_id must exist in trusted_signing_keys
    # - by default, key must be "active"
    # - allow retired keys only if CODE_AUDIT_ALLOW_RETIRED_SIGNATURE_KEYS=1
    allow_retired = (os.environ.get("CODE_AUDIT_ALLOW_RETIRED_SIGNATURE_KEYS", "") or "").strip().lower() in ("1", "true", "yes", "on")
    for sig_key in ("rule_pack_signature", "release_bom_signature"):
        a = artifacts.get(sig_key)
        if not isinstance(a, dict):
            continue
        kid = a.get("key_id")
        if not isinstance(kid, str) or not kid:
            raise AssertionError(f"Missing key_id in {sig_key}")
        if scs is True:
            assert kid == signing_kid, f"{sig_key}.key_id must match artifacts.signing_key_id"
        status = trusted.get(kid)
        if status is None:
            raise AssertionError(f"{sig_key}.key_id={kid!r} is not present in trusted_signing_keys")
        if status != "active" and not allow_retired:
            raise AssertionError(
                f"{sig_key}.key_id={kid!r} is {status!r}; set CODE_AUDIT_ALLOW_RETIRED_SIGNATURE_KEYS=1 to permit."
            )

    # Key rotation tightening:
    # By default, both release signatures must be produced by the same trusted key_id.
    # Mixed-key releases require explicit opt-in.
    if has_rp_sig and has_bom_sig:
        rp_sig = artifacts.get("rule_pack_signature")
        bom_sig = artifacts.get("release_bom_signature")
        if isinstance(rp_sig, dict) and isinstance(bom_sig, dict):
            rp_kid = rp_sig.get("key_id")
            bom_kid = bom_sig.get("key_id")
            assert isinstance(rp_kid, str) and rp_kid, "artifacts.rule_pack_signature.key_id missing"
            assert isinstance(bom_kid, str) and bom_kid, "artifacts.release_bom_signature.key_id missing"
            if rp_kid != bom_kid and not allow_mixed_keys:
                raise AssertionError(
                    "Mixed signature key_ids are not allowed by default: "
                    f"rule_pack_signature.key_id={rp_kid!r}, release_bom_signature.key_id={bom_kid!r}. "
                    "Set CODE_AUDIT_ALLOW_MIXED_SIGNATURE_KEYS=1 to permit."
                )
            if scs is True:
                assert rp_kid == bom_kid == signing_kid, (
                    "artifacts.signing_key_id must be the canonical key_id for all signature artifacts."
                )

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
