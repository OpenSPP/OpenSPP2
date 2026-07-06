import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
        for line in detail.member_line_ids:
            individual = line.individual_id
            # End the source membership.
            source_membership = Membership.search(
                [("group", "=", source_group.id), ("individual", "=", individual.id), ("status", "=", "active")],
                limit=1,
            )
            if source_membership:
                source_membership.write({"ended_date": fields.Datetime.now()})
            # Create the membership in the new group following the CR line's role
            # exactly - a blank role on the line means no role in the new group
            # (the source role is NOT carried over).
            vals = {"group": new_group.id, "individual": individual.id, "start_date": fields.Datetime.now()}
            if line.membership_type_id:
                vals["membership_type_ids"] = [Command.link(line.membership_type_id.id)]
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
