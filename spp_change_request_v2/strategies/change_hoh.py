import logging

from odoo import Command, _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ROLE_NAMESPACE = "urn:openspp:vocab:group-membership-type"
HEAD_ROLE_CODE = "head"


class SPPCRApplyChangeHOH(models.AbstractModel):
    """Custom apply strategy for Change Head of Household CR type (OP#873)."""

    _name = "spp.cr.apply.change_hoh"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Change Head of Household"

    def apply(self, change_request):
        """Apply the per-member role assignments. Each member's role is set to
        exactly their New Role; a blank New Role means the member ends up with
        NO role (OP#873 QA). The member assigned Head becomes the new head; the
        current head may not be reassigned Head and only one Head is allowed."""
        group = change_request.registrant_id
        if not group.is_group:
            raise UserError(_("Registrant must be a group."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        head_kind = self.env["spp.vocabulary.code"].get_code(ROLE_NAMESPACE, HEAD_ROLE_CODE)
        if not head_kind:
            raise UserError(
                _(
                    "Head of Household membership type not found. "
                    "Please configure the 'head' membership type in the vocabulary."
                )
            )

        lines = detail.member_line_ids
        if not lines:
            raise UserError(_("No members are available to assign roles to."))

        head_lines = lines.filtered(lambda r: r.new_role_id == head_kind)
        if not head_lines:
            raise UserError(_("You must designate one member as the new Head of Household."))
        if len(head_lines) > 1:
            raise UserError(_("A group can have at most one Head of Household."))
        if detail.current_head_id and head_lines.individual_id == detail.current_head_id:
            raise UserError(
                _("The current Head of Household cannot be set as Head again. Designate a different member.")
            )

        Membership = self.env["spp.group.membership"]

        def active_membership(line):
            membership = line.membership_id
            if not membership or membership.status != "active":
                # Membership may have changed since the lines were seeded.
                membership = Membership.search(
                    [
                        ("group", "=", group.id),
                        ("individual", "=", line.individual_id.id),
                        ("status", "=", "active"),
                    ],
                    limit=1,
                )
            return membership

        # The CR follows the New Role column exactly: every member's roles become
        # [New Role] or [] when blank. Process the new head LAST so the group
        # never transiently holds two heads (rejected by the registry constraint
        # at flush) while the outgoing head's row is being cleared.
        ordered = lines.sorted(key=lambda r: 1 if r.new_role_id == head_kind else 0)
        for line in ordered:
            membership = active_membership(line)
            if not membership:
                continue
            role_ids = line.new_role_id.ids if line.new_role_id else []
            membership.write({"membership_type_ids": [Command.set(role_ids)]})

        _logger.info(
            "Applied head-of-household role changes for group partner_id=%s via CR %s (new head partner_id=%s)",
            group.id,
            change_request.name,
            head_lines.individual_id.id,
        )
        return True

    def preview(self, change_request):
        """Preview the role changes: household, reason, remarks and a members
        table (Name / Current Role / New Role)."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        reason_label = None
        if detail.reason:
            selection = dict(detail.fields_get(["reason"])["reason"]["selection"])
            reason_label = selection.get(detail.reason)

        rows = []
        for line in detail.member_line_ids:
            rows.append(
                [
                    line.individual_id.display_name or "",
                    line.old_role_display or "",
                    line.new_role_id.display if line.new_role_id else "",
                ]
            )

        return {
            "_action": "change_head_of_household",
            "_header": _("Head of Household role changes to apply:"),
            _("Household"): change_request.registrant_id.display_name,
            _("Reason for Change"): reason_label,
            _("Remarks"): detail.remarks,
            "_tables": [
                {
                    "title": _("Members"),
                    "columns": [_("Name"), _("Current Role"), _("New Role")],
                    "rows": rows,
                }
            ],
        }
