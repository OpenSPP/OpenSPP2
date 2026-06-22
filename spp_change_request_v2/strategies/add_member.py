# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Apply strategy for the Add Member CR (OP#871).

Adds an existing individual registrant to the group with a role. (The earlier
create-a-new-individual flow was replaced per the updated #871 spec — the first
page now searches for an existing member.)
"""

import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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

        self._validate(detail, group)

        vals = {
            "group": group.id,
            "individual": detail.individual_id.id,
            "start_date": fields.Datetime.now(),
        }
        if detail.membership_type_id:
            vals["membership_type_ids"] = [Command.link(detail.membership_type_id.id)]
        self.env["spp.group.membership"].create(vals)

        _logger.info(
            "Added existing member partner_id=%s to group partner_id=%s via CR %s",
            detail.individual_id.id,
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
        individual = detail.individual_id

        def field_val(name):
            """Read a field off the selected individual, guarding for registry
            fields that may be absent without spp_registry on the path."""
            if not individual or name not in individual._fields:
                return None
            return individual[name] or None

        gender = field_val("gender_id")
        civil_status = field_val("civil_status_id")
        occupation = field_val("occupation_id")
        area = field_val("area_id")
        birthdate = field_val("birthdate")

        # The review page shows who is being added; empty fields render as a
        # "-" placeholder through the action-summary formatter.
        return {
            "_action": "add_member",
            "_header": _("The following individual is to be added to the group:"),
            _("Group"): change_request.registrant_id.display_name,
            _("Name"): individual.display_name if individual else None,
            _("Role"): detail.membership_type_id.display if detail.membership_type_id else None,
            _("Date of Birth"): str(birthdate) if birthdate else None,
            _("Gender"): gender.display_name if gender else None,
            _("Civil Status"): civil_status.display_name if civil_status else None,
            _("Occupation"): occupation.display_name if occupation else None,
            _("Area"): area.display_name if area else None,
            _("Address"): field_val("address"),
            _("Email"): individual.email if individual else None,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────────────────────────────
    def _validate(self, detail, group):
        individual = detail.individual_id
        if not individual:
            raise UserError(_("Select an individual to add to the group."))
        if individual.is_group:
            raise UserError(_("Only individuals can be added as group members."))

        already_member = self.env["spp.group.membership"].search_count(
            [
                ("group", "=", group.id),
                ("individual", "=", individual.id),
                ("status", "=", "active"),
            ]
        )
        if already_member:
            raise UserError(_("%s is already an active member of this group.") % individual.display_name)

        cr_type = detail.change_request_id.request_type_id
        if cr_type.requires_head and not detail.membership_type_id:
            raise UserError(
                _(
                    "This Change Request type requires a Head of Household role assignment. "
                    "Pick a role for the new member before applying."
                )
            )

        # OP#871: the Head role is offered for all groups; if the target group
        # already has an active Head of Household, adding another as Head is
        # rejected here (a validation error, for uniformity with the other CRs)
        # rather than silently hidden from the picker.
        role = detail.membership_type_id
        if role and role.code == "head":
            group_has_head = self.env["spp.group.membership"].search_count(
                [
                    ("group", "=", group.id),
                    ("status", "=", "active"),
                    ("membership_type_ids.code", "=", "head"),
                ]
            )
            if group_has_head:
                raise UserError(_("This group already has a Head of Household. Only one member can be Head."))
