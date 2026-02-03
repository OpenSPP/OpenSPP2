# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extension of spp.relationship to add vocabulary code mapping.

This module adds vocabulary code integration to the relationship type model,
enabling standardized terminology and interoperability while preserving
the rich features of the existing relationship model (inverse names,
bidirectional flag, type constraints).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Namespace URI for the relationship vocabulary
RELATIONSHIP_VOCAB_URI = "urn:openspp:vocab:relationship"


class SPPRelationshipVocabulary(models.Model):
    """Extend spp.relationship with vocabulary code mapping for standardization.

    This extension adds the ability to link relationship types to standardized
    vocabulary codes from the OpenSPP relationship vocabulary. This enables:

    - Interoperability between different OpenSPP deployments
    - Standardized terminology for external integrations
    - Mapping to international standards where applicable

    The vocabulary link is optional - existing relationships continue to work
    without modification.
    """

    _inherit = "spp.relationship"

    vocabulary_code_id = fields.Many2one(
        comodel_name="spp.vocabulary.code",
        string="Vocabulary Code",
        domain=f"[('namespace_uri', '=', '{RELATIONSHIP_VOCAB_URI}')]",
        index=True,
        ondelete="set null",
        help="Link to standardized vocabulary code for interoperability. "
        "Uses the OpenSPP relationship vocabulary (urn:openspp:vocab:relationship).",
    )
    vocabulary_code = fields.Char(
        string="Vocabulary Code Value",
        related="vocabulary_code_id.code",
        store=True,
        index=True,
        help="The machine-readable code from the linked vocabulary entry.",
    )

    _unique_vocabulary_code = models.Constraint(
        "UNIQUE(vocabulary_code_id)",
        "Each vocabulary code can only be linked to one relationship type.",
    )

    @api.model
    def create(self, vals_list):
        """Pre-validate unique vocabulary_code_id to raise ValidationError before SQL."""
        if isinstance(vals_list, dict):
            vals_iter = [vals_list]
        else:
            vals_iter = vals_list

        for vals in vals_iter:
            vocab_code = vals.get("vocabulary_code_id")
            if vocab_code:
                duplicate = self.search(
                    [
                        ("vocabulary_code_id", "=", vocab_code),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(
                        _(
                            "Each vocabulary code can only be linked to one relationship type. "
                            "Code '%s' is already linked to relationship '%s'."
                        )
                        % (duplicate.vocabulary_code, duplicate.name)
                    )

        return super().create(vals_iter)

    @api.constrains("vocabulary_code_id")
    def _check_unique_vocabulary_code(self):
        """Ensure vocabulary codes are unique across relationships."""
        for record in self:
            if record.vocabulary_code_id:
                # Use env.search to ensure we search all records, not just current recordset
                # This ensures we find records created earlier in the same transaction
                existing = self.env[self._name].search(
                    [
                        ("vocabulary_code_id", "=", record.vocabulary_code_id.id),
                        ("id", "!=", record.id),
                    ],
                    limit=1,
                )
                if existing:
                    raise ValidationError(
                        _(
                            "Each vocabulary code can only be linked to one relationship type. "
                            "Code '%s' is already linked to relationship '%s'."
                        )
                        % (record.vocabulary_code_id.code, existing.name)
                    )

    @api.model
    def get_by_vocabulary_code(self, code):
        """Find relationship type by vocabulary code.

        Args:
            code (str): The vocabulary code to search for (e.g., 'head', 'spouse')

        Returns:
            recordset: Relationship record if found, empty recordset otherwise
        """
        return self.search([("vocabulary_code", "=", code)], limit=1)

    @api.model
    def sync_from_vocabulary(self):
        """Synchronize relationship types from vocabulary codes.

        Creates any missing relationship types based on vocabulary codes
        that don't have corresponding relationship records. Handles errors
        gracefully and logs progress.

        Returns:
            recordset: Newly created relationship records

        Raises:
            UserError: If the relationship vocabulary doesn't exist
        """
        # Verify vocabulary exists
        vocab = self.env["spp.vocabulary"].search([("namespace_uri", "=", RELATIONSHIP_VOCAB_URI)], limit=1)
        if not vocab:
            raise UserError(_("Relationship vocabulary not found: %s") % RELATIONSHIP_VOCAB_URI)

        # Get all active vocabulary codes
        VocabCode = self.env["spp.vocabulary.code"]
        vocab_codes = VocabCode.search(
            [
                ("namespace_uri", "=", RELATIONSHIP_VOCAB_URI),
                ("active", "=", True),
            ]
        )

        # Get existing linked vocabulary codes efficiently
        existing_rels = self.search([("vocabulary_code_id", "!=", False)])
        existing_codes = set(existing_rels.mapped("vocabulary_code"))

        created = self.browse()
        failed = []

        for vc in vocab_codes:
            if vc.code in existing_codes:
                continue

            try:
                rel = self.create(
                    {
                        "name": vc.display,
                        "name_inverse": _("Inverse of %s") % vc.display,
                        "vocabulary_code_id": vc.id,
                        "bidirectional": False,
                    }
                )
                created |= rel
                _logger.info(
                    "Created relationship type '%s' (code: %s) from vocabulary",
                    vc.display,
                    vc.code,
                )
            except Exception as e:
                failed.append((vc.code, str(e)))
                _logger.warning(
                    "Failed to create relationship for vocabulary code '%s': %s",
                    vc.code,
                    str(e),
                )

        if failed:
            _logger.error(
                "Vocabulary sync completed with %d failures: %s",
                len(failed),
                failed,
            )

        if created:
            _logger.info(
                "Vocabulary sync completed: %d relationships created",
                len(created),
            )

        return created
