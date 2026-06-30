"""HMAC-SHA256 webhook signing per docs/technical/api-and-webhooks.md.

The signature base is ``timestamp + "." + raw_body`` and the resulting hex
digest is sent in the ``NSE-Signature`` header (``v1`` version). Receivers
verify with their endpoint secret.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass


SIGNATURE_VERSION = "v1"


@dataclass(frozen=True)
class SignedHeaders:
    event_id: str
    timestamp: str
    signature: str
    version: str = SIGNATURE_VERSION

    def as_http(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "NSE-Event-Id": self.event_id,
            "NSE-Timestamp": self.timestamp,
            "NSE-Signature": self.signature,
            "NSE-Signature-Version": self.version,
        }


def compute_signature(*, secret: str, timestamp: str, raw_body: str) -> str:
    """Return the lowercase hex HMAC-SHA256 of ``timestamp + "." + raw_body``."""
    base = f"{timestamp}.{raw_body}".encode("utf-8")
    key = (secret or "").encode("utf-8")
    return hmac.new(key, base, hashlib.sha256).hexdigest()


def sign_payload(
    *, event_id: str, secret: str, timestamp: str, raw_body: str
) -> SignedHeaders:
    """Return :class:`SignedHeaders` for the given payload."""
    sig = compute_signature(secret=secret, timestamp=timestamp, raw_body=raw_body)
    return SignedHeaders(event_id=event_id, timestamp=timestamp, signature=sig)


def verify_signature(
    *, secret: str, timestamp: str, raw_body: str, signature: str
) -> bool:
    """Constant-time signature verification helper (used in tests)."""
    expected = compute_signature(secret=secret, timestamp=timestamp, raw_body=raw_body)
    return hmac.compare_digest(expected, signature or "")
