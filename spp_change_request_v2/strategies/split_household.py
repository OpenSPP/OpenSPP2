import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

HEAD_ROLE_CODE = "head"

# Editable member fields captured on a move-line (proposed edits, OP#877).
# Labels are translated at use-time (preview), not at module import.
MEMBER_EDIT_FIELDS = [
    ("given_name", "Given Name"),
    ("family_name", "Family Name"),
    ("middle_name", "Middle Name"),
    ("birthdate", "Date of Birth"),
    ("birth_place", "Birth Place"),
    ("gender_id", "Gender"),
    ("civil_status_id", "Civil Status"),
    ("occupation_id", "Occupation"),
    ("income", "Income"),
]


class SPPCRApplySplitHousehold(models.AbstractModel):
    """Custom apply strategy for Split Household CR type (OP#877)."""

    _name = "spp.cr.apply.split_household"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Split Household"

    # ──────────────────────────────────────────────────────────────────────
    # apply
    # ──────────────────────────────────────────────────────────────────────
    def apply(self, change_request):
        source_group = change_request.registrant_id
        if not source_group.is_group:
            raise UserError(_("Registrant must be a group."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))
        if not detail.member_line_ids:
            raise UserError(_("Select at least one member to move to the new household."))
        if not detail.new_group_name:
            raise UserError(_("New household name is required."))

        new_group = self._create_new_group(detail, source_group)
        self._attach_group_lines(detail, new_group)

        Membership = self.env["spp.group.membership"]
        head_kind = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", HEAD_ROLE_CODE)
        for line in detail.member_line_ids:
            individual = line.individual_id
            # End the source membership.
            source_membership = Membership.search(
                [("group", "=", source_group.id), ("individual", "=", individual.id), ("status", "=", "active")],
                limit=1,
            )
            if source_membership:
                source_membership.write({"ended_date": fields.Datetime.now()})
            # Apply any proposed edits to the individual.
            self._apply_member_edits(line, individual)
            # Create the membership in the new group with the chosen role.
            vals = {"group": new_group.id, "individual": individual.id, "start_date": fields.Datetime.now()}
            if line.membership_type_id:
                vals["membership_type_ids"] = [Command.link(line.membership_type_id.id)]
            elif head_kind:
                # carry over non-head roles from the source membership
                roles = (source_membership.membership_type_ids - head_kind) if source_membership else False
                if roles:
                    vals["membership_type_ids"] = [Command.set(roles.ids)]
            Membership.create(vals)

        detail.write({"created_group_id": new_group.id})
        _logger.info(
            "Split household: moved %d members from group partner_id=%s to new group partner_id=%s via CR %s",
            len(detail.member_line_ids),
            source_group.id,
            new_group.id,
            change_request.name,
        )
        return True

    def _create_new_group(self, detail, source_group):
        Partner = self.env["res.partner"]
        vals = {
            "name": detail.new_group_name,
            "is_registrant": True,
            "is_group": True,
        }
        group_type = detail.new_group_type_id or source_group.group_type_id
        if group_type and "group_type_id" in Partner._fields:
            vals["group_type_id"] = group_type.id
        for fname, value in [
            ("email", detail.new_email),
            ("address", detail.new_address),
            ("area_id", detail.new_area_id.id if detail.new_area_id else False),
            ("latitude", detail.new_latitude),
            ("longitude", detail.new_longitude),
        ]:
            if fname in Partner._fields:
                vals[fname] = value
        return Partner.create(vals)

    def _attach_group_lines(self, detail, group):
        """Attach the new household's phone/bank/ID lines to the group partner."""
        for line in detail.new_phone_line_ids:
            self.env["spp.phone.number"].create(
                {
                    "partner_id": group.id,
                    "phone_no": line.phone_no,
                    "country_id": line.country_id.id if line.country_id else False,
                    "date_collected": fields.Date.today(),
                }
            )
        for line in detail.new_bank_line_ids:
            bank_vals = {"partner_id": group.id, "acc_number": line.acc_number}
            if line.acc_holder_name:
                bank_vals["acc_holder_name"] = line.acc_holder_name
            if line.bank_id:
                bank_vals["bank_id"] = line.bank_id.id
            self.env["res.partner.bank"].create(bank_vals)
        for line in detail.new_id_doc_line_ids:
            self.env["spp.registry.id"].create(
                {
                    "partner_id": group.id,
                    "id_type_id": line.id_type_id.id,
                    "value": line.value,
                    "expiry_date": line.expiry_date,
                }
            )

    def _changed_edits(self, line):
        """Return [(field, label, new_value)] for member fields the line changes."""
        individual = line.individual_id
        changed = []
        for fname, label in MEMBER_EDIT_FIELDS:
            if fname not in line._fields:
                continue
            new_val = line[fname]
            if not new_val:
                continue
            current = individual[fname] if individual and fname in individual._fields else False
            if new_val != current:
                changed.append((fname, label, new_val))
        return changed

    def _apply_member_edits(self, line, individual):
        vals = {}
        for fname, _label, new_val in self._changed_edits(line):
            if fname in individual._fields:
                vals[fname] = new_val.id if hasattr(new_val, "id") else new_val
        if vals:
            individual.write(vals)
            if hasattr(individual, "name_change"):
                individual.name_change()

    # ──────────────────────────────────────────────────────────────────────
    # preview
    # ──────────────────────────────────────────────────────────────────────
    def preview(self, change_request):
        detail = change_request.get_detail()
        if not detail:
            return {}

        reason_label = None
        if detail.split_reason:
            reason_label = dict(detail.fields_get(["split_reason"])["split_reason"]["selection"]).get(
                detail.split_reason
            )

        members_rows = [
            [line.individual_id.display_name or "", line.membership_type_id.display if line.membership_type_id else ""]
            for line in detail.member_line_ids
        ]
        tables = [
            {"title": _("Members to Move"), "columns": [_("Name"), _("Role")], "rows": members_rows},
        ]

        # Separate table for proposed member edits (like the Edit Member CR).
        edit_rows = []
        for line in detail.member_line_ids:
            for _fname, label, new_val in self._changed_edits(line):
                display = new_val.display_name if hasattr(new_val, "display_name") else str(new_val)
                edit_rows.append([line.individual_id.display_name or "", _(label), display])
        if edit_rows:
            tables.append(
                {"title": _("Member Edits"), "columns": [_("Member"), _("Field"), _("New Value")], "rows": edit_rows}
            )

        return {
            "_action": "split_household",
            "_header": _("The following new household will be created:"),
            _("New Household Name"): detail.new_group_name,
            _("Group Type"): detail.new_group_type_id.display if detail.new_group_type_id else None,
            _("Area"): detail.new_area_id.display_name if detail.new_area_id else None,
            _("Address"): detail.new_address or None,
            _("Email"): detail.new_email or None,
            _("Reason for Split"): reason_label,
            _("Remarks"): detail.remarks or None,
            "_tables": tables,
        }
