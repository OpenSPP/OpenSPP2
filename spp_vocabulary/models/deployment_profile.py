import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DeploymentProfile(models.Model):
    """Deployment-specific configuration for vocabulary code subsets.

    A deployment profile defines which codes from various vocabularies are
    active/selectable in a specific country/program deployment. This enables
    the same vocabulary definitions to be reused across deployments while
    allowing each to configure their own subset of applicable codes.

    Example: Philippines 4Ps might only show Male/Female for gender, while
    another deployment might include additional gender identity options.

    See ADR-016 Phase 2 for full context.
    """

    _name = "spp.deployment.profile"
    _description = "Deployment Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Name of this deployment profile (e.g., 'Philippines 4Ps', 'Kenya CT-OVC')",
    )
    description = fields.Text(
        translate=True,
        help="Detailed description of this deployment profile and its purpose",
    )
    is_active = fields.Boolean(
        string="Active",
        default=False,
        help="Set to True to make this the active deployment profile. "
        "Only one profile can be active per company at a time.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        help="Optional: Restrict this profile to a specific company for multi-tenancy",
    )

    # Relations
    vocabulary_selection_ids = fields.One2many(
        comodel_name="spp.vocabulary.selection",
        inverse_name="deployment_profile_id",
        string="Vocabulary Selections",
        help="Code selections for each vocabulary in this deployment profile",
    )
    vocabulary_count = fields.Integer(
        string="Vocabulary Count",
        compute="_compute_vocabulary_count",
        help="Number of vocabularies configured in this profile",
    )
    total_code_count = fields.Integer(
        string="Total Codes",
        compute="_compute_total_code_count",
        help="Total number of active codes across all vocabularies",
    )

    active = fields.Boolean(
        default=True,
        help="Set to inactive to archive this profile without deleting it",
    )

    @api.depends("vocabulary_selection_ids")
    def _compute_vocabulary_count(self):
        """Compute the number of vocabularies configured in this profile."""
        for rec in self:
            rec.vocabulary_count = len(rec.vocabulary_selection_ids)

    @api.depends("vocabulary_selection_ids.effective_code_count")
    def _compute_total_code_count(self):
        """Compute the total number of active codes across all vocabularies."""
        for rec in self:
            rec.total_code_count = sum(rec.vocabulary_selection_ids.mapped("effective_code_count"))

    @api.constrains("is_active", "company_id")
    def _check_single_active_profile(self):
        """Ensure only one profile is active per company at a time."""
        for rec in self:
            if rec.is_active:
                domain = [
                    ("is_active", "=", True),
                    ("id", "!=", rec.id),
                ]
                if rec.company_id:
                    domain.append(("company_id", "=", rec.company_id.id))
                else:
                    domain.append(("company_id", "=", False))

                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(
                        _("Only one deployment profile can be active at a time. Profile '%s' is already active.")
                        % duplicate.name
                    )

    def action_activate(self):
        """Activate this profile (deactivates other profiles for the same company)."""
        self.ensure_one()
        # Deactivate other profiles for the same company
        domain = [
            ("id", "!=", self.id),
        ]
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        else:
            domain.append(("company_id", "=", False))

        other_profiles = self.search(domain)
        other_profiles.write({"is_active": False})

        # Activate this profile
        self.write({"is_active": True})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Profile Activated"),
                "message": _("Deployment profile '%s' is now active.") % self.name,
                "type": "success",
                "sticky": False,
            },
        }

    def action_view_vocabulary_selections(self):
        """Open vocabulary selections for this profile.

        Returns:
            dict: Action definition to display vocabulary selections
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Vocabulary Selections: %s") % self.name,
            "res_model": "spp.vocabulary.selection",
            "view_mode": "list,form",
            "domain": [("deployment_profile_id", "=", self.id)],
            "context": {"default_deployment_profile_id": self.id},
        }

    @api.model
    def get_active_profile(self, company_id=None):
        """Get the active deployment profile.

        Args:
            company_id (int, optional): Company ID to get profile for.
                                       Defaults to current company.

        Returns:
            recordset: Active deployment profile, or empty recordset if none active
        """
        if company_id is None:
            company_id = self.env.company.id

        # Search for company-specific profile first, then system-wide
        profile = self.search(
            [
                ("is_active", "=", True),
                "|",
                ("company_id", "=", company_id),
                ("company_id", "=", False),
            ],
            order="company_id desc",  # Company-specific takes precedence
            limit=1,
        )
        return profile

    @api.model
    def get_active_domain(self, namespace_uri):
        """Return Odoo domain filter for active codes in a vocabulary.

        This is used to dynamically filter vocabulary code fields based on
        the active deployment profile.

        Args:
            namespace_uri (str): Namespace URI of the vocabulary

        Returns:
            list: Odoo domain filter (e.g., [('uri', 'in', [...])])
                 Returns empty list if no profile is active or no selection exists
        """
        profile = self.get_active_profile()
        if not profile:
            # No active profile - show all codes
            return []

        # Find vocabulary selection for this namespace
        vocabulary = self.env["spp.vocabulary"].search([("namespace_uri", "=", namespace_uri)], limit=1)
        if not vocabulary:
            return []

        selection = self.env["spp.vocabulary.selection"].search(
            [
                ("deployment_profile_id", "=", profile.id),
                ("vocabulary_id", "=", vocabulary.id),
            ],
            limit=1,
        )
        if not selection:
            # No selection for this vocabulary - show all codes
            return []

        # Get effective codes (considering inheritance and exclusions)
        effective_codes = selection.get_effective_codes()
        if not effective_codes:
            # No codes selected - return domain that matches nothing
            return [("id", "=", False)]

        # Get URIs, filtering out any empty/None values
        uri_list = [uri for uri in effective_codes.mapped("uri") if uri]
        if not uri_list:
            # All codes lack URIs - return domain that matches nothing
            _logger.warning(f"[Deployment Profile] Effective codes for '{namespace_uri}' have no URIs")
            return [("id", "=", False)]

        # Return domain filtering by URI
        return [("uri", "in", uri_list)]
