from odoo import api, fields, models


class SPPCRDetailAssignProgram(models.Model):
    """Detail model for the assign-to-program CR type."""

    _name = "spp.cr.detail.assign_program"
    _description = "CR Detail: Assign to Program"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    program_id = fields.Many2one(
        "spp.program",
        string="Program",
        tracking=True,
        domain="[('id', 'in', allowed_program_ids)]",
        help="Program the registrant will be enrolled in.",
    )
    allowed_program_ids = fields.Many2many(
        "spp.program",
        string="Allowed Programs",
        compute="_compute_allowed_program_ids",
    )
    registrant_target_type = fields.Selection(
        [("group", "Group"), ("individual", "Individual")],
        compute="_compute_registrant_target_type",
        store=True,
    )
    created_membership_id = fields.Many2one(
        "spp.program.membership",
        string="Created Membership",
        readonly=True,
    )

    @api.depends("registrant_id", "registrant_id.is_group")
    def _compute_registrant_target_type(self):
        for rec in self:
            if not rec.registrant_id:
                rec.registrant_target_type = False
                continue
            rec.registrant_target_type = "group" if rec.registrant_id.is_group else "individual"

    @api.depends("registrant_target_type")
    def _compute_allowed_program_ids(self):
        Program = self.env["spp.program"]
        # target_type only has two distinct values; cache the search per
        # value so a recordset of N details runs at most 2 queries.
        # Note: the result can become stale if a program transitions
        # active <-> ended while a CR form is open. Acceptable: the apply
        # strategy revalidates `state == 'active'` at apply time, so
        # staleness is a UI-only concern.
        cache = {}
        for rec in self:
            tt = rec.registrant_target_type
            if not tt:
                rec.allowed_program_ids = False
                continue
            if tt not in cache:
                cache[tt] = Program.search(
                    [
                        ("state", "=", "active"),
                        ("target_type", "=", tt),
                    ]
                )
            rec.allowed_program_ids = cache[tt]
