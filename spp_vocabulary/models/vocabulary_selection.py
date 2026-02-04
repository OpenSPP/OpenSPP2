import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class VocabularySelection(models.Model):
    """Vocabulary code selection within a deployment profile.

    Defines which codes from a specific vocabulary are active/selectable in
    a deployment. Supports inheritance from parent selections to reduce
    duplication.

    Example:
        Base selection: [male, female, unknown]
        Inclusive selection (extends base): adds [non-binary, other]
        Conservative selection (restricts base): excludes [unknown]

    See ADR-016 Phase 2 for full context.
    """

    _name = "spp.vocabulary.selection"
    _description = "Vocabulary Selection"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "deployment_profile_id, vocabulary_id"
    _parent_name = "parent_selection_id"

    deployment_profile_id = fields.Many2one(
        comodel_name="spp.deployment.profile",
        string="Deployment Profile",
        required=True,
        ondelete="cascade",
        index=True,
        help="The deployment profile this selection belongs to",
    )
    vocabulary_id = fields.Many2one(
        comodel_name="spp.vocabulary",
        string="Vocabulary",
        required=True,
        ondelete="restrict",
        index=True,
        help="The vocabulary to configure code selection for",
    )
    vocabulary_namespace = fields.Char(
        string="Vocabulary Namespace",
        related="vocabulary_id.namespace_uri",
        store=True,
        help="Namespace URI of the vocabulary",
    )

    # Inheritance
    parent_selection_id = fields.Many2one(
        comodel_name="spp.vocabulary.selection",
        string="Parent Selection",
        ondelete="restrict",
        help="Optional: Inherit codes from another selection",
    )

    # Code configuration
    active_code_ids = fields.Many2many(
        comodel_name="spp.vocabulary.code",
        relation="spp_vocab_selection_code_rel",
        column1="selection_id",
        column2="code_id",
        string="Active Codes",
        domain="[('vocabulary_id', '=', vocabulary_id)]",
        help="Codes explicitly included in this selection",
    )
    excluded_code_ids = fields.Many2many(
        comodel_name="spp.vocabulary.code",
        relation="spp_vocab_selection_excluded_rel",
        column1="selection_id",
        column2="code_id",
        string="Excluded Codes",
        domain="[('vocabulary_id', '=', vocabulary_id)]",
        help="Codes explicitly excluded from parent selection",
    )

    # Computed fields
    effective_code_ids = fields.Many2many(
        comodel_name="spp.vocabulary.code",
        string="Effective Codes",
        compute="_compute_effective_codes",
        recursive=True,
        help="All codes active in this selection (including inherited, excluding excluded)",
    )
    effective_code_count = fields.Integer(
        string="Effective Code Count",
        compute="_compute_effective_codes",
        help="Total number of effective codes",
    )

    active = fields.Boolean(
        default=True,
        help="Set to inactive to archive this selection without deleting it",
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=False,
    )

    _unique_profile_vocabulary = models.Constraint(
        "UNIQUE(deployment_profile_id, vocabulary_id)",
        "Each vocabulary can only have one selection per deployment profile",
    )

    @api.depends("deployment_profile_id", "vocabulary_id")
    def _compute_display_name(self):
        """Compute display name as 'Deployment Profile - Vocabulary'."""
        for rec in self:
            if not rec.id or not isinstance(rec.id, int):
                rec.display_name = _("New Vocabulary Selection")
            else:
                profile_name = rec.deployment_profile_id.name if rec.deployment_profile_id else ""
                vocab_name = rec.vocabulary_id.name if rec.vocabulary_id else ""

                if profile_name and vocab_name:
                    rec.display_name = f"{profile_name} - {vocab_name}"
                elif profile_name:
                    rec.display_name = profile_name
                elif vocab_name:
                    rec.display_name = vocab_name
                else:
                    rec.display_name = _("Vocabulary Selection")

    @api.constrains("deployment_profile_id", "vocabulary_id")
    def _check_unique_profile_vocabulary(self):
        """Ensure each vocabulary has only one selection per deployment profile."""
        for rec in self:
            duplicate = self.search_count(
                [
                    ("deployment_profile_id", "=", rec.deployment_profile_id.id),
                    ("vocabulary_id", "=", rec.vocabulary_id.id),
                    ("id", "!=", rec.id),
                ]
            )
            if duplicate:
                raise ValidationError(
                    _("Vocabulary '%s' already has a selection in profile '%s'.")
                    % (rec.vocabulary_id.name, rec.deployment_profile_id.name)
                )

    @api.constrains("parent_selection_id")
    def _check_parent_recursion(self):
        """Prevent circular parent relationships."""
        if not self._check_recursion():
            raise ValidationError(_("You cannot create recursive parent selection relationships."))

    @api.constrains("parent_selection_id", "vocabulary_id")
    def _check_parent_same_vocabulary(self):
        """Ensure parent selection is for the same vocabulary."""
        for rec in self:
            if rec.parent_selection_id:
                if rec.parent_selection_id.vocabulary_id != rec.vocabulary_id:
                    raise ValidationError(
                        _("Parent selection must be for the same vocabulary (%s).") % rec.vocabulary_id.name
                    )

    @api.depends(
        "active_code_ids",
        "parent_selection_id",
        "excluded_code_ids",
        "parent_selection_id.effective_code_ids",
    )
    def _compute_effective_codes(self):
        """Compute effective codes considering inheritance and exclusions.

        Logic:
        1. Start with explicitly included codes (active_code_ids)
        2. If parent exists, add parent's effective codes
        3. Remove explicitly excluded codes
        """
        for rec in self:
            codes = set(rec.active_code_ids.ids)

            # Add parent codes if parent exists
            if rec.parent_selection_id:
                parent_codes = set(rec.parent_selection_id.get_effective_codes().ids)
                excluded = set(rec.excluded_code_ids.ids)
                codes |= parent_codes - excluded

            rec.effective_code_ids = [Command.set(list(codes))]
            rec.effective_code_count = len(codes)

    def get_effective_codes(self):
        """Return effective codes considering inheritance and exclusions.

        This is a helper method that can be called programmatically. It returns
        the actual recordset of codes, handling the inheritance chain properly.

        Returns:
            recordset: spp.vocabulary.code records that are effective in this selection
        """
        self.ensure_one()

        codes = set(self.active_code_ids.ids)

        # Recursively get parent codes and apply exclusions
        if self.parent_selection_id:
            parent_codes = set(self.parent_selection_id.get_effective_codes().ids)
            excluded = set(self.excluded_code_ids.ids)
            codes |= parent_codes - excluded

        return self.env["spp.vocabulary.code"].browse(codes)

    def action_add_all_codes(self):
        """Add all codes from the vocabulary to this selection."""
        self.ensure_one()
        all_codes = self.env["spp.vocabulary.code"].search([("vocabulary_id", "=", self.vocabulary_id.id)])
        self.write({"active_code_ids": [Command.set(all_codes.ids)]})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("All Codes Added"),
                "message": _("Added all %d codes from vocabulary '%s'.") % (len(all_codes), self.vocabulary_id.name),
                "type": "success",
                "sticky": False,
            },
        }

    def action_clear_codes(self):
        """Remove all explicitly included codes from this selection."""
        self.ensure_one()
        self.write({"active_code_ids": [Command.clear()]})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Codes Cleared"),
                "message": _("Cleared all active codes from this selection."),
                "type": "info",
                "sticky": False,
            },
        }

    def name_get(self):
        """Return display name as 'Deployment Profile - Vocabulary'.

        For new records (no ID yet), returns 'New Vocabulary Selection'.
        For saved records, returns concatenated deployment profile and vocabulary names.

        Returns:
            list: List of (id, name) tuples
        """
        result = []
        for rec in self:
            # Check if record is new/unsaved (id is False, None, or NewId)
            if not rec.id or not isinstance(rec.id, int):
                name = _("New Vocabulary Selection")
            else:
                # Ensure related fields are loaded
                profile_name = rec.deployment_profile_id.name if rec.deployment_profile_id else ""
                vocab_name = rec.vocabulary_id.name if rec.vocabulary_id else ""

                if profile_name and vocab_name:
                    name = f"{profile_name} - {vocab_name}"
                elif profile_name:
                    name = profile_name
                elif vocab_name:
                    name = vocab_name
                else:
                    name = _("Vocabulary Selection")
            result.append((rec.id, name))
        return result
