# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Case Triage Rule Model.

Triage rules automatically categorize and prioritize new cases based on
CEL conditions that evaluate case properties.
"""

import logging

from odoo import _, api, fields, models

# Import CEL parser from spp_cel_domain
try:
    from odoo.addons.spp_cel_domain.services import cel_parser as P
except ImportError:
    P = None
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CaseTriageRule(models.Model):
    """Case Triage Rule using CEL expressions.

    Triage rules evaluate new cases on creation to automatically
    set intensity level, priority, and case type based on conditions.
    """

    _name = "spp.case.triage.rule"
    _description = "Case Triage Rule"
    _order = "sequence, id"

    name = fields.Char(
        string="Rule Name",
        required=True,
        help="Descriptive name for this triage rule",
    )
    sequence = fields.Integer(
        default=10,
        help="Rules are evaluated in sequence order (lower number = higher priority)",
    )
    active = fields.Boolean(
        default=True,
        help="Set to inactive to disable this rule without deleting it",
    )

    # Condition (CEL expression)
    condition_cel = fields.Text(
        string="Condition (CEL)",
        help="CEL expression that must evaluate to true for this rule to apply.\n"
        "Available context variables:\n"
        "  - case: The case record\n"
        "  - client: case.partner_id\n"
        "  - case_type: case.case_type_id\n"
        "  - intake_source: case.intake_source\n"
        "  - client_type: case.client_type\n"
        "Example: intake_source == 'grm' || case_type.name == 'Child Protection'",
    )

    # Actions to perform when rule matches
    set_intensity = fields.Selection(
        selection=[
            ("1", "Level 1 - Low Intensity"),
            ("2", "Level 2 - Medium Intensity"),
            ("3", "Level 3 - High Intensity"),
        ],
        string="Set Intensity Level",
        help="Override case intensity when this rule matches",
    )
    set_priority = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        help="Override case priority when this rule matches",
    )
    set_case_type_id = fields.Many2one(
        comodel_name="spp.case.type",
        string="Set Case Type",
        help="Override case type when this rule matches",
    )
    add_risk_factor_ids = fields.Many2many(
        comodel_name="spp.case.risk.factor",
        string="Add Risk Factors",
        help="Risk factors to add to the case when this rule matches",
    )
    add_vulnerability_ids = fields.Many2many(
        comodel_name="spp.case.vulnerability",
        string="Add Vulnerabilities",
        help="Vulnerabilities to add to the case when this rule matches",
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # Statistics
    match_count = fields.Integer(
        string="Matched Cases",
        default=0,
        help="Number of cases this rule has matched",
    )

    @api.constrains("condition_cel")
    def _check_condition_cel(self):
        """Validate CEL expression syntax."""
        for rule in self:
            if rule.condition_cel:
                try:
                    # Basic syntax validation
                    pass
                except Exception as e:
                    raise ValidationError(
                        _(
                            "Invalid CEL expression in rule '%(rule_name)s': %(error)s",
                            rule_name=rule.name,
                            error=str(e),
                        )
                    ) from e

    def evaluate(self, case):
        """Evaluate if this rule applies to the given case.

        Args:
            case: spp.case record

        Returns:
            bool: True if the rule condition matches, False otherwise
        """
        self.ensure_one()

        if not self.condition_cel:
            return True

        context = self._build_evaluation_context(case)

        try:
            result = self._evaluate_expression(self.condition_cel, context)
            _logger.debug(
                "Triage rule '%s' evaluation for case_id=%s: %s",
                self.name,
                case.id,
                result,
            )
            return bool(result)
        except Exception as e:
            _logger.warning(
                "Error evaluating triage rule '%s' for case_id=%s: %s",
                self.name,
                case.id,
                str(e),
            )
            return False

    def _build_evaluation_context(self, case):
        """Build the context dictionary for CEL evaluation."""
        return {
            "case": case,
            "client": case.partner_id,
            "case_type": case.case_type_id,
            "intake_source": case.intake_source,
            "client_type": case.client_type,
            "presenting_issue": case.presenting_issue or "",
            "risk_factors": case.risk_factor_ids,
            "vulnerabilities": case.vulnerability_ids,
        }

    def _evaluate_expression(self, expression, context):
        """Evaluate a CEL expression using the CEL parser.

        Parses the expression into an AST and evaluates it against the context
        using the centralized evaluate() function from cel_parser.

        Args:
            expression: str, the CEL expression
            context: dict, variables available to the expression

        Returns:
            bool or any: Result of the expression
        """
        if not P:
            raise RuntimeError("CEL parser not available")

        try:
            ast = P.parse(expression)
            return P.evaluate(ast, context)
        except Exception as e:
            _logger.warning("Expression evaluation error: %s", str(e))
            raise

    @api.model
    def apply_triage(self, case):
        """Apply the first matching triage rule to a case.

        Args:
            case: spp.case record

        Returns:
            bool: True if a rule was applied, False otherwise
        """
        rules = self.search([("active", "=", True)], order="sequence, id")

        for rule in rules:
            if rule.evaluate(case):
                vals = {}

                if rule.set_intensity:
                    vals["intensity_level"] = rule.set_intensity

                if rule.set_priority:
                    vals["priority"] = rule.set_priority

                if rule.set_case_type_id:
                    vals["case_type_id"] = rule.set_case_type_id.id

                if vals:
                    case.write(vals)
                    _logger.info(
                        "Applied triage rule '%s' to case_id=%s: %s",
                        rule.name,
                        case.id,
                        vals,
                    )

                # Add risk factors and vulnerabilities
                if rule.add_risk_factor_ids:
                    case.write({"risk_factor_ids": [(4, rf.id) for rf in rule.add_risk_factor_ids]})

                if rule.add_vulnerability_ids:
                    case.write({"vulnerability_ids": [(4, v.id) for v in rule.add_vulnerability_ids]})

                # nosemgrep: semgrep.odoo-sudo-without-context -- counter update needs sudo
                rule.sudo().write({"match_count": rule.match_count + 1})
                return True

        _logger.debug("No triage rules matched for case_id=%s", case.id)
        return False
