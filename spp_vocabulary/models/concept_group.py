import json
import logging

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class VocabularyConceptGroup(models.Model):
    """Semantic groupings of vocabulary codes for business logic abstraction.

    ADR-016 Phase 4: Concept groups allow business logic to check semantic concepts
    rather than specific code values, making the logic robust across deployments
    with different vocabularies.

    Example: Instead of checking if gender_id.code == "female", check if
    gender_id is in the "feminine_gender" concept group. This works across
    deployments whether they use "female", "F", "2", or local codes like "babae".
    """

    _name = "spp.vocabulary.concept.group"
    _description = "Vocabulary Concept Group"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        string="Name",
        required=True,
        index=True,
        help="Machine-readable identifier (e.g., 'feminine_gender', 'pregnant_eligible')",
    )
    label = fields.Char(
        string="Label",
        translate=True,
        help="Human-readable label for this concept group",
    )
    cel_function = fields.Char(
        string="CEL Function Name",
        help="User-friendly CEL function name (e.g., 'is_female', 'is_pregnant')",
    )
    target_field = fields.Char(
        string="Target Field",
        help="The field this concept checks (e.g., 'gender_id' for is_female). "
        "Used to auto-generate CEL expressions like 'is_female(r.gender_id)'.",
    )
    description = fields.Text(
        string="Description",
        translate=True,
        help="Description of what this concept group represents",
    )
    code_ids = fields.Many2many(
        comodel_name="spp.vocabulary.code",
        relation="spp_vocab_concept_group_code_rel",
        column1="group_id",
        column2="code_id",
        string="Codes",
        help="Vocabulary codes that belong to this concept group",
    )
    code_uris = fields.Text(
        string="Code URIs",
        compute="_compute_code_uris",
        store=True,
        help="JSON list of URIs for fast lookup (includes reference_uri mappings)",
    )

    @api.constrains("name")
    def _check_name_unique(self):
        """Ensure concept group name is unique."""
        for rec in self:
            duplicate = self.search_count(
                [
                    ("name", "=", rec.name),
                    ("id", "!=", rec.id),
                ]
            )
            if duplicate:
                raise ValidationError(_("Concept group name '%s' already exists.") % rec.name)

    @api.depends("code_ids", "code_ids.uri", "code_ids.reference_uri")
    def _compute_code_uris(self):
        """Compute JSON list of all URIs in this group.

        Includes both direct code URIs and reference URIs (for local code mappings).
        This enables fast membership checking without joining tables.
        """
        for rec in self:
            uri_set = set()

            # Add direct URIs
            for code in rec.code_ids:
                if code.uri:
                    uri_set.add(code.uri)
                # Also add reference URI if present (for local codes)
                if code.reference_uri:
                    uri_set.add(code.reference_uri)

            # Store as JSON for fast lookup
            rec.code_uris = json.dumps(sorted(uri_set))

    # ═══════════════════════════════════════════════════════════════════════════
    # CACHED LOOKUPS
    # ═══════════════════════════════════════════════════════════════════════════

    @api.model
    @tools.ormcache("group_name")
    def _get_group_uris_cached(self, group_name):
        """Cached lookup of group URIs by name.

        This method provides O(1) access to concept group membership data,
        eliminating N+1 queries in CEL vocabulary function evaluation.

        Args:
            group_name: The name of the concept group

        Returns:
            frozenset or None: Set of URIs in the group, None if not found
        """
        group = self.search([("name", "=", group_name)], limit=1)
        if not group:
            return None

        try:
            uri_list = json.loads(group.code_uris) if group.code_uris else []
            return frozenset(uri_list)
        except (json.JSONDecodeError, TypeError):
            _logger.warning("Invalid JSON in code_uris for group %s", group_name)
            return frozenset()

    @api.model
    def _invalidate_concept_group_cache(self):
        """Clear the ormcache for concept group lookups.

        Note: clear_cache() without args only clears the 'default' cache group,
        not all caches. This is the standard approach in Odoo for ormcache invalidation.
        """
        self.env.registry.clear_cache()
        _logger.debug("[Vocabulary Cache] Cleared concept group cache")

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to invalidate cache."""
        result = super().create(vals_list)
        self._invalidate_concept_group_cache()
        return result

    def write(self, vals):
        """Override write to invalidate cache on relevant changes."""
        result = super().write(vals)
        # Invalidate if any cache-relevant fields changed
        cache_fields = {"code_ids", "name", "code_uris"}
        if cache_fields & set(vals.keys()):
            self._invalidate_concept_group_cache()
        return result

    def unlink(self):
        """Override unlink to invalidate cache."""
        self._invalidate_concept_group_cache()
        return super().unlink()

    def contains(self, code):
        """Check if a vocabulary code is in this concept group.

        Uses cached URI lookup for O(1) membership checking.

        Args:
            code: spp.vocabulary.code recordset (single record or empty)

        Returns:
            bool: True if code is in this group, False otherwise

        Note:
            Checks both direct URI match and reference_uri match.
            This allows local codes to match their standard equivalents.
        """
        self.ensure_one()

        if not code:
            return False

        # Use cached lookup for O(1) access
        uri_set = self._get_group_uris_cached(self.name)
        if not uri_set:
            return False

        # Check if code's URI or reference_uri is in the group
        if code.uri and code.uri in uri_set:
            return True

        if code.reference_uri and code.reference_uri in uri_set:
            return True

        return False

    def get_code_uris(self):
        """Return list of all URIs in this group.

        Returns:
            list: List of URI strings (including reference URIs)
        """
        self.ensure_one()

        try:
            return json.loads(self.code_uris) if self.code_uris else []
        except (json.JSONDecodeError, TypeError):
            _logger.warning("Invalid JSON in code_uris for group %s", self.name)
            return []

    def name_get(self):
        """Return label if available, otherwise fall back to name.

        Returns:
            list: List of (id, name) tuples
        """
        result = []
        for rec in self:
            display = rec.label or rec.name
            if rec.cel_function:
                display = f"{display} ({rec.cel_function})"
            result.append((rec.id, display))
        return result
