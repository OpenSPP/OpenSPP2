import logging

from psycopg2 import IntegrityError

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class VocabularyCode(models.Model):
    """A single code within a vocabulary.

    Represents individual values within a vocabulary (e.g., 'Male' in Gender,
    'Head of Household' in Relationship Type). Supports hierarchy for complex
    classifications and deprecation for lifecycle management.

    Phase 1 of ADR-016: Each code has a globally unique URI for interoperability
    and supports local extensions with reference mappings.
    """

    _name = "spp.vocabulary.code"
    _description = "Vocabulary Code"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, code"
    _rec_name = "display"

    def _is_protection_bypassed(self):
        """Check if system vocabulary protection should be bypassed.

        Protection is bypassed during:
        - XML data loading (install_xmlid context)
        - Test fixtures with explicit bypass flag
        """
        return "install_xmlid" in self.env.context or self.env.context.get("_test_bypass_system_protection")

    vocabulary_id = fields.Many2one(
        comodel_name="spp.vocabulary",
        string="Vocabulary",
        required=True,
        ondelete="restrict",
        index=True,
        help="The vocabulary this code belongs to",
    )
    namespace_uri = fields.Char(
        string="Namespace URI",
        related="vocabulary_id.namespace_uri",
        store=True,
        index=True,
        help="Globally unique namespace URI from vocabulary",
    )

    code = fields.Char(
        required=True,
        index=True,
        help="Machine-readable code (e.g., 'M', 'head', 'crop')",
    )
    display = fields.Char(
        string="Display Name",
        required=True,
        translate=True,
        help="Human-readable label",
    )
    definition = fields.Text(
        translate=True,
        help="Formal definition of what this code means",
    )
    sequence = fields.Integer(
        default=10,
        help="Order of display - lower values appear first",
    )
    color = fields.Integer(
        string="Color Index",
        help="Color for visual identification in UI (used by many2many_tags widget)",
    )

    # ADR-016: Code URIs for global identification
    uri = fields.Char(
        string="Code URI",
        compute="_compute_uri",
        store=True,
        readonly=False,
        index=True,
        help="Globally unique URI for this code (computed by default, can be overridden)",
    )

    # ADR-016: Local code extensions
    is_local = fields.Boolean(
        string="Local Code",
        default=False,
        help="Indicates if this is a local/country-specific code",
    )
    reference_uri = fields.Char(
        string="Reference URI",
        help="For local codes: URI of the standard code this maps to",
    )
    equivalence = fields.Selection(
        selection=[
            ("equivalent", "Equivalent"),
            ("wider", "Wider"),
            ("narrower", "Narrower"),
            ("inexact", "Inexact"),
        ],
        string="Equivalence",
        help="How closely this local code maps to the reference code",
    )

    # Hierarchy (optional)
    parent_id = fields.Many2one(
        comodel_name="spp.vocabulary.code",
        string="Parent",
        ondelete="cascade",
        domain="[('vocabulary_id', '=', vocabulary_id)]",
        help="Parent code for hierarchical vocabularies",
    )
    child_ids = fields.One2many(
        comodel_name="spp.vocabulary.code",
        inverse_name="parent_id",
        string="Children",
        help="Child codes in the hierarchy",
    )
    level = fields.Integer(
        string="Hierarchy Level",
        compute="_compute_level",
        store=True,
        recursive=True,
        help="Level in the hierarchy (0 for root codes)",
    )

    # Lifecycle
    active = fields.Boolean(
        default=True,
        help="Set to inactive to disable this code without deleting it",
    )
    deprecated = fields.Boolean(
        default=False,
        help="Mark as deprecated when this code should no longer be used",
    )
    deprecated_date = fields.Date(
        string="Deprecation Date",
        help="Date when this code was deprecated",
    )
    replaced_by_id = fields.Many2one(
        comodel_name="spp.vocabulary.code",
        string="Replaced By",
        domain="[('vocabulary_id', '=', vocabulary_id)]",
        help="If deprecated, the code that supersedes this one",
    )

    # Mapping to other vocabularies
    mapping_ids = fields.One2many(
        comodel_name="spp.vocabulary.mapping",
        inverse_name="source_id",
        string="Mappings",
        help="Mappings from this code to codes in other vocabularies",
    )

    target_type = fields.Selection(
        selection=[
            ("individual", "Individual"),
            ("group", "Group/Household"),
            ("both", "Both"),
        ],
        string="Target Type",
        help="Type of the target of the code",
        default="both",
    )

    # ID Type specific fields (for codes in ID type vocabularies)
    id_validation = fields.Char(
        string="ID Validation Regex",
        help="Regular expression pattern to validate ID values for this ID type",
    )

    _unique_code = models.Constraint("UNIQUE(vocabulary_id, code)", "Code must be unique within vocabulary")
    _unique_uri = models.Constraint("UNIQUE(uri)", "URI must be globally unique")

    @api.model_create_multi
    def create(self, vals_list):
        """Pre-validate code uniqueness to surface ValidationError instead of IntegrityError.

        Also protects system vocabularies from having codes added during normal operation.
        """
        # Protect system vocabularies (unless loading from module data or in test mode)
        # ADR-016: Local codes (is_local=True) can be added to system vocabularies
        if not self._is_protection_bypassed():
            for vals in vals_list:
                vocab_id = vals.get("vocabulary_id")
                if vocab_id:
                    vocab = self.env["spp.vocabulary"].browse(vocab_id)
                    if vocab.is_system and not vals.get("is_local"):
                        raise UserError(
                            _(
                                "Cannot add codes to system vocabulary '%(vocab)s'. "
                                "Use is_local=True for country-specific extensions, "
                                "or modify through module data."
                            )
                            % {"vocab": vocab.name}
                        )

        for vals in vals_list:
            vocab_id = vals.get("vocabulary_id")
            code = vals.get("code")
            if vocab_id and code:
                duplicate = (
                    self.sudo()  # nosemgrep: odoo-sudo-without-context - Uniqueness checks need a global view across active/archive; result is only used to raise validation errors, not exposed to callers.
                    .with_context(active_test=False)
                    .search(
                        [
                            ("vocabulary_id", "=", vocab_id),
                            ("code", "=", code),
                        ],
                        limit=1,
                    )
                )
                if duplicate:
                    raise ValidationError(
                        _("Code '%s' already exists in vocabulary '%s'.") % (code, duplicate.vocabulary_id.name)
                    )

        # Clear cached lookups before creation to keep _get_code_id accurate
        self.invalidate_model(["uri", "code", "active"])

        try:
            return super().create(vals_list)
        except IntegrityError as e:
            # Re-raise as ValidationError for cleaner user-facing message
            raise ValidationError(_("Code must be unique within the vocabulary.")) from e

    def write(self, vals):
        """Override write to validate uniqueness, protect system vocab, and clear cache.

        Args:
            vals (dict): Dictionary of field values to update

        Returns:
            bool: True if successful

        Raises:
            ValidationError: If code would create a duplicate
            UserError: If attempting to modify system vocabulary codes beyond allowed fields
        """
        # 1. Check uniqueness if code or vocabulary is changing
        if "code" in vals or "vocabulary_id" in vals:
            new_code = vals.get("code")
            new_vocab = vals.get("vocabulary_id")
            for rec in self:
                code = new_code or rec.code
                vocab_id = new_vocab or rec.vocabulary_id.id
                duplicate = (
                    self.sudo()  # nosemgrep: odoo-sudo-without-context - Uniqueness checks need a global view across active/archive; result is only used to raise validation errors, not exposed to callers.
                    .with_context(active_test=False)
                    .search(
                        [
                            ("vocabulary_id", "=", vocab_id),
                            ("code", "=", code),
                            ("id", "!=", rec.id),
                        ],
                        limit=1,
                    )
                )
                if duplicate:
                    raise ValidationError(
                        _("Code '%(code)s' already exists in vocabulary '%(vocab)s'.")
                        % {
                            "code": code,
                            "vocab": duplicate.vocabulary_id.name,
                        }
                    )

        # 2. Protect system vocabulary codes (unless loading from module data or in test mode)
        # ADR-016: Local codes (is_local=True) can be fully modified
        if not self._is_protection_bypassed():
            for rec in self:
                if rec.vocabulary_id.is_system and not rec.is_local:
                    # Only allow active/deprecated/sequence changes on system vocab codes
                    allowed_fields = {
                        "active",
                        "deprecated",
                        "deprecated_date",
                        "sequence",
                    }
                    disallowed = set(vals.keys()) - allowed_fields
                    if disallowed:
                        raise UserError(
                            _(
                                "Cannot modify system vocabulary codes. "
                                "Only active, deprecated, and sequence fields can be changed. "
                                "Attempted to change: %(fields)s"
                            )
                            % {"fields": ", ".join(disallowed)}
                        )

        # 3. Clear cache if any lookup-related fields change
        if "code" in vals or "active" in vals or "uri" in vals:
            self.invalidate_model(["uri", "code", "active"])

        return super().write(vals)

    @api.constrains("parent_id")
    def _check_parent_recursion(self):
        """Prevent circular parent hierarchies"""
        if self._has_cycle():
            raise ValidationError(_("You cannot create recursive parent relationships."))

    @api.constrains("vocabulary_id", "code")
    def _check_code_unique(self):
        """Ensure code is unique within vocabulary (Python-level validation)."""
        for rec in self:
            duplicate = self.with_context(active_test=False).search_count(
                [
                    ("vocabulary_id", "=", rec.vocabulary_id.id),
                    ("code", "=", rec.code),
                    ("id", "!=", rec.id),
                ]
            )
            if duplicate:
                raise ValidationError(
                    _("Code '%s' already exists in vocabulary '%s'.") % (rec.code, rec.vocabulary_id.name)
                )

    @api.depends("parent_id", "parent_id.level")
    def _compute_level(self):
        """Compute the hierarchy level based on parent.

        Root codes (no parent) have level 0. Each level down increments by 1.
        """
        for rec in self:
            rec.level = (rec.parent_id.level + 1) if rec.parent_id else 0

    @api.depends("vocabulary_id.namespace_uri", "code")
    def _compute_uri(self):
        """Compute the globally unique URI for this code.

        ADR-016: Format is {vocabulary.namespace_uri}#{code}
        Always computes the default URI. Users can override via readonly=False.
        """
        for rec in self:
            if rec.vocabulary_id and rec.code:
                rec.uri = f"{rec.vocabulary_id.namespace_uri}#{rec.code}"
            elif not rec.uri:
                rec.uri = False

    def name_get(self):
        """Return display name with code in parentheses.

        Returns:
            list: List of (id, name) tuples
        """
        return [(rec.id, f"{rec.display} ({rec.code})") for rec in self]

    @api.model
    @tools.ormcache("namespace_uri", "code")
    def _get_code_id(self, namespace_uri, code):
        """Cached lookup by namespace + code.

        Args:
            namespace_uri (str): Namespace URI of the vocabulary
            code (str): Code value to find

        Returns:
            int or False: Record ID if found, False otherwise
        """
        rec = self.search(
            [
                ("namespace_uri", "=", namespace_uri),
                ("code", "=", code),
                ("active", "=", True),
            ],
            limit=1,
        )
        return rec.id if rec else False

    @api.model
    def get_code(self, namespace_uri, code):
        """Get code record by namespace URI and code value.

        Args:
            namespace_uri (str): Namespace URI of the vocabulary
            code (str): Code value to find

        Returns:
            recordset: Code record if found, empty recordset otherwise
        """
        code_id = self._get_code_id(namespace_uri, code)
        return self.browse(code_id) if code_id else self.browse()

    @api.model
    def get_or_create(self, namespace_uri, code, display=None):
        """Get existing code or create if vocabulary allows.

        Args:
            namespace_uri (str): Namespace URI of the vocabulary
            code (str): Code value
            display (str, optional): Display name for new code

        Returns:
            recordset: Existing or newly created code record

        Raises:
            UserError: If code is inactive, vocabulary not found, or vocabulary is system
        """
        # Search for both active and inactive to avoid unique constraint violation
        existing = self.with_context(active_test=False).search(
            [
                ("namespace_uri", "=", namespace_uri),
                ("code", "=", code),
            ],
            limit=1,
        )

        if existing:
            if not existing.active:
                raise UserError(
                    f"Code '{code}' exists but is inactive in vocabulary "
                    f"'{namespace_uri}'. Reactivate it if needed."
                )
            return existing

        vocab = self.env["spp.vocabulary"].search([("namespace_uri", "=", namespace_uri)], limit=1)
        if not vocab:
            raise UserError(f"Vocabulary not found: {namespace_uri}")
        if vocab.is_system:
            raise UserError(f"Cannot add codes to system vocabulary: {vocab.name}")

        self.env.registry.clear_cache()  # Clear ormcache
        return self.create(
            {
                "vocabulary_id": vocab.id,
                "code": code,
                "display": display or code,
            }
        )

    @api.model
    def get_or_create_local(self, namespace_uri, code, display=None, reference_uri=None, equivalence=None):
        """Get existing code or create a local extension for system vocabularies.

        ADR-016: Allows adding country-specific codes to standard vocabularies
        while maintaining traceability to the original standard.

        Args:
            namespace_uri (str): Namespace URI of the vocabulary
            code (str): Code value
            display (str, optional): Display name for new code
            reference_uri (str, optional): URI of the standard code this maps to
            equivalence (str, optional): How closely this maps ('equivalent', 'wider', 'narrower', 'inexact')

        Returns:
            recordset: Existing or newly created local code record

        Raises:
            UserError: If code is inactive or vocabulary not found
        """
        # Search for both active and inactive to avoid unique constraint violation
        existing = self.with_context(active_test=False).search(
            [
                ("namespace_uri", "=", namespace_uri),
                ("code", "=", code),
            ],
            limit=1,
        )

        if existing:
            if not existing.active:
                raise UserError(
                    f"Code '{code}' exists but is inactive in vocabulary "
                    f"'{namespace_uri}'. Reactivate it if needed."
                )
            return existing

        vocab = self.env["spp.vocabulary"].search([("namespace_uri", "=", namespace_uri)], limit=1)
        if not vocab:
            raise UserError(f"Vocabulary not found: {namespace_uri}")

        self.env.registry.clear_cache()  # Clear ormcache
        vals = {
            "vocabulary_id": vocab.id,
            "code": code,
            "display": display or code,
            "is_local": True,
        }
        if reference_uri:
            vals["reference_uri"] = reference_uri
        if equivalence:
            vals["equivalence"] = equivalence
        return self.create(vals)

    @api.model
    @tools.ormcache("uri")
    def _get_code_id_by_uri(self, uri):
        """Cached lookup by URI.

        Args:
            uri (str): Full URI of the code

        Returns:
            int or False: Record ID if found, False otherwise
        """
        rec = self.search(
            [
                ("uri", "=", uri),
                ("active", "=", True),
            ],
            limit=1,
        )
        return rec.id if rec else False

    @api.model
    def resolve_by_uri(self, uri):
        """Resolve a code by its URI.

        ADR-016: Primary method for code resolution in interoperability scenarios.

        Args:
            uri (str): Full URI of the code (e.g., 'urn:iso:std:iso:5218#1')

        Returns:
            recordset: Code record if found, empty recordset otherwise
        """
        code_id = self._get_code_id_by_uri(uri)
        return self.browse(code_id) if code_id else self.browse()

    @api.model
    def resolve_alias(self, alias, namespace=None):
        """Resolve a code by alias (code, display, or reference mapping).

        ADR-016: Flexible resolution for user-friendly code lookups.
        Searches in order:
        1. By code value
        2. By display name (exact match)
        3. By reference_uri (for local codes mapping to standards)

        Args:
            alias (str): Code value, display name, or reference identifier
            namespace (str, optional): Namespace URI to restrict search

        Returns:
            recordset: First matching code record, empty recordset if not found
        """
        domain = [("active", "=", True)]
        if namespace:
            domain.append(("namespace_uri", "=", namespace))

        # Try by code value first
        code_domain = domain + [("code", "=", alias)]
        result = self.search(code_domain, limit=1)
        if result:
            return result

        # Try by display name
        display_domain = domain + [("display", "=", alias)]
        result = self.search(display_domain, limit=1)
        if result:
            return result

        # Try by reference_uri (for local codes)
        # Build the reference URI if namespace is provided and alias doesn't contain #
        if namespace and "#" not in alias:
            reference = f"{namespace}#{alias}"
        else:
            reference = alias

        reference_domain = domain + [("reference_uri", "=", reference)]
        result = self.search(reference_domain, limit=1)
        return result if result else self.browse()

    def unlink(self):
        """Override unlink to protect system vocabulary codes and clear cache.

        Returns:
            bool: True if successful

        Raises:
            UserError: If attempting to delete system vocabulary codes
        """
        # Protect system vocabularies (unless loading from module data or in test mode)
        # ADR-016: Local codes (is_local=True) can be deleted
        if not self._is_protection_bypassed():
            for rec in self:
                if rec.vocabulary_id.is_system and not rec.is_local:
                    raise UserError(
                        _("Cannot delete codes from system vocabulary '%(vocab)s'.") % {"vocab": rec.vocabulary_id.name}
                    )
        # Clear ormcache lookups before deletion
        self.env.registry.clear_cache()
        self.invalidate_model(["uri", "code", "active"])
        result = super().unlink()
        # Clear again after deletion to ensure get_code returns empty
        self.env.registry.clear_cache()
        return result
