from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ..models import KycLevel, KycReview, KycStatus


def _parse_submitted_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _document(
    *,
    kind: str,
    name: str,
    data_url: str,
    uploaded_at: str,
) -> dict | None:
    if not name and not data_url:
        return None
    doc = {
        "kind": kind,
        "status": "Pending",
        "uploadedAt": uploaded_at,
    }
    if name:
        doc["fileName"] = name
    if data_url:
        doc["dataUrl"] = data_url
    return doc


def kyc_documents_from_metadata(metadata: Mapping | None) -> list[dict]:
    kyc = dict((metadata or {}).get("kyc") or {})
    submitted = _parse_submitted_at(kyc.get("submitted_at"))
    uploaded_at = submitted.date().isoformat() if submitted else timezone.now().date().isoformat()
    documents = [
        _document(
            kind="Director ID",
            name=str(kyc.get("director_id_name") or ""),
            data_url=str(kyc.get("director_id_data") or ""),
            uploaded_at=uploaded_at,
        ),
        _document(
            kind="Utility bill",
            name=str(kyc.get("address_proof_name") or ""),
            data_url=str(kyc.get("address_proof_data") or ""),
            uploaded_at=uploaded_at,
        ),
    ]
    return [doc for doc in documents if doc is not None]


def sync_merchant_kyc_review_from_metadata(
    merchant,
    *,
    replace_documents: bool = False,
) -> KycReview | None:
    metadata = dict(merchant.metadata or {})
    kyc = dict(metadata.get("kyc") or {})
    if not kyc:
        return None

    documents = kyc_documents_from_metadata(metadata)
    submitted_at = _parse_submitted_at(kyc.get("submitted_at")) or timezone.now()
    review, created = KycReview.objects.get_or_create(
        merchant=merchant,
        defaults={
            "status": KycStatus.IN_REVIEW,
            "level": KycLevel.TIER_1,
            "documents": documents,
            "flags": [],
            "notes": "Submitted during merchant onboarding.",
            "submitted_at": submitted_at,
        },
    )
    changed = False
    if (replace_documents or not review.documents) and documents != list(review.documents or []):
        review.documents = documents
        changed = True
    if review.submitted_at is None:
        review.submitted_at = submitted_at
        changed = True
    if not review.notes:
        review.notes = "Submitted during merchant onboarding."
        changed = True
    if changed and not created:
        review.save(update_fields=["documents", "submitted_at", "notes", "updated_at"])
    return review
