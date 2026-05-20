import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Vocabulary(models.Model):
    """A collection of codes with a namespace.

    Vocabularies represent standardized code lists used across OpenSPP modules.
    They can be based on international standards (ISO, WHO, ILO) or
    OpenSPP-specific definitions.
    """

    _name = "spp.vocabulary"
    _description = "Vocabulary"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Human-readable name: 'Gender', 'Relationship Type'",
    )
    namespace_uri = fields.Char(
        string="Namespace URI",
        required=True,
        index=True,
        help="Globally unique URI. Examples:\n"
        "- urn:iso:std:iso:5218 (ISO Gender)\n"
        "- urn:who:icf (WHO ICF Disability)\n"
        "- urn:openspp:vocab:{name} (OpenSPP-defined)",
    )
    version = fields.Char(
        help="Version of the vocabulary (e.g., '2024')",
    )
    description = fields.Text(
        translate=True,
        help="Detailed description of this vocabulary and its purpose",
    )
    reference_url = fields.Char(
        string="Reference URL",
        help="Link to official documentation",
    )

    # Characteristics
    is_system = fields.Boolean(
        string="System Vocabulary",
        default=False,
        help="System vocabularies cannot be edited by users",
    )
    is_hierarchical = fields.Boolean(
        string="Hierarchical",
        default=False,
        help="Codes can have parent/child relationships",
    )
    domain = fields.Selection(
        selection=[
            ("core", "Core"),
            ("social_assistance", "Social Assistance"),
            ("social_insurance", "Social Insurance"),
            ("labor", "Labor"),
            ("disability", "Disability"),
            ("agriculture", "Agriculture"),
            ("health", "Health"),
            ("education", "Education"),
        ],
        default="core",
        required=True,
        index=True,
        help="Domain area this vocabulary belongs to",
    )

    # Relations
    code_ids = fields.One2many(
        comodel_name="spp.vocabulary.code",
        inverse_name="vocabulary_id",
        string="Codes",
        help="All codes within this vocabulary",
    )
    code_count = fields.Integer(
        string="Code Count",
        compute="_compute_code_count",
        help="Total number of codes in this vocabulary",
    )
    active = fields.Boolean(
        default=True,
        help="Set to inactive to disable this vocabulary without deleting it",
    )

    _unique_namespace = models.Constraint("UNIQUE(namespace_uri)", "Namespace URI must be unique")

    @api.model
    def create(self, vals_list):
        """Pre-validate namespace uniqueness to raise ValidationError instead of DB IntegrityError."""
        if isinstance(vals_list, dict):
            vals_iter = [vals_list]
        else:
            vals_iter = vals_list

        for vals in vals_iter:
            namespace = vals.get("namespace_uri")
            if namespace:
                existing = self.search([("namespace_uri", "=", namespace)], limit=1)
                if existing:
                    raise ValidationError(_("Namespace URI '%s' is already used by another vocabulary.") % namespace)

        return super().create(vals_iter)

    def write(self, vals):
        """Ensure namespace uniqueness on updates as well."""
        if "namespace_uri" in vals:
            namespace = vals.get("namespace_uri")
            for rec in self:
                if namespace:
                    existing = self.search(
                        [
                            ("namespace_uri", "=", namespace),
                            ("id", "!=", rec.id),
                        ],
                        limit=1,
                    )
                    if existing:
                        raise ValidationError(
                            _("Namespace URI '%s' is already used by another vocabulary.") % namespace
                        )

        return super().write(vals)

    @api.constrains("namespace_uri")
    def _check_namespace_unique(self):
        """Ensure namespace_uri is unique (Python-level validation)."""
        for rec in self:
            duplicate = self.search_count(
                [
                    ("namespace_uri", "=", rec.namespace_uri),
                    ("id", "!=", rec.id),
                ]
            )
            if duplicate:
                raise ValidationError(
                    _("Namespace URI '%s' is already used by another vocabulary.") % rec.namespace_uri
                )

    @api.depends("code_ids")
    def _compute_code_count(self):
        """Compute the number of codes in this vocabulary using _read_group for efficiency."""
        if not self.ids:
            for rec in self:
                rec.code_count = 0
            return

        code_data = self.env["spp.vocabulary.code"]._read_group(
            domain=[("vocabulary_id", "in", self.ids)],
            groupby=["vocabulary_id"],
            aggregates=["__count"],
        )
        count_map = {vocab.id: count for vocab, count in code_data}
        for rec in self:
            rec.code_count = count_map.get(rec.id, 0)

    def action_view_codes(self):
        """Open codes for this vocabulary.

        Returns:
            dict: Action definition to display codes
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Codes: %s") % self.name,
            "res_model": "spp.vocabulary.code",
            "view_mode": "list,form",
            "domain": [("vocabulary_id", "=", self.id)],
            "context": {"default_vocabulary_id": self.id},
        }

    def action_add_manual_code(self):
        """Open the code form pre-flagged as a Manual (local) code.

        Manual codes (`is_local=True`) are admin-added overlays on top of a
        SYSTEM vocabulary. They are fully editable and deletable, unlike the
        module-shipped system codes which the backend locks. See OP#954.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Add Manual Code: %s") % self.name,
            "res_model": "spp.vocabulary.code",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_vocabulary_id": self.id,
                "default_is_local": True,
            },
        }
