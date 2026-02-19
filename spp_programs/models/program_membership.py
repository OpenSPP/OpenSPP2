# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import constants


class SPPProgramMembership(models.Model):
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
    ]

    _name = "spp.program.membership"
    _description = "Program Membership"
    _inherits = {"res.partner": "partner_id"}
    _order = "id desc"

    partner_id = fields.Many2one(
        "res.partner",
        "Registrant",
        help="A beneficiary",
        required=True,
        delegate=True,
        ondelete="cascade",
        domain=[("is_registrant", "=", True)],
    )
    program_id = fields.Many2one("spp.program", "", help="A program", required=True)

    # TODO: When the state is changed from "exited", "not_eligible" or "duplicate" to something else
    #      then reset the deduplication date.
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("enrolled", "Enrolled"),
            ("paused", "Paused"),
            ("exited", "Exited"),
            ("not_eligible", "Not Eligible"),
            ("duplicated", "Duplicated"),
        ],
        default="draft",
        copy=False,
    )

    enrollment_date = fields.Datetime(compute="_compute_enrolled_date", store=True)

    last_deduplication = fields.Date("Last Deduplication Date")
    exit_date = fields.Date()

    registrant_id = fields.Integer(string="Registrant ID", related="partner_id.id")

    @api.constrains("partner_id", "program_id")
    def _check_unique_partner_per_program(self):
        # Prefetch partner_id and program_id to avoid N+1 queries in loop
        self.mapped("partner_id")
        self.mapped("program_id")

        for record in self:
            if record.partner_id and record.program_id:
                existing = self.search(
                    [
                        ("partner_id", "=", record.partner_id.id),
                        ("program_id", "=", record.program_id.id),
                        ("id", "!=", record.id),
                    ],
                    limit=1,
                )
                if existing:
                    raise ValidationError(_("Beneficiary must be unique per program."))

    # TODO: Implement exit reasons
    # exit_reason_id = fields.Many2one("Exit Reason") Default: Completed, Opt-Out, Other

    # TODO: Implement not eligible reasons
    # Default: "Missing data", "Does not match the criterias", "Duplicate", "Other"
    # not_eligible_reason_id = fields.Many2one("Not Eligible Reason")

    # TODO: Add a field delivery_mechanism_id
    # delivery_mechanism_id = fields.Many2one("Delivery mechanism type", help="Delivery mechanism")
    # the phone number, bank account, etc.
    delivery_mechanism_value = fields.Char()

    # TODO: JJ - Add a field for the preferred notification method

    deduplication_status = fields.Selection(
        selection=[
            ("new", "New"),
            ("processing", "Processing"),
            ("verified", "Verified"),
            ("duplicated", "duplicated"),
        ],
        default="new",
        copy=False,
    )

    @api.depends("state")
    def _compute_enrolled_date(self):
        # Prefetch state to avoid N+1 queries in loop (if not already loaded)
        self.mapped("state")

        for rec in self:
            if rec.state == "enrolled":
                rec.enrollment_date = fields.Datetime.now()

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        context = self.env.context
        arch, view = super()._get_view(view_id, view_type, **options)

        if view_type == "form":
            update_arch = False
            doc = arch
            # Check if we need to change the partner_id domain filter
            target_type = context.get("target_type", False)
            if target_type:
                domain = None
                if context.get("target_type", False) == "group":
                    domain = "[('is_registrant', '=', True), ('is_group','=',True)]"
                elif context.get("target_type", False) == "individual":
                    domain = "[('is_registrant', '=', True), ('is_group','=',False)]"
                if domain:
                    update_arch = True
                    nodes = doc.xpath("//field[@name='partner_id']")
                    for node in nodes:
                        node.set("domain", domain)

            if update_arch:
                arch = etree.tostring(doc, encoding="unicode")
        return arch, view

    def name_get(self):
        res = super().name_get()
        # Prefetch program_id and partner_id to avoid N+1 queries in loop
        self.mapped("program_id.name")
        self.mapped("partner_id.name")

        for rec in self:
            name = ""
            if rec.program_id:
                name += "[" + rec.program_id.name + "] "
            if rec.partner_id:
                name += rec.partner_id.name
            rec.display_name = name
        return res

    def open_beneficiaries_form(self):
        for rec in self:
            return {
                "name": "Program Beneficiaries",
                "view_mode": "form",
                "res_model": "spp.program.membership",
                "res_id": rec.id,
                "view_id": self.env.ref("spp_programs.view_program_membership_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
                "context": {
                    "target_type": rec.program_id.target_type,
                    "default_program_id": rec.program_id.id,
                },
            }

    def open_registrant_form(self):
        if self.partner_id.is_group:
            return {
                "name": "Group Member",
                "view_mode": "form",
                "res_model": "res.partner",
                "res_id": self.partner_id.id,
                "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
                "context": {
                    "default_is_group": True,
                    "create": False,
                    "edit": False,
                },
            }
        else:
            return {
                "name": "Individual Member",
                "view_mode": "form",
                "res_model": "res.partner",
                "res_id": self.partner_id.id,
                "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
                "context": {
                    "default_is_group": False,
                    "create": False,
                    "edit": False,
                },
            }

    def verify_eligibility(self):
        eligibility_managers = self.program_id.get_managers(constants.MANAGER_ELIGIBILITY)
        member = self
        for em in eligibility_managers:
            member = em.enroll_eligible_registrants(member)
        if len(member) == 0:
            self.state = "not_eligible"
        return

    def enroll_eligible_registrants(self):
        eligibility_managers = self.program_id.get_managers(constants.MANAGER_ELIGIBILITY)
        message = None
        kind = "success"
        member = self
        for em in eligibility_managers:
            member = em.enroll_eligible_registrants(member)

        if len(member) > 0:
            if self.state != "enrolled":
                self.write(
                    {
                        "state": "enrolled",
                        "enrollment_date": fields.Datetime.now(),
                    }
                )
                message = _("%s Beneficiaries enrolled.", len(member))
                kind = "success"
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Enrollment"),
                        "message": message,
                        "sticky": False,
                        "type": kind,
                        "next": {
                            "type": "ir.actions.act_window_close",
                        },
                    },
                }

        else:
            self.state = "not_eligible"
            message = "beneficiary is not eligible"
            kind = "warning"
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Enrollment"),
                    "message": message,
                    "sticky": False,
                    "type": kind,
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }

    def deduplicate_beneficiaries(self):
        deduplication_managers = self.program_id.get_managers(constants.MANAGER_DEDUPLICATION)

        message = None
        kind = "success"
        if len(deduplication_managers):
            states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
            duplicates = 0
            for el in deduplication_managers:
                duplicates += el.deduplicate_beneficiaries(states)

                if duplicates > 0:
                    message = _("%s Beneficiaries duplicate.", duplicates)
                    kind = "warning"
                else:
                    message = _("No duplicates found.")
                    kind = "success"
        else:
            raise UserError(_("No Deduplication Manager defined."))

        if message:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Deduplication"),
                    "message": message,
                    "sticky": False,
                    "type": kind,
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }

    def back_to_draft(self):
        """Reset membership to draft state."""
        self.write(
            {
                "state": "draft",
            }
        )
        return

    def action_pause(self):
        """Pause the membership."""
        self.ensure_one()
        if self.state != "enrolled":
            raise UserError(_("Only enrolled memberships can be paused."))
        self.write({"state": "paused"})

    def action_resume(self):
        """Resume a paused membership."""
        self.ensure_one()
        if self.state != "paused":
            raise UserError(_("Only paused memberships can be resumed."))
        self.write({"state": "enrolled"})

    def action_exit(self):
        """Exit the registrant from the program."""
        self.ensure_one()
        if self.state not in ("enrolled", "paused"):
            raise UserError(_("Only enrolled or paused memberships can be exited."))
        self.write(
            {
                "state": "exited",
                "exit_date": fields.Date.today(),
            }
        )

    @api.model_create_multi
    def bulk_create_memberships(self, vals_list, chunk_size=1000):
        """Create program memberships in bulk with optional chunking.

        This helper is intended for large enrollment jobs (e.g. CEL-driven
        bulk enrollment) where thousands of memberships need to be created
        in a single operation.

        It preserves the normal create() semantics, including:
        - standard ORM validations and constraints
        - audit logging (via spp_audit rules)
        - source tracking mixins

        The only optimisation is to:
        - accept already-prepared value dicts
        - optionally split very large batches into smaller chunks to keep
          memory use and per-transaction work bounded.
        """
        if not vals_list:
            return self.env["spp.program.membership"]

        if chunk_size and chunk_size > 0:
            all_memberships = self.env["spp.program.membership"]
            for i in range(0, len(vals_list), chunk_size):
                batch_vals = vals_list[i : i + chunk_size]
                # Use sudo() to avoid per-record access right re-evaluation
                # when called from trusted managers, while still going
                # through the ORM and audit hooks.
                batch_memberships = super(
                    SPPProgramMembership,
                    self.sudo(),  # nosemgrep: odoo-sudo-without-context
                    # Bulk enrollment helper used by trusted background managers
                    # (e.g. CEL load tests); still goes through ORM and audit hooks.
                ).create(batch_vals)
                all_memberships |= batch_memberships
            return all_memberships

        return super(
            SPPProgramMembership,
            self.sudo(),  # nosemgrep: odoo-sudo-without-context
        ).create(vals_list)
