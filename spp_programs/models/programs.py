# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import constants

_logger = logging.getLogger(__name__)


class SPPProgram(models.Model):
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "spp.job.relate.mixin",
        # "disable.edit.mixin",
    ]
    _name = "spp.program"
    _description = "Program"
    _order = "id desc"
    _check_company_auto = True

    MANAGER_ELIGIBILITY = constants.MANAGER_ELIGIBILITY
    MANAGER_CYCLE = constants.MANAGER_CYCLE
    MANAGER_PROGRAM = constants.MANAGER_PROGRAM
    MANAGER_ENTITLEMENT = constants.MANAGER_ENTITLEMENT
    MANAGER_DEDUPLICATION = constants.MANAGER_DEDUPLICATION
    MANAGER_NOTIFICATION = constants.MANAGER_NOTIFICATION
    MANAGER_PAYMENT = constants.MANAGER_PAYMENT
    MANAGER_COMPLIANCE = constants.MANAGER_COMPLIANCE

    MANAGER_MODELS = constants.MANAGER_MODELS
    # DISABLE_EDIT_DOMAIN = [("state", "=", "ended")]

    # TODO: Associate a Wallet to each program using the accounting module
    # TODO: (For later) Associate a Warehouse to each program using the stock module for in-kind programs

    @api.model
    def _default_journal_id(self):
        journals = self.env["account.journal"].search(
            [("is_beneficiary_disb", "=", True), ("type", "in", ("bank", "cash"))]
        )
        if journals:
            return journals[0].id
        else:
            return None

    name = fields.Char(required=True)
    description = fields.Text(string="description")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    target_type = fields.Selection(selection=[("group", "Group"), ("individual", "Individual")], default="group")

    # Access control fields
    can_edit_configuration = fields.Boolean(
        compute="_compute_can_edit_configuration",
        help="Whether the current user can edit program configuration",
    )

    # delivery_mechanism = fields.Selection([("mobile", "Mobile"), ("bank_account", "Bank Account"),
    # ("id", "ID Document"), ("biometric", "Biometrics")], default='id')

    # Pre-cycle steps
    # TODO: for those, we should allow to have multiple managers and
    #  the order of the steps should be defined by the user
    eligibility_manager_ids = fields.Many2many("spp.eligibility.manager")  # All will be run
    deduplication_manager_ids = fields.Many2many("spp.deduplication.manager")  # All will be run
    # for each beneficiary, their preferred will be used or the first one that works.
    notification_manager_ids = fields.Many2many("spp.program.notification.manager")
    program_manager_ids = fields.Many2many("spp.program.manager")
    # Cycle steps
    cycle_manager_ids = fields.Many2many("spp.cycle.manager")
    entitlement_manager_ids = fields.Many2many("spp.program.entitlement.manager")
    # Payment management
    payment_manager_ids = fields.Many2many("spp.program.payment.manager")
    # Compliance management - defines ongoing conditions beneficiaries must meet
    compliance_manager_ids = fields.One2many(
        comodel_name="spp.compliance.manager",
        inverse_name="program_id",
        string="Compliance Managers",
    )
    # Computed field to check if compliance filtering is configured
    has_compliance_criteria = fields.Boolean(
        compute="_compute_has_compliance_criteria",
        string="Has Compliance Criteria",
        help="True if any compliance manager is configured for this program.",
    )

    reconciliation_managers = fields.Selection([])

    program_membership_ids = fields.One2many("spp.program.membership", "program_id", "Program Memberships")
    has_members = fields.Boolean(
        string="Have Beneficiaries",
        compute="_compute_has_members",
        default=False,
        store=True,
    )
    cycle_ids = fields.One2many("spp.cycle", "program_id", "Cycles")

    date_ended = fields.Date()
    state = fields.Selection(
        [("active", "Active"), ("ended", "Ended")],
        "Status",
        default="active",
        readonly=True,
    )

    # Accounting config
    currency_id = fields.Many2one(
        "res.currency",
        "Currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
        help="Currency used for this program's financial transactions",
    )
    journal_id = fields.Many2one(
        "account.journal",
        "Disbursement Journal",
        domain=[("is_beneficiary_disb", "=", True), ("type", "in", ("bank", "cash"))],
        default=_default_journal_id,
    )

    # Statistics
    eligible_beneficiaries_count = fields.Integer(
        string="# Eligible Beneficiaries",
        readonly=True,
        compute="_compute_eligible_beneficiary_count",
    )
    beneficiaries_count = fields.Integer(string="# Beneficiaries", readonly=True, compute="_compute_beneficiary_count")

    cycles_count = fields.Integer(string="# Cycles", compute="_compute_cycle_count", store=True)
    duplicate_membership_count = fields.Integer(
        string="# Membership Duplicates", compute="_compute_duplicate_membership_count"
    )
    active = fields.Boolean(default=True)

    # This is used to prevent any issue while some background tasks are happening
    #  such as importing beneficiaries
    is_locked = fields.Boolean(default=False)
    locked_reason = fields.Char()

    # OpenSPP-specific fields
    is_one_time_distribution = fields.Boolean("One-time Distribution")

    view_id = fields.Many2one(
        "ir.ui.view",
        "Program UI Template",
        domain="[('model', '=', 'spp.program'), ('type', '=', 'form'),('inherit_id', '=', False),]",
        default=lambda self: self._get_default_program_ui(),
    )

    def _get_default_program_ui(self):
        return self.env.ref("spp_programs.view_program_list_form")

    def toggle_active(self):
        """
        Overrides the default :meth:`toggle_active` to cancel
        all `draft`, `to_approve`, and `approved` associated cycles and
        'draft' and 'pending_validation' entitlements.

        :return: toggle_active function of parent class
        """
        for rec in self:
            # Cancel cycles and entitlements only if the program is active (for archiving)
            if rec.active:
                _logger.debug("Archive Program: cancel cycles and entitlements.")
                if rec.cycle_ids:
                    entitlement_manager = rec.get_manager(self.MANAGER_ENTITLEMENT)
                    # Get only `draft`, `to_approve`, and `approved` cycles
                    cycles = rec.cycle_ids.filtered(lambda a: a.state in ("draft", "to_approve", "approved"))
                    if cycles:
                        for cycle in cycles:
                            entitlement_manager.cancel_entitlements(cycle)
                        # Set the cycle_ids state to 'cancelled'
                        cycles.update({"state": "cancelled"})
        return super().toggle_active()

    @api.constrains("name")
    def _check_unique_program_name(self):
        """Validate that program name is unique."""
        for rec in self:
            if rec.name:
                domain = [("name", "=", rec.name), ("id", "!=", rec.id)]
                existing = self.search(domain, limit=1)
                if existing:
                    raise UserError(_("A program with this name already exists. Program names must be unique."))

    @api.depends("program_membership_ids")
    def _compute_has_members(self):
        for rec in self:
            rec.has_members = bool(rec.program_membership_ids)

    @api.depends("compliance_manager_ids", "compliance_manager_ids.manager_ref_id")
    def _compute_has_compliance_criteria(self):
        """Check if any compliance manager is configured."""
        for rec in self:
            rec.has_compliance_criteria = bool(rec.compliance_manager_ids)

    def _get_compliance_managers(self):
        """Get compliance managers with their implementations.

        Returns a list of manager_ref_id records (spp.compliance.manager.default)
        that have compliance criteria configured.
        """
        self.ensure_one()
        managers = []
        for compliance_manager in self.compliance_manager_ids:
            manager_ref = compliance_manager.manager_ref_id
            if manager_ref:
                managers.append(manager_ref)
        return managers

    def _compute_can_edit_configuration(self):
        """Check if current user can edit program configuration.

        Only Admin and Program Managers can edit configuration.
        Validators can view but not edit.
        """
        for rec in self:
            rec.can_edit_configuration = self.env.user.has_group(
                "spp_security.group_spp_admin"
            ) or self.env.user.has_group("spp_programs.group_programs_manager")

    @api.model
    def create(self, vals):
        res = super().create(vals)
        if self.env.context.get("skip_default_managers"):
            return res
        if self.env.context.get("create_default_managers"):
            program_id = res.id
            man_ids = self.create_default_managers(program_id)
            for man in man_ids:
                res.update({man: [(4, man_ids[man])]})
        return res

    @api.model
    def create_default_managers(self, program_id):
        ret_vals = {}
        for mgr_fld in self.MANAGER_MODELS:
            for mgr_obj in self.MANAGER_MODELS[mgr_fld]:
                # Add a new record to default manager models
                def_mgr_obj = self.MANAGER_MODELS[mgr_fld][mgr_obj]
                _logger.debug("DEBUG: %s", def_mgr_obj)
                def_mgr = self.env[def_mgr_obj].create(
                    {
                        "name": "Default",
                        "program_id": program_id,
                    }
                )
                # Add a new record to manager parent models
                man_obj = self.env[mgr_obj]
                mgr = man_obj.create(
                    {
                        "program_id": program_id,
                        "manager_ref_id": f"{def_mgr_obj},{str(def_mgr.id)}",
                    }
                )
                ret_vals.update({mgr_fld: mgr.id})
        return ret_vals

    def _compute_duplicate_membership_count(self):
        for rec in self:
            count = rec.count_beneficiaries(["duplicated"])["value"]
            rec.update({"duplicate_membership_count": count})

    def _compute_eligible_beneficiary_count(self):
        for rec in self:
            count = rec.count_beneficiaries(["enrolled"])["value"]
            rec.update({"eligible_beneficiaries_count": count})

    def _compute_beneficiary_count(self):
        for rec in self:
            count = rec.count_beneficiaries(None)["value"]
            rec.update({"beneficiaries_count": count})

    @api.depends("cycle_ids")
    def _compute_cycle_count(self):
        for rec in self:
            domain = [("program_id", "=", rec.id)]
            count = self.env["spp.cycle"].search_count(domain)
            rec.update({"cycles_count": count})

    @api.model
    def get_manager(self, kind):
        self.ensure_one()
        for rec in self:
            if kind == self.MANAGER_CYCLE:
                managers = rec.cycle_manager_ids
            elif kind == self.MANAGER_PROGRAM:
                managers = rec.program_manager_ids
            elif kind == self.MANAGER_ENTITLEMENT:
                managers = rec.entitlement_manager_ids
            elif kind == self.MANAGER_PAYMENT:
                managers = rec.payment_manager_ids
            else:
                raise NotImplementedError("Manager not supported")
            if managers:
                managers.ensure_one()
                for el in managers:
                    return el.manager_ref_id

    @api.model
    def get_managers(self, kind):
        self.ensure_one()
        for rec in self:
            if kind == self.MANAGER_ELIGIBILITY:
                managers = rec.eligibility_manager_ids
            elif kind == self.MANAGER_DEDUPLICATION:
                managers = rec.deduplication_manager_ids
            elif kind == self.MANAGER_NOTIFICATION:
                managers = rec.notification_manager_ids
            else:
                raise NotImplementedError("Manager not supported")
            return [el.manager_ref_id for el in managers]

    @api.model
    def get_beneficiaries(self, state=None, offset=0, limit=None, order=None, count=False, last_id=None):
        """
        Get program beneficiaries with pagination support.

        :param state: State(s) to filter by
        :param offset: Row offset for pagination (WARNING: causes O(n) scaling issues with large datasets)
        :param limit: Maximum number of records to return
        :param order: Sort order
        :param count: If True, return count instead of records
        :param last_id: For cursor-based pagination - ID of last record from previous batch (more efficient)
        :return: Recordset or count

        Note: For large datasets, use cursor-based pagination with last_id parameter instead of offset.
        """
        self.ensure_one()
        if isinstance(state, str):
            state = [state]
        domain = [("program_id", "=", self.id)]
        if state is not None:
            domain.append(("state", "in", state))
        if count:
            return self.env["spp.program.membership"].search_count(domain, limit=limit)

        # Use cursor-based pagination if last_id is provided (more efficient)
        if last_id is not None:
            domain = domain + [("id", ">", last_id)]
            return self.env["spp.program.membership"].search(domain, limit=limit, order=order or "id")

        # Fall back to offset-based pagination (less efficient for large datasets)
        return self.env["spp.program.membership"].search(domain, offset=offset, limit=limit, order=order)

    # TODO: JJ - Review
    def count_beneficiaries(self, state=None):
        domain = [("program_id", "=", self.id)]
        if state is not None:
            domain += [("state", "in", state)]

        return {"value": self.env["spp.program.membership"].search_count(domain)}

    # TODO: JJ - Add a way to link reports/Dashboard about this program.

    def enroll_eligible_registrants(self):
        if self.beneficiaries_count <= 0:
            raise UserError(_("No Registrants Added to Program"))
        for rec in self:
            program_manager = rec.get_manager(self.MANAGER_PROGRAM)
            if program_manager:
                return program_manager.enroll_eligible_registrants()
            else:
                raise UserError(_("No Program Manager defined."))

    def verify_eligibility(self):
        for rec in self:
            program_manager = rec.get_manager(self.MANAGER_PROGRAM)
            if program_manager:
                return program_manager.enroll_eligible_registrants(["enrolled", "not_eligible"])

            else:
                raise UserError(_("No Program Manager defined."))

    def deduplicate_beneficiaries(self):
        for rec in self:
            deduplication_managers = rec.get_managers(self.MANAGER_DEDUPLICATION)
            message = None
            kind = "success"
            if len(deduplication_managers):
                # Count already-flagged duplicates before running
                already_duplicated = self.env["spp.program.membership"].search_count(
                    [("program_id", "=", rec.id), ("state", "=", "duplicated")]
                )

                states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
                duplicates = 0
                for el in deduplication_managers:
                    duplicates += el.deduplicate_beneficiaries(states)

                # Count total duplicates after running
                total_duplicated = self.env["spp.program.membership"].search_count(
                    [("program_id", "=", rec.id), ("state", "=", "duplicated")]
                )
                new_duplicates = total_duplicated - already_duplicated

                if total_duplicated > 0:
                    parts = []
                    if new_duplicates > 0:
                        parts.append(_("%(new)s new duplicate(s) found", new=new_duplicates))
                    if already_duplicated > 0:
                        parts.append(_("%(existing)s already flagged", existing=already_duplicated))
                    message = ", ".join(parts) + "."
                    kind = "warning"
                elif duplicates > 0:
                    message = _(
                        "Found %(count)s duplicate beneficiaries.",
                        count=duplicates,
                    )
                    kind = "warning"
                else:
                    message = _("No duplicates found.")
            else:
                raise UserError(_("No Deduplication Manager defined."))

            if message:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "message": message,
                        "sticky": False,
                        "type": kind,
                        "next": {
                            "type": "ir.actions.act_window_close",
                        },
                    },
                }

    def notify_eligible_beneficiaries(self):
        # 1. Notify the beneficiaries using notification_manager.enrolled_in_program()
        pass

    def create_new_cycle(self):
        # 1. Create the next cycle using cycles_manager.new_cycle()
        # 2. Import the beneficiaries from the previous cycle to this one.
        #  If it is the first one, import from the
        # program memberships.
        if self.beneficiaries_count <= 0:
            raise UserError(_("No enrolled registrants. Enroll registrants to program to create new cycle."))
        for rec in self:
            message = None
            kind = "success"
            cycle_manager = rec.get_manager(self.MANAGER_CYCLE)
            program_manager = rec.get_manager(self.MANAGER_PROGRAM)
            if cycle_manager is None:
                raise UserError(_("No Cycle Manager defined."))
            elif program_manager is None:
                raise UserError(_("No Program Manager defined."))
            if message is not None:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Cycle"),
                        "message": message,
                        "sticky": False,
                        "type": kind,
                        "next": {
                            "type": "ir.actions.act_window_close",
                        },
                    },
                }

            _logger.debug("-" * 80)
            _logger.debug("pm: %s", program_manager)
            new_cycle = program_manager.new_cycle()
            message = _("New cycle %s created.", new_cycle.name)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Cycle"),
                    "message": message,
                    "sticky": False,
                    "type": kind,
                    "next": {
                        "type": "ir.actions.act_window_close",
                    },
                },
            }

    def create_journal(self):
        for rec in self:
            program_name = rec.name.split(" ")
            code = ""
            for pn in program_name:
                if pn:
                    code += pn[0].upper()
            if len(code) == 0:
                code = program_name[3].strip().upper()
            account_model = self.env["account.account"]
            company_domain = []
            # account.company_id replaced by company_ids in newer Odoo versions.
            if "company_id" in account_model._fields:
                company_domain = [("company_id", "=", self.env.company.id)]
            elif "company_ids" in account_model._fields:
                company_domain = [("company_ids", "in", self.env.company.id)]

            account_chart = account_model.search(
                company_domain + [("account_type", "=", "asset_cash")],
                limit=1,
            )
            default_account_id = account_chart.id if account_chart else None
            new_journal = self.env["account.journal"].create(
                {
                    "name": rec.name,
                    "is_beneficiary_disb": True,
                    "type": "bank",
                    "default_account_id": default_account_id,
                    "code": code,
                    "currency_id": rec.currency_id.id if rec.currency_id else rec.company_id.currency_id.id,
                }
            )
            rec.update({"journal_id": new_journal.id})

    def end_program(self):
        for rec in self.env.context.get("active_ids"):
            program = self.env["spp.program"].search(
                [
                    ("id", "=", rec),
                ]
            )
            if program.state == "active":
                program.update({"state": "ended", "date_ended": fields.Date.today()})
            else:
                message = _("Ony 'active' programs can be ended.")
                kind = "danger"

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Program"),
                        "message": message,
                        "sticky": False,
                        "type": kind,
                        "next": {
                            "type": "ir.actions.act_window_close",
                        },
                    },
                }

    def reactivate_program(self):
        for rec in self.env.context.get("active_ids"):
            program = self.env["spp.program"].search(
                [
                    ("id", "=", rec),
                ]
            )
            if program.state == "ended":
                program.update({"state": "active", "date_ended": None})
            else:
                message = _("Ony 'ended' programs can be re-activated.")
                kind = "danger"

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Project"),
                        "message": message,
                        "sticky": False,
                        "type": kind,
                        "next": {
                            "type": "ir.actions.act_window_close",
                        },
                    },
                }

    def open_eligible_beneficiaries_form(self):
        self.ensure_one()

        # Use stored action for proper URL/refresh handling
        # nosemgrep: odoo-sudo-without-context
        action = self.env.ref("spp_programs.action_program_membership").sudo().read()[0]
        action.update(
            {
                "name": _("Beneficiaries - %s", self.name),
                "context": {
                    "create": False,
                    "edit": False,
                    "default_program_id": self.id,
                    "active_id": self.id,
                    "active_model": "spp.program",
                    "search_default_program_id": self.id,
                },
                "domain": [("program_id", "=", self.id)],
            }
        )
        return action

    def open_duplicate_membership_form(self):
        self.ensure_one()

        action = {
            "name": _("Beneficiaries Duplicates"),
            "type": "ir.actions.act_window",
            "res_model": "spp.program.membership",
            "context": {
                "create": False,
                "edit": False,
                "default_program_id": self.id,
            },
            "view_mode": "list,form",
            "domain": [("program_id", "=", self.id), ("state", "=", "duplicated")],
            "path": f"programs/{self.id}/duplicates",
        }
        return action

    def open_cycles_form(self):
        self.ensure_one()

        # Use stored action for proper URL/refresh handling
        action = self.env.ref("spp_programs.action_cycle_list").sudo().read()[0]  # nosemgrep: odoo-sudo-without-context
        action.update(
            {
                "name": _("Cycles - %s", self.name),
                "context": {
                    "create": False,
                    "default_program_id": self.id,
                    "active_id": self.id,
                    "active_model": "spp.program",
                    "search_default_program_id": self.id,
                },
                "domain": [("program_id", "=", self.id)],
            }
        )
        return action

    def open_program_form(self):
        for rec in self:
            view_id = self.env.ref("spp_programs.view_program_list_form")
            if rec.view_id:
                view_id = rec.view_id

            # Use stored action for proper URL/refresh handling
            # nosemgrep: odoo-sudo-without-context
            action = self.env.ref("spp_programs.action_program_list").sudo().read()[0]
            action.update(
                {
                    "name": rec.name,
                    "view_mode": "form",
                    "views": [[view_id.id, "form"]],
                    "res_id": rec.id,
                    "target": "current",
                }
            )
            return action

    def import_eligible_registrants(self, state="draft"):
        eligibility_managers = self.get_managers(self.MANAGER_ELIGIBILITY)
        if eligibility_managers:
            manager = eligibility_managers[0]
            _logger.debug(
                "spp_programs: Importing eligible registrants using manager: %s",
                manager,
            )
            new_beneficiaries_count = manager.import_eligible_registrants()

            if new_beneficiaries_count < 1000:
                message = _("%s Imported Beneficiaries") % new_beneficiaries_count
                kind = "success"
            else:
                message = _("Started importing %s beneficiaries") % new_beneficiaries_count
                kind = "warning"
        else:
            message = _("No Eligibility Manager defined.")
            kind = "danger"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import"),
                "message": message,
                "sticky": True,
                "type": kind,
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }

    def refresh_page(self):
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def _get_related_job_domain(self):
        jobs = self.env["queue.job"].search([("model_name", "like", self._name)])
        related_jobs = jobs.filtered(lambda r: self in r.records.program_id)
        return [("id", "in", related_jobs.ids)]

    @api.constrains(
        "entitlement_manager_ids",
        "program_manager_ids",
        "cycle_manager_ids",
        "payment_manager_ids",
    )
    def check_managers_limit(self):
        for record in self:
            error_messages = []

            if len(record.entitlement_manager_ids) > 1:
                error_messages.append("Entitlement Managers")

            if len(record.program_manager_ids) > 1:
                error_messages.append("Program Managers")

            if len(record.cycle_manager_ids) > 1:
                error_messages.append("Cycle Managers")

            if len(record.payment_manager_ids) > 1:
                error_messages.append("Payment Managers")

            if error_messages:
                combined_message = ", ".join(error_messages)
                raise UserError(
                    f"Only one manager can be configured under {combined_message}."
                    f"Please delete any new manager(s) before saving your changes."  # noqa: B950
                )

    def _pre_enrollment_hook(self, partner):
        """
        Hook called before a registrant is enrolled in the program.

        Override this method in extensions to add custom validation
        before enrollment. Raise ValidationError to prevent enrollment.

        :param partner: The partner (registrant) being enrolled
        """
        pass

    def _post_enrollment_hook(self, partner):
        """
        Hook called after a registrant is enrolled in the program.

        Override this method in extensions to perform actions after
        enrollment, such as triggering notifications or calculations.

        :param partner: The partner (registrant) that was enrolled
        """
        pass

    def unlink(self):
        managers_to_delete = [
            self.eligibility_manager_ids,
            self.deduplication_manager_ids,
            self.notification_manager_ids,
            self.program_manager_ids,
            self.cycle_manager_ids,
            self.entitlement_manager_ids,
            self.payment_manager_ids,
            self.reconciliation_managers,
        ]
        for managers in managers_to_delete:
            if managers:
                for manager in managers:
                    # First remove the underlying default manager record to avoid
                    # foreign key issues, then clean up the relation itself.
                    manager.manager_ref_id.unlink()
                managers.unlink()

        return super().unlink()
