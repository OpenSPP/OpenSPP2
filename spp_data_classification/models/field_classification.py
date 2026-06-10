# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FieldClassification(models.Model):
    """Maps model fields to classification levels.

    This is the central registry of all PII/sensitive fields in the system.
    Each record links a specific field on a specific model to a classification
    level and defines handling policies.

    Usage:
        Classifications can be:
        1. Auto-detected from field name patterns
        2. Declared via XML data files
        3. Set via pii=True field attribute
        4. Manually configured via UI
    """

    _name = "spp.field.classification"
    _description = "Field Classification"
    _rec_name = "display_name"
    _order = "model_id, field_id"

    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True,
        help="The model containing the classified field",
    )
    model_name = fields.Char(
        related="model_id.model",
        store=True,
        index=True,
    )
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Field",
        required=True,
        ondelete="cascade",
        domain="[('model_id', '=', model_id)]",
        index=True,
        help="The field being classified",
    )
    field_name = fields.Char(
        related="field_id.name",
        store=True,
        index=True,
    )
    classification_id = fields.Many2one(
        "spp.data.classification.level",
        string="Classification Level",
        required=True,
        ondelete="restrict",
        index=True,
        help="The sensitivity level of this field",
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    is_pii = fields.Boolean(
        string="Is PII",
        compute="_compute_is_pii",
        store=True,
        help="Set automatically when a PII category is assigned.",
    )

    # === PII Categorization ===
    pii_category = fields.Selection(
        [
            ("direct_id", "Direct Identifier"),
            ("quasi_id", "Quasi-Identifier"),
            ("sensitive", "Sensitive Personal Data"),
            ("financial", "Financial Information"),
            ("contact", "Contact Information"),
            ("biometric", "Biometric Data"),
            ("health", "Health Information"),
            ("political", "Political/Religious/Union"),
            ("genetic", "Genetic Data"),
            ("location", "Location Data"),
        ],
        string="PII Category",
        help="Category of personally identifiable information",
    )

    # === Compliance Flags ===
    is_gdpr_special_category = fields.Boolean(
        string="GDPR Special Category",
        default=False,
        help="GDPR Article 9 special category data (race, health, politics, etc.)",
    )
    cross_border_restricted = fields.Boolean(
        string="Cross-Border Restricted",
        default=False,
        help="Cannot be transferred outside jurisdiction without safeguards",
    )
    child_data = fields.Boolean(
        string="May Contain Child Data",
        default=False,
        help="Field may contain data about minors (requires extra protection)",
    )

    # === Handling Configuration ===
    mask_pattern = fields.Char(
        string="Mask Pattern",
        help="Display mask pattern. Use * for hidden, # for visible. E.g., '****-****-####' shows last 4 characters.",
    )
    search_strategy = fields.Selection(
        [
            ("none", "No Search Allowed"),
            ("blind_index", "Blind Index (Exact Match)"),
            ("partial_index", "Partial Index (Last N chars)"),
            ("phonetic", "Phonetic Search (Names)"),
            ("range", "Range Search (Dates)"),
            ("full", "Full Search (Decrypted)"),
        ],
        string="Search Strategy",
        default="blind_index",
        help="How this field can be searched when encrypted",
    )

    # === Legal Basis ===
    legal_basis = fields.Selection(
        [
            ("consent", "Consent"),
            ("contract", "Contractual Necessity"),
            ("legal", "Legal Obligation"),
            ("vital", "Vital Interests"),
            ("public", "Public Interest"),
            ("legitimate", "Legitimate Interest"),
        ],
        string="Legal Basis",
        help="Legal basis for processing this data (GDPR Article 6)",
    )
    data_source = fields.Char(
        string="Data Source",
        help="Where this data originates (e.g., 'Government ID Document')",
    )

    # === Source Tracking ===
    source = fields.Selection(
        [
            ("auto", "Auto-detected"),
            ("attribute", "Field Attribute"),
            ("xml", "XML Data"),
            ("manual", "Manual"),
        ],
        string="Classification Source",
        default="manual",
        readonly=True,
        help="How this classification was created",
    )
    pattern_id = fields.Many2one(
        "spp.classification.pattern",
        string="Matched Pattern",
        readonly=True,
        help="If auto-detected, the pattern that matched",
    )

    notes = fields.Text(
        string="Notes",
        help="Additional notes about this classification",
    )

    _unique_model_field = models.Constraint(
        "UNIQUE(model_id, field_id)",
        "Each field can only have one classification",
    )

    @api.depends("model_id", "field_id", "classification_id")
    def _compute_display_name(self):
        for record in self:
            if record.model_id and record.field_id:
                record.display_name = (
                    f"{record.model_id.model}.{record.field_id.name} [{record.classification_id.code or 'N/A'}]"
                )
            else:
                record.display_name = _("New Classification")

    @api.depends("pii_category")
    def _compute_is_pii(self):
        for record in self:
            record.is_pii = bool(record.pii_category)

    @api.constrains("model_id", "field_id")
    def _check_field_belongs_to_model(self):
        for record in self:
            if record.field_id and record.model_id:
                if record.field_id.model_id != record.model_id:
                    raise ValidationError(
                        _("Field '%(field)s' does not belong to model '%(model)s'")
                        % {
                            "field": record.field_id.name,
                            "model": record.model_id.model,
                        }
                    )

    @api.model
    def get_classification(self, model_name, field_name):
        """Get classification for a specific model field.

        Args:
            model_name: The model name (e.g., 'res.partner')
            field_name: The field name (e.g., 'national_id')

        Returns:
            recordset: The field classification or empty recordset
        """
        return self.search(
            [
                ("model_name", "=", model_name),
                ("field_name", "=", field_name),
            ],
            limit=1,
        )

    @api.model
    def get_model_classifications(self, model_name):
        """Get all classifications for a model.

        Args:
            model_name: The model name (e.g., 'res.partner')

        Returns:
            recordset: All field classifications for the model
        """
        return self.search([("model_name", "=", model_name)])

    @api.model
    def get_fields_requiring_encryption(self, model_name=None):
        """Get all fields that require encryption.

        Args:
            model_name: Optional model name to filter by

        Returns:
            recordset: Field classifications requiring encryption
        """
        domain = [("classification_id.is_requires_encryption", "=", True)]
        if model_name:
            domain.append(("model_name", "=", model_name))
        return self.search(domain)

    @api.model
    def ensure_classification(self, model_name, field_name, level_code, source="manual", **kwargs):
        """Ensure a field classification exists, creating if needed.

        Args:
            model_name: The model name
            field_name: The field name
            level_code: Classification level code (e.g., 'RESTRICTED')
            source: Source of classification
            **kwargs: Additional field values

        Returns:
            recordset: The existing or created classification
        """
        existing = self.get_classification(model_name, field_name)
        if existing:
            return existing

        model = self.env["ir.model"].search([("model", "=", model_name)], limit=1)
        if not model:
            _logger.warning("Model not found for classification: %s", model_name)
            return self.browse()

        field = self.env["ir.model.fields"].search(
            [("model_id", "=", model.id), ("name", "=", field_name)],
            limit=1,
        )
        if not field:
            _logger.warning("Field not found for classification: %s.%s", model_name, field_name)
            return self.browse()

        level = self.env["spp.data.classification.level"].get_level_by_code(level_code)
        if not level:
            _logger.warning("Classification level not found: %s", level_code)
            return self.browse()

        values = {
            "model_id": model.id,
            "field_id": field.id,
            "classification_id": level.id,
            "source": source,
            **kwargs,
        }
        return self.create(values)
