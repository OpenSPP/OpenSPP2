# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Case Assignment Rule Model.

Assignment rules automatically assign cases to workers or teams based on
CEL conditions that evaluate case properties and workload.
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


class CaseAssignmentRule(models.Model):
    """Case Assignment Rule using CEL expressions.

    Assignment rules determine which case worker or team should handle
    a case based on conditions like case type, location, and workload.
    """

    _name = "spp.case.assignment.rule"
    _description = "Case Assignment Rule"
    _order = "sequence, id"

    name = fields.Char(
        string="Rule Name",
        required=True,
        help="Descriptive name for this assignment rule",
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
        "  - case_type: case.case_type_id\n"
        "  - intensity: case.intensity_level\n"
        "  - priority: case.priority\n"
        "  - client: case.partner_id\n"
        "Example: intensity == '3' || case_type.name == 'Emergency'",
    )

    # Assignment actions
    assign_team_id = fields.Many2one(
        comodel_name="spp.case.team",
        string="Assign to Team",
        help="Team to assign the case to when this rule matches",
    )
    assign_worker_id = fields.Many2one(
        comodel_name="res.users",
        string="Assign to Worker",
        help="Case worker to assign when this rule matches",
    )
    assign_supervisor_id = fields.Many2one(
        comodel_name="res.users",
        string="Assign Supervisor",
        help="Supervisor to assign when this rule matches",
    )

    # Workload balancing
    is_consider_workload = fields.Boolean(
        string="Consider Workload",
        default=False,
        help="If checked, assign to worker with lowest caseload in the team",
    )
    max_cases_per_worker = fields.Integer(
        string="Max Cases per Worker",
        default=25,
        help="Skip workers who have this many or more active cases",
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
        """Evaluate if this rule applies to the given case."""
        self.ensure_one()

        if not self.condition_cel:
            return True

        context = self._build_evaluation_context(case)

        try:
            result = self._evaluate_expression(self.condition_cel, context)
            _logger.debug(
                "Assignment rule '%s' evaluation for case_id=%s: %s",
                self.name,
                case.id,
                result,
            )
            return bool(result)
        except Exception as e:
            _logger.warning(
                "Error evaluating assignment rule '%s' for case_id=%s: %s",
                self.name,
                case.id,
                str(e),
            )
            return False

    def _build_evaluation_context(self, case):
        """Build the context dictionary for CEL evaluation."""
        return {
            "case": case,
            "case_type": case.case_type_id,
            "intensity": case.intensity_level,
            "priority": case.priority,
            "client": case.partner_id,
            "client_type": case.client_type,
            "intake_source": case.intake_source,
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

    def _get_worker_with_lowest_caseload(self, team):
        """Find the team member with the lowest active caseload.

        Args:
            team: spp.case.team record

        Returns:
            res.users record or False
        """
        Case = self.env["spp.case"]
        best_worker = False
        lowest_count = float("inf")

        for member in team.member_ids:
            case_count = Case.search_count(
                [
                    ("case_worker_id", "=", member.id),
                    ("is_active", "=", True),
                ]
            )

            if case_count < self.max_cases_per_worker and case_count < lowest_count:
                lowest_count = case_count
                best_worker = member

        return best_worker

    @api.model
    def apply_assignment(self, case):
        """Apply the first matching assignment rule to a case.

        Args:
            case: spp.case record

        Returns:
            bool: True if a rule was applied, False otherwise
        """
        rules = self.search([("active", "=", True)], order="sequence, id")

        for rule in rules:
            if rule.evaluate(case):
                vals = {}

                if rule.assign_team_id:
                    vals["team_id"] = rule.assign_team_id.id

                if rule.assign_supervisor_id:
                    vals["supervisor_id"] = rule.assign_supervisor_id.id

                # Determine case worker
                if rule.is_consider_workload and rule.assign_team_id:
                    worker = rule._get_worker_with_lowest_caseload(rule.assign_team_id)
                    if worker:
                        vals["case_worker_id"] = worker.id
                elif rule.assign_worker_id:
                    vals["case_worker_id"] = rule.assign_worker_id.id

                if vals:
                    case.write(vals)
                    _logger.info(
                        "Applied assignment rule '%s' to case_id=%s: %s",
                        rule.name,
                        case.id,
                        vals,
                    )

                rule.sudo().write({"match_count": rule.match_count + 1})
                return True

        _logger.debug("No assignment rules matched for case_id=%s", case.id)
        return False
