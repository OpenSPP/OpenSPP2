"""DR-side register service.

Idempotent upsert of res.partner + spp.registry.id rows on the DR,
driven by a DCI ``register-individual`` envelope from the SP. Per-item
status mirrors the search service's pattern so partial failures
surface as individual ``rjct`` rows rather than rolling the whole
transaction back.
"""

import logging
import uuid
from datetime import UTC, datetime

from odoo import fields

from ..schemas import RegisterRequest, RegisterResponse, RegisterResponseItem

_logger = logging.getLogger(__name__)


class DisabilityRegisterService:
    """Service for executing register-individual requests on the DR."""

    UIN_VOCAB_CODE = "UIN"

    def __init__(self, env):
        self.env = env

    def execute_register(self, request: RegisterRequest) -> RegisterResponse:
        items = []
        for req_item in request.register_request:
            try:
                response_item = self._register_one(req_item, request.refresh_existing)
            except Exception as e:  # noqa: BLE001 — boundary, never swallow into a 500
                _logger.warning("DR register failed for %s: %s", req_item.uin, e, exc_info=True)
                response_item = RegisterResponseItem(
                    reference_id=req_item.reference_id,
                    timestamp=datetime.now(UTC),
                    status="rjct",
                    status_reason_code="REG-ERR-INTERNAL",
                    status_reason_message=str(e)[:200],
                    uin=req_item.uin,
                )
            items.append(response_item)

        return RegisterResponse(
            transaction_id=request.transaction_id,
            correlation_id=str(uuid.uuid4()),
            register_response=items,
        )

    # ------------------------------------------------------------------
    # Per-item logic
    # ------------------------------------------------------------------

    def _register_one(self, item, refresh_existing: bool) -> RegisterResponseItem:
        # Resolve the UIN id_type vocabulary code on the DR. Both SP and
        # DR ship the same spp_dci_openg2p id_type_uin record, so the
        # lookup is by code. sudo() is API access — auth is via the DCI
        # signature + bearer middleware at the endpoint boundary.
        VocabCode = self.env["spp.vocabulary.code"].sudo()  # nosemgrep: odoo-sudo-without-context
        uin_type = VocabCode.search([("code", "=", self.UIN_VOCAB_CODE)], limit=1)
        if not uin_type:
            return RegisterResponseItem(
                reference_id=item.reference_id,
                timestamp=datetime.now(UTC),
                status="rjct",
                status_reason_code="REG-ERR-NO-UIN-TYPE",
                status_reason_message="DR has no UIN vocabulary code",
                uin=item.uin,
            )

        RegId = self.env["spp.registry.id"].sudo()  # nosemgrep: odoo-sudo-without-context
        existing_regid = RegId.search(
            [("id_type_id", "=", uin_type.id), ("value", "=", item.uin)],
            limit=1,
        )

        partner_vals = self._partner_vals(item)

        if existing_regid:
            partner = existing_regid.partner_id
            if not refresh_existing:
                # Even when skipping the partner write, an SR self-report
                # of disability still warrants surfacing the registrant
                # to the assessor backlog — but only if no assessment
                # exists yet. This handles the case where a registrant
                # was mirrored before disability was claimed on SR.
                draft_created = self._maybe_create_draft_assessment(partner, item)
                return RegisterResponseItem(
                    reference_id=item.reference_id,
                    timestamp=datetime.now(UTC),
                    status="succ",
                    operation="skipped",
                    local_partner_id=partner.id,
                    uin=item.uin,
                    draft_assessment_created=draft_created,
                )
            partner_sudo = partner.sudo()  # nosemgrep: odoo-sudo-without-context,odoo-sudo-on-sensitive-models
            partner_sudo.write(partner_vals)
            draft_created = self._maybe_create_draft_assessment(partner, item)
            return RegisterResponseItem(
                reference_id=item.reference_id,
                timestamp=datetime.now(UTC),
                status="succ",
                operation="updated",
                local_partner_id=partner.id,
                uin=item.uin,
                draft_assessment_created=draft_created,
            )

        Partner = self.env["res.partner"].sudo()  # nosemgrep: odoo-sudo-without-context,odoo-sudo-on-sensitive-models
        new_partner = Partner.create(partner_vals)
        RegId.create(
            {
                "partner_id": new_partner.id,
                "id_type_id": uin_type.id,
                "value": item.uin,
            }
        )
        draft_created = self._maybe_create_draft_assessment(new_partner, item)
        return RegisterResponseItem(
            reference_id=item.reference_id,
            timestamp=datetime.now(UTC),
            status="succ",
            operation="created",
            local_partner_id=new_partner.id,
            uin=item.uin,
            draft_assessment_created=draft_created,
        )

    def _maybe_create_draft_assessment(self, partner, item) -> bool:
        """Create a draft disability assessment when the SR self-reports
        disability and the registrant has no prior assessment.

        Returns:
            True  — a new draft assessment was created.
            False — the SR didn't claim disability, OR the registrant
                    already has an assessment (any state). No-op.

        Why "any state":

            Once an assessor has touched this registrant — whether the
            assessment is still draft, has been submitted, approved, or
            rejected — the SR's claim is no longer the authoritative
            input. We don't pile on additional drafts behind the
            assessor's back.

            The assessor can always create a new assessment manually
            (e.g. for a re-assessment cycle) through the DR UI.

        WG responses are intentionally LEFT BLANK on the draft. The
        computed has_disability stays False until an assessor conducts
        the WG interview, fills the responses, and approves — at which
        point res.partner.has_disability flips through the existing
        related field path.
        """
        if not item.is_disabled:
            return False

        Assessment = self.env["spp.disability.assessment"].sudo()  # nosemgrep: odoo-sudo-without-context
        if Assessment.search_count([("registrant_id", "=", partner.id)]):
            return False

        new_assessment = Assessment.create(
            {
                "registrant_id": partner.id,
                "assessment_date": fields.Date.today(),
                # WG responses left blank — assessor fills during interview.
                # approval_state defaults to 'draft' via spp.approval.mixin.
            }
        )
        # Post a chatter message so the assessor sees the SR provenance.
        # message_post handles the mail.thread plumbing; sudo() preserves
        # the API-access context the parent call ran under.
        new_assessment.message_post(
            body=(
                "Draft assessment auto-created from Social Registry self-report. "
                f"Registrant {item.uin} indicated disability on their SR record. "
                "Please conduct the Washington Group assessment to confirm "
                "or reject this claim."
            ),
        )
        _logger.info(
            "DR: created draft assessment %s for %s (SR self-report)",
            new_assessment.id,
            item.uin,
        )
        return True

    @staticmethod
    def _partner_vals(item) -> dict:
        vals = {
            "name": item.name or f"{item.given_name or ''} {item.family_name or ''}".strip() or item.uin,
            "given_name": item.given_name or False,
            "family_name": item.family_name or False,
            "is_registrant": True,
            "is_group": False,
        }
        if item.birth_date:
            vals["birthdate"] = item.birth_date
        return vals
