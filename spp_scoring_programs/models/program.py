import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SppProgram(models.Model):
    """Extends program with scoring-based eligibility."""

    _inherit = "spp.program"

    scoring_model_id = fields.Many2one(
        comodel_name="spp.scoring.model",
        string="Scoring Model",
        domain="[('is_active', '=', True)]",
        help="Scoring model used for eligibility determination",
    )
    is_use_scoring_eligibility = fields.Boolean(
        string="Use Scoring for Eligibility",
        default=False,
        help="If enabled, scoring is used to determine eligibility",
    )
    eligibility_min_score = fields.Float(
        string="Minimum Score",
        help="Minimum score required for eligibility (inclusive)",
    )
    eligibility_max_score = fields.Float(
        string="Maximum Score",
        help="Maximum score allowed for eligibility (inclusive)",
    )
    eligibility_classifications = fields.Char(
        string="Required Classifications",
        help="Comma-separated list of classification codes that qualify (e.g., 'POOR,EXTREME_POOR')",
    )
    is_auto_score_on_enrollment = fields.Boolean(
        string="Auto-Score on Enrollment",
        default=False,
        help="Automatically calculate score when a registrant is enrolled",
    )
    score_max_age_days = fields.Integer(
        string="Maximum Score Age (Days)",
        default=180,
        help="Maximum age of an existing score before recalculation (0 = always recalculate)",
    )

    @api.constrains("eligibility_min_score", "eligibility_max_score")
    def _check_score_range(self):
        for record in self:
            if record.is_use_scoring_eligibility:
                if (
                    record.eligibility_min_score
                    and record.eligibility_max_score
                    and record.eligibility_min_score > record.eligibility_max_score
                ):
                    raise ValidationError(_("Minimum score must be less than or equal to maximum score."))

    def check_scoring_eligibility(self, registrant):
        """
        Check if a registrant meets the scoring eligibility criteria.

        Returns:
            dict with:
                - eligible: bool
                - score: float
                - classification: str
                - reason: str (if not eligible)
        """
        self.ensure_one()

        if not self.is_use_scoring_eligibility or not self.scoring_model_id:
            return {"eligible": True, "score": None, "classification": None}

        # Get or calculate score
        engine = self.env["spp.scoring.engine"]
        max_age = self.score_max_age_days if self.score_max_age_days > 0 else None

        score_result = engine.get_or_calculate_score(
            registrant,
            self.scoring_model_id,
            max_age_days=max_age,
        )

        result = {
            "eligible": False,
            "score": score_result.score,
            "classification": score_result.classification_code,
            "reason": None,
        }

        # Check classification-based eligibility
        if self.eligibility_classifications:
            allowed_classifications = [c.strip() for c in self.eligibility_classifications.split(",")]
            if score_result.classification_code in allowed_classifications:
                result["eligible"] = True
            else:
                result["reason"] = _("Classification '%s' not in allowed list: %s") % (
                    score_result.classification_code,
                    self.eligibility_classifications,
                )

        # Check score range eligibility
        elif self.eligibility_min_score or self.eligibility_max_score:
            min_score = self.eligibility_min_score or 0
            max_score = self.eligibility_max_score or float("inf")

            if min_score <= score_result.score <= max_score:
                result["eligible"] = True
            else:
                result["reason"] = _("Score %.2f not in range [%.2f, %.2f]") % (
                    score_result.score,
                    min_score,
                    max_score,
                )

        else:
            # No specific criteria, just need a score
            result["eligible"] = True

        return result

    def _pre_enrollment_hook(self, partner):
        """Check scoring eligibility before enrollment."""
        super()._pre_enrollment_hook(partner)

        if self.is_use_scoring_eligibility:
            eligibility = self.check_scoring_eligibility(partner)
            if not eligibility["eligible"]:
                raise ValidationError(
                    _("Registrant does not meet scoring eligibility: %s") % eligibility.get("reason", "Unknown reason")
                )

    def _post_enrollment_hook(self, partner):
        """Calculate score after enrollment and record it on membership."""
        super()._post_enrollment_hook(partner)

        if not self.scoring_model_id:
            return

        score_result = None

        if self.is_auto_score_on_enrollment:
            engine = self.env["spp.scoring.engine"]
            try:
                score_result = engine.calculate_score(
                    partner,
                    self.scoring_model_id,
                    mode="automatic",
                )
            except (ValidationError, UserError) as e:
                _logger.warning(
                    "Score calculation failed for registrant_id=%s: %s",
                    partner.id,
                    str(e),
                )
            except Exception:
                _logger.exception(
                    "Unexpected error calculating score for registrant_id=%s",
                    partner.id,
                )

        # If no auto-score, use existing latest score
        if not score_result:
            Result = self.env["spp.scoring.result"]
            score_result = Result.get_latest_score(partner, self.scoring_model_id)

        # Record enrollment score on membership
        if score_result:
            membership = self.env["spp.program.membership"].search(
                [
                    ("partner_id", "=", partner.id),
                    ("program_id", "=", self.id),
                    ("state", "=", "enrolled"),
                ],
                limit=1,
            )
            if membership:
                membership.write(
                    {
                        "enrollment_score": score_result.score,
                        "enrollment_classification": score_result.classification_code,
                    }
                )


class SppProgramMembership(models.Model):
    """Extends membership with scoring information."""

    _inherit = "spp.program.membership"

    enrollment_score = fields.Float(
        string="Enrollment Score",
        help="Score at the time of enrollment",
    )
    enrollment_classification = fields.Char(
        string="Enrollment Classification",
        help="Classification at the time of enrollment",
    )
    latest_score_id = fields.Many2one(
        comodel_name="spp.scoring.result",
        string="Latest Score",
        compute="_compute_latest_score",
    )
    latest_score = fields.Float(
        string="Latest Score Value",
        compute="_compute_latest_score",
    )
    latest_classification = fields.Char(
        string="Latest Classification",
        compute="_compute_latest_score",
    )

    def _compute_latest_score(self):
        Result = self.env["spp.scoring.result"]
        for record in self:
            if record.program_id.scoring_model_id and record.partner_id:
                score_result = Result.get_latest_score(
                    record.partner_id,
                    record.program_id.scoring_model_id,
                )
                record.latest_score_id = score_result
                record.latest_score = score_result.score if score_result else 0.0
                record.latest_classification = score_result.classification_code if score_result else False
            else:
                record.latest_score_id = False
                record.latest_score = 0.0
                record.latest_classification = False
