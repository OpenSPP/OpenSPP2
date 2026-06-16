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
        self._attach_phones(detail.phone_line_ids, group)
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

        location = None
        if detail.latitude or detail.longitude:
            location = f"{detail.latitude}, {detail.longitude}"

        # One2many lines are shown as separate tables on the review page (OP#876).
        # preview() supplies them via the generic "_tables" contract:
        # each entry is {title, columns, rows} with rows as lists of cell strings.
        tables = []
        phone_rows = [
            [p.phone_no or "", p.country_id.display_name or "", _("Yes") if p.is_primary else ""]
            for p in detail.phone_line_ids
        ]
        if phone_rows:
            tables.append(
                {"title": _("Phone Numbers"), "columns": [_("Number"), _("Country"), _("Primary")], "rows": phone_rows}
            )
        bank_rows = [
            [b.acc_number or "", b.acc_holder_name or "", b.bank_id.display_name or ""] for b in detail.bank_line_ids
        ]
        if bank_rows:
            tables.append(
                {
                    "title": _("Bank Accounts"),
                    "columns": [_("Account Number"), _("Account Holder"), _("Bank")],
                    "rows": bank_rows,
                }
            )
        id_doc_rows = [
            [d.id_type_id.display_name or "", d.value or "", str(d.expiry_date) if d.expiry_date else ""]
            for d in detail.id_doc_line_ids
        ]
        if id_doc_rows:
            tables.append(
                {
                    "title": _("ID Documents"),
                    "columns": [_("Type"), _("Number"), _("Expiry Date")],
                    "rows": id_doc_rows,
                }
            )

        # Existing members: a simple Name + Role table.
        existing_rows = [
            [m.individual_id.name or "", m.membership_type_id.display or ""] for m in detail.member_existing_ids
        ]
        if existing_rows:
            tables.append({"title": _("Existing Members"), "columns": [_("Name"), _("Role")], "rows": existing_rows})

        # New members: one labelled detail block each (full individual record plus
        # that member's own phone numbers), via the generic "_sections" contract.
        sections = []
        for m in detail.member_new_ids:
            title = _("New member: %s") % (m.full_name or "")
            if m.membership_type_id:
                title = f"{title} ({m.membership_type_id.display})"
            member_phone_rows = [
                [p.phone_no or "", p.country_id.display_name or "", _("Yes") if p.is_primary else ""]
                for p in m.phone_line_ids
            ]
            member_tables = []
            if member_phone_rows:
                member_tables.append(
                    {
                        "title": _("Phone Numbers"),
                        "columns": [_("Number"), _("Country"), _("Primary")],
                        "rows": member_phone_rows,
                    }
                )
            sections.append(
                {
                    "title": title,
                    "fields": [
                        [_("Role"), m.membership_type_id.display or ""],
                        [_("Date of Birth"), str(m.birthdate) if m.birthdate else ""],
                        [_("Gender"), m.gender_id.display_name or ""],
                        [_("Civil Status"), m.civil_status_id.display_name or ""],
                        [_("Occupation"), m.occupation_id.display_name or ""],
                        [_("Birth Place"), m.birth_place or ""],
                        [_("Income"), str(m.income) if m.income else ""],
                        [_("Area"), m.area_id.display_name or ""],
                        [_("Address"), m.address or ""],
                        [_("Email"), m.email or ""],
                    ],
                    "tables": member_tables,
                }
            )

        return {
            "_action": "create_group",
            "_header": _("The following group is to be added:"),
            "group_name": detail.group_name,
            "group_type": detail.group_type_id.display if detail.group_type_id else None,
            "area": detail.area_id.display_name if detail.area_id else None,
            "address": detail.address,
            "email": detail.email,
            "location": location,
            "head_of_household": head_label,
            "_tables": tables,
            "_sections": sections,
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
            "address": detail.address,
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
    def _attach_phones(self, phone_lines, partner):
        """Create spp.phone.number records (the registry's Phone Numbers list)
        on ``partner`` from the given phone rows."""
        SppPhone = self.env["spp.phone.number"]
        for line in phone_lines:
            SppPhone.create(
                {
                    "partner_id": partner.id,
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
            individual = Partner.create(self._new_member_vals(line))
            # Some downstream modules format the partner's name on the fly.
            if hasattr(individual, "name_change"):
                individual.name_change()
            # Create the individual's phone records (the registry's Phone
            # Numbers list), the same way the group's phones are attached.
            self._attach_phones(line.phone_line_ids, individual)
            self._create_membership(Membership, group, individual, line.membership_type_id, now)

    def _new_member_vals(self, line):
        """Build res.partner vals for a new in-group individual from a member_new row.

        Mirrors the registry's individual field set (OP#876 QA round 1). res.partner
        has no native middle name, so the middle name is folded into the display name
        only (full_name is "FAMILY, GIVEN MIDDLE").
        """
        full_name = line.full_name or " ".join(filter(None, [line.given_name, line.family_name]))
        # res.partner has a single header phone; fold the captured numbers into
        # it in entry order — there's no "primary" concept for a new member
        # since they all land in the one field (OP#876 QA round 1).
        phone = ", ".join(p.phone_no for p in line.phone_line_ids if p.phone_no)
        vals = {
            "name": full_name,
            "given_name": line.given_name,
            "family_name": line.family_name,
            "birthdate": line.birthdate,
            "birthdate_not_exact": line.is_approximate_birthdate,
            "birth_place": line.birth_place,
            "income": line.income,
            "address": line.address,
            "email": line.email,
            "phone": phone,
            "is_registrant": True,
            "is_group": False,
        }
        if line.gender_id:
            vals["gender_id"] = line.gender_id.id
        if line.occupation_id:
            vals["occupation_id"] = line.occupation_id.id
        if line.civil_status_id:
            vals["civil_status_id"] = line.civil_status_id.id
        if line.area_id and "area_id" in self.env["res.partner"]._fields:
            vals["area_id"] = line.area_id.id
        return vals

    def _create_membership(self, Membership, group, individual, membership_type, when):
        vals = {
            "group": group.id,
            "individual": individual.id,
            "start_date": when,
        }
        if membership_type:
            vals["membership_type_ids"] = [Command.link(membership_type.id)]
        Membership.create(vals)
