from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from code_audit.contracts.signing import SigningConfig, sign_payload
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


def _write_json(p: Path, obj: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_trusted_keys() -> dict[str, str]:
    if not TRUSTED_KEYS.exists():
        raise SystemExit("Missing dist/contracts/trusted_signing_keys.json (required for signing)")
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
    kid = cfg.key_id()
    status = trusted.get(kid)
    if status is None:
        raise SystemExit(f"Signing key_id={kid!r} is not present in trusted_signing_keys.json")
    if status != "active" and not allow_retired:
        raise SystemExit(
            f"Signing key_id={kid!r} is {status!r}. Set CODE_AUDIT_ALLOW_RETIRED_SIGNATURE_KEYS=1 to permit."
        )

    if not RULE_PACK.exists():
        raise SystemExit("Missing dist/contracts/rule_pack.json (generate release artifacts first)")
    if not BOM.exists():
        raise SystemExit("Missing dist/release_bom.json (generate release artifacts first)")

    rp_obj = _load_json(RULE_PACK)
    bom_obj = _load_json(BOM)

    rp_payload = canonical_payload_for_artifact(str(RULE_PACK), rp_obj)
    bom_payload = canonical_payload_for_artifact(str(BOM), bom_obj)

    rp_sig = sign_payload(rp_payload, cfg=cfg)
    bom_sig = sign_payload(bom_payload, cfg=cfg)

    # Tighten: signature outputs must be distinct because payloads differ.
    if rp_sig.get("payload_sha256") == bom_sig.get("payload_sha256"):
        raise SystemExit("rule_pack and release_bom produced identical payload_sha256; signing inputs are unexpectedly identical")
    if rp_sig.get("signature") == bom_sig.get("signature"):
        raise SystemExit("rule_pack and release_bom produced identical signatures; signing inputs are unexpectedly identical")

    _write_json(RULE_PACK_SIG, rp_sig)
    _write_json(BOM_SIG, bom_sig)

    print(f"[code-audit] wrote {RULE_PACK_SIG.relative_to(ROOT)}")
    print(f"[code-audit] wrote {BOM_SIG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
