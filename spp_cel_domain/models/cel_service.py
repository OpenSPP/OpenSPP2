"""CEL Service Facade.

Provides a unified interface for CEL expression compilation and execution.
This decouples consumers from the internal CEL implementation details.

Following ADR-008, this service integrates with the variable resolver
to expand variable references (r.variable, constants) before compilation.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class CELService(models.AbstractModel):
    """Unified service for CEL expression operations.

    This facade provides a stable API for other modules to use CEL functionality
    without depending on internal implementation details.

    Usage:
        service = env["spp.cel.service"]
        result = service.compile_expression(
            "age_years(r.birthdate) >= 18",
            profile="registry_individuals"
        )
        # result = {"domain": [...], "count": 123, "ids": [...], "explain": "..."}
    """

    _name = "spp.cel.service"
    _description = "CEL Expression Service"

    @api.model
    def compile_expression(
        self,
        expression,
        profile,
        base_domain=None,
        limit=0,
        fields=None,
        materialize_sql=False,
    ):
        """Compile a CEL expression and return results.

        Args:
            expression: The CEL expression string
            profile: Profile name (e.g., "registry_individuals", "registry_groups")
            base_domain: Optional additional domain to AND with the result
            limit: Max number of IDs to return (0 = count only)
            fields: Optional list of field names to include in preview_records
            materialize_sql: If True, execute SQL subqueries to get actual IDs (needed for window actions)

        Returns:
            dict with keys:
                - domain: The compiled Odoo domain
                - count: Number of matching records
                - ids: List of matching record IDs (if limit > 0)
                - preview_records: List of record dicts with requested fields (JSON-safe)
                - explain: Human-readable explanation
                - valid: Boolean indicating if expression is valid
                - error: Error message if invalid
        """
        from ..exceptions import CELError, CELSymbolError, CELSyntaxError

        result = {
            "domain": [],
            "count": 0,
            "ids": [],
            "preview_records": [],
            "explain": "",
            "valid": False,
            "error": None,
        }

        if not expression or not expression.strip():
            result["error"] = "Expression cannot be empty"
            return result

        # Normalize limit: negative values treated as None (count-only mode)
        # limit=0 means use executor's default, limit>0 is explicit
        if limit < 0:
            limit = None  # Sentinel for count-only mode

        try:
            # Load profile configuration
            cfg = self.env["spp.cel.registry"].load_profile(profile)

            # Apply base domain if provided
            if base_domain:
                existing_base = cfg.get("base_domain", [])
                cfg["base_domain"] = list(existing_base) + list(base_domain)

            # Get root model from profile
            root_model = cfg.get("root_model", "res.partner")

            # ADR-017: Resolve variables before compilation
            # Determine context_type from profile name (default to "individual" if None)
            profile_str = str(profile) if profile else ""
            context_type = "individual" if "individual" in profile_str or not profile_str else "group"
            resolver = self.env["spp.cel.variable.resolver"]
            resolution = resolver.resolve_for_evaluation(expression, context_type=context_type)
            expanded_expression = resolution.get("expression", expression)

            # Execute compilation with expanded expression
            executor = self.env["spp.cel.executor"].with_context(cel_profile=profile, cel_cfg=cfg)
            exec_result = executor.compile_and_preview(
                root_model,
                expanded_expression,
                limit=limit,
                fields=fields,
                materialize_sql=materialize_sql,
            )

            result["domain"] = exec_result.get("domain", [])
            result["count"] = exec_result.get("count", 0)
            result["ids"] = exec_result.get("ids", [])
            result["preview_records"] = exec_result.get("preview_records", [])
            result["explain"] = exec_result.get("explain", "")
            result["path"] = exec_result.get("path")
            result["valid"] = True

        except CELSyntaxError as e:
            result["error"] = f"Syntax error: {e.message}"
            if e.line:
                result["error"] += f" (line {e.line})"
        except CELSymbolError as e:
            result["error"] = f"Unknown symbol: {e.symbol}"
            if e.available_symbols:
                suggestions = ", ".join(sorted(e.available_symbols)[:5])
                result["error"] += f". Did you mean: {suggestions}?"
        except CELError as e:
            result["error"] = str(e.message)
        except SyntaxError as e:
            # Legacy syntax errors from parser
            result["error"] = f"Syntax error: {str(e)}"
        except KeyError as e:
            # Legacy symbol errors
            result["error"] = f"Unknown symbol: {str(e).strip(chr(39))}"
        except Exception as e:
            _logger.exception("CEL compilation error")
            result["error"] = f"Compilation error: {str(e)}"

        return result

    @api.model
    def validate_expression(self, expression, profile):
        """Validate a CEL expression without executing it.

        Args:
            expression: The CEL expression string
            profile: Profile name

        Returns:
            dict with keys:
                - valid: Boolean
                - error: Error message if invalid
                - explain: Explanation of what the expression does
        """
        result = self.compile_expression(expression, profile, limit=0)
        return {
            "valid": result["valid"],
            "error": result["error"],
            "explain": result["explain"],
        }

    @api.model
    def validate_formula_expression(self, expression, profile, output_type=None):
        """Validate a formula/scoring CEL expression without domain compilation.

        Formula expressions calculate values (numbers, money, strings) rather than
        filtering records. They should not be compiled to Odoo domains.

        This method validates:
        1. Syntax is correct (via CEL parser)
        2. All referenced variables exist and can be resolved
        3. Expression can be parsed into a valid AST

        Args:
            expression: The CEL expression string
            profile: Profile name (used for context_type determination)
            output_type: Expected output type (number, money, string) - for future type checking

        Returns:
            dict with keys:
                - valid: Boolean indicating if expression is valid
                - error: Error message if invalid
                - explain: Description of the formula
                - resolved_expression: Expression after variable resolution
        """
        from ..services.cel_parser import parse

        result = {
            "valid": False,
            "error": None,
            "explain": "",
            "resolved_expression": expression,
            "count": None,  # Formulas don't have matching counts
        }

        if not expression or not expression.strip():
            result["error"] = "Expression cannot be empty"
            return result

        try:
            # Step 1: Resolve variables
            profile_str = str(profile) if profile else ""
            context_type = "individual" if "individual" in profile_str or not profile_str else "group"
            resolver = self.env["spp.cel.variable.resolver"]
            resolution = resolver.resolve_for_evaluation(expression, context_type=context_type)
            expanded_expression = resolution.get("expression", expression)
            result["resolved_expression"] = expanded_expression

            # Check for missing variables
            if resolution.get("missing_variables"):
                missing = ", ".join(resolution["missing_variables"])
                result["error"] = f"Missing variables: {missing}"
                return result

            # Step 2: Parse the expanded expression (syntax validation)
            ast = parse(expanded_expression)
            if ast is None:
                result["error"] = "Failed to parse expression"
                return result

            # Step 3: Generate explanation
            variables_used = resolution.get("variables_used", [])
            if variables_used:
                result["explain"] = f"Formula using: {', '.join(variables_used)}"
            else:
                result["explain"] = f"Formula: {expanded_expression}"

            # Validation passed
            result["valid"] = True

        except SyntaxError as e:
            result["error"] = f"Syntax error: {str(e)}"
        except Exception as e:
            _logger.exception("Formula validation error")
            result["error"] = f"Validation error: {str(e)}"

        return result

    @api.model
    def get_matching_ids(self, expression, profile, base_domain=None, limit=0):
        """Get IDs of records matching the expression.

        Args:
            expression: The CEL expression string
            profile: Profile name
            base_domain: Optional additional domain filter
            limit: Max IDs to return (0 = all)

        Returns:
            List of record IDs, or empty list on error
        """
        result = self.compile_expression(expression, profile, base_domain, limit=limit or 10000)
        if result["valid"]:
            return result["ids"]
        return []

    @api.model
    def get_domain(self, expression, profile, base_domain=None):
        """Get the Odoo domain for an expression.

        Args:
            expression: The CEL expression string
            profile: Profile name
            base_domain: Optional additional domain filter

        Returns:
            Odoo domain list, or empty list on error
        """
        result = self.compile_expression(expression, profile, base_domain)
        if result["valid"]:
            return result["domain"]
        return []

    @api.model
    def get_available_profiles(self):
        """Get list of available CEL profiles.

        Returns:
            List of profile names
        """
        return [
            "registry_individuals",
            "registry_groups",
            "program_memberships",
            "entitlements",
        ]

    @api.model
    def get_profile_info(self, profile):
        """Get information about a profile.

        Args:
            profile: Profile name

        Returns:
            dict with profile details (root_model, symbols, etc.)
        """
        try:
            cfg = self.env["spp.cel.registry"].load_profile(profile)
            return {
                "name": profile,
                "root_model": cfg.get("root_model"),
                "symbols": list(cfg.get("symbols", {}).keys()),
                "base_domain": cfg.get("base_domain", []),
            }
        except Exception as e:
            return {"name": profile, "error": str(e)}

    @api.model
    def evaluate_expression(self, expression, profile_or_context, context=None):
        """Evaluate a CEL expression with a context dictionary.

        This method evaluates CEL expressions directly with provided context data,
        rather than compiling to Odoo domains. This is used for testing and
        validation of logic expressions.

        Args:
            expression: The CEL expression string to evaluate
            profile_or_context: Either a profile name (str) or context dict.
                               If context param is None, this is treated as context.
            context: Optional context dict (if profile_or_context is a profile name)

        Returns:
            The evaluated result (bool, int, float, or str)
        """
        # Determine if we have profile + context or just context
        if context is None:
            # Called with (expression, context)
            actual_context = profile_or_context
        else:
            # Called with (expression, profile, context)
            actual_context = context

        if not isinstance(actual_context, dict):
            actual_context = {}

        try:
            result = self._evaluate_cel_expression(expression, actual_context)
            return result
        except Exception as e:
            _logger.warning(
                "CEL expression evaluation failed. Expression: %s, Error: %s",
                expression,
                str(e),
            )
            raise

    def _evaluate_cel_expression(self, expression, context):
        """Evaluate a CEL expression using the proper AST parser and evaluator.

        Uses the CEL lexer/parser to parse expressions into an AST, then
        evaluates the AST against the provided context. This is more robust
        and secure than regex-based conversion to Python eval().

        Supports:
        - Variable access from context
        - Comparisons: ==, !=, <, <=, >, >=
        - Logical: &&, ||, !
        - List membership: x in [a, b, c]
        - Function calls: age_years(), is_female(), etc.
        - Arithmetic: +, -, *, /
        - Boolean literals: true, false
        - Ternary: condition ? true_expr : false_expr

        Args:
            expression: CEL expression string
            context: Dict of variable values

        Returns:
            Evaluated result (bool, int, float, or str)
        """
        from ..services.cel_parser import evaluate, parse

        if not expression or not expression.strip():
            return None

        # Build evaluation context with functions
        eval_context = self._build_eval_context(context)

        try:
            # Parse expression to AST using proper CEL lexer/parser
            ast = parse(expression.strip())
            # Evaluate AST against context
            return evaluate(ast, eval_context)
        except SyntaxError as e:
            _logger.warning("CEL syntax error in '%s': %s", expression, str(e))
            raise
        except RecursionError as e:
            _logger.warning("CEL recursion limit exceeded in '%s': %s", expression, str(e))
            raise
        except Exception as e:
            _logger.warning("CEL evaluation error for '%s': %s", expression, str(e))
            raise

    def _build_eval_context(self, context):
        """Build evaluation context with variables and functions for AST evaluator.

        Args:
            context: Dict of user-provided variable values

        Returns:
            Dict context for cel_parser.evaluate()
        """
        from ..services import cel_functions

        # Start with user context variables
        eval_context = dict(context) if context else {}

        # Add core CEL functions from cel_functions module
        eval_context.update(
            {
                "today": cel_functions.today,
                "now": cel_functions.now,
                "days_ago": cel_functions.days_ago,
                "months_ago": cel_functions.months_ago,
                "years_ago": cel_functions.years_ago,
                "age_years": cel_functions.age_years,
                "between": cel_functions.between,
                "size": cel_functions.size,
                "has": cel_functions.has,
                "matches": cel_functions.matches,
            }
        )

        # Add safe builtins
        eval_context.update(
            {
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "abs": abs,
                "min": min,
                "max": max,
                "sum": sum,
            }
        )

        # Ensure vocabulary functions are registered (lazy initialization)
        try:
            if "spp.cel.vocabulary.functions" in self.env:
                self.env["spp.cel.vocabulary.functions"]._ensure_registered()
        except Exception as e:
            _logger.debug("Could not ensure vocabulary function registration: %s", e)

        # Create session-scoped vocabulary cache for efficient lookups
        vocab_cache = None
        try:
            if "spp.vocabulary.concept.group" in self.env:
                from odoo.addons.spp_cel_vocabulary.services.vocabulary_cache import (
                    VocabularyCache,
                )

                vocab_cache = VocabularyCache(self.env)
        except ImportError:
            _logger.debug("VocabularyCache not available, using fallback caching")

        # Add functions from the function registry (including vocabulary functions)
        try:
            registry = self.env["spp.cel.function.registry"]
            for func_name in registry.list_functions():
                handler = registry.get_handler(func_name)
                if handler:
                    # Check if function needs environment injection
                    if getattr(handler, "_cel_needs_env", False):
                        # Wrap with current environment - vocab_cache passed via context
                        if vocab_cache:
                            current_env = self.with_context(_vocab_cache=vocab_cache).env
                        else:
                            current_env = self.env

                        def env_wrapper(*args, _h=handler, _e=current_env, **kwargs):
                            return _h(_e, *args, **kwargs)

                        env_wrapper.__name__ = getattr(handler, "__name__", func_name)
                        env_wrapper.__doc__ = handler.__doc__
                        eval_context[func_name] = env_wrapper
                    else:
                        eval_context[func_name] = handler
        except Exception as e:
            _logger.warning("Failed to load CEL functions from registry: %s", e)

        return eval_context

    @api.model
    def invalidate_caches(self):
        """Invalidate all CEL-related caches.

        Call this when system parameters or configurations change.
        """
        try:
            self.env["spp.cel.registry"].invalidate_cache()
        except Exception as e:
            _logger.warning("Failed to invalidate CEL registry cache: %s", e)

        # Also try to clear translation cache if it exists
        try:
            from . import cel_translator

            if hasattr(cel_translator, "_translation_cache"):
                cel_translator._translation_cache.clear()
        except Exception as e:
            _logger.warning("Failed to clear CEL translation cache: %s", e)

        # Clear variable resolver cache
        try:
            self.env["spp.cel.variable.resolver"].invalidate_variable_cache()
        except Exception as e:
            _logger.warning("Failed to invalidate variable resolver cache: %s", e)

        return True

    # ═══════════════════════════════════════════════════════════════════════
    # MEMBER AGGREGATE EVALUATION
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def evaluate_member_aggregate(self, group, expression):
        """Evaluate a member aggregate expression for a specific group.

        Handles expressions like:
        - members.count(true) or members.count(m, filter) - count members
        - members.exists(filter) or members.exists(m, filter) - check if any match
        - members.sum(m, m.field, filter) - sum of field values
        - members.avg(m, m.field, filter) - average of field values
        - members.min(m, m.field, filter) - minimum field value
        - members.max(m, m.field, filter) - maximum field value

        Args:
            group: res.partner record (must be a group with group_membership_ids)
            expression: CEL aggregate expression string

        Returns:
            Aggregate result (int/float for numeric, bool for exists)
        """
        import re

        if not group or not hasattr(group, "group_membership_ids"):
            _logger.warning("evaluate_member_aggregate called with invalid group")
            return 0

        # Get active memberships
        memberships = group.group_membership_ids.filtered(lambda m: not m.is_ended)

        if not memberships:
            if ".exists(" in expression:
                return False
            return 0

        # Parse the expression: members.operation(args...)
        match = re.match(r"members\.(count|exists|sum|avg|min|max)\((.+)\)$", expression, re.DOTALL)
        if not match:
            _logger.warning("Could not parse members aggregate: %s", expression)
            return 0 if ".count(" in expression else False

        operation = match.group(1)
        args_str = match.group(2).strip()

        # Parse arguments - split on top-level commas (respecting parentheses)
        args = self._split_aggregate_args(args_str)

        if operation in ("sum", "avg", "min", "max"):
            return self._evaluate_field_aggregate(group, memberships, operation, args)

        # count / exists: determine filter expression
        if len(args) >= 2:
            # 2-arg format: members.count(m, filter) - skip iterator var
            filter_expr = args[-1].strip()
        else:
            filter_expr = args[0].strip()

        # For simple "true" filter, count/check all members
        if filter_expr.lower() == "true":
            individuals = memberships.mapped("individual")
            if operation == "exists":
                return len(individuals) > 0
            return len(individuals)

        # Evaluate filter for each member
        matching_count = self._evaluate_member_filter(group, memberships, filter_expr)

        if operation == "exists":
            return matching_count > 0
        return matching_count

    @staticmethod
    def _split_aggregate_args(args_str):
        """Split aggregate arguments on top-level commas, respecting parentheses.

        E.g. "m, m.income, age_years(m.birthdate) >= 18" -> ["m", "m.income", "age_years(m.birthdate) >= 18"]
        """
        args = []
        depth = 0
        current = []
        for ch in args_str:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            args.append("".join(current).strip())
        return args

    def _evaluate_field_aggregate(self, group, memberships, operation, args):
        """Evaluate sum/avg/min/max aggregation over a member field.

        Args format: [iterator_var, field_expr, filter_expr]
        E.g. ["m", "m.income", "true"] for members.sum(m, m.income, true)
        """
        if len(args) >= 3:
            # 3-arg: (m, m.field, filter)
            field_expr = args[1].strip()
            filter_expr = args[2].strip()
        elif len(args) == 2:
            # 2-arg legacy: (m.field, filter)
            field_expr = args[0].strip()
            filter_expr = args[1].strip()
        else:
            _logger.warning("Field aggregate requires at least 2 arguments, got: %s", args)
            return 0

        # Extract field name from m.field_name
        field_name = field_expr
        if field_name.startswith("m."):
            field_name = field_name[2:]

        # Collect field values from matching members
        values = []
        for membership in memberships:
            individual = membership.individual

            # Check filter
            if filter_expr.lower() != "true":
                context = {
                    "m": individual,
                    "r": individual,
                    "_membership": membership,
                    "_group": group,
                }
                try:
                    result = self.evaluate_expression(filter_expr, context)
                    if not result:
                        continue
                except Exception as e:
                    _logger.debug("Member filter failed for '%s': %s", filter_expr, e)
                    continue

            # Get field value
            try:
                val = getattr(individual, field_name, 0)
                if val is None or val is False:
                    val = 0
                values.append(float(val))
            except (TypeError, ValueError) as e:
                _logger.debug("Could not get numeric value for '%s': %s", field_name, e)
                values.append(0.0)

        if not values:
            return 0.0 if operation != "avg" else 0.0

        if operation == "sum":
            return sum(values)
        elif operation == "avg":
            return sum(values) / len(values)
        elif operation == "min":
            return min(values)
        elif operation == "max":
            return max(values)
        return 0

    def _evaluate_member_filter(self, group, memberships, filter_expr):
        """Evaluate a filter expression against group memberships.

        This method properly handles:
        - head(m) - checks membership_type_ids
        - is_female(m.gender_id) - uses vocabulary functions
        - age_years(m.birthdate) - uses registered functions
        - Combined expressions with && and ||

        Args:
            group: The group (res.partner) being evaluated
            memberships: Active membership recordset
            filter_expr: CEL filter expression

        Returns:
            int: Count of matching members
        """
        matching_count = 0

        for membership in memberships:
            individual = membership.individual

            # Build context with both membership and individual data
            # 'm' represents the member context - includes both individual fields
            # and membership relationship to the group
            context = {
                "m": individual,
                "r": individual,
                # Store membership for head() function to access
                "_membership": membership,
                "_group": group,
            }

            try:
                # Use evaluate_expression which has access to vocabulary functions
                result = self.evaluate_expression(filter_expr, context)
                if result:
                    matching_count += 1
            except Exception as e:
                _logger.debug("Member filter evaluation failed for '%s': %s", filter_expr, str(e))

        return matching_count

    # ═══════════════════════════════════════════════════════════════════════
    # VARIABLE RESOLUTION INTEGRATION (ADR-008)
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def resolve_variables(self, expression, program_id=None, context_type="group"):
        """Resolve variable references in a CEL expression.

        Expands variables defined in spp.cel.variable to their CEL expressions.
        Following ADR-008 syntax:
        - r.field -> field on current record
        - r.variable -> expands to variable's CEL expression
        - constant -> expands to constant value (no prefix)
        - m.field -> member field (inside aggregations)

        Args:
            expression: The CEL expression with variable references
            program_id: Optional program ID for constant overrides
            context_type: 'individual', 'group', or 'both'

        Returns:
            dict: {
                'expression': str,  # Resolved expression
                'variables_used': list,  # Variables that were resolved
                'missing_variables': list,  # Variables not found
                'warnings': list,  # Resolution warnings
                'from_cache': bool,  # Whether result was cached
            }
        """
        try:
            resolver = self.env["spp.cel.variable.resolver"]
            return resolver.resolve_for_evaluation(expression, program_id, context_type)
        except Exception as e:
            _logger.warning("Variable resolution failed: %s", str(e))
            return {
                "expression": expression,
                "variables_used": [],
                "missing_variables": [],
                "warnings": [str(e)],
                "from_cache": False,
            }

    @api.model
    def compile_with_variables(self, expression, profile, program_id=None, base_domain=None, limit=0):
        """Compile a CEL expression with automatic variable resolution.

        This method first resolves all variable references, then compiles
        the resulting expression. Use this for expressions that reference
        spp.cel.variable definitions.

        Args:
            expression: CEL expression with variable references
            profile: Profile name for compilation context
            program_id: Optional program ID for constant overrides
            base_domain: Optional additional domain filter
            limit: Max number of IDs to return (0 = count only)

        Returns:
            dict: Same as compile_expression, plus:
                - resolved_expression: The expression after variable resolution
                - variables_used: List of variables that were resolved
                - resolution_warnings: Any warnings from resolution
        """
        # Determine context_type from profile
        context_type = "group"
        if "individual" in profile:
            context_type = "individual"

        # Resolve variables first
        resolution = self.resolve_variables(expression, program_id, context_type)

        # Compile the resolved expression
        result = self.compile_expression(
            resolution["expression"],
            profile,
            base_domain,
            limit,
        )

        # Add resolution info to result
        result["resolved_expression"] = resolution["expression"]
        result["variables_used"] = resolution["variables_used"]
        result["resolution_warnings"] = resolution["warnings"]

        # If there were missing variables, add to error
        if resolution["missing_variables"]:
            missing_str = ", ".join(resolution["missing_variables"])
            if result["error"]:
                result["error"] += f" (missing variables: {missing_str})"
            else:
                result["valid"] = False
                result["error"] = f"Missing variables: {missing_str}"

        return result

    @api.model
    def evaluate_with_variables(self, expression, context, program_id=None, context_type="group"):
        """Evaluate a CEL expression with automatic variable resolution.

        This method first resolves all variable references, then evaluates
        the resulting expression against the provided context.

        Args:
            expression: CEL expression with variable references
            context: Dict of runtime values for evaluation
            program_id: Optional program ID for constant overrides
            context_type: 'individual', 'group', or 'both'

        Returns:
            The evaluated result (bool, int, float, or str)
        """
        # Resolve variables first
        resolution = self.resolve_variables(expression, program_id, context_type)

        if resolution["missing_variables"]:
            _logger.warning("Expression has missing variables: %s", resolution["missing_variables"])

        # Evaluate the resolved expression
        return self.evaluate_expression(resolution["expression"], context)

    @api.model
    def get_available_variables(self, context_type="both"):
        """Get list of available CEL variables for a context.

        Args:
            context_type: 'individual', 'group', or 'both'

        Returns:
            recordset: spp.cel.variable records
        """
        try:
            resolver = self.env["spp.cel.variable.resolver"]
            return resolver.get_available_variables(context_type)
        except Exception as e:
            _logger.warning("Failed to get available variables: %s", str(e))
            return self.env["spp.cel.variable"].browse()

    @api.model
    def validate_expression_with_variables(self, expression, program_id=None, context_type="group"):
        """Validate that an expression has all required variables defined.

        Args:
            expression: CEL expression to validate
            program_id: Optional program ID for constant overrides
            context_type: 'individual', 'group', or 'both'

        Returns:
            dict: {
                'valid': bool,
                'errors': list,
                'warnings': list,
                'resolved_expression': str,
            }
        """
        try:
            resolver = self.env["spp.cel.variable.resolver"]
            return resolver.validate_expression(expression, program_id, context_type)
        except Exception as e:
            return {
                "valid": False,
                "errors": [str(e)],
                "warnings": [],
                "resolved_expression": expression,
            }
