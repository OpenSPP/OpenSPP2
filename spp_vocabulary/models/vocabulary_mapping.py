import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class VocabularyMapping(models.Model):
    """Maps codes between different vocabularies.

    Enables translation between different vocabulary systems. For example,
    mapping local gender codes to ISO 5218, or mapping deployment-specific
    disability codes to WHO ICF.
    """

    _name = "spp.vocabulary.mapping"
    _description = "Vocabulary Code Mapping"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"

    source_id = fields.Many2one(
        comodel_name="spp.vocabulary.code",
        string="Source Code",
        required=True,
        ondelete="cascade",
        index=True,
        help="The code being mapped from",
    )
    target_id = fields.Many2one(
        comodel_name="spp.vocabulary.code",
        string="Target Code",
        required=True,
        ondelete="cascade",
        index=True,
        help="The code being mapped to",
    )

    # Related fields for vocabulary context in views
    source_vocabulary_id = fields.Many2one(
        comodel_name="spp.vocabulary",
        string="Source Vocabulary",
        related="source_id.vocabulary_id",
        store=True,
        readonly=True,
    )
    target_vocabulary_id = fields.Many2one(
        comodel_name="spp.vocabulary",
        string="Target Vocabulary",
        related="target_id.vocabulary_id",
        store=True,
        readonly=True,
    )

    equivalence = fields.Selection(
        selection=[
            ("equivalent", "Equivalent"),
            ("wider", "Wider (target more general)"),
            ("narrower", "Narrower (target more specific)"),
            ("inexact", "Inexact"),
        ],
        required=True,
        default="equivalent",
        help="Type of equivalence between source and target codes",
    )
    comment = fields.Text(
        help="Additional notes about this mapping",
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Human-readable representation of this mapping",
    )

    _unique_mapping = models.Constraint("UNIQUE(source_id, target_id)", "Mapping already exists")

    @api.model
    def create(self, vals_list):
        """Pre-validate mapping uniqueness to avoid DB IntegrityError."""
        if isinstance(vals_list, dict):
            vals_iter = [vals_list]
        else:
            vals_iter = vals_list

        for vals in vals_iter:
            src = vals.get("source_id")
            tgt = vals.get("target_id")
            if src and tgt:
                duplicate = self.search(
                    [
                        ("source_id", "=", src),
                        ("target_id", "=", tgt),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(
                        _("Mapping already exists between '%s' and '%s'.")
                        % (duplicate.source_id.code, duplicate.target_id.code)
                    )

        return super().create(vals_iter)

    def write(self, vals):
        if "source_id" in vals or "target_id" in vals:
            for rec in self:
                src = vals.get("source_id", rec.source_id.id)
                tgt = vals.get("target_id", rec.target_id.id)
                duplicate = self.search(
                    [
                        ("source_id", "=", src),
                        ("target_id", "=", tgt),
                        ("id", "!=", rec.id),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(
                        _("Mapping already exists between '%s' and '%s'.")
                        % (duplicate.source_id.code, duplicate.target_id.code)
                    )

        return super().write(vals)

    @api.constrains("source_id", "target_id")
    def _check_unique_mapping(self):
        """Ensure mapping between source and target is unique (Python-level validation)."""
        for rec in self:
            if not rec.source_id or not rec.target_id:
                continue
            duplicate = self.search_count(
                [
                    ("source_id", "=", rec.source_id.id),
                    ("target_id", "=", rec.target_id.id),
                    ("id", "!=", rec.id),
                ]
            )
            if duplicate:
                raise ValidationError(
                    _("Mapping already exists between '%s' and '%s'.") % (rec.source_id.code, rec.target_id.code)
                )

    @api.depends("source_id", "target_id", "equivalence")
    def _compute_display_name(self):
        """Compute display name from source and target codes.

        Format: "source_code → target_code (equivalence)"
        """
        for rec in self:
            if rec.source_id and rec.target_id:
                src = rec.source_id
                tgt = rec.target_id
                rec.display_name = f"{src.code} → {tgt.code} ({rec.equivalence})"
            else:
                rec.display_name = "Incomplete Mapping"

    @api.model
    def map_code(self, source_namespace, source_code, target_namespace):
        """Find equivalent code in target vocabulary.

        Args:
            source_namespace (str): Namespace URI of source vocabulary
            source_code (str): Code value in source vocabulary
            target_namespace (str): Namespace URI of target vocabulary

        Returns:
            recordset: Target code if mapping exists, empty recordset otherwise
        """
        mapping = self.search(
            [
                ("source_id.namespace_uri", "=", source_namespace),
                ("source_id.code", "=", source_code),
                ("target_id.namespace_uri", "=", target_namespace),
            ],
            limit=1,
        )
        return mapping.target_id if mapping else self.env["spp.vocabulary.code"].browse()
