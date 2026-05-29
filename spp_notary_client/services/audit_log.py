# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Sanitized outgoing log helpers for Notary calls."""

from __future__ import annotations

import hashlib
import hmac
import logging
from collections.abc import Iterable
from typing import Any

_logger = logging.getLogger(__name__)


def hmac_subject_hash(subject_id: str, secret: str) -> str:
    """Return a stable keyed hash for a subject identifier."""
    if not secret:
        raise ValueError("subject hash secret is required")
    if subject_id is None:
        raise ValueError("subject id is required")

    digest = hmac.new(str(secret).encode(), str(subject_id).encode(), hashlib.sha256).hexdigest()
    return f"hmac:{digest}"


def claim_ids_from_refs(claim_refs: Iterable[Any]) -> list[str]:
    """Extract claim ids from string refs, dict refs, or ClaimRef-like objects."""
    claim_ids = []
    for claim_ref in claim_refs or []:
        if isinstance(claim_ref, str):
            claim_ids.append(claim_ref)
        elif isinstance(claim_ref, dict):
            claim_ids.append(str(claim_ref.get("id") or claim_ref.get("claim_id") or ""))
        else:
            claim_ids.append(str(getattr(claim_ref, "id", None) or getattr(claim_ref, "claim_id", "") or ""))
    return [claim_id for claim_id in claim_ids if claim_id]


def build_request_summary(
    *,
    purpose: str,
    purpose_layer: str,
    claim_refs: Iterable[Any],
    subject_id: str | None = None,
    subject_count: int = 1,
    subject_hash_secret: str | None = None,
    evaluation_id: str | None = None,
    response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the only request fields allowed into Notary audit logs."""
    summary = {
        "purpose": purpose,
        "purpose_layer": purpose_layer,
        "claim_ids": claim_ids_from_refs(claim_refs),
        "subject_count": subject_count,
    }
    if subject_id:
        summary["subject_hash"] = hmac_subject_hash(subject_id, subject_hash_secret or "")
    if evaluation_id:
        summary["evaluation_id"] = evaluation_id
    elif response and response.get("evaluation_id"):
        summary["evaluation_id"] = response["evaluation_id"]
    return summary


class NotaryOutgoingLogWrapper:
    """Optional Odoo outgoing-log adapter that only receives sanitized payloads."""

    def __init__(self, env, service_code: str = "notary", user_id: int | None = None):
        self.env = env
        self.service_code = service_code
        self.user_id = user_id

    def log_call(self, **kwargs):
        """Log via spp_api_v2 when available; logging failures do not block calls."""
        try:
            if "spp.api.outgoing.log" not in self.env:
                _logger.warning("spp.api.outgoing.log not installed; skipping Notary outgoing log")
                return None

            from odoo.addons.spp_api_v2.services.outgoing_api_log_service import OutgoingApiLogService

            service = OutgoingApiLogService(
                self.env,
                service_name="Notary Client",
                service_code=self.service_code,
                user_id=self.user_id,
            )
            return service.log_call(**kwargs)
        except (KeyError, AttributeError, TypeError, RuntimeError):
            _logger.exception("Failed to log Notary outgoing call")
            return None
