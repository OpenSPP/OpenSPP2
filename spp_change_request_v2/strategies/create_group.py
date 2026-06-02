# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Apply strategy for the Create New Group CR (OP#876)."""

import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

HEAD_ROLE_CODE = "head"


class SPPCRApplyCreateGroup(models.AbstractModel):
    """Custom apply strategy for Create Group CR type."""

    _name = "spp.cr.apply.create_group"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Create New Group"

    # ──────────────────────────────────────────────────────────────────────
    # apply
    # ──────────────────────────────────────────────────────────────────────
    def apply(self, change_request):
        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        self._validate(detail)

        # 1. Group itself.
        group = self._create_group(detail)

        # 2. Multi-value attachments tied to the group partner.
        self._attach_phones(detail, group)
        self._attach_banks(detail, group)
        self._attach_id_docs(detail, group)

        # 3. Members (existing + new). Each line carries its own role, the
        #    Head requirement is already validated in `_validate`.
        self._attach_members(detail, group)

        detail.write({"created_group_id": group.id})
        change_request.write({"registrant_id": group.id})

        _logger.info(
            "Created group partner_id=%s (%s) via CR %s",
            group.id,
            group.name,
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

        existing_heads, new_heads = detail._heads()
        head_label = None
        if existing_heads:
            head_label = existing_heads[0].individual_id.name
        elif new_heads:
            head_label = new_heads[0].full_name

        return {
            "_action": "create_group",
            "group_name": detail.group_name,
            "group_type": detail.group_type_id.display if detail.group_type_id else None,
            "address": ", ".join(filter(None, [detail.address_line1, detail.city])),
            "phone_count": len(detail.phone_line_ids),
            "bank_count": len(detail.bank_line_ids),
            "id_doc_count": len(detail.id_doc_line_ids),
            "existing_member_count": len(detail.member_existing_ids),
            "new_member_count": len(detail.member_new_ids),
            "head_of_household": head_label,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────────────────────────────
    def _validate(self, detail):
        if not detail.group_name:
            raise UserError(_("Group name is required."))

        cr_type = detail.change_request_id.request_type_id

        # Member-presence requirement.
        has_members = bool(detail.member_existing_ids or detail.member_new_ids)
        if not cr_type.allow_empty_members and not has_members:
            raise UserError(
                _(
                    "This Change Request type requires at least one member. "
                    "Add an existing individual or create a new one before applying."
                )
            )

        # Head requirement.
        if cr_type.requires_head:
            head_count = detail._head_count()
            if head_count == 0:
                raise UserError(
                    _(
                        "This Change Request type requires a Head of Household. "
                        "Assign the 'Head' role to exactly one member before applying."
                    )
                )
            if head_count > 1:
                # _check_at_most_one_head already catches this at write-time,
                # but apply-time is the last line of defense.
                raise UserError(_("A group can have at most one Head of Household."))

    # ──────────────────────────────────────────────────────────────────────
    # Group creation
    # ──────────────────────────────────────────────────────────────────────
    def _create_group(self, detail):
        # Pick the first explicitly-flagged primary phone, falling back to
        # the first phone in the list, so the partner header carries
        # something searchable.
        primary_phone = False
        if detail.phone_line_ids:
            primary = detail.phone_line_ids.filtered(lambda p: p.is_primary)[:1]
            chosen = primary or detail.phone_line_ids[:1]
            primary_phone = chosen.phone_no

        group_vals = {
            "name": detail.group_name,
            "is_registrant": True,
            "is_group": True,
            "street": detail.address_line1,
            "street2": detail.address_line2,
            "city": detail.city,
            "state_id": detail.state_id.id if detail.state_id else False,
            "zip": detail.postal_code,
            "country_id": detail.country_id.id if detail.country_id else False,
            "phone": primary_phone,
            "email": detail.email,
        }
        if detail.group_type_id:
            group_vals["group_type_id"] = detail.group_type_id.id
        if detail.area_id and "area_id" in self.env["res.partner"]._fields:
            group_vals["area_id"] = detail.area_id.id
        return self.env["res.partner"].create(group_vals)

    # ──────────────────────────────────────────────────────────────────────
    # Sub-record attachers
    # ──────────────────────────────────────────────────────────────────────
    def _attach_phones(self, detail, group):
        SppPhone = self.env["spp.phone.number"]
        for line in detail.phone_line_ids:
            SppPhone.create(
                {
                    "partner_id": group.id,
                    "phone_no": line.phone_no,
                    "country_id": line.country_id.id if line.country_id else False,
                    "date_collected": fields.Date.today(),
                }
            )

    def _attach_banks(self, detail, group):
        Bank = self.env["res.partner.bank"]
        for line in detail.bank_line_ids:
            vals = {
                "partner_id": group.id,
                "acc_number": line.acc_number,
            }
            if line.acc_holder_name:
                vals["acc_holder_name"] = line.acc_holder_name
            if line.bank_id:
                vals["bank_id"] = line.bank_id.id
            Bank.create(vals)

    def _attach_id_docs(self, detail, group):
        RegId = self.env["spp.registry.id"]
        for line in detail.id_doc_line_ids:
            RegId.create(
                {
                    "partner_id": group.id,
                    "id_type_id": line.id_type_id.id,
                    "value": line.value,
                    "expiry_date": line.expiry_date,
                }
            )

    # ──────────────────────────────────────────────────────────────────────
    # Members
    # ──────────────────────────────────────────────────────────────────────
    def _attach_members(self, detail, group):
        Membership = self.env["spp.group.membership"]
        Partner = self.env["res.partner"]
        now = fields.Datetime.now()

        for line in detail.member_existing_ids:
            self._create_membership(Membership, group, line.individual_id, line.membership_type_id, now)

        for line in detail.member_new_ids:
            full_name = line.full_name or " ".join(filter(None, [line.given_name, line.family_name]))
            individual_vals = {
                "name": full_name,
                "given_name": line.given_name,
                "family_name": line.family_name,
                "birthdate": line.birthdate,
                "phone": line.phone,
                "is_registrant": True,
                "is_group": False,
            }
            if line.gender_id:
                individual_vals["gender_id"] = line.gender_id.id
            individual = Partner.create(individual_vals)
            # Some downstream modules format the partner's name on the fly.
            if hasattr(individual, "name_change"):
                individual.name_change()
            self._create_membership(Membership, group, individual, line.membership_type_id, now)

    def _create_membership(self, Membership, group, individual, membership_type, when):
        vals = {
            "group": group.id,
            "individual": individual.id,
            "start_date": when,
        }
        if membership_type:
            vals["membership_type_ids"] = [Command.link(membership_type.id)]
        Membership.create(vals)
