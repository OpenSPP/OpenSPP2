"""Pack vocabulary provisioning models for Studio packs."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

VOCABULARY_DOMAIN_SELECTION = [
    ("core", "Core"),
    ("social_assistance", "Social Assistance"),
    ("social_insurance", "Social Insurance"),
    ("labor", "Labor"),
    ("disability", "Disability"),
    ("agriculture", "Agriculture"),
    ("health", "Health"),
    ("education", "Education"),
]


class PackVocabulary(models.Model):
    """Vocabulary provisioning entry within a pack.

    Handles two modes:
    - Add codes to an existing vocabulary (set vocabulary_id)
    - Create a new vocabulary with codes (set new_vocabulary_* fields)
    """

    _name = "spp.studio.pack.vocabulary"
    _description = "Pack Vocabulary"
    _order = "sequence, id"

    pack_id = fields.Many2one(
        "spp.studio.pack",
        string="Pack",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(
        string="Name",
        required=True,
        help="Descriptive name for this vocabulary provisioning entry",
    )
    sequence = fields.Integer(string="Sequence", default=10)

    # Add-codes mode: target an existing vocabulary
    vocabulary_id = fields.Many2one(
        "spp.vocabulary",
        string="Existing Vocabulary",
        help="Target vocabulary to add codes to. Leave empty to create a new vocabulary.",
    )

    # Create-new mode: define a new vocabulary
    new_vocabulary_name = fields.Char(
        string="New Vocabulary Name",
        help="Name for the new vocabulary (required when not targeting an existing one)",
    )
    new_vocabulary_namespace = fields.Char(
        string="New Vocabulary Namespace",
        help="Namespace URI for the new vocabulary (required when not targeting an existing one)",
    )
    new_vocabulary_domain = fields.Selection(
        selection=VOCABULARY_DOMAIN_SELECTION,
        string="New Vocabulary Domain",
        default="core",
    )
    new_vocabulary_hierarchical = fields.Boolean(
        string="New Vocabulary Hierarchical",
        default=False,
    )

    # Codes to provision
    code_ids = fields.One2many(
        "spp.studio.pack.vocabulary.code",
        "vocabulary_item_id",
        string="Codes",
    )

    # Tracking (only set for create-new mode)
    installed_vocabulary_id = fields.Many2one(
        "spp.vocabulary",
        string="Installed Vocabulary",
        readonly=True,
        help="The vocabulary that was created during installation (create-new mode only)",
    )

    # Computed
    is_installed = fields.Boolean(
        compute="_compute_is_installed",
        store=True,
    )
    code_count = fields.Integer(compute="_compute_code_count")

    @api.depends("code_ids.installed_code_id", "installed_vocabulary_id", "vocabulary_id")
    def _compute_is_installed(self):
        for rec in self:
            if rec.vocabulary_id:
                # Add-codes mode: installed if any code has been installed
                rec.is_installed = any(c.installed_code_id for c in rec.code_ids)
            else:
                # Create-new mode: installed if the vocabulary was created
                rec.is_installed = bool(rec.installed_vocabulary_id)

    @api.depends("code_ids")
    def _compute_code_count(self):
        for rec in self:
            rec.code_count = len(rec.code_ids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_mode_consistency()
        return records

    def write(self, vals):
        result = super().write(vals)
        if any(f in vals for f in ("vocabulary_id", "new_vocabulary_name", "new_vocabulary_namespace")):
            self._check_mode_consistency()
        return result

    def _check_mode_consistency(self):
        """Ensure either vocabulary_id OR new_vocabulary_* fields are set, not both."""
        for rec in self:
            has_existing = bool(rec.vocabulary_id)
            has_new_name = bool(rec.new_vocabulary_name)
            has_new_namespace = bool(rec.new_vocabulary_namespace)

            if has_existing and (has_new_name or has_new_namespace):
                raise ValidationError(
                    _(
                        "Cannot set both an existing vocabulary and new vocabulary fields. "
                        "Choose one mode: add codes to existing, or create a new vocabulary."
                    )
                )

            if not has_existing and not (has_new_name and has_new_namespace):
                raise ValidationError(
                    _(
                        "Either select an existing vocabulary, or provide both a name "
                        "and namespace URI for a new vocabulary."
                    )
                )

    def get_target_vocabulary(self):
        """Return the target vocabulary for this item.

        For add-codes mode, returns vocabulary_id.
        For create-new mode, returns installed_vocabulary_id.
        """
        self.ensure_one()
        if self.vocabulary_id:
            return self.vocabulary_id
        return self.installed_vocabulary_id


class PackVocabularyCode(models.Model):
    """A vocabulary code to provision within a pack."""

    _name = "spp.studio.pack.vocabulary.code"
    _description = "Pack Vocabulary Code"
    _order = "sequence, id"

    vocabulary_item_id = fields.Many2one(
        "spp.studio.pack.vocabulary",
        string="Vocabulary Item",
        required=True,
        ondelete="cascade",
    )
    code = fields.Char(string="Code", required=True)
    display = fields.Char(string="Display Label", required=True)
    definition = fields.Text(string="Definition")
    sequence = fields.Integer(string="Sequence", default=10)
    target_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group"),
            ("both", "Both"),
        ],
        string="Target Type",
    )
    is_local = fields.Boolean(
        string="Local Extension",
        default=False,
        help="Create as local extension for system vocabularies",
    )

    # Tracking
    installed_code_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Installed Code",
        readonly=True,
    )
    is_installed = fields.Boolean(
        compute="_compute_is_installed",
        store=True,
    )

    @api.depends("installed_code_id")
    def _compute_is_installed(self):
        for rec in self:
            rec.is_installed = bool(rec.installed_code_id)

    @api.constrains("is_local", "vocabulary_item_id")
    def _check_system_vocab_local(self):
        """Codes added to system vocabularies must be marked as local extensions."""
        for rec in self:
            vocab = rec.vocabulary_item_id.vocabulary_id
            if vocab and vocab.is_system and not rec.is_local:
                raise ValidationError(
                    _(
                        "Codes added to system vocabularies must be marked as local extensions. "
                        "Set 'Local Extension' to True for code '%s'."
                    )
                    % rec.code
                )


class PackConcept(models.Model):
    """A concept group to provision within a pack."""

    _name = "spp.studio.pack.concept"
    _description = "Pack Concept Group"
    _order = "id"

    pack_id = fields.Many2one(
        "spp.studio.pack",
        string="Pack",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(
        string="Name",
        required=True,
        help="Machine-readable name (e.g., 'farmer_relationship')",
    )
    label = fields.Char(
        string="Label",
        help="Human-readable label",
    )
    cel_function = fields.Char(
        string="CEL Function",
        help="CEL function name (e.g., 'is_farmer')",
    )
    target_field = fields.Char(
        string="Target Field",
        help="Field this concept checks (e.g., 'relationship_id')",
    )
    description = fields.Text(string="Description")
    code_ref_ids = fields.One2many(
        "spp.studio.pack.concept.code",
        "concept_id",
        string="Code References",
    )

    # Tracking
    installed_group_id = fields.Many2one(
        "spp.vocabulary.concept.group",
        string="Installed Concept Group",
        readonly=True,
    )
    is_installed = fields.Boolean(
        compute="_compute_is_installed",
        store=True,
    )

    @api.depends("installed_group_id")
    def _compute_is_installed(self):
        for rec in self:
            rec.is_installed = bool(rec.installed_group_id)


class PackConceptCode(models.Model):
    """A code URI reference within a pack concept group definition."""

    _name = "spp.studio.pack.concept.code"
    _description = "Pack Concept Code Reference"
    _order = "id"

    concept_id = fields.Many2one(
        "spp.studio.pack.concept",
        string="Concept",
        required=True,
        ondelete="cascade",
    )
    uri = fields.Char(
        string="Code URI",
        required=True,
        help="Vocabulary code URI (e.g., 'urn:openspp:vocab:relationship#farmer')",
    )
