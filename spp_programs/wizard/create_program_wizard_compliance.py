import logging

from odoo import Command, _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SppProgramCreateWizard(models.TransientModel):
    _inherit = "spp.program.create.wizard"

    enable_compliance_verification = fields.Boolean(string="Enable Compliance Verification")
    compliance_type = fields.Selection(
        selection=[
            ("spp.compliance.manager.default", "Default (CEL Expression)"),
        ],
        default="spp.compliance.manager.default",
    )
    compliance_cel_expression = fields.Text(
        string="Compliance CEL Expression",
        help="CEL expression for compliance criteria. " "Leave empty to create manager without initial expression.",
    )

    def _check_required_fields(self):
        """Override to validate compliance settings before program creation."""
        res = super()._check_required_fields()
        self._check_compliance_manager_info()
        return res

    def create_program(self):
        action = super().create_program()
        if self.enable_compliance_verification:
            program = self.env["spp.program"].browse(action["params"]["program_id"])
            self._create_compliance_manager(program)
        return action

    def _check_compliance_manager_info(self):
        self.ensure_one()
        if not self.enable_compliance_verification:
            return
        if not self.compliance_type:
            raise ValidationError(_("Not enough information for creating compliance manager!"))

    def _create_compliance_manager(self, program):
        self.ensure_one()
        program.ensure_one()
        self._check_compliance_manager_info()
        manager = self.env[self.compliance_type].sudo().create(self._prepare_compliance_criteria_create_vals(program))
        program.write(
            {
                "compliance_manager_ids": [
                    Command.create(
                        {
                            "manager_ref_id": "%s,%d" % (self.compliance_type, manager.id),
                        }
                    ),
                ],
            }
        )

    def _prepare_compliance_criteria_create_vals(self, program):
        """
        Preparing vals for creating compliance criteria manager for new program.

        :param program: instance of spp.program()
        :return (dictionary): create vals for compliance criteria manager
        :raise: NotImplementedError for compliance_type not yet existed

        How to inherit this function:
        ```python
            def _prepare_compliance_criteria_create_vals(self, program):
                if self.compliance_type = "new.manager.type":
                    return {
                        "key": "value",
                        ...
                    }
                return super()._prepare_compliance_criteria_create_vals(program)
        ```
        """
        if self.compliance_type == "spp.compliance.manager.default":
            vals = {
                "name": f"{program.name} Compliance",
                "program_id": program.id,
            }
            if self.compliance_cel_expression:
                vals["compliance_cel_expression"] = self.compliance_cel_expression
            return vals
        raise NotImplementedError()
