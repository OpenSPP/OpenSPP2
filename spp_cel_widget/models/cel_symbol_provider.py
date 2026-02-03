"""CEL Symbol Provider - Extracts symbols for frontend autocompletion."""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Built-in CEL functions with their signatures and documentation
BUILTIN_FUNCTIONS = [
    {
        "name": "age_years",
        "signature": "age_years(date) -> int",
        "doc": "Calculate age in years from a date field",
        "params": [{"name": "birthdate", "type": "date", "doc": "Date of birth"}],
        "return_type": "int",
        "examples": ["age_years(r.birthdate) >= 18", "age_years(r.birthdate) >= 60"],
    },
    {
        "name": "today",
        "signature": "today() -> date",
        "doc": "Returns current date",
        "params": [],
        "return_type": "date",
        "examples": ["r.birthdate < today()"],
    },
    {
        "name": "now",
        "signature": "now() -> datetime",
        "doc": "Returns current date and time",
        "params": [],
        "return_type": "datetime",
        "examples": ["r.create_date < now()"],
    },
    {
        "name": "days_ago",
        "signature": "days_ago(n) -> date",
        "doc": "Returns date n days in the past",
        "params": [{"name": "n", "type": "int", "doc": "Number of days"}],
        "return_type": "date",
        "examples": ["r.create_date >= days_ago(30)"],
    },
    {
        "name": "months_ago",
        "signature": "months_ago(n) -> date",
        "doc": "Returns date n months in the past",
        "params": [{"name": "n", "type": "int", "doc": "Number of months"}],
        "return_type": "date",
        "examples": ["r.create_date >= months_ago(6)"],
    },
    {
        "name": "years_ago",
        "signature": "years_ago(n) -> date",
        "doc": "Returns date n years in the past",
        "params": [{"name": "n", "type": "int", "doc": "Number of years"}],
        "return_type": "date",
        "examples": ["r.birthdate <= years_ago(18)"],
    },
    {
        "name": "between",
        "signature": "between(value, min, max) -> bool",
        "doc": "Check if value is between min and max (inclusive)",
        "params": [
            {"name": "value", "type": "any", "doc": "Value to check"},
            {"name": "min", "type": "any", "doc": "Minimum value"},
            {"name": "max", "type": "any", "doc": "Maximum value"},
        ],
        "return_type": "bool",
        "examples": ["between(age_years(r.birthdate), 18, 65)"],
    },
    {
        "name": "exists",
        "signature": "collection.exists(var, condition) -> bool",
        "doc": "Check if any item in collection matches condition",
        "params": [
            {"name": "var", "type": "identifier", "doc": "Variable name for iteration"},
            {"name": "condition", "type": "expression", "doc": "Boolean condition"},
        ],
        "return_type": "bool",
        "examples": [
            "members.exists(m, m.gender == 'female')",
            "enrollments.exists(e, e.state == 'enrolled')",
        ],
    },
    {
        "name": "count",
        "signature": "collection.count(var, condition) -> int",
        "doc": "Count items in collection matching condition",
        "params": [
            {"name": "var", "type": "identifier", "doc": "Variable name for iteration"},
            {"name": "condition", "type": "expression", "doc": "Boolean condition"},
        ],
        "return_type": "int",
        "examples": [
            "members.count(m, age_years(m.birthdate) < 18) >= 2",
            "members.count(m, m.disabled == true) > 0",
        ],
    },
    {
        "name": "head",
        "signature": "head(member_var) -> bool",
        "doc": "Check if membership represents head of household",
        "params": [{"name": "member_var", "type": "identifier", "doc": "Member variable in exists/count"}],
        "return_type": "bool",
        "examples": ["members.exists(m, head(m) and m.gender == 'female')"],
    },
    {
        "name": "contains",
        "signature": "contains(field, text) -> bool",
        "doc": "Case-insensitive substring match",
        "params": [
            {"name": "field", "type": "char", "doc": "Text field to search"},
            {"name": "text", "type": "string", "doc": "Substring to find"},
        ],
        "return_type": "bool",
        "examples": ["contains(r.name, 'Santos')"],
    },
    {
        "name": "startswith",
        "signature": "startswith(field, prefix) -> bool",
        "doc": "Case-insensitive prefix match",
        "params": [
            {"name": "field", "type": "char", "doc": "Text field to check"},
            {"name": "prefix", "type": "string", "doc": "Prefix to match"},
        ],
        "return_type": "bool",
        "examples": ["startswith(r.phone, '+63')"],
    },
    {
        "name": "metric",
        "signature": "metric(name, subject?, period?) -> float",
        "doc": "Get indicator metric value (requires spp_indicators)",
        "params": [
            {"name": "name", "type": "string", "doc": "Metric name"},
            {"name": "subject", "type": "string", "doc": "Optional subject context", "optional": True},
            {"name": "period", "type": "string", "doc": "Optional time period", "optional": True},
        ],
        "return_type": "float",
        "examples": ['metric("household.size") >= 4', 'metric("income.monthly") < 5000'],
    },
]

