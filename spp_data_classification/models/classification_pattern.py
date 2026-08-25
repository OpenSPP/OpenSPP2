# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import functools
import logging
import re
from types import SimpleNamespace

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=256)
def _compile_regex(pattern_str):
    """Compile regex pattern with caching.

    Uses functools.lru_cache for thread-safe caching.
    """
    try:
        return re.compile(pattern_str, re.IGNORECASE)
    except re.error as e:
        _logger.warning("Invalid regex pattern '%s': %s", pattern_str, e)
        return None


class ClassificationPattern(models.Model):
    """Auto-detection patterns for PII fields.

    Supports two matching modes:
    1. Regex (default): Simple pattern matching against field names
    2. CEL: Complex expressions using field metadata (type, name, model, etc.)

    CEL expressions have access to:
    - field.name: Field name (str)
    - field.type: Field type like 'char', 'integer', etc. (str)
    - field.store: Whether field is stored in DB (bool)
    - field.required: Whether field is required (bool)
    - model.model: Model technical name like 'res.partner' (str)
    - model.name: Model display name (str)

    Example CEL expressions:
    - field.type == 'char' && field.name.endsWith('_id')
    - model.model.startsWith('spp.') && field.name matches 'national.*'
    - field.type in ['char', 'text'] && field.store

    Usage:
        Patterns are evaluated in priority order (higher = first).
        When a field matches, it's automatically classified.
    """

    _name = "spp.classification.pattern"
    _description = "Classification Auto-Detection Pattern"
    _order = "priority desc, id"

    name = fields.Char(
        required=True,
        help="Descriptive name for this pattern",
    )

    # === Matching Mode ===
    match_mode = fields.Selection(
        [
            ("regex", "Regex Pattern"),
            ("cel", "CEL Expression"),
        ],
        string="Match Mode",
        default="regex",
        required=True,
        help="How to match fields: Regex for simple name patterns, CEL for complex rules",
    )

    # Regex pattern (legacy/simple mode)
    pattern = fields.Char(
        help="Regex pattern to match field names. Case-insensitive. "
        "E.g., '(national|passport|tax).*id' matches 'national_id', 'passport_id'",
    )

    # CEL expression (advanced mode)
    cel_expression = fields.Text(
        string="CEL Expression",
        help="CEL expression for complex field matching. "
        "Use 'field' for field metadata and 'model' for model metadata.\n"
        "Example: field.type == 'char' && field.name matches 'national.*'",
    )

    classification_id = fields.Many2one(
        "spp.data.classification.level",
        string="Classification Level",
        required=True,
        ondelete="restrict",
        help="Classification level to apply when pattern matches",
    )
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
        help="PII category to assign when pattern matches",
    )
    priority = fields.Integer(
        default=50,
        help="Higher priority patterns are evaluated first (0-100)",
    )
    active = fields.Boolean(default=True)

    # === Default Handling ===
    default_mask_pattern = fields.Char(
        string="Default Mask Pattern",
        help="Mask pattern to apply (e.g., '****-****-####')",
    )
    default_search_strategy = fields.Selection(
        [
            ("none", "No Search Allowed"),
            ("blind_index", "Blind Index (Exact Match)"),
            ("partial_index", "Partial Index (Last N chars)"),
            ("phonetic", "Phonetic Search (Names)"),
            ("range", "Range Search (Dates)"),
            ("full", "Full Search (Decrypted)"),
        ],
        string="Default Search Strategy",
        default="blind_index",
    )

    # === Scope ===
    apply_to_model_pattern = fields.Char(
        string="Model Pattern",
        help="Optional: Only apply to models matching this pattern. "
        "E.g., 'spp\\..*' for all OpenSPP models. Empty = all models.",
    )

    notes = fields.Text(
        string="Notes",
        help="Documentation about what this pattern matches",
    )

    @api.constrains("match_mode", "pattern", "cel_expression")
    def _check_pattern_or_expression(self):
        """Ensure either pattern or CEL expression is provided based on mode."""
        for record in self:
            if record.match_mode == "regex":
                if not record.pattern:
                    raise ValidationError(_("Regex pattern is required when using Regex match mode"))
            elif record.match_mode == "cel":
                if not record.cel_expression:
                    raise ValidationError(_("CEL expression is required when using CEL match mode"))

    @api.constrains("pattern", "apply_to_model_pattern")
    def _check_regex_compiles(self):
        """Reject uncompilable regexes at save time; at scan time they would
        only log a warning and silently never match."""
        for record in self:
            for value in (record.pattern, record.apply_to_model_pattern):
                if not value:
                    continue
                try:
                    re.compile(value, re.IGNORECASE)
                except re.error as e:
                    raise ValidationError(
                        _("Invalid regular expression '%(pattern)s': %(error)s") % {"pattern": value, "error": e}
                    ) from e

    @api.model
    def _get_compiled_pattern(self, pattern_str):
        """Get compiled regex pattern with caching.

        Uses module-level lru_cache for thread-safe caching.
        """
        return _compile_regex(pattern_str)

    def matches_field(self, field_name, model_name=None, field_obj=None, model_obj=None):
        """Check if this pattern matches a field.

        Args:
            field_name: The field name to check
            model_name: Optional model name for scope filtering
            field_obj: Optional ir.model.fields record for CEL evaluation
            model_obj: Optional ir.model record for CEL evaluation

        Returns:
            bool: True if pattern matches
        """
        self.ensure_one()

        # Check model scope if specified (applies to both modes)
        if self.apply_to_model_pattern and model_name:
            model_pattern = self._get_compiled_pattern(self.apply_to_model_pattern)
            if model_pattern and not model_pattern.search(model_name):
                return False

        # Dispatch to appropriate matcher based on mode
        if self.match_mode == "cel":
            return self._matches_field_cel(field_name, model_name, field_obj, model_obj)
        else:
            return self._matches_field_regex(field_name)

    def _matches_field_regex(self, field_name):
        """Check if field name matches regex pattern.

        Args:
            field_name: The field name to check

        Returns:
            bool: True if pattern matches
        """
        if not self.pattern:
            return False

        pattern = self._get_compiled_pattern(self.pattern)
        if pattern:
            return bool(pattern.search(field_name))
        return False

    def _matches_field_cel(self, field_name, model_name=None, field_obj=None, model_obj=None):
        """Check if field matches CEL expression.

        Builds a context with field and model metadata, then evaluates
        the CEL expression.

        Args:
            field_name: The field name
            model_name: The model name
            field_obj: Optional ir.model.fields record
            model_obj: Optional ir.model record

        Returns:
            bool: True if CEL expression evaluates to True
        """
        if not self.cel_expression:
            return False

        # Check if CEL service is available
        cel_service = self.env.get("spp.cel.service")
        if not cel_service:
            _logger.warning(
                "CEL service not available for pattern '%s'. Install spp_cel_domain module to use CEL patterns.",
                self.name,
            )
            return False

        # Build context for CEL evaluation
        context = self._build_cel_context(field_name, model_name, field_obj, model_obj)

        try:
            result = cel_service.evaluate_expression(self.cel_expression, context)
            return bool(result)
        except SyntaxError as e:
            _logger.warning(
                "CEL syntax error in pattern '%s': %s",
                self.name,
                str(e),
            )
            return False
        except Exception as e:
            # Broad on purpose: evaluate_expression re-raises whatever the CEL
            # parser/evaluator throws (incl. RecursionError and service-specific
            # errors); one broken pattern must not crash an entire registry scan.
            _logger.warning(
                "CEL evaluation failed for pattern '%s': %s",
                self.name,
                str(e),
            )
            return False

    def _build_cel_context(self, field_name, model_name=None, field_obj=None, model_obj=None):
        """Build CEL evaluation context with field and model metadata.

        Args:
            field_name: The field name
            model_name: The model name
            field_obj: Optional ir.model.fields record
            model_obj: Optional ir.model record

        Returns:
            dict: Context for CEL evaluation
        """
        # Build field context
        field_ctx = {
            "name": field_name,
            "type": "unknown",
            "store": True,
            "required": False,
            "readonly": False,
            "translate": False,
        }

        if field_obj:
            field_ctx.update(
                {
                    "type": field_obj.ttype,
                    "store": field_obj.store,
                    "required": field_obj.required,
                    "readonly": field_obj.readonly,
                    "translate": field_obj.translate,
                    "help": field_obj.help or "",
                    "relation": field_obj.relation or "",
                }
            )

        # Build model context
        model_ctx = {
            "model": model_name or "",
            "name": "",
            "transient": False,
        }

        if model_obj:
            model_ctx.update(
                {
                    "model": model_obj.model,
                    "name": model_obj.name,
                    "transient": model_obj.transient,
                }
            )

        # Use SimpleNamespace for dot access in CEL expressions
        return {
            "field": SimpleNamespace(**field_ctx),
            "model": SimpleNamespace(**model_ctx),
        }

    @api.model
    def find_matching_pattern(self, field_name, model_name=None, field_obj=None, model_obj=None):
        """Find the first (highest priority) matching pattern.

        Args:
            field_name: The field name to check
            model_name: Optional model name for scope filtering
            field_obj: Optional ir.model.fields record for CEL evaluation
            model_obj: Optional ir.model record for CEL evaluation

        Returns:
            recordset: The matching pattern or empty recordset
        """
        patterns = self.search([("active", "=", True)])
        for pattern in patterns:
            if pattern.matches_field(field_name, model_name, field_obj, model_obj):
                return pattern
        return self.browse()

    @api.model
    def auto_classify_field(self, model_name, field_name, field_obj=None, model_obj=None):
        """Attempt to auto-classify a field based on patterns.

        Args:
            model_name: The model name
            field_name: The field name
            field_obj: Optional ir.model.fields record for CEL evaluation
            model_obj: Optional ir.model record for CEL evaluation

        Returns:
            recordset: The created classification or empty if no match
        """
        pattern = self.find_matching_pattern(field_name, model_name, field_obj, model_obj)
        if not pattern:
            return self.env["spp.field.classification"].browse()

        _logger.info(
            "Auto-classifying %s.%s as %s (pattern: %s, mode: %s)",
            model_name,
            field_name,
            pattern.classification_id.code,
            pattern.name,
            pattern.match_mode,
        )

        return self.env["spp.field.classification"].ensure_classification(
            model_name=model_name,
            field_name=field_name,
            level_code=pattern.classification_id.code,
            source="auto",
            pattern_id=pattern.id,
            pii_category=pattern.pii_category,
            mask_pattern=pattern.default_mask_pattern,
            search_strategy=pattern.default_search_strategy,
        )

    @api.model
    def scan_model_fields(self, model_name, skip_classified=True):
        """Scan all fields of a model and auto-classify matches.

        Args:
            model_name: The model to scan
            skip_classified: Skip fields that already have classifications

        Returns:
            list: List of (field_name, classification) tuples
        """
        model = self.env["ir.model"].search([("model", "=", model_name)], limit=1)
        if not model:
            _logger.warning("Model not found: %s", model_name)
            return []

        results = []
        for field in model.field_id:
            # Skip non-data fields
            if field.ttype in ("one2many", "many2many"):
                continue

            # Skip if already classified
            if skip_classified:
                existing = self.env["spp.field.classification"].get_classification(model_name, field.name)
                if existing:
                    continue

            # Try to auto-classify (pass field and model objects for CEL evaluation)
            classification = self.auto_classify_field(model_name, field.name, field, model)
            if classification:
                results.append((field.name, classification))

        return results

    @api.model
    def scan_all_models(self, model_pattern=None, skip_classified=True):
        """Scan all models (or matching pattern) for PII fields.

        Args:
            model_pattern: Optional regex pattern to filter models
            skip_classified: Skip fields that already have classifications

        Returns:
            dict: {model_name: [(field_name, classification), ...]}
        """
        domain = [("transient", "=", False)]
        models = self.env["ir.model"].search(domain)

        if model_pattern:
            pattern = self._get_compiled_pattern(model_pattern)
            if pattern:
                models = models.filtered(lambda m: pattern.search(m.model))

        results = {}
        for model in models:
            model_results = self.scan_model_fields(model.model, skip_classified)
            if model_results:
                results[model.model] = model_results

        return results

    def action_test_pattern(self):
        """Test this pattern against a sample model to preview matches.

        Returns:
            Action to display notification with test results
        """
        self.ensure_one()

        # Use res.partner as sample model
        test_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        if not test_model:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Test Failed"),
                    "message": _("Cannot find res.partner model for testing"),
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Test against all fields
        matching_fields = []
        for field in test_model.field_id:
            if field.ttype in ("one2many", "many2many"):
                continue
            if self.matches_field(field.name, test_model.model, field, test_model):
                matching_fields.append(field.name)

        if matching_fields:
            message = _("Pattern matches %d fields:\n%s") % (
                len(matching_fields),
                ", ".join(sorted(matching_fields)[:20]),
            )
            if len(matching_fields) > 20:
                message += _(", ... and %d more") % (len(matching_fields) - 20)
            msg_type = "success"
        else:
            message = _("Pattern does not match any fields in res.partner")
            msg_type = "warning"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pattern Test Results"),
                "message": message,
                "type": msg_type,
                "sticky": True,
            },
        }
