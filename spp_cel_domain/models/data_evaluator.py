# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Data Cache Manager - Variable cache lifecycle management service.

This module manages the lifecycle of cached variables in the Unified Variable System.
It handles pre-computation, refresh, invalidation, and retrieval of cached values
stored in spp.data.value.

As of Phase 4 (ADR-017), variable evaluation flows through:
  CEL Service → Variable Resolver → Executor → metric() → spp.data.value

This cache manager focuses on CACHE LIFECYCLE:
- Pre-computation: Batch compute variables before eligibility checks
- Refresh: Update stale or expired cache entries
- Invalidation: Explicitly clear cache entries
- Session caching: In-memory cache for request-scoped values
"""

import logging
import threading

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DataCacheManager(models.AbstractModel):
    """Variable cache lifecycle manager.

    This service manages the lifecycle of cached variables in the Unified Variable
    System. It handles batch pre-computation, cache refresh, and invalidation
    operations for variables with persistent caching (cache_strategy='ttl' or 'manual').

    Key responsibilities:
    - Pre-compute cached variables before eligibility checks
    - Refresh stale/expired cache entries (scheduled jobs)
    - Invalidate cache entries (API or manual trigger)
    - Manage session-scoped in-memory cache
    - Provide cache statistics and health metrics

    Usage:
        cache_mgr = env["spp.data.cache.manager"]

        # Pre-compute all cached variables for a cycle
        result = cache_mgr.precompute_cached_variables(
            subject_ids=[1, 2, 3],
            period_key="2024-12",
        )

        # Refresh a specific variable
        cache_mgr.refresh_variable("complex_score", [1, 2, 3])

        # Invalidate cache entries
        cache_mgr.invalidate_variable("pmt_score", subject_ids=[1, 2])
    """

    _name = "spp.data.cache.manager"
    _description = "Variable Cache Manager"

    # Thread-local storage for session-scoped caching
    # Ensures proper request isolation in multi-threaded environments
    _session_cache = threading.local()

    # ═══════════════════════════════════════════════════════════════════════
    # NOTE: Variable evaluation now flows through CEL Service (Phase 1-2 of ADR-017)
    # ═══════════════════════════════════════════════════════════════════════
    # Evaluation path: cel_service.evaluate_with_variables()
    #                  → variable_resolver.expand_expression()
    #                  → executor.execute()
    #                  → metric() for cached variables
    #                  → spp.data.value cache lookup
    #
    # This cache manager focuses on LIFECYCLE operations (pre-compute, refresh, invalidate),
    # NOT on evaluation itself.

    # ═══════════════════════════════════════════════════════════════════════
    # CACHE VALUE COMPUTATION
    # ═══════════════════════════════════════════════════════════════════════
    # These methods compute values for pre-computation and refresh operations

    def _compute_variable_values(self, variable, subject_ids, period_key, program_id):
        """Compute values for a variable across subjects.

        Routes to appropriate computation method based on source_type.

        Args:
            variable: Variable record
            subject_ids: List of subject IDs
            period_key: Period key
            program_id: Program ID

        Returns:
            dict: {subject_id: value, ...}
        """
        source_type = variable.source_type

        if source_type == "field":
            return self._compute_field_values(variable, subject_ids)

        elif source_type == "computed":
            return self._compute_cel_values(variable, subject_ids, program_id)

        elif source_type == "aggregate":
            return self._compute_aggregate_values(variable, subject_ids, program_id)

        elif source_type == "constant":
            return self._compute_constant_values(variable, subject_ids, program_id)

        elif source_type in ("external", "scoring"):
            # These should come from cache; if missing, return None
            _logger.warning(
                "Variable '%s' with source_type '%s' has no cached value. "
                "Values must be pushed via API or scoring run.",
                variable.name,
                source_type,
            )
            return {}

        else:
            _logger.warning("Unknown source_type '%s' for variable ID %s", source_type, variable.id)
            return {}

    def _compute_field_values(self, variable, subject_ids):
        """Compute values from direct field access.

        Args:
            variable: Variable record with source_type='field'
            subject_ids: List of subject IDs

        Returns:
            dict: {subject_id: value, ...}
        """
        if not variable.source_field:
            return {}

        model_name = variable.source_model or "res.partner"
        try:
            Model = self.env[model_name]
        except KeyError:
            _logger.warning("Model '%s' not found for variable ID %s", model_name, variable.id)
            return {}

        records = Model.browse(subject_ids).exists()
        result = {}

        for rec in records:
            try:
                value = rec[variable.source_field]
                # Handle relational fields
                if hasattr(value, "id"):
                    value = value.id
                elif hasattr(value, "ids"):
                    value = value.ids
                result[rec.id] = value
            except Exception as e:
                _logger.debug(
                    "Error reading field '%s' on %s#%d: %s",
                    variable.source_field,
                    model_name,
                    rec.id,
                    e,
                )

        return result

    def _compute_cel_values(self, variable, subject_ids, program_id):
        """Compute values from CEL expression evaluation.

        Args:
            variable: Variable record with source_type='computed'
            subject_ids: List of subject IDs

        Returns:
            dict: {subject_id: value, ...}
        """
        if not variable.cel_expression:
            return {}

        cel_service = self.env["spp.cel.service"]
        Model = self.env[variable.source_model or "res.partner"]
        records = Model.browse(subject_ids).exists()
        result = {}

        for rec in records:
            try:
                # Build context from record
                context = self._build_record_context(rec)

                # Evaluate CEL expression
                value = cel_service.evaluate_with_variables(
                    variable.cel_expression,
                    context,
                    program_id,
                    variable.applies_to or "both",
                )
                result[rec.id] = value
            except Exception as e:
                _logger.debug(
                    "Error evaluating CEL for %s on record %d: %s",
                    variable.name,
                    rec.id,
                    e,
                )

        return result

    def _compute_aggregate_values(self, variable, subject_ids, program_id):
        """Compute aggregate values over group members.

        Args:
            variable: Variable record with source_type='aggregate'
            subject_ids: List of group IDs

        Returns:
            dict: {subject_id: value, ...}
        """
        cel_expression = variable.cel_expression or variable._build_aggregate_cel()
        if not cel_expression:
            return {}

        cel_service = self.env["spp.cel.service"]
        Partner = self.env["res.partner"]
        groups = Partner.browse(subject_ids).exists()
        result = {}

        for group in groups:
            try:
                value = cel_service.evaluate_member_aggregate(group, cel_expression)
                result[group.id] = value
            except Exception as e:
                _logger.debug(
                    "Error evaluating aggregate for %s on group %d: %s",
                    variable.name,
                    group.id,
                    e,
                )

        return result

    def _compute_constant_values(self, variable, subject_ids, program_id):
        """Get constant values (same for all subjects).

        Args:
            variable: Variable record with source_type='constant'
            subject_ids: List of subject IDs
            program_id: Program ID for overrides

        Returns:
            dict: {subject_id: value, ...}
        """
        value = variable.get_cel_expression(program_id)

        # Try to parse as number
        try:
            if "." in str(value):
                value = float(value)
            else:
                value = int(value)
        except (ValueError, TypeError):
            pass  # Keep as string

        return {sid: value for sid in subject_ids}

    def _build_record_context(self, record):
        """Build CEL evaluation context from a record.

        Args:
            record: Odoo record (typically res.partner)

        Returns:
            dict: Context for CEL evaluation
        """
        # Access the record via 'r' prefix as per ADR-008
        context = {"r": record}

        # Add individual record fields directly for convenience
        for field_name in record._fields:
            try:
                context[field_name] = record[field_name]
            except Exception:
                pass

        return context

    def _cache_computed_values(self, variable, computed, period_key):
        """Store computed values in appropriate cache.

        Args:
            variable: Variable record
            computed: Dict of {subject_id: value}
            period_key: Period key
        """
        if not computed:
            return

        if variable.cache_strategy == "session":
            # Store in session cache (thread-local)
            company_id = self.env.company.id
            cache = getattr(self._session_cache, "cache", None)
            if cache is None:
                cache = {}
                self._session_cache.cache = cache
            for subject_id, value in computed.items():
                cache_key = (
                    company_id,
                    variable.name,
                    subject_id,
                    period_key or "current",
                )
                cache[cache_key] = value

        elif variable.cache_strategy in ("ttl", "manual"):
            # Store in persistent cache
            DataValue = self.env["spp.data.value"]
            values_list = []

            # Map variable source_type to valid cache source_type
            source_type_map = {
                "field": "computed",
                "constant": "computed",
                "computed": "computed",
                "aggregate": "aggregate",
                "vocabulary": "computed",
                "external": "external",
                "scoring": "scoring",
            }
            cache_source_type = source_type_map.get(variable.source_type, "computed")

            for subject_id, value in computed.items():
                values_list.append(
                    {
                        "variable_name": variable.name,
                        "subject_model": variable.source_model or "res.partner",
                        "subject_id": subject_id,
                        "period_key": period_key or "current",
                        "value_json": {"value": value},
                        "value_type": variable.value_type or "number",
                        "source_type": cache_source_type,
                        "ttl_seconds": variable.cache_ttl_seconds if variable.cache_strategy == "ttl" else None,
                    }
                )

            DataValue.upsert_values(values_list)

    # ═══════════════════════════════════════════════════════════════════════
    # SESSION CACHE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def clear_session_cache(self):
        """Clear the session cache.

        Call this at the end of a request or batch operation to free memory.
        """
        self._session_cache.cache = {}
        _logger.debug("Session cache cleared")

    @api.model
    def get_session_cache_stats(self):
        """Get statistics about the session cache.

        Returns:
            dict: {
                'size': int,
                'variables': list,
            }
        """
        cache = getattr(self._session_cache, "cache", {})
        variables = set()
        for key in cache:
            if len(key) >= 2:
                variables.add(key[1])  # variable name is second element

        return {
            "size": len(cache),
            "variables": list(variables),
        }

    # ═══════════════════════════════════════════════════════════════════════
    # REFRESH OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def refresh_variable(self, variable_name, subject_ids, period_key=None, program_id=None):
        """Force refresh of a variable's cached values.

        Computes fresh values and stores in cache, regardless of current cache state.

        Args:
            variable_name: Variable name
            subject_ids: List of subject IDs
            period_key: Optional period key
            program_id: Optional program ID

        Returns:
            dict: {subject_id: value, ...} with freshly computed values
        """
        result = self.precompute_variable(
            variable_name,
            subject_ids,
            period_key=period_key or "current",
            program_id=program_id,
        )

        if not result.get("success"):
            _logger.warning(
                "Failed to refresh variable '%s': %s",
                variable_name,
                result.get("error_message"),
            )
            return {}

        # Fetch the computed values from cache to return
        DataValue = self.env["spp.data.value"]
        cached = DataValue.read_values(
            variable_name,
            subject_ids,
            period_key=period_key or "current",
        )
        return cached

    @api.model
    def refresh_variables_for_subject(self, subject_id, variable_names=None, period_key=None):
        """Refresh all or selected variables for a subject.

        Args:
            subject_id: Subject ID
            variable_names: Optional list of variable names (None = all cacheable)
            period_key: Optional period key

        Returns:
            dict: {variable_name: value, ...}
        """
        if variable_names is None:
            # Get all variables with persistent caching
            Variable = self.env["spp.cel.variable"]
            variables = Variable.search(
                [
                    ("active", "=", True),
                    ("cache_strategy", "in", ["ttl", "manual"]),
                ]
            )
            variable_names = variables.mapped("name")

        if not variable_names:
            return {}

        # Use precompute_cached_variables to refresh all
        self.precompute_cached_variables(
            [subject_id],
            period_key=period_key or "current",
            variable_names=variable_names,
        )

        # Fetch values from cache
        DataValue = self.env["spp.data.value"]
        result = {}
        for var_name in variable_names:
            cached = DataValue.read_values(
                var_name,
                [subject_id],
                period_key=period_key or "current",
            )
            if subject_id in cached:
                result[var_name] = cached[subject_id]

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # CACHE INVALIDATION
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def invalidate_variable(self, variable_name, subject_ids=None, period_key=None):
        """Invalidate (delete) cache entries for a variable.

        This method explicitly removes cache entries from spp.data.value.
        Use this when you know that cached values are stale and should be
        recomputed on next access.

        Args:
            variable_name: Variable name to invalidate
            subject_ids: Optional list of subject IDs to invalidate.
                        If None, invalidates ALL cache entries for this variable.
            period_key: Optional period key to invalidate.
                       If None, invalidates all periods.

        Returns:
            int: Number of cache entries invalidated

        Example:
            # Invalidate specific subjects
            cache_mgr.invalidate_variable("pmt_score", subject_ids=[1, 2, 3])

            # Invalidate all cache entries for a variable
            cache_mgr.invalidate_variable("household_size")
        """
        DataValue = self.env["spp.data.value"]

        # Build domain for cache entries to invalidate
        domain = [
            ("variable_name", "=", variable_name),
            ("company_id", "=", self.env.company.id),
        ]
        if subject_ids:
            domain.append(("subject_id", "in", subject_ids))
        if period_key:
            domain.append(("period_key", "=", period_key))

        entries = DataValue.search(domain)
        count = len(entries)
        if entries:
            entries.unlink()

        _logger.info("Invalidated %d cache entries for variable '%s'", count, variable_name)

        return count

    # ═══════════════════════════════════════════════════════════════════════
    # BATCH PRE-COMPUTATION (Phase 3 of ADR-017)
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def precompute_variable(
        self,
        variable_name,
        subject_ids,
        period_key="current",
        program_id=None,
    ):
        """Pre-compute a cached variable for given subjects and store in cache.

        This method computes variable values for a batch of subjects and stores
        them in the persistent cache (spp.data.value). It's designed to populate
        cache before eligibility runs to ensure fast SQL-based lookups.

        Args:
            variable_name: Name of the variable to pre-compute
            subject_ids: List of subject IDs to compute for
            period_key: Period key for the computation (default: 'current')
            program_id: Optional program ID for constant overrides

        Returns:
            dict: {
                'success': bool,
                'computed': int,  # Number of values computed
                'cached': int,    # Number of values stored in cache
                'errors': int,    # Number of errors encountered
                'error_message': str or None,
            }

        Example:
            evaluator.precompute_variable(
                'complex_score',
                [1, 2, 3, 4, 5],
                period_key='2024-12',
            )
        """
        result = {
            "success": False,
            "computed": 0,
            "cached": 0,
            "errors": 0,
            "error_message": None,
        }

        if not subject_ids:
            result["success"] = True
            return result

        try:
            # Load variable definition
            Variable = self.env["spp.cel.variable"]
            var = Variable.search(
                [
                    ("name", "=", variable_name),
                    ("active", "=", True),
                ],
                limit=1,
            )

            if not var:
                result["error_message"] = f"Variable '{variable_name}' not found or inactive"
                _logger.warning(result["error_message"])
                return result

            # Only pre-compute variables with persistent caching
            if var.cache_strategy not in ("ttl", "manual"):
                result["error_message"] = (
                    f"Variable '{variable_name}' does not use persistent caching "
                    f"(cache_strategy={var.cache_strategy}). Pre-computation is only "
                    "available for 'ttl' and 'manual' cache strategies."
                )
                _logger.warning(result["error_message"])
                return result

            # Validate period_key for the variable
            try:
                var.validate_period_key(period_key)
            except Exception as e:
                result["error_message"] = f"Invalid period_key: {e}"
                _logger.warning(result["error_message"])
                return result

            # Compute values directly
            _logger.info(
                "Pre-computing variable '%s' for %d subjects (period=%s)",
                variable_name,
                len(subject_ids),
                period_key,
            )

            computed = self._compute_variable_values(var, subject_ids, period_key, program_id)

            # Store in persistent cache
            if computed:
                self._cache_computed_values(var, computed, period_key)

            # Count successful computations
            result["computed"] = len(computed)
            result["cached"] = len(computed)
            result["errors"] = len(subject_ids) - len(computed)
            result["success"] = True

            _logger.info(
                "Pre-computation complete for '%s': %d computed, %d errors",
                variable_name,
                result["computed"],
                result["errors"],
            )

        except Exception as e:
            _logger.exception("Error during pre-computation of '%s'", variable_name)
            result["error_message"] = str(e)
            result["success"] = False

        return result

    @api.model
    def precompute_cached_variables(
        self,
        subject_ids,
        period_key="current",
        program_id=None,
        variable_names=None,
    ):
        """Pre-compute ALL cached variables for given subjects.

        This method finds all variables with persistent caching enabled and
        computes their values for the given subjects. It's designed to be called
        before eligibility checks to ensure cache is warm.

        Args:
            subject_ids: List of subject IDs to compute for
            period_key: Period key for the computation (default: 'current')
            program_id: Optional program ID for constant overrides
            variable_names: Optional list of specific variable names to compute.
                          If None, computes all cached variables.

        Returns:
            dict: {
                'success': bool,
                'variables_processed': int,
                'total_computed': int,
                'total_cached': int,
                'total_errors': int,
                'results': {variable_name: result_dict, ...},
                'error_message': str or None,
            }

        Example:
            evaluator.precompute_cached_variables(
                [1, 2, 3, 4, 5],
                period_key='2024-12',
            )
        """
        overall_result = {
            "success": False,
            "variables_processed": 0,
            "total_computed": 0,
            "total_cached": 0,
            "total_errors": 0,
            "results": {},
            "error_message": None,
        }

        if not subject_ids:
            overall_result["success"] = True
            return overall_result

        try:
            # Find all variables with persistent caching
            Variable = self.env["spp.cel.variable"]
            domain = [
                ("active", "=", True),
                ("cache_strategy", "in", ["ttl", "manual"]),
            ]

            if variable_names:
                domain.append(("name", "in", variable_names))

            variables = Variable.search(domain)

            if not variables:
                msg = "No cached variables found"
                if variable_names:
                    msg += f" matching names: {variable_names}"
                overall_result["error_message"] = msg
                _logger.warning(msg)
                overall_result["success"] = True
                return overall_result

            _logger.info(
                "Pre-computing %d cached variables for %d subjects",
                len(variables),
                len(subject_ids),
            )

            # Pre-compute each variable
            for var in variables:
                try:
                    result = self.precompute_variable(
                        var.name,
                        subject_ids,
                        period_key=period_key,
                        program_id=program_id,
                    )

                    overall_result["results"][var.name] = result
                    overall_result["variables_processed"] += 1

                    if result["success"]:
                        overall_result["total_computed"] += result["computed"]
                        overall_result["total_cached"] += result["cached"]
                        overall_result["total_errors"] += result["errors"]
                    else:
                        _logger.warning(
                            "Failed to pre-compute variable '%s': %s",
                            var.name,
                            result.get("error_message"),
                        )

                except Exception as e:
                    _logger.exception("Error pre-computing variable '%s'", var.name)
                    overall_result["results"][var.name] = {
                        "success": False,
                        "error_message": str(e),
                    }

            overall_result["success"] = True

            _logger.info(
                "Pre-computation complete: %d variables, %d values computed, %d errors",
                overall_result["variables_processed"],
                overall_result["total_computed"],
                overall_result["total_errors"],
            )

        except Exception as e:
            _logger.exception("Error during batch pre-computation")
            overall_result["error_message"] = str(e)
            overall_result["success"] = False

        return overall_result

    @api.model
    def refresh_stale_cached_variables(self, max_age_hours=24, batch_size=1000):
        """Refresh stale cached variables.

        This method is designed to be called by a scheduled action (cron job)
        to periodically refresh cached variables that have expired or are
        approaching expiration.

        Args:
            max_age_hours: Refresh values older than this many hours (default: 24)
            batch_size: Maximum number of subjects to process per variable (default: 1000)

        Returns:
            dict: {
                'success': bool,
                'variables_refreshed': int,
                'values_refreshed': int,
                'errors': list of error messages,
            }

        Example:
            # Called by cron job daily
            evaluator.refresh_stale_cached_variables(max_age_hours=24)
        """
        result = {
            "success": False,
            "variables_refreshed": 0,
            "values_refreshed": 0,
            "errors": [],
        }

        try:
            from datetime import timedelta

            # Calculate cutoff time
            cutoff = fields.Datetime.now() - timedelta(hours=max_age_hours)

            DataValue = self.env["spp.data.value"]
            Variable = self.env["spp.cel.variable"]

            # Find all cached variables
            cached_variables = Variable.search(
                [
                    ("active", "=", True),
                    ("cache_strategy", "in", ["ttl", "manual"]),
                ]
            )

            _logger.info(
                "Refreshing stale cached variables (cutoff: %s, batch_size: %d)",
                cutoff,
                batch_size,
            )

            for var in cached_variables:
                try:
                    # Find stale values for this variable
                    stale_domain = [
                        ("variable_name", "=", var.name),
                        ("company_id", "=", self.env.company.id),
                        "|",
                        ("expires_at", "!=", False),
                        ("expires_at", "<", fields.Datetime.now()),
                    ]

                    # Also check recorded_at for manual refresh variables
                    if var.cache_strategy == "manual":
                        stale_domain = [
                            ("variable_name", "=", var.name),
                            ("company_id", "=", self.env.company.id),
                            ("recorded_at", "<", cutoff),
                        ]

                    stale_values = DataValue.search(stale_domain, limit=batch_size)

                    if not stale_values:
                        continue

                    # Extract unique subject IDs
                    subject_ids = list(set(stale_values.mapped("subject_id")))

                    _logger.info(
                        "Refreshing variable '%s' for %d subjects",
                        var.name,
                        len(subject_ids),
                    )

                    # Refresh the variable
                    refresh_result = self.precompute_variable(
                        var.name,
                        subject_ids,
                        period_key="current",
                    )

                    if refresh_result["success"]:
                        result["variables_refreshed"] += 1
                        result["values_refreshed"] += refresh_result["cached"]
                    else:
                        error_msg = f"Variable '{var.name}': {refresh_result.get('error_message')}"
                        result["errors"].append(error_msg)
                        _logger.warning(error_msg)

                except Exception as e:
                    error_msg = f"Variable '{var.name}': {str(e)}"
                    result["errors"].append(error_msg)
                    _logger.exception("Error refreshing variable '%s'", var.name)

            result["success"] = True

            _logger.info(
                "Stale cache refresh complete: %d variables refreshed, %d values updated",
                result["variables_refreshed"],
                result["values_refreshed"],
            )

        except Exception as e:
            error_msg = f"Batch refresh failed: {str(e)}"
            result["errors"].append(error_msg)
            _logger.exception("Error during stale cache refresh")

        return result
