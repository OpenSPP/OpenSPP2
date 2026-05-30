# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Interactive Registry Notary lab demo runs."""

from odoo import _, api, fields, models

from ..hooks import PERSONAS, PROGRAMS

EXPECTED_OUTCOMES = {
    "Registry Lab Living Person Grant": {
        "NID-1001": True,
        "NID-1002": True,
        "NID-1003": False,
    },
    "Registry Lab Combined Support": {
        "NID-1001": True,
        "NID-1002": False,
        "NID-1003": False,
    },
    "Registry Lab Health Access Support": {
        "NID-1001": True,
        "NID-1002": False,
        "NID-1003": True,
    },
}


class NotaryDemoRun(models.Model):
    """A replayable demo execution over the seeded lab personas and programs."""

    _name = "spp.notary.demo.run"
    _description = "Registry Notary Demo Run"
    _order = "started_at desc, id desc"

    name = fields.Char(default=lambda self: _("Registry Notary Demo"), required=True)
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
    )
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)
    result_ids = fields.One2many(
        comodel_name="spp.notary.demo.result",
        inverse_name="run_id",
        string="Results",
        readonly=True,
    )
    pass_count = fields.Integer(compute="_compute_counts")
    fail_count = fields.Integer(compute="_compute_counts")
    error_count = fields.Integer(compute="_compute_counts")
    skipped_count = fields.Integer(compute="_compute_counts")
    summary = fields.Text(readonly=True)

    @api.depends("result_ids.outcome")
    def _compute_counts(self):
        for run in self:
            outcomes = run.result_ids.mapped("outcome")
            run.pass_count = outcomes.count("pass")
            run.fail_count = outcomes.count("fail")
            run.error_count = outcomes.count("error")
            run.skipped_count = outcomes.count("skipped")

    @api.model
    def action_create_and_run_demo(self):
        run = self.create({"name": _("Registry Notary Demo")})
        run.action_run_demo()
        return run._open_form_action()

    def action_run_demo(self):
        for run in self:
            run._run_demo()
        return self._open_form_action()

    def _run_demo(self):
        self.ensure_one()
        self.result_ids.unlink()
        self.write(
            {
                "state": "running",
                "started_at": fields.Datetime.now(),
                "finished_at": False,
                "summary": False,
            }
        )
        Result = self.env["spp.notary.demo.result"].sudo()
        sequence = 10
        for program_def in PROGRAMS:
            program = self.env["spp.program"].sudo().search([("name", "=", program_def["name"])], limit=1)
            expression = self._program_expression(program)
            for persona in PERSONAS:
                result_values = self._evaluate_persona_program(program, expression, persona)
                result_values.update({"run_id": self.id, "sequence": sequence})
                Result.create(result_values)
                sequence += 10
        self.write(
            {
                "state": "failed"
                if self.result_ids.filtered(lambda result: result.outcome in ("fail", "error"))
                else "done",
                "finished_at": fields.Datetime.now(),
                "summary": self._build_summary(),
            }
        )

    def _evaluate_persona_program(self, program, expression, persona):
        national_id = persona["national_id"]
        expected = EXPECTED_OUTCOMES.get(program.name if program else "", {}).get(national_id, False)
        partner = self._partner_for_national_id(national_id)
        if not program:
            return self._result_values(persona, program, expected, False, "error", "Program is not configured.")
        if not partner:
            return self._result_values(persona, program, expected, False, "error", "Demo persona is not configured.")
        if not expression:
            return self._result_values(persona, program, expected, False, "error", "Program has no CEL expression.")
        missing = self._missing_provider_credentials(expression)
        if missing:
            return self._result_values(
                persona,
                program,
                expected,
                False,
                "skipped",
                _("Missing provider credential: %s") % missing,
                expression=expression,
                partner=partner,
            )
        try:
            result = (
                self.env["spp.cel.service"]
                .sudo()
                .compile_expression(
                    expression,
                    "registry_individuals",
                    base_domain=[("id", "=", partner.id)],
                )
            )
        except Exception as error:  # noqa: BLE001 - demo result should record operational failures.
            return self._result_values(
                persona,
                program,
                expected,
                False,
                "error",
                str(error),
                expression=expression,
                partner=partner,
            )
        if not result.get("valid"):
            return self._result_values(
                persona,
                program,
                expected,
                False,
                "error",
                result.get("error") or _("CEL expression did not validate."),
                expression=expression,
                partner=partner,
            )
        actual = partner.id in result.get("ids", [])
        outcome = "pass" if actual == expected else "fail"
        detail = _("Expected %(expected)s and got %(actual)s.") % {
            "expected": expected,
            "actual": actual,
        }
        return self._result_values(
            persona,
            program,
            expected,
            actual,
            outcome,
            detail,
            expression=expression,
            partner=partner,
        )

    def _result_values(self, persona, program, expected, actual, outcome, detail, expression=None, partner=None):
        return {
            "persona_id": partner.id if partner else False,
            "program_id": program.id if program else False,
            "persona_name": persona["name"],
            "national_id": persona["national_id"],
            "expected_eligible": expected,
            "actual_eligible": actual,
            "outcome": outcome,
            "expression": expression or "",
            "detail": detail,
        }

    def _program_expression(self, program):
        if not program or not program.eligibility_manager_ids:
            return ""
        manager = program.eligibility_manager_ids[0].manager_ref_id
        if manager and "cel_expression" in manager._fields:
            return manager.cel_expression or ""
        return ""

    def _partner_for_national_id(self, national_id):
        providers = self.env["spp.data.provider"].sudo().search([("provider_kind", "=", "notary")])
        id_types = providers.mapped("notary_subject_id_type_id")
        if not id_types:
            return self.env["res.partner"]
        reg_id = (
            self.env["spp.registry.id"]
            .sudo()
            .search(
                [
                    ("id_type_id", "in", id_types.ids),
                    ("value", "=", national_id),
                ],
                limit=1,
            )
        )
        return reg_id.partner_id

    def _missing_provider_credentials(self, expression):
        providers = self.env["spp.data.provider"].sudo()
        if "notary_registry_lab_civil_notary_" in expression:
            providers |= providers.search([("code", "=", "registry_lab_civil_notary")], limit=1)
        if "notary_registry_lab_shared_eligibility_notary_" in expression:
            providers |= providers.search([("code", "=", "registry_lab_shared_eligibility_notary")], limit=1)
        for provider in providers:
            if provider.auth_type == "api_key" and not provider.api_key:
                return _("%s API key") % provider.display_name
            if provider.auth_type == "bearer" and not provider.notary_bearer_token:
                return _("%s bearer token") % provider.display_name
        return None

    def _build_summary(self):
        self.ensure_one()
        return _("%(passed)s passed, %(failed)s failed, %(errors)s errors, %(skipped)s skipped.") % {
            "passed": self.pass_count,
            "failed": self.fail_count,
            "errors": self.error_count,
            "skipped": self.skipped_count,
        }

    def _open_form_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Registry Notary Demo Run"),
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }


class NotaryDemoResult(models.Model):
    """One persona/program decision from a Notary demo run."""

    _name = "spp.notary.demo.result"
    _description = "Registry Notary Demo Result"
    _order = "run_id desc, sequence, id"

    run_id = fields.Many2one(
        comodel_name="spp.notary.demo.run",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    persona_id = fields.Many2one("res.partner", readonly=True)
    persona_name = fields.Char(readonly=True)
    national_id = fields.Char(readonly=True)
    program_id = fields.Many2one("spp.program", readonly=True)
    expected_eligible = fields.Boolean(readonly=True)
    actual_eligible = fields.Boolean(readonly=True)
    outcome = fields.Selection(
        selection=[
            ("pass", "Pass"),
            ("fail", "Fail"),
            ("error", "Error"),
            ("skipped", "Skipped"),
        ],
        required=True,
        readonly=True,
    )
    expression = fields.Text(readonly=True)
    detail = fields.Text(readonly=True)
