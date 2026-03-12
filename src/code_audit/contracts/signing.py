from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


class SigningError(RuntimeError):
    pass


@dataclass(frozen=True)
class SigningConfig:
    """
    Supply-chain signing configuration.

    We keep this intentionally simple + dependency-free:
      Uses an HMAC key from env for signing (CI secret).
      Produces deterministic JSON signing payloads.

    If you later want public-key verification (Sigstore/cosign), this module
    becomes the abstraction seam.
    """

    key_env: str = "CODE_AUDIT_SIGNING_KEY_B64"
    # Multi-key rotation env (preferred):
    # JSON mapping of key_id -> base64 key bytes.
    keys_env: str = "CODE_AUDIT_SIGNING_KEYS_JSON_B64"
    key_id_env: str = "CODE_AUDIT_SIGNING_KEY_ID"
    algorithm: str = "hmac-sha256"

    def load_key(self, *, key_id: Optional[str] = None) -> bytes:
        """
        Load a signing key, supporting both:
        - CODE_AUDIT_SIGNING_KEYS_JSON_B64 (rotation)
        - CODE_AUDIT_SIGNING_KEY_B64 (legacy)
        """
        target = key_id or self.key_id()
        keys_b64 = (os.environ.get(self.keys_env, "") or "").strip()
        if keys_b64:
            try:
                raw = base64.b64decode(keys_b64, validate=True).decode("utf-8")
                obj = json.loads(raw)
            except Exception as e:
                raise SigningError(f"Invalid {self.keys_env} (expected base64(JSON))") from e
            if not isinstance(obj, dict):
                raise SigningError(f"Invalid {self.keys_env} (expected JSON object)")
            b64 = obj.get(target)
            if not isinstance(b64, str) or not b64.strip():
                raise SigningError(f"Missing signing key for key_id={target!r} in {self.keys_env}")
            try:
                return base64.b64decode(b64.strip(), validate=True)
            except Exception as e:
                raise SigningError(f"Invalid base64 signing key for key_id={target!r} in {self.keys_env}") from e
        # Legacy fallback
        b64 = (os.environ.get(self.key_env, "") or "").strip()
        if not b64:
            raise SigningError(f"Missing signing key env: {self.keys_env} or {self.key_env}")
        try:
            return base64.b64decode(b64, validate=True)
        except Exception as e:
            raise SigningError(f"Invalid base64 signing key in {self.key_env}") from e

    def key_id(self) -> str:
        kid = (os.environ.get(self.key_id_env, "") or "").strip()
        return kid or "default"

    def have_any_key_material(self) -> bool:
        return bool((os.environ.get(self.keys_env, "") or "").strip() or (os.environ.get(self.key_env, "") or "").strip())


def _canonical_json_bytes(obj: Any) -> bytes:
    # Strict canonicalization: stable key order, no whitespace variance.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_payload_for_artifact(path: str, payload_obj: dict[str, Any]) -> dict[str, Any]:
    """
    Return the canonical payload object that should be signed/verified for a given artifact.

    This exists to avoid self-referential signing cycles.
    """
    # release_bom.json includes release_bom_signature; the signature cannot cover itself.
    # Canonical signing payload is the BOM with release_bom_signature removed.
    if path.endswith("/dist/release_bom.json") or path.endswith("\\dist\\release_bom.json") or path.endswith("dist/release_bom.json"):
        out = dict(payload_obj)
        arts = out.get("artifacts")
        if isinstance(arts, dict):
            arts2 = dict(arts)
            arts2.pop("release_bom_signature", None)
            out["artifacts"] = arts2
        return out
    return payload_obj


def sha256_hex_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sign_payload(payload_obj: dict[str, Any], *, cfg: Optional[SigningConfig] = None) -> dict[str, Any]:
    """
    Return a signature envelope for a JSON payload.
    """
    cfg = cfg or SigningConfig()
    kid = cfg.key_id()
    key = cfg.load_key(key_id=kid)
    msg = _canonical_json_bytes(payload_obj)

    import hmac

    sig = hmac.new(key, msg, hashlib.sha256).hexdigest()

    return {
        "algorithm": cfg.algorithm,
        "key_id": kid,
        "payload_sha256": hashlib.sha256(msg).hexdigest(),
        "signature": sig,
    }


def verify_payload(payload_obj: dict[str, Any], sig_obj: dict[str, Any], *, cfg: Optional[SigningConfig] = None) -> None:
    cfg = cfg or SigningConfig()
    kid = sig_obj.get("key_id")
    if not isinstance(kid, str) or not kid.strip():
        raise SigningError("Missing key_id in signature")
    key = cfg.load_key(key_id=kid.strip())

    import hmac

    msg = _canonical_json_bytes(payload_obj)
    expected = hmac.new(key, msg, hashlib.sha256).hexdigest()
    got = sig_obj.get("signature")
    if not isinstance(got, str) or not got:
        raise SigningError("Missing signature")
    if not hmac.compare_digest(expected, got):
        raise SigningError("Signature verification failed")
