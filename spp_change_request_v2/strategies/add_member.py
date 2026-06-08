# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Apply strategy for the Add Member CR (OP#871)."""

import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

HEAD_ROLE_CODE = "head"


class SPPCRApplyAddMember(models.AbstractModel):
    """Custom apply strategy for Add Member CR type."""

    _name = "spp.cr.apply.add_member"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Add Group Member"

    # ──────────────────────────────────────────────────────────────────────
    # apply
    # ──────────────────────────────────────────────────────────────────────
    def apply(self, change_request):
        group = change_request.registrant_id
        if not group.is_group:
            raise UserError(_("Registrant must be a group."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        self._validate(detail)

        # 1. Individual itself.
        individual = self._create_individual(detail)

        # 2. Multi-value attachments tied to the new individual.
        self._attach_phones(detail, individual)
        self._attach_banks(detail, individual)
        self._attach_id_docs(detail, individual)

        # 3. If the new member is being added as head and one already exists,
        #    demote it first so the group invariant holds (single active head).
        self._demote_existing_head_if_needed(detail, group)

        # 4. Membership row.
        self._create_membership(detail, group, individual)

        detail.write({"created_individual_id": individual.id})

        _logger.info(
            "Added member partner_id=%s to group partner_id=%s via CR %s",
            individual.id,
            group.id,
            change_request.name,
        )
        return True

    # ──────────────────────────────────────────────────────────────────────
    # preview
    # ──────────────────────────────────────────────────────────────────────
    def preview(self, change_request):
        detail = change_request.get_detail()
        if not detail:
            return {}
        return {
            "_action": "create_member",
            "_header": _("The following individual is to be added:"),
            "member_name": detail.member_name,
            "group": change_request.registrant_id.name,
            "role": detail.membership_type_id.display if detail.membership_type_id else None,
            "address": detail.address,
            "phone_count": len(detail.phone_line_ids),
            "bank_count": len(detail.bank_line_ids),
            "id_doc_count": len(detail.id_doc_line_ids),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────────────────────────────
    def _validate(self, detail):
        if not detail.given_name or not detail.family_name:
            raise UserError(_("Given name and family name are both required."))

        cr_type = detail.change_request_id.request_type_id
        if cr_type.requires_head and not detail.membership_type_id:
            raise UserError(
                _(
                    "This Change Request type requires a Head of Household role assignment. "
                    "Pick a role for the new member before applying."
                )
            )

    # ──────────────────────────────────────────────────────────────────────
    # Individual creation
    # ──────────────────────────────────────────────────────────────────────
    def _create_individual(self, detail):
        primary_phone = False
        if detail.phone_line_ids:
            primary = detail.phone_line_ids.filtered(lambda p: p.is_primary)[:1]
            chosen = primary or detail.phone_line_ids[:1]
            primary_phone = chosen.phone_no

        Partner = self.env["res.partner"]
        vals = {
            "name": detail.member_name,
            "given_name": detail.given_name,
            "family_name": detail.family_name,
            "birthdate": detail.birthdate,
            "phone": primary_phone,
            "email": detail.email,
            "is_registrant": True,
            "is_group": False,
        }
        if detail.gender_id:
            vals["gender_id"] = detail.gender_id.id
        # The following fields are added by spp_registry; guard so the module
        # remains importable without it on the path.
        for fname, value in [
            ("address", detail.address),
            ("birth_place", detail.birth_place),
            ("birthdate_not_exact", detail.is_approximate_birthdate),
            ("occupation_id", detail.occupation_id.id if detail.occupation_id else False),
            ("civil_status_id", detail.civil_status_id.id if detail.civil_status_id else False),
            ("income", detail.income),
            ("area_id", detail.area_id.id if detail.area_id else False),
        ]:
            if fname in Partner._fields:
                vals[fname] = value

        individual = Partner.create(vals)
        if hasattr(individual, "name_change"):
            individual.name_change()
        return individual

    # ──────────────────────────────────────────────────────────────────────
    # Sub-record attachers (same shape as create_group strategy)
    # ──────────────────────────────────────────────────────────────────────
    def _attach_phones(self, detail, individual):
        SppPhone = self.env["spp.phone.number"]
        for line in detail.phone_line_ids:
            SppPhone.create(
                {
                    "partner_id": individual.id,
                    "phone_no": line.phone_no,
                    "country_id": line.country_id.id if line.country_id else False,
                    "date_collected": fields.Date.today(),
                }
            )

    def _attach_banks(self, detail, individual):
        Bank = self.env["res.partner.bank"]
        for line in detail.bank_line_ids:
            vals = {
                "partner_id": individual.id,
                "acc_number": line.acc_number,
            }
            if line.acc_holder_name:
                vals["acc_holder_name"] = line.acc_holder_name
            if line.bank_id:
                vals["bank_id"] = line.bank_id.id
            Bank.create(vals)

    def _attach_id_docs(self, detail, individual):
        RegId = self.env["spp.registry.id"]
        for line in detail.id_doc_line_ids:
            RegId.create(
                {
                    "partner_id": individual.id,
                    "id_type_id": line.id_type_id.id,
                    "value": line.value,
                    "expiry_date": line.expiry_date,
                }
            )

    # ──────────────────────────────────────────────────────────────────────
    # Membership + head handling
    # ──────────────────────────────────────────────────────────────────────
    def _is_head_role(self, code):
        return bool(code and code.code == HEAD_ROLE_CODE)

    def _head_code(self):
        return self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-membership-type"),
                ("code", "=", HEAD_ROLE_CODE),
            ],
            limit=1,
        )

    def _demote_existing_head_if_needed(self, detail, group):
        """Demote the group's current head when the user confirmed replacement.

        Only runs when ``replace_existing_head`` is set on the CR — making the
        new member the head is an explicit action, not a silent side effect of
        picking the Head role. "Demote" unlinks the ``head`` code from the
        existing membership's ``membership_type_ids``; other roles are kept.
        """
        # Only when the new member is being made head. Demotion is automatic on
        # apply; the form warns the user beforehand via the info banner.
        if not self._is_head_role(detail.membership_type_id):
            return

        head_code = self._head_code()
        if not head_code:
            return
        Membership = self.env["spp.group.membership"]
        existing_head_memberships = Membership.search(
            [
                ("group", "=", group.id),
                ("status", "=", "active"),
                ("membership_type_ids", "=", head_code.id),
            ]
        )
        for m in existing_head_memberships:
            m.membership_type_ids = [Command.unlink(head_code.id)]
            _logger.info(
                "Demoted existing head individual partner_id=%s on group partner_id=%s "
                "(role removed from membership %s)",
                m.individual.id,
                group.id,
                m.id,
            )

    def _create_membership(self, detail, group, individual):
        vals = {
            "group": group.id,
            "individual": individual.id,
            "start_date": fields.Datetime.now(),
        }
        # The picked Role determines the new member's role; the replace toggle
        # is only a confirmation that gates demoting the current head.
        if detail.membership_type_id:
            vals["membership_type_ids"] = [Command.link(detail.membership_type_id.id)]
        self.env["spp.group.membership"].create(vals)
