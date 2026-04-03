# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import constants

_logger = logging.getLogger(__name__)


class SPPProgramMembership(models.Model):
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
    ]

    _name = "spp.program.membership"
    _description = "Program Membership"
    _inherits = {"res.partner": "partner_id"}
    _order = "id desc"

    _unique_partner_program = models.Constraint(
        "UNIQUE(partner_id, program_id)",
        "Beneficiary must be unique per program.",
    )

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS
                spp_program_membership_program_id_state_idx
            ON spp_program_membership (program_id, state)
            """
        )

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

    duplicate_reason = fields.Char(
        string="Duplicate Reason",
        compute="_compute_duplicate_reason",
    )

    def _compute_duplicate_reason(self):
        for rec in self:
            if rec.state == "duplicated":
                dup_records = self.env["spp.program.membership.duplicate"].search(
                    [("beneficiary_ids", "in", rec.id), ("state", "=", "duplicate")],
                    order="id desc",
                    limit=1,
                )
                rec.duplicate_reason = dup_records.reason if dup_records else False
            else:
                rec.duplicate_reason = False

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
            if self.state in ("duplicated", "exited"):
                message = _(
                    "Cannot enroll: beneficiary is currently %s.",
                    dict(self._fields["state"].selection).get(self.state, self.state),
                )
                kind = "warning"
            elif self.state != "enrolled":
                self.write(
                    {
                        "state": "enrolled",
                        "enrollment_date": fields.Datetime.now(),
                    }
                )
                message = _("%s Beneficiaries enrolled.", len(member))
                kind = "success"
            else:
                message = _("Beneficiary is already enrolled.")
                kind = "info"
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

    @api.model
    def bulk_create_memberships(self, vals_list, chunk_size=1000, skip_duplicates=False):
        """Create program memberships in bulk with optional chunking.

        This helper is intended for large enrollment jobs (e.g. CEL-driven
        bulk enrollment) where thousands of memberships need to be created
        in a single operation.

        :param vals_list: List of dicts with membership values
        :param chunk_size: Number of records per batch (default 1000)
        :param skip_duplicates: When True, use INSERT ... ON CONFLICT DO NOTHING
            to silently skip duplicate (partner_id, program_id) pairs instead of
            raising IntegrityError. Returns the count of inserted rows.
        :return: Recordset (skip_duplicates=False) or int count (skip_duplicates=True)
        """
        if not vals_list:
            return 0 if skip_duplicates else self.env["spp.program.membership"]

        if skip_duplicates:
            return self._bulk_insert_on_conflict(vals_list, chunk_size)

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

    def _bulk_insert_on_conflict(self, vals_list, chunk_size=1000):
        """Insert memberships using raw SQL with ON CONFLICT DO NOTHING.

        Bypasses ORM for maximum throughput during bulk enrollment. Duplicates
        (matching the UNIQUE constraint on partner_id, program_id) are silently
        skipped.

        :param vals_list: List of dicts with at least partner_id, program_id, state
        :param chunk_size: Number of records per SQL INSERT batch
        :return: Total number of rows actually inserted
        """
        cr = self.env.cr
        uid = self.env.uid
        total_inserted = 0

        now = fields.Datetime.now()

        for i in range(0, len(vals_list), chunk_size):
            batch = vals_list[i : i + chunk_size]
            values = []
            params = []
            for v in batch:
                state = v.get("state", "draft")
                enrollment_date = now if state == "enrolled" else None
                values.append("(%s, %s, %s, %s, %s, %s, now(), now())")
                params.extend(
                    [
                        v["partner_id"],
                        v["program_id"],
                        state,
                        enrollment_date,
                        uid,
                        uid,
                    ]
                )

            sql = """
                INSERT INTO spp_program_membership
                    (partner_id, program_id, state, enrollment_date,
                     create_uid, write_uid, create_date, write_date)
                VALUES {}
                ON CONFLICT (partner_id, program_id) DO NOTHING
            """.format(  # noqa: S608  # nosec B608
                ", ".join(values)
            )
            cr.execute(sql, params)
            total_inserted += cr.rowcount

        _logger.info(
            "Bulk inserted %d program memberships (%d skipped as duplicates)",
            total_inserted,
            len(vals_list) - total_inserted,
        )
        return total_inserted
