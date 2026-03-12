from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from code_audit.contracts.signing import SigningConfig, SigningError, verify_payload
from code_audit.contracts.signing import canonical_payload_for_artifact


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

RULE_PACK = DIST / "contracts" / "rule_pack.json"
BOM = DIST / "release_bom.json"

RULE_PACK_SIG = DIST / "contracts" / "rule_pack.sig.json"
BOM_SIG = DIST / "release_bom.sig.json"
TRUSTED_KEYS = DIST / "contracts" / "trusted_signing_keys.json"


def _load_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _load_trusted_keys() -> dict[str, str]:
    if not TRUSTED_KEYS.exists():
        raise SystemExit(f"Missing trusted signing keys registry: {TRUSTED_KEYS.relative_to(ROOT)}")
    obj = _load_json(TRUSTED_KEYS)
    # Full schema validation (defense-in-depth).
    try:
        import jsonschema  # type: ignore
    except Exception as e:
        raise SystemExit(f"jsonschema dependency missing: {e}")
    schema_path = ROOT / "schemas" / "trusted_signing_keys.schema.json"
    if not schema_path.exists():
        raise SystemExit("Missing schemas/trusted_signing_keys.schema.json")
    jsonschema.validate(instance=obj, schema=_load_json(schema_path))
    keys = obj.get("keys") or []
    if not isinstance(keys, list) or not keys:
        raise SystemExit("trusted_signing_keys.json invalid: keys must be a non-empty list")
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
    if not out:
        raise SystemExit("trusted_signing_keys.json invalid: no usable key entries")
    if ids != sorted(ids):
        raise SystemExit("trusted_signing_keys.json invalid: keys must be sorted by key_id")
    if len(ids) != len(set(ids)):
        raise SystemExit("trusted_signing_keys.json invalid: duplicate key_id entries")
    if active < 1:
        raise SystemExit("trusted_signing_keys.json invalid: must include at least one active key")
    return out


def main() -> int:
    cfg = SigningConfig()

    trusted = _load_trusted_keys()
    allow_retired = (os.environ.get("CODE_AUDIT_ALLOW_RETIRED_SIGNATURE_KEYS", "") or "").strip().lower() in ("1", "true", "yes", "on")
    allow_mixed_keys = (os.environ.get("CODE_AUDIT_ALLOW_MIXED_SIGNATURE_KEYS", "") or "").strip().lower() in ("1", "true", "yes", "on")

    seen_key_ids: list[str] = []

    for payload, sigp, label in [
        (RULE_PACK, RULE_PACK_SIG, "rule_pack"),
        (BOM, BOM_SIG, "release_bom"),
    ]:
        if not payload.exists():
            raise SystemExit(f"Missing payload: {payload.relative_to(ROOT)}")
        if not sigp.exists():
            raise SystemExit(f"Missing signature: {sigp.relative_to(ROOT)}")
        obj = _load_json(payload)
        sig = _load_json(sigp)
        kid = sig.get("key_id")
        if not isinstance(kid, str) or not kid.strip():
            raise SystemExit(f"[code-audit] {label} signature missing key_id")
        seen_key_ids.append(kid)
        status = trusted.get(kid)
        if status is None:
            raise SystemExit(f"[code-audit] {label} signature key_id={kid!r} not present in trusted_signing_keys.json")
        if status != "active" and not allow_retired:
            raise SystemExit(
                f"[code-audit] {label} signature key_id={kid!r} is {status!r}. "
                "Set CODE_AUDIT_ALLOW_RETIRED_SIGNATURE_KEYS=1 to permit."
            )
        try:
            canon = canonical_payload_for_artifact(str(payload), obj)
            verify_payload(canon, sig, cfg=cfg)
        except SigningError as e:
            raise SystemExit(f"[code-audit] {label} signature invalid: {e}")

    if len(set(seen_key_ids)) > 1 and not allow_mixed_keys:
        raise SystemExit(
            "[code-audit] mixed signature key_ids are not allowed by default. "
            f"Observed: {sorted(set(seen_key_ids))}. "
            "Set CODE_AUDIT_ALLOW_MIXED_SIGNATURE_KEYS=1 to permit."
        )

    print("[code-audit] signatures verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