# CEL operators
OPERATORS = [
    {"symbol": "and", "doc": "Logical AND", "type": "logical"},
    {"symbol": "or", "doc": "Logical OR", "type": "logical"},
    {"symbol": "not", "doc": "Logical NOT (prefix)", "type": "logical"},
    {"symbol": "==", "doc": "Equal to", "type": "comparison"},
    {"symbol": "!=", "doc": "Not equal to", "type": "comparison"},
    {"symbol": ">", "doc": "Greater than", "type": "comparison"},
    {"symbol": ">=", "doc": "Greater than or equal", "type": "comparison"},
    {"symbol": "<", "doc": "Less than", "type": "comparison"},
    {"symbol": "<=", "doc": "Less than or equal", "type": "comparison"},
    {"symbol": "in", "doc": "Value in list", "type": "membership"},
]

# CEL keywords
KEYWORDS = ["true", "false", "null"]

# Field types we expose for autocompletion
SIMPLE_FIELD_TYPES = ("char", "text", "integer", "float", "boolean", "date", "datetime", "selection", "monetary")

# Module prefixes whose fields should be included in the symbol browser.
# Fields from other Odoo modules (accounting, CRM, stock, etc.) are excluded.
ALLOWED_MODULE_PREFIXES = ("spp_", "g2p_", "openg2p_")

# Core Odoo fields on res.partner that are useful for CEL expressions.
# Only these fields from non-SPP modules are shown.
BASE_ALLOWED_FIELDS = frozenset(
    {
        "name",
        "active",
        "email",
        "phone",
        "mobile",
        "street",
        "street2",
        "city",
        "zip",
        "state_id",
        "country_id",
        "lang",
        "company_id",
    }
)

# Fields to always exclude regardless of origin
EXCLUDED_FIELD_SUFFIXES = ("_count", "_ids")


