from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

ROLE_NAMESPACE = "urn:openspp:vocab:group-membership-type"
HEAD_ROLE_CODE = "head"


class SPPCRDetailChangeHOH(models.Model):
    """Detail model for Change Head of Household CR type (OP#873)."""

    _name = "spp.cr.detail.change_hoh"
    _description = "CR Detail: Change Head of Household"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # HEAD OF HOUSEHOLD INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    current_head_id = fields.Many2one(
        "res.partner",
        string="Current Head of Household",
        compute="_compute_current_head",
        store=True,
        readonly=True,
    )
    # One editable role line per active group member. The new head is whichever
    # member is assigned the Head role (OP#873 — replaces the single new-head
    # dropdown with a members-with-roles table).
    member_line_ids = fields.One2many(
        "spp.cr.detail.change_hoh.member",
        "detail_id",
        string="Members",
    )
    reason = fields.Selection(
        [
            ("deceased", "Head Deceased"),
            ("incapacitated", "Head Incapacitated"),
            ("left_household", "Head Left Household"),
            ("age_change", "Age-based Change"),
            ("correction", "Data Correction"),
            ("other", "Other"),
        ],
        string="Reason for Change",
        tracking=True,
    )
    remarks = fields.Text(string="Remarks", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends("change_request_id.registrant_id")
    def _compute_current_head(self):
        """Find the current head of household."""
        head_kind = self.env["spp.vocabulary.code"].get_code(ROLE_NAMESPACE, HEAD_ROLE_CODE)
        for rec in self:
            current_head = False
            if rec.change_request_id.registrant_id and head_kind:
                membership = self.env["spp.group.membership"].search(
                    [
                        ("group", "=", rec.change_request_id.registrant_id.id),
                        ("membership_type_ids", "in", [head_kind.id]),
                        ("status", "=", "active"),
                    ],
                    limit=1,
                )
                if membership:
                    current_head = membership.individual
            rec.current_head_id = current_head

    @api.model_create_multi
    def create(self, vals_list):
        details = super().create(vals_list)
        for detail in details:
            if not detail.member_line_ids:
                detail._seed_member_lines()
        return details

    def _seed_member_lines(self):
        """Populate one editable role line per active group member.

        The New Role is left blank (NOT prefilled with the current role): the
        user only fills the row(s) they want to change — typically setting one
        member's New Role to Head. A blank New Role means "no change"; the
        previous head is demoted automatically on apply (OP#873 QA)."""
        self.ensure_one()
        group = self.change_request_id.registrant_id
        if not group or not group.is_group:
            return
        memberships = self.env["spp.group.membership"].search([("group", "=", group.id), ("status", "=", "active")])
        lines = []
        for membership in memberships:
            current_roles = membership.membership_type_ids
            lines.append(
                (
                    0,
                    0,
                    {
                        "individual_id": membership.individual.id,
                        "membership_id": membership.id,
                        "old_role_display": ", ".join(current_roles.mapped("display")),
                        "new_role_id": False,
                    },
                )
            )
        self.member_line_ids = lines


class SPPCRDetailChangeHOHMember(models.Model):
    """One editable role line per current group member (Change HoH, OP#873)."""

    _name = "spp.cr.detail.change_hoh.member"
    _description = "CR Detail: Change HoH - Member Role"

    detail_id = fields.Many2one(
        "spp.cr.detail.change_hoh",
        required=True,
        ondelete="cascade",
    )
    individual_id = fields.Many2one("res.partner", string="Member", readonly=True)
    membership_id = fields.Many2one("spp.group.membership", readonly=True)
    old_role_display = fields.Char(string="Current Role", readonly=True)
    new_role_id = fields.Many2one(
        "spp.vocabulary.code",
        string="New Role",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-membership-type')]",
    )

    @api.constrains("new_role_id")
    def _check_head_assignment(self):
        """Validate the Head assignment at save/submit (OP#873 QA):
        - at most one member may be set to Head;
        - the current Head of Household cannot be reassigned Head (a Change HoH
          must hand the role to a different member)."""
        head = self.env["spp.vocabulary.code"].get_code(ROLE_NAMESPACE, HEAD_ROLE_CODE)
        if not head:
            return
        for detail in self.mapped("detail_id"):
            head_lines = detail.member_line_ids.filtered(lambda r: r.new_role_id == head)
            if len(head_lines) > 1:
                raise ValidationError(_("A group can have at most one Head of Household."))
            if head_lines and detail.current_head_id and head_lines.individual_id == detail.current_head_id:
                raise ValidationError(
                    _("The current Head of Household cannot be set as Head again. Designate a different member.")
                )
