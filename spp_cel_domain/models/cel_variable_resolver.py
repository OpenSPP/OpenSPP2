# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CEL Variable Resolver Service.

This service handles the expansion of variable references in CEL expressions.
It translates simplified variable names (like 'child_count', 'hh_size', 'poverty_line')
into their full CEL expressions (like 'members.count(age_years(m.birthdate) < 18)',
'members.count(true)', '2500').

Variable expansion is recursive - if a computed variable references other
variables, those will also be expanded.

Following ADR-008 syntax:
- r.field - Field on current record
- r.variable - Variable for current record (expands to CEL)
- constant - Global constant (no prefix)
- m.field - Member field (inside members.* only)
"""

import logging
import re
from collections import OrderedDict

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class CELVariableResolver(models.AbstractModel):
    """Service for resolving variable references in CEL expressions.

    This is an abstract model (no database table) that provides
    variable resolution functionality for the CEL engine.

    This is the base implementation that can be extended by other modules
    (e.g., spp_studio) to work with their own variable models while
    sharing the core resolution logic.

    To extend, override:
    - _get_variable_model(): Return your variable model name
    - _get_cache_version_key(): Return your cache version parameter key
    """

    _name = "spp.cel.variable.resolver"
    _description = "CEL Variable Resolver Service"

    # Pattern to match potential variable names in CEL expressions
    VARIABLE_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")

    # Maximum recursion depth for variable expansion
    MAX_EXPANSION_DEPTH = 10

    # ═══════════════════════════════════════════════════════════════════════
    # EXTENSION HOOKS - Override in subclasses
    # ═══════════════════════════════════════════════════════════════════════

    def _get_variable_model(self):
        """Return the variable model name to use for resolution.

        Override this in subclasses to use a different variable model.

        Returns:
            str: Model name (e.g., 'spp.cel.variable', 'spp.logic.variable')
        """
        return "spp.cel.variable"

    def _get_cache_version_key(self):
        """Return the config parameter key for cache version.

        Override this in subclasses to use a different cache key.

        Returns:
            str: Config parameter key for cache versioning
        """
        return "spp.cel.variable.resolver.cache_version"

    # ═══════════════════════════════════════════════════════════════════════
    # RESERVED WORDS
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def _get_reserved_words(self):
        """Get all reserved words dynamically.

        Combines constants from spp_cel_domain with dynamically registered functions.

        Returns:
            set: All reserved words that should not be treated as variables
        """
        try:
            from ..services.cel_parser import (
                CEL_CONTEXT_IDENTIFIERS,
                CEL_RESERVED_WORDS,
                PYTHON_BUILTINS,
            )

            reserved = set()
            reserved.update(CEL_RESERVED_WORDS)
            reserved.update(PYTHON_BUILTINS)
            reserved.update(CEL_CONTEXT_IDENTIFIERS)
        except ImportError:
            # Fallback defaults
            reserved = {
                "true",
                "false",
                "null",
                "in",
                "not",
                "and",
                "or",
                "r",
                "m",
                "members",
                "enrollments",
                "entitlements",
            }

        # Get registered functions from the CEL function registry
        try:
            registry = self.env["spp.cel.function.registry"]
            registered_functions = registry.list_functions()
            reserved.update(registered_functions)
        except Exception:
            _logger.debug("Could not load CEL function registry")

        return reserved

    # ═══════════════════════════════════════════════════════════════════════
    # VARIABLE EXPANSION
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def expand_expression(
        self,
        expression,
        program_id=None,
        context_type="group",
        _depth=0,
        _seen_vars=None,
    ):
        """Expand variable references in a CEL expression recursively.

        Takes a simplified expression like:
            "r.age >= retirement_age && r.hh_size > 1"

        And expands it to the full CEL:
            "age_years(r.birthdate) >= 60 && members.count(true) > 1"

        Supports recursive expansion for computed variables that reference
        other variables.

        Args:
            expression (str): CEL expression with variable references
            program_id (int): Optional program ID for constant overrides
            context_type (str): 'individual' or 'group' for context-appropriate expansion
            _depth (int): Internal recursion depth counter
            _seen_vars (set): Internal set of already-expanded variables

        Returns:
            dict: {
                'expression': str,  # Expanded expression
                'variables_used': list,  # Variable names that were expanded
                'missing_variables': list,  # Variable names that couldn't be found
                'warnings': list,  # Any warnings during expansion
            }
        """
        if not expression:
            return {
                "expression": "",
                "variables_used": [],
                "missing_variables": [],
                "warnings": [],
            }

        # Initialize seen variables set for recursion tracking
        if _seen_vars is None:
            _seen_vars = set()

        # Check recursion depth
        if _depth > self.MAX_EXPANSION_DEPTH:
            return {
                "expression": expression,
                "variables_used": [],
                "missing_variables": [],
                "warnings": [_("Maximum expansion depth reached. Possible circular reference.")],
            }

        variables_used = []
        missing_variables = []
        warnings = []

        # Extract potential variable names
        potential_vars = self._extract_variable_names(expression)

        # Build replacement map
        replacements = {}
        Variable = self.env[self._get_variable_model()]
        reserved_words = self._get_reserved_words()

        # First pass: filter out names that shouldn't be looked up
        names_to_lookup = []
        for var_name in potential_vars:
            # Skip CEL reserved words
            if var_name.lower() in reserved_words or var_name in reserved_words:
                continue

            # Skip already-expanded variables to prevent infinite loops
            if var_name in _seen_vars:
                continue

            # Check if this name is being used as a function call
            func_call_pattern = rf"\b{re.escape(var_name)}\s*\("
            if re.search(func_call_pattern, expression):
                continue

            # Skip property accesses (names preceded by a dot, e.g., m.income)
            # This prevents expanding field accesses like m.income as variables
            property_access_pattern = rf"\.{re.escape(var_name)}\b"
            if re.search(property_access_pattern, expression):
                continue

            names_to_lookup.append(var_name)

        # BATCH QUERY: Fetch all matching variables in ONE query (N+1 prevention)
        var_lookup = {}
        if names_to_lookup:
            # Build OR domain for all names
            domain = ["&", ("active", "=", True)]
            name_domain = ["|"] * (len(names_to_lookup) * 2 - 1) if len(names_to_lookup) > 1 else []
            for name in names_to_lookup:
                name_domain.extend([("name", "=", name), ("cel_accessor", "=", name)])

            if len(names_to_lookup) == 1:
                domain = [
                    ("active", "=", True),
                    "|",
                    ("name", "=", names_to_lookup[0]),
                    ("cel_accessor", "=", names_to_lookup[0]),
                ]
            else:
                domain = [("active", "=", True)] + name_domain

            all_candidates = Variable.search(domain)

            # Build lookup dict: var_name -> list of matching variables
            for var in all_candidates:
                if var.name in names_to_lookup:
                    var_lookup.setdefault(var.name, []).append(var)
                if var.cel_accessor and var.cel_accessor in names_to_lookup:
                    var_lookup.setdefault(var.cel_accessor, []).append(var)

        # Second pass: process each variable name using the pre-fetched lookup
        for var_name in names_to_lookup:
            candidates = var_lookup.get(var_name, [])

            variable = False
            if candidates:
                # Convert list to recordset for filtering
                candidate_ids = [v.id for v in candidates]
                candidates_rs = Variable.browse(candidate_ids)

                # Prefer variables that match the current context_type
                if context_type in ("individual", "group"):
                    preferred = candidates_rs.filtered(lambda v: v.applies_to == context_type)
                    if preferred:
                        variable = preferred[0]
                    else:
                        # Fall back to context-agnostic variables
                        both_ctx = candidates_rs.filtered(lambda v: v.applies_to == "both")
                        variable = both_ctx[:1] or candidates_rs[:1]
                else:
                    # Unknown or 'both' context: prefer 'both', then any
                    both_ctx = candidates_rs.filtered(lambda v: v.applies_to == "both")
                    variable = both_ctx[:1] or candidates_rs[:1]

            if variable:
                # Check context compatibility
                if context_type == "individual" and variable.applies_to == "group":
                    warnings.append(_("Variable '%s' is for groups but used in individual context") % var_name)
                elif context_type == "group" and variable.applies_to == "individual":
                    pass  # May still work

                # ADR-017: Check if variable uses persistent caching
                # Variables with ttl/manual cache_strategy should emit metric() calls
                # instead of expanding to inline CEL expressions
                cache_strategy = getattr(variable, "cache_strategy", "none")

                if cache_strategy in ("ttl", "manual"):
                    # Emit metric() call for cached variables
                    metric_call = f"metric('{var_name}', me)"
                    replacements[var_name] = metric_call
                    variables_used.append(var_name)
                    _logger.debug(
                        "Variable '%s' has cache_strategy='%s', emitting metric() call",
                        var_name,
                        cache_strategy,
                    )
                else:
                    # Get the CEL expression for this variable
                    cel_expr = variable.get_cel_expression(program_id)

                    if cel_expr and cel_expr != var_name:
                        # Mark this variable as seen before recursing
                        new_seen = _seen_vars | {var_name}

                        # Recursively expand the variable's expression
                        recursive_result = self.expand_expression(
                            cel_expr,
                            program_id,
                            context_type,
                            _depth=_depth + 1,
                            _seen_vars=new_seen,
                        )

                        # Use the recursively expanded expression
                        replacements[var_name] = recursive_result["expression"]
                        variables_used.append(var_name)
                        variables_used.extend(recursive_result["variables_used"])
                        missing_variables.extend(recursive_result["missing_variables"])
                        warnings.extend(recursive_result["warnings"])
                    else:
                        # Variable exists but has same accessor (no expansion needed)
                        variables_used.append(var_name)
            else:
                # Check if it might be a literal or known field
                if not self._is_likely_literal(var_name, expression):
                    missing_variables.append(var_name)

        # Apply replacements
        expanded = self._apply_replacements(expression, replacements)

        return {
            "expression": expanded,
            "variables_used": list(set(variables_used)),
            "missing_variables": list(set(missing_variables)),
            "warnings": warnings,
        }

    @api.model
    def _extract_variable_names(self, expression):
        """Extract potential variable names from a CEL expression.

        Uses the CEL lexer to properly tokenize the expression, which correctly
        handles string literals, numbers, and other tokens.

        Args:
            expression (str): CEL expression

        Returns:
            set: Set of potential variable names
        """
        if not expression:
            return set()

        try:
            from ..services.cel_parser import Lexer

            lexer = Lexer(expression)
            tokens = lexer.tokens()
            # Extract only IDENT tokens
            return {tok.value for tok in tokens if tok.kind == "IDENT"}
        except (ImportError, SyntaxError):
            # Fall back to regex if lexer fails
            _logger.debug("Lexer failed on expression, falling back to regex: %s", expression)
            matches = self.VARIABLE_PATTERN.findall(expression)
            return set(matches)

    @api.model
    def _is_likely_literal(self, name, expression):
        """Check if a name is likely a literal value or object property.

        Args:
            name (str): The potential variable name
            expression (str): The full expression for context

        Returns:
            bool: True if likely a literal/property, not a variable
        """
        # Check if it's accessed as a property (preceded by dot)
        pattern = rf"\.{re.escape(name)}\b"
        if re.search(pattern, expression):
            return True

        # Check if it's a function call
        pattern = rf"\b{re.escape(name)}\s*\("
        if re.search(pattern, expression):
            return True

        return False

    @api.model
    def _apply_replacements(self, expression, replacements):
        """Apply variable replacements to an expression.

        Uses word boundaries to ensure we only replace whole variable names,
        not parts of other names.

        Args:
            expression (str): Original expression
            replacements (dict): Map of variable name -> CEL expression

        Returns:
            str: Expression with replacements applied
        """
        result = expression

        # Sort by length descending to replace longer names first
        sorted_names = sorted(replacements.keys(), key=len, reverse=True)

        for var_name in sorted_names:
            cel_expr = replacements[var_name]

            # Use word boundaries
            pattern = rf"(?<![a-zA-Z0-9_]){re.escape(var_name)}(?![a-zA-Z0-9_])"

            # Wrap complex expressions in parentheses
            if " " in cel_expr or any(op in cel_expr for op in ["&&", "||", "+", "-", "*", "/"]):
                replacement = f"({cel_expr})"
            else:
                replacement = cel_expr

            result = re.sub(pattern, replacement, result)

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # VALIDATION
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def validate_expression(self, expression, program_id=None, context_type="group"):
        """Validate that an expression can be fully expanded.

        Args:
            expression (str): CEL expression to validate
            program_id (int): Optional program ID
            context_type (str): 'individual' or 'group'

        Returns:
            dict: {
                'valid': bool,
                'errors': list,
                'warnings': list,
                'expanded_expression': str,
            }
        """
        result = self.expand_expression(expression, program_id, context_type)

        errors = []
        if result["missing_variables"]:
            errors.append(_("Undefined variables: %s") % ", ".join(result["missing_variables"]))

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": result["warnings"],
            "expanded_expression": result["expression"],
        }

    @api.model
    def get_available_variables(self, context_type="both"):
        """Get list of available variables for a context.

        Args:
            context_type (str): 'individual', 'group', or 'both'

        Returns:
            recordset: Variable records from the configured model
        """
        Variable = self.env[self._get_variable_model()]

        domain = [("active", "=", True)]

        if context_type == "individual":
            domain.append(("applies_to", "in", ["individual", "both"]))
        elif context_type == "group":
            domain.append(("applies_to", "in", ["group", "both"]))

        return Variable.search(domain, order="category_id, sequence, name")

    @api.model
    def expand_pack_item(self, pack_item, program_id=None):
        """Expand variables in a pack item's logic_data.

        This method is for Studio logic pack integration.

        Args:
            pack_item: spp.logic.pack.item record
            program_id (int): Optional program ID for constant overrides

        Returns:
            dict: {
                'original_expression': str,
                'expanded_expression': str,
                'variables_used': list,
                'missing_variables': list,
                'warnings': list,
            }
        """
        import json

        try:
            logic_data = json.loads(pack_item.logic_data)
        except (json.JSONDecodeError, TypeError):
            return {
                "original_expression": "",
                "expanded_expression": "",
                "variables_used": [],
                "missing_variables": [],
                "warnings": [_("Invalid JSON in pack item")],
            }

        original_expr = logic_data.get("cel_expression", "")

        # Determine context from pack item (fallback to group)
        context_type = pack_item.context_type or "group"

        result = self.expand_expression(original_expr, program_id, context_type)

        return {
            "original_expression": original_expr,
            "expanded_expression": result["expression"],
            "variables_used": result["variables_used"],
            "missing_variables": result["missing_variables"],
            "warnings": result["warnings"],
        }

    # ═══════════════════════════════════════════════════════════════════════
    # DEFERRED RESOLUTION (Runtime Cache)
    # ═══════════════════════════════════════════════════════════════════════

    # Cache for variable definitions - invalidated when variables change
    # Uses OrderedDict for true LRU (Least Recently Used) behavior:
    # - move_to_end() marks items as recently used on access
    # - popitem(last=False) evicts oldest accessed item
    _variable_cache = OrderedDict()
    _CACHE_MAX_SIZE = 1000

    @api.model
    def _get_cache_key(self, expression, program_id, context_type):
        """Generate a cache key for an expression resolution."""
        company_id = self.env.company.id
        return (
            expression,
            program_id,
            context_type,
            company_id,
            self._get_cache_version(),
        )

    @api.model
    def _get_cache_version(self):
        """Get the current cache version.

        Uses raw SQL with parameterized query to ensure consistency with
        invalidate_variable_cache() which also uses raw SQL. This avoids
        ORM cache staleness issues.
        """
        cache_key = self._get_cache_version_key()
        self.env.cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (cache_key,))
        result = self.env.cr.fetchone()
        if result:
            try:
                return int(result[0])
            except (ValueError, TypeError):
                return 0
        return 0

    @api.model
    def invalidate_variable_cache(self):
        """Invalidate the variable resolution cache.

        Call this whenever a variable definition changes to ensure
        that subsequent evaluations use the updated definitions.

        NOTE: Local cache is cleared BEFORE incrementing version to prevent
        a race condition where another thread reads the new version but
        gets stale data from this thread's not-yet-cleared cache.
        """
        # Clear local cache FIRST to prevent race condition
        self.__class__._variable_cache = OrderedDict()

        cache_key = self._get_cache_version_key()

        # Use SQL UPDATE with parameterized query for atomic increment
        self.env.cr.execute(
            """
            UPDATE ir_config_parameter
            SET value = (COALESCE(value::integer, 0) + 1)::text
            WHERE key = %s
            RETURNING value
            """,
            (cache_key,),
        )
        result = self.env.cr.fetchone()

        if not result:
            # nosemgrep: odoo-sudo-without-context — standard Odoo pattern for system parameter access
            ICP = self.env["ir.config_parameter"].sudo()
            ICP.set_param(cache_key, "1")
            new_version = 1
        else:
            new_version = int(result[0])

        _logger.debug("Variable resolution cache invalidated (version %d)", new_version)

    @api.model
    def _cache_get(self, key):
        """Get item from cache and mark as recently used.

        Returns None if key not found. Moves accessed item to end
        of OrderedDict to implement true LRU behavior.
        """
        cache = self.__class__._variable_cache
        if key in cache:
            cache.move_to_end(key)  # Mark as recently used
            return cache[key]
        return None

    @api.model
    def _cache_put(self, key, value):
        """Add item to cache with LRU eviction if needed.

        Uses true LRU eviction: removes least recently accessed items first.
        """
        cache = self.__class__._variable_cache

        # Evict oldest accessed items until we're under the limit
        while len(cache) >= self._CACHE_MAX_SIZE:
            evicted_key, _ = cache.popitem(last=False)  # Remove oldest accessed
            key_str = evicted_key[:50] if isinstance(evicted_key, str) else str(evicted_key)[:50]
            _logger.debug("Cache eviction: removed entry %s", key_str)

        cache[key] = value

    @api.model
    def resolve_for_evaluation(self, expression, program_id=None, context_type="group"):
        """Resolve variable references in an expression for runtime evaluation.

        This is the main entry point for deferred variable resolution.
        It expands variable names to their current CEL definitions at
        evaluation time, allowing changes to propagate automatically.

        Args:
            expression (str): CEL expression with variable references
            program_id (int): Optional program ID for constant overrides
            context_type (str): 'individual', 'group', or 'both'

        Returns:
            dict: {
                'expression': str,  # Resolved expression ready for evaluation
                'variables_used': list,
                'missing_variables': list,
                'warnings': list,
                'from_cache': bool,
            }
        """
        if not expression:
            return {
                "expression": "",
                "variables_used": [],
                "missing_variables": [],
                "warnings": [],
                "from_cache": False,
            }

        # Check cache first (using _cache_get to mark as recently used)
        cache_key = self._get_cache_key(expression, program_id, context_type)
        cached = self._cache_get(cache_key)
        if cached is not None:
            result = cached.copy()
            result["from_cache"] = True
            return result

        # Not in cache - resolve variables
        result = self.expand_expression(expression, program_id, context_type)
        result["from_cache"] = False

        # Cache the result
        self._cache_put(cache_key, result.copy())

        return result

    @api.model
    def preview_resolution(self, expression, program_id=None, context_type="group"):
        """Preview how an expression would be resolved without caching.

        Args:
            expression (str): CEL expression with variable references
            program_id (int): Optional program ID for constant overrides
            context_type (str): 'individual', 'group', or 'both'

        Returns:
            dict: Same as resolve_for_evaluation but never cached
        """
        if not expression:
            return {
                "expression": "",
                "variables_used": [],
                "missing_variables": [],
                "warnings": [],
                "from_cache": False,
            }

        result = self.expand_expression(expression, program_id, context_type)
        result["from_cache"] = False
        return result

    # ═══════════════════════════════════════════════════════════════════════
    # CACHED VARIABLE SUPPORT (Unified Variable System)
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def analyze_expression_caching(self, expression, context_type="group"):
        """Analyze an expression for cached variable usage.

        This method identifies which variables in an expression use persistent
        caching, allowing the evaluator to optimize execution by:
        1. Pre-fetching cached values in batch
        2. Using SQL JOINs against spp.data.value for cached variables
        3. Only computing inline for non-cached variables

        Args:
            expression (str): CEL expression to analyze
            context_type (str): 'individual', 'group', or 'both'

        Returns:
            dict: {
                'cached_variables': list,  # Variables with persistent cache
                'session_cached_variables': list,  # Variables with session cache
                'inline_variables': list,  # Variables computed inline
                'external_variables': list,  # Variables from external sources
                'variable_details': dict,  # {var_name: {cache_strategy, source_type, ...}}
            }
        """
        if not expression:
            return {
                "cached_variables": [],
                "session_cached_variables": [],
                "inline_variables": [],
                "external_variables": [],
                "variable_details": {},
            }

        # Extract variable names
        potential_vars = self._extract_variable_names(expression)
        reserved_words = self._get_reserved_words()

        # Filter to actual variable names
        var_names = []
        for name in potential_vars:
            if name.lower() in reserved_words or name in reserved_words:
                continue
            # Check if used as function call
            func_call_pattern = rf"\b{re.escape(name)}\s*\("
            if re.search(func_call_pattern, expression):
                continue
            var_names.append(name)

        if not var_names:
            return {
                "cached_variables": [],
                "session_cached_variables": [],
                "inline_variables": [],
                "external_variables": [],
                "variable_details": {},
            }

        # Batch fetch all matching variables
        Variable = self.env[self._get_variable_model()]
        domain = [
            ("active", "=", True),
            "|",
            ("name", "in", var_names),
            ("cel_accessor", "in", var_names),
        ]
        variables = Variable.search(domain)

        # Build name-to-variable mapping
        var_by_name = {}
        for var in variables:
            if var.name in var_names:
                var_by_name[var.name] = var
            if var.cel_accessor and var.cel_accessor in var_names:
                var_by_name[var.cel_accessor] = var

        # Classify variables
        cached = []
        session_cached = []
        inline = []
        external = []
        details = {}

        for var_name in var_names:
            var = var_by_name.get(var_name)
            if not var:
                continue

            info = {
                "cache_strategy": var.cache_strategy,
                "source_type": var.source_type,
                "value_type": var.value_type,
                "period_granularity": var.period_granularity,
                "variable_id": var.id,
            }
            details[var_name] = info

            if var.cache_strategy in ("ttl", "manual"):
                cached.append(var_name)
            elif var.cache_strategy == "session":
                session_cached.append(var_name)
            else:
                inline.append(var_name)

            if var.source_type in ("external", "scoring"):
                external.append(var_name)

        return {
            "cached_variables": cached,
            "session_cached_variables": session_cached,
            "inline_variables": inline,
            "external_variables": external,
            "variable_details": details,
        }

    @api.model
    def resolve_with_cache_info(self, expression, program_id=None, context_type="group", period_key=None):
        """Resolve expression with caching metadata for hybrid evaluation.

        This is the enhanced resolution method that returns both the expanded
        expression AND information about which variables should be fetched
        from cache vs computed inline.

        Args:
            expression (str): CEL expression with variable references
            program_id (int): Optional program ID for constant overrides
            context_type (str): 'individual', 'group', or 'both'
            period_key (str): Optional period key for historical queries

        Returns:
            dict: {
                'expression': str,  # Expanded expression
                'variables_used': list,
                'missing_variables': list,
                'warnings': list,
                'cache_info': {
                    'cached_variables': list,
                    'session_cached_variables': list,
                    'inline_variables': list,
                    'variable_details': dict,
                },
                'requires_cache_join': bool,  # True if SQL should JOIN spp.data.value
            }
        """
        # First get standard expansion
        result = self.resolve_for_evaluation(expression, program_id, context_type)

        # Then analyze caching
        cache_info = self.analyze_expression_caching(expression, context_type)

        result["cache_info"] = cache_info
        result["requires_cache_join"] = bool(cache_info["cached_variables"])

        return result

    @api.model
    def get_cached_variable_sql_alias(self, variable_name):
        """Get the SQL alias to use for a cached variable in JOINs.

        When building SQL queries that JOIN against spp.data.value for
        cached variables, this method provides consistent aliasing.

        Args:
            variable_name (str): Variable name

        Returns:
            str: SQL-safe alias like 'dv_household_size'
        """
        # Sanitize for SQL identifier
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", variable_name)
        return f"dv_{safe_name}"

    @api.model
    def build_cache_join_sql(self, variable_names, subject_alias="p", period_key=None):
        """Build SQL JOINs for cached variables.

        Generates LEFT JOIN clauses to fetch cached variable values from
        spp.data.value in a single query.

        Args:
            variable_names (list): List of cached variable names
            subject_alias (str): Alias of the subject table (default 'p' for partner)
            period_key (str): Period key for the query (default 'current')

        Returns:
            dict: {
                'joins': str,  # SQL JOIN clauses
                'select_columns': list,  # Column expressions to add to SELECT
                'column_aliases': dict,  # {variable_name: sql_alias}
            }
        """
        if not variable_names:
            return {"joins": "", "select_columns": [], "column_aliases": {}}

        joins = []
        select_cols = []
        aliases = {}
        period = period_key or "current"
        company_id = self.env.company.id

        for var_name in variable_names:
            alias = self.get_cached_variable_sql_alias(var_name)
            aliases[var_name] = alias

            # LEFT JOIN to get cached value
            join_sql = f"""
                LEFT JOIN spp_data_value AS {alias}
                    ON {alias}.subject_id = {subject_alias}.id
                    AND {alias}.subject_model = 'res.partner'
                    AND {alias}.variable_name = '{var_name}'
                    AND {alias}.period_key = '{period}'
                    AND {alias}.company_id = {company_id}
            """
            joins.append(join_sql)

            # Select the numeric value from JSON
            select_cols.append(f"({alias}.value_json->>'value')::float AS {alias}_value")

        return {
            "joins": "\n".join(joins),
            "select_columns": select_cols,
            "column_aliases": aliases,
        }

    @api.model
    def expand_for_hybrid_evaluation(self, expression, program_id=None, context_type="group"):
        """Expand expression for hybrid SQL/Python evaluation.

        For expressions with cached variables, this method:
        1. Identifies which variables need cache lookups
        2. Returns SQL components for cached variables
        3. Returns Python expression for remaining computation

        This enables efficient evaluation where cached values come from
        SQL JOINs and only non-cached parts need Python evaluation.

        Args:
            expression (str): CEL expression
            program_id (int): Optional program ID
            context_type (str): 'individual', 'group', or 'both'

        Returns:
            dict: {
                'original_expression': str,
                'expanded_expression': str,
                'cached_variables': list,
                'inline_variables': list,
                'sql_joins': str,  # SQL JOIN clauses for cached variables
                'sql_select_columns': list,  # Additional SELECT columns
                'column_mapping': dict,  # {variable_name: sql_column_alias}
                'evaluation_mode': str,  # 'pure_sql', 'hybrid', 'pure_python'
            }
        """
        if not expression:
            return {
                "original_expression": "",
                "expanded_expression": "",
                "cached_variables": [],
                "inline_variables": [],
                "sql_joins": "",
                "sql_select_columns": [],
                "column_mapping": {},
                "evaluation_mode": "pure_python",
            }

        # Analyze caching
        cache_info = self.analyze_expression_caching(expression, context_type)

        # Expand expression
        expansion = self.expand_expression(expression, program_id, context_type)

        # Build SQL components for cached variables
        sql_info = self.build_cache_join_sql(cache_info["cached_variables"])

        # Determine evaluation mode
        if not cache_info["cached_variables"] and not cache_info["inline_variables"]:
            mode = "pure_python"  # Simple expression, no variable lookups
        elif cache_info["cached_variables"] and not cache_info["inline_variables"]:
            mode = "pure_sql"  # All variables are cached, can do full SQL
        elif cache_info["cached_variables"]:
            mode = "hybrid"  # Mix of cached and inline
        else:
            mode = "pure_python"  # All inline computation

        return {
            "original_expression": expression,
            "expanded_expression": expansion["expression"],
            "cached_variables": cache_info["cached_variables"],
            "inline_variables": cache_info["inline_variables"],
            "sql_joins": sql_info["joins"],
            "sql_select_columns": sql_info["select_columns"],
            "column_mapping": sql_info["column_aliases"],
            "evaluation_mode": mode,
        }