class CelSymbolProvider(models.AbstractModel):
    """Provides symbol information for CEL expression editor widget."""

    _name = "spp.cel.symbol.provider"
    _description = "CEL Symbol Provider for Editor Widget"

    @api.model
    def get_symbols_for_profile(self, profile_name):
        """Return complete symbol information for frontend autocompletion.

        Args:
            profile_name: CEL profile name (e.g., "registry_individuals")

        Returns:
            Dict with variables, functions, operators, keywords
        """
        # Load profile configuration
        try:
            cfg = self.env["spp.cel.registry"].load_profile(profile_name)
        except (KeyError, ValueError) as e:
            _logger.warning("Failed to load profile '%s': %s", profile_name, e)
            return self._empty_result(profile_name, str(e))

        if not cfg:
            return self._empty_result(profile_name, f"Profile '{profile_name}' not found")

        root_model = cfg.get("root_model", "res.partner")
        symbols = cfg.get("symbols", {})

        # Build variables list
        variables = []
        for sym_name, sym_config in symbols.items():
            var_info = self._build_variable_info(sym_name, sym_config, root_model)
            if var_info:
                variables.append(var_info)

        # Build functions list (built-in + registered)
        functions = self._get_all_functions()

        # Get CEL variables filtered by context
        cel_variables = self._get_cel_variables(profile_name)

        # Get library expressions filtered by context
        library_expressions = self._get_library_expressions(profile_name)

        return {
            "profile": profile_name,
            "root_model": root_model,
            "variables": variables,
            "cel_variables": cel_variables,
            "library": library_expressions,
            "functions": functions,
            "operators": OPERATORS,
            "keywords": KEYWORDS,
        }

    def _empty_result(self, profile_name, error=None):
        """Return empty result structure."""
        return {
            "profile": profile_name,
            "root_model": None,
            "variables": [],
            "cel_variables": [],
            "library": [],
            "functions": BUILTIN_FUNCTIONS,
            "operators": OPERATORS,
            "keywords": KEYWORDS,
            "error": error,
        }

    def _infer_context_from_profile(self, profile_name):
        """Map profile name to context type for filtering.

        Args:
            profile_name: CEL profile name (e.g., "registry_individuals")

        Returns:
            str: Context type ("individual", "group", or "both")
        """
        if "individual" in profile_name:
            return "individual"
        elif "group" in profile_name:
            return "group"
        return "both"

    def _get_cel_variables(self, profile_name):
        """Fetch spp.cel.variable records filtered by profile context.

        Args:
            profile_name: CEL profile name for context inference

        Returns:
            list: Variable info dicts for frontend display
        """
        context_type = self._infer_context_from_profile(profile_name)

        domain = [("active", "=", True), ("state", "=", "active")]
        if context_type and context_type != "both":
            domain.append(("applies_to", "in", [context_type, "both"]))

        try:
            Variable = self.env["spp.cel.variable"]
            variables = Variable.search(domain, order="category_id, sequence, name")
        except KeyError:
            _logger.debug("spp.cel.variable model not available")
            return []

        result = []
        for v in variables:
            # Get the expression to use - prefer cel_expression, fallback to accessor
            cel_expr = v.cel_expression or v.cel_accessor
            # For field-type variables, build r.field expression
            if v.source_type == "field" and v.source_field and not v.cel_expression:
                cel_expr = f"r.{v.source_field}"

            result.append(
                {
                    "name": v.cel_accessor,
                    "label": getattr(v, "label", None) or v.name,
                    "description": getattr(v, "description", None) or "",
                    "value_type": v.value_type,
                    "source_type": v.source_type,
                    "category": v.category_id.name if v.category_id else None,
                    "category_icon": getattr(v.category_id, "icon", None) if v.category_id else None,
                    "cel_expression": cel_expr,
                    "applies_to": v.applies_to,
                }
            )

        return result

    def _get_library_expressions(self, profile_name):
        """Fetch published library expressions filtered by context.

        Args:
            profile_name: CEL profile name for context inference

        Returns:
            list: Expression info dicts for frontend display
        """
        context_type = self._infer_context_from_profile(profile_name)

        domain = [
            ("active", "=", True),
        ]

        # Check if is_inline field exists (from spp_studio extension)
        try:
            Expression = self.env["spp.cel.expression"]
            if "is_inline" in Expression._fields:
                domain.append(("is_inline", "=", False))
            if "state" in Expression._fields:
                # spp_studio uses "published", base uses "active"
                if Expression._fields["state"].selection:
                    states = [s[0] for s in Expression._fields["state"].selection]
                    if "published" in states:
                        domain.append(("state", "=", "published"))
                    elif "active" in states:
                        domain.append(("state", "=", "active"))
        except KeyError:
            _logger.debug("spp.cel.expression model not available")
            return []

        if context_type and context_type != "both":
            domain.append(("context_type", "in", [context_type, "both"]))

        try:
            expressions = Expression.search(domain, order="sequence, name")
        except Exception as e:
            _logger.debug("Error fetching library expressions: %s", e)
            return []

        result = []
        for e in expressions:
            # Prefer compiled expression (frozen/published), fallback to raw
            cel_expr = getattr(e, "compiled_expression", None) or e.cel_expression or ""

            result.append(
                {
                    "id": e.id,
                    "name": e.name,
                    "code": getattr(e, "code", None) or "",
                    "description": getattr(e, "description", None) or "",
                    "expression_type": e.expression_type,
                    "output_type": e.output_type,
                    "cel_expression": cel_expr,
                    "context_type": e.context_type,
                }
            )

        return result

    def _build_variable_info(self, sym_name, sym_config, root_model):
        """Build variable information for a symbol."""
        if isinstance(sym_config, dict):
            model_name = sym_config.get("model")
            relation = sym_config.get("relation")

            if relation == "rel":
                # Collection variable (e.g., members, enrollments)
                through_model = sym_config.get("through")
                child_model = sym_config.get("child_model")
                link_to = sym_config.get("link_to")

                # Determine the actual child model
                target_model = child_model
                if not target_model and through_model and link_to:
                    try:
                        through_obj = self.env[through_model]
                        if link_to in through_obj._fields:
                            field = through_obj._fields[link_to]
                            if hasattr(field, "comodel_name"):
                                target_model = field.comodel_name
                    except KeyError:
                        # Model not found in registry
                        pass

                if not target_model:
                    target_model = through_model

                return {
                    "name": sym_name,
                    "type": "relation",
                    "doc": f"Collection via {through_model}" if through_model else "Collection",
                    "iterable": True,
                    "item_model": target_model,
                    "fields": self._get_model_fields(target_model) if target_model else [],
                }

            elif relation == "many2one":
                # Many2one reference (e.g., registrant, program)
                m2o_model = sym_config.get("model")
                return {
                    "name": sym_name,
                    "type": "object",
                    "doc": f"Reference to {m2o_model}",
                    "model": m2o_model,
                    "fields": self._get_model_fields(m2o_model) if m2o_model else [],
                }

            elif model_name:
                # Simple model reference (e.g., me)
                return {
                    "name": sym_name,
                    "type": "object",
                    "doc": f"Current {model_name.replace('.', ' ').title()}",
                    "model": model_name,
                    "fields": self._get_model_fields(model_name),
                }

        return None

    def _get_model_fields(self, model_name):
        """Get fields for a model suitable for autocompletion.

        Uses a module-origin allowlist: only fields defined by SPP/G2P modules
        or from an explicit base allowlist are included. This filters out hundreds
        of irrelevant fields from accounting, CRM, stock, and other Odoo modules.
        """
        fields = []

        try:
            model_obj = self.env[model_name]
            model_fields = model_obj._fields
        except KeyError:
            _logger.debug("Model '%s' not found", model_name)
            return fields
        except AttributeError as e:
            _logger.debug("Error accessing model '%s': %s", model_name, e)
            return fields

        # For models that are themselves SPP models, include all meaningful fields
        is_spp_model = model_name.startswith(("spp.", "g2p.", "openg2p."))

        # Build set of allowed field names from SPP modules via ir.model.data
        spp_field_names = set()
        if not is_spp_model:
            spp_field_names = self._get_spp_module_fields(model_name)

        for field_name, field_desc in model_fields.items():
            # Skip private and suffix-pattern fields always
            if field_name.startswith("_"):
                continue
            if field_name.endswith(EXCLUDED_FIELD_SUFFIXES):
                continue

            # For non-SPP models (e.g. res.partner), only allow:
            # 1. Fields defined by SPP/G2P modules
            # 2. Explicitly allowed base fields
            if not is_spp_model:
                if field_name not in spp_field_names and field_name not in BASE_ALLOWED_FIELDS:
                    continue

            field_type = field_desc.type

            # Include simple fields
            if field_type in SIMPLE_FIELD_TYPES:
                field_info = {
                    "name": field_name,
                    "type": field_type,
                    "doc": field_desc.string or field_name.replace("_", " ").title(),
                    "required": field_desc.required,
                }

                # Add selection options
                if field_type == "selection" and field_desc.selection:
                    try:
                        selection = field_desc.selection
                        if callable(selection):
                            selection = selection(model_obj)
                        field_info["options"] = [{"value": val, "label": label} for val, label in selection]
                    except (TypeError, ValueError):
                        pass

                fields.append(field_info)

            # Include many2one fields (for navigation)
            elif field_type == "many2one" and hasattr(field_desc, "comodel_name"):
                fields.append(
                    {
                        "name": field_name,
                        "type": "many2one",
                        "doc": field_desc.string or field_name.replace("_", " ").title(),
                        "comodel": field_desc.comodel_name,
                        "required": field_desc.required,
                    }
                )

        # Sort by name for consistent ordering
        fields.sort(key=lambda x: x["name"])
        return fields

    def _get_spp_module_fields(self, model_name):
        """Get field names defined by SPP/G2P modules for a given model.

        Queries ir.model.fields to find which module contributed each field,
        then returns only field names from allowed module prefixes.
        """
        try:
            query = """
                SELECT f.name
                FROM ir_model_fields f
                JOIN ir_model_data d ON (
                    d.model = 'ir.model.fields'
                    AND d.res_id = f.id
                )
                WHERE f.model = %s
                  AND d.module LIKE ANY(%s)
            """
            patterns = [prefix + "%" for prefix in ALLOWED_MODULE_PREFIXES]
            self.env.cr.execute(query, (model_name, patterns))
            return {row[0] for row in self.env.cr.fetchall()}
        except Exception:
            _logger.debug("Could not query SPP fields for model %s", model_name)
            return set()

    def _get_all_functions(self):
        """Get all available CEL functions (built-in + registered)."""
        functions = list(BUILTIN_FUNCTIONS)

        # Add dynamically registered functions
        try:
            registry = self.env["spp.cel.function.registry"]
            registered_names = registry.list_functions()
            builtin_names = {f["name"] for f in BUILTIN_FUNCTIONS}

            for name in registered_names:
                if name not in builtin_names:
                    functions.append(
                        {
                            "name": name,
                            "signature": f"{name}(...)",
                            "doc": "Dynamically registered function",
                            "params": [],
                            "return_type": "any",
                            "examples": [],
                        }
                    )
        except (KeyError, AttributeError) as e:
            _logger.debug("Could not fetch registered functions: %s", e)

        return functions

    @api.model
    def validate_expression(self, expression, profile_name, expression_type=None, output_type=None):
        """Validate a CEL expression and return structured errors.

        Args:
            expression: CEL expression to validate
            profile_name: CEL profile name
            expression_type: Type of expression (filter, formula, scoring, validation, other)
            output_type: Expected output type (boolean, number, string, money)

        Returns:
            Dict with valid, errors, warnings, matching_count, explain
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "matching_count": None,
            "explain": None,
        }

        if not expression or not expression.strip():
            result["errors"].append(
                {
                    "message": "Expression cannot be empty",
                    "line": 1,
                    "col_start": 0,
                    "col_end": 0,
                    "severity": "error",
                }
            )
            return result

        try:
            cel_service = self.env["spp.cel.service"]

            # Route to appropriate validation based on expression_type
            # Filter and validation types use domain compilation (boolean predicates)
            # Formula, scoring, and other types use syntax-only validation (value expressions)
            if expression_type in ("formula", "scoring", "other"):
                compile_result = cel_service.validate_formula_expression(
                    expression, profile_name, output_type=output_type
                )
            else:
                # Default to domain compilation for filter, validation, or unspecified types
                compile_result = cel_service.compile_expression(expression, profile_name)

            if compile_result.get("valid"):
                result["valid"] = True
                result["matching_count"] = compile_result.get("count", 0)
                result["explain"] = compile_result.get("explain", "")
            else:
                error_msg = compile_result.get("error", "Unknown error")
                error_info = self._parse_error_message(error_msg, expression)
                result["errors"].append(error_info)

        except Exception as e:
            _logger.exception("Error validating CEL expression")
            result["errors"].append(
                {
                    "message": str(e),
                    "line": 1,
                    "col_start": 0,
                    "col_end": len(expression),
                    "severity": "error",
                }
            )

        return result

    def _parse_error_message(self, error_msg, expression):
        """Parse error message to extract position and suggestions."""
        error_info = {
            "message": error_msg,
            "line": 1,
            "col_start": 0,
            "col_end": len(expression),
            "severity": "error",
            "suggestion": None,
        }

        # Try to extract position from error message
        # Format: "Syntax error: ... (line X)"
        if "(line " in error_msg:
            try:
                line_part = error_msg.split("(line ")[1].split(")")[0]
                error_info["line"] = int(line_part)
            except (IndexError, ValueError):
                pass

        # Try to extract suggestion
        # Format: "Did you mean: X, Y, Z?"
        if "Did you mean:" in error_msg:
            try:
                suggestion = error_msg.split("Did you mean:")[1].strip().rstrip("?")
                error_info["suggestion"] = suggestion
            except IndexError:
                pass

        # Try to find the problematic symbol
        if "Unknown symbol:" in error_msg:
            try:
                symbol = error_msg.split("Unknown symbol:")[1].split(".")[0].strip()
                pos = expression.find(symbol)
                if pos >= 0:
                    error_info["col_start"] = pos
                    error_info["col_end"] = pos + len(symbol)
            except IndexError:
                pass

        return error_info

    @api.model
    def get_available_profiles(self):
        """Get list of available CEL profiles with descriptions.

        Dynamically discovers profiles from:
        1. DEFAULT_PRESETS in spp_cel_domain
        2. YAML configuration files
        3. System parameters (ir.config_parameter)
        """
        profiles = []
        seen_names = set()

        # Profile descriptions (for known profiles)
        descriptions = {
            "registry_individuals": "Individual registrants (non-group members)",
            "registry_groups": "Groups/households with members",
            "program_memberships": "Program enrollment records",
            "entitlements": "Entitlement/benefit records",
            "grm_tickets": "GRM ticket records",
        }

        # Get profiles from CEL registry
        try:
            # Import DEFAULT_PRESETS from cel_registry
            from odoo.addons.spp_cel_domain.models.cel_registry import DEFAULT_PRESETS

            for name, config in DEFAULT_PRESETS.items():
                if name not in seen_names:
                    profiles.append(
                        {
                            "name": name,
                            "doc": descriptions.get(name, f"CEL profile: {name}"),
                            "root_model": config.get("root_model", "res.partner"),
                        }
                    )
                    seen_names.add(name)
        except ImportError:
            _logger.debug("Could not import DEFAULT_PRESETS from spp_cel_domain")

        # Also check for YAML-defined profiles
        try:
            registry = self.env["spp.cel.registry"]
            yaml_profiles = registry._load_yaml_profiles()
            if yaml_profiles:
                for name, config in yaml_profiles.items():
                    if name not in seen_names:
                        profiles.append(
                            {
                                "name": name,
                                "doc": config.get("description", f"Custom profile: {name}"),
                                "root_model": config.get("root_model", "res.partner"),
                            }
                        )
                        seen_names.add(name)
        except (KeyError, AttributeError) as e:
            _logger.debug("Could not load YAML profiles: %s", e)

        # Sort by name for consistent ordering
        profiles.sort(key=lambda p: p["name"])
        return profiles
