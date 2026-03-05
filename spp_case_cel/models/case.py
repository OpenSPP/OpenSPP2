# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Case Extension for CEL Rules.

Extends spp.case to apply triage and assignment rules on case creation.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class Case(models.Model):
    """Extension of spp.case to apply CEL rules."""

    _inherit = "spp.case"

    @api.model_create_multi
    def create(self, vals_list):
        """Apply triage and assignment rules on case creation."""
        cases = super().create(vals_list)

        for case in cases:
            # Apply triage rules to categorize and prioritize
            self.env["spp.case.triage.rule"].apply_triage(case)

            # Apply assignment rules if case worker not already set
            if not case.case_worker_id:
                self.env["spp.case.assignment.rule"].apply_assignment(case)

        return cases
