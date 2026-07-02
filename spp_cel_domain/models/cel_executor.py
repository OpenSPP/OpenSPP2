from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from typing import Any

from odoo import api, models
from odoo.fields import Domain
from odoo.tools.sql import SQL

from ..exceptions import CELMetricsUnavailableError
from .cel_queryplan import (
    AND,
    NOT,
    OR,
    AggMetricCompare,
    CountThrough,
    CoverageRequire,
    ExistsThrough,
    FieldAggregateThrough,
    LeafDomain,
    MetricCompare,
    flatten_and,
)
from .cel_sql_builder import SQLBuilder


class CelExecutor(models.AbstractModel):
    _name = "spp.cel.executor"
    _description = "CEL Executor"
    _logger = logging.getLogger("odoo.addons.spp_cel_domain")

    # -------------------------------------------------------------------------
    # Logging Helpers
    # -------------------------------------------------------------------------
    def _format_domain_for_log(self, domain: list[Any], max_ids: int = 10) -> str:
        """Format domain for logging, truncating large ID lists.

        Converts [("id", "in", [1,2,3,...100000])] to readable format:
        [("id", "in", [1,2,3,...10] + "...(99990 more)")]
        """
        if not domain:
            return "[]"

        def truncate_value(val: Any) -> Any:
            if isinstance(val, SQL):
                return "<SQL subquery>"
            if isinstance(val, list | tuple) and len(val) > max_ids:
                truncated = list(val[:max_ids])
                remaining = len(val) - max_ids
                return f"{truncated}...({remaining} more)"
            return val

        def format_term(term: Any) -> str:
            if isinstance(term, tuple | list) and len(term) == 3:
                field, op, value = term
                formatted_val = truncate_value(value)
                return f"({field!r}, {op!r}, {formatted_val})"
            if isinstance(term, SQL):
                return "<SQL subquery>"
            return repr(term)

        parts = [format_term(t) for t in domain]
        return f"[{', '.join(parts)}]"

    # -------------------------------------------------------------------------
    # SQL Generation for Scale (millions of records)
    # -------------------------------------------------------------------------
    def _domain_to_id_sql(self, model: str, domain: list[Any]) -> SQL | None:
        """Convert an Odoo domain to a SQL subquery selecting IDs.

        Returns SQL object like: SELECT id FROM res_partner WHERE ...
        Returns None if domain cannot be safely converted to SQL.
        """
        if not domain:
            return None

        try:
            from odoo.osv import expression as osv_expression

            Model = self.env[model]
            table = Model._table

            # Build the expression and extract query
            expr = osv_expression.expression(model=Model, domain=domain)
            query = expr.query

            # Use query.select() to get the full SQL including FROM clause
            # with all JOINs (needed for related field domains like gender_id.uri)
            select_sql = query.select(SQL.identifier(table, "id"))

            return SQL("(%s)", select_sql)
        except Exception as e:
            self._logger.debug("[CEL SQL] Failed to convert domain to SQL: %s", e)
            return None

    def _exists_to_sql(self, p: ExistsThrough) -> SQL | None:
        """Convert ExistsThrough to a SQL subquery.

        Returns SQL selecting parent IDs where at least one matching child exists.
        """
        try:
            through_table = self.env[p.through_model]._table

            # Build child filter SQL
            child_sql: SQL | None = None
            if p.child_plan is not None:
                child_domain, requires_exec = self._plan_to_domain(p.child_model, p.child_plan)
                if requires_exec:
                    # Child plan requires execution - can't do SQL fast path
                    return None
                if child_domain:
                    child_sql = self._domain_to_id_sql(p.child_model, child_domain)
                    if child_sql is None:
                        return None

            # Build default domain SQL using SQLBuilder
            builder = SQLBuilder(self.env)
            through_where_parts: list[SQL] = []

            if p.default_domain:
                default_terms, success = builder.build_default_domain_sql("m", p.default_domain)
                if not success:
                    # Unsupported operator, fall back to Python
                    return None
                through_where_parts.extend(default_terms)

            # Build the EXISTS query
            if child_sql:
                where_child = SQL("m.%s IN %s", SQL.identifier(p.link_field), child_sql)
                through_where_parts.append(where_child)

            if through_where_parts:
                where_clause = builder.where_and(through_where_parts)
                result = SQL(
                    "(SELECT DISTINCT m.%s FROM %s m WHERE %s)",
                    SQL.identifier(p.parent_field),
                    SQL.identifier(through_table),
                    where_clause,
                )
            else:
                result = SQL(
                    "(SELECT DISTINCT m.%s FROM %s m)",
                    SQL.identifier(p.parent_field),
                    SQL.identifier(through_table),
                )

            return result
        except Exception as e:
            self._logger.debug("[CEL SQL] Failed to build EXISTS SQL: %s", e)
            return None

    def _count_to_sql(self, p: CountThrough) -> SQL | None:
        """Convert CountThrough to a SQL subquery.

        Returns SQL selecting parent IDs where child count matches the comparison.

        Special handling for edge cases:
        - count == 0: Parents with NO matching children (NOT IN subquery)
        - count < N or count <= N: Fall back to Python (needs special handling for 0-count parents)
        - count != N: Fall back to Python (complex edge cases)
        - count > 0, count >= N, count > N: Use GROUP BY + HAVING (standard approach)
        """
        try:
            through_table = self.env[p.through_model]._table

            # Build child filter SQL
            child_sql: SQL | None = None
            if p.child_plan is not None:
                child_domain, requires_exec = self._plan_to_domain(p.child_model, p.child_plan)
                if requires_exec:
                    return None
                if child_domain:
                    child_sql = self._domain_to_id_sql(p.child_model, child_domain)
                    if child_sql is None:
                        return None

            # Build default domain SQL using SQLBuilder
            builder = SQLBuilder(self.env)
            where_parts: list[SQL] = []

            if p.default_domain:
                default_terms, success = builder.build_default_domain_sql("m", p.default_domain)
                if not success:
                    # Unsupported operator, fall back to Python
                    return None
                where_parts.extend(default_terms)

            if child_sql:
                where_parts.append(SQL("m.%s IN %s", SQL.identifier(p.link_field), child_sql))

            where_clause = builder.where_and(where_parts)

            # Normalize operator
            op = p.op
            if op == "==":
                op = "="
            rhs = p.rhs

            # Fall back to Python for comparisons that need zero-count parents included
            # These are complex to handle correctly in SQL without the parent table:
            # - count == 0: Parents with no rows in membership table won't appear in SQL
            # - count < N: Must include zero-count parents
            # - count <= N: Must include zero-count parents
            # - count != N: Complex edge cases with zero-count
            if op == "=" and rhs == 0:
                return None
            if op in ("<", "<="):
                return None
            if op == "!=":
                return None

            # Map operator for standard GROUP BY + HAVING approach
            # Works for: count > 0, count >= N (N > 0), count > N
            op_map = {">": ">", ">=": ">=", "=": "="}
            sql_op = op_map.get(op)
            if sql_op is None:
                return None

            # Build the COUNT query with HAVING
            return SQL(
                "(SELECT m.%s FROM %s m WHERE %s GROUP BY m.%s HAVING COUNT(*) %s %s)",
                SQL.identifier(p.parent_field),
                SQL.identifier(through_table),
                where_clause,
                SQL.identifier(p.parent_field),
                SQL(sql_op),
                rhs,
            )
        except Exception as e:
            self._logger.debug("[CEL SQL] Failed to build COUNT SQL: %s", e)
            return None

    def _aggregate_to_sql(self, p: FieldAggregateThrough) -> SQL | None:
        """Convert FieldAggregateThrough to SQL subquery.

        Uses CTE pattern for clarity and correctness:
        WITH allowed_children AS (
            SELECT id, {agg_field} FROM {child_table}
            WHERE id IN {child_subquery}  -- with record rules
        )
        SELECT m.{parent_col} FROM {through_table} m
        JOIN allowed_children c ON c.id = m.{link_col}
        WHERE {default_domain conditions}
        GROUP BY m.{parent_col}
        HAVING {agg_func}(c.{agg_field}) {op} {rhs}
        """
        try:
            builder = SQLBuilder(self.env)
            through_table = self.env[p.through_model]._table
            child_table = self.env[p.child_model]._table

            # Build child subquery with record rules
            child_domain: list[Any] = []
            if p.child_plan is not None:
                child_domain, requires_exec = self._plan_to_domain(p.child_model, p.child_plan)
                if requires_exec:
                    # Child plan requires execution - can't do SQL fast path
                    return None

            # Convert child domain to SQL (with record rules applied)
            child_sql = builder.select_ids_from_domain(p.child_model, child_domain)
            if child_sql is None:
                return None

            # Build WHERE clause for through table from default_domain
            where_sql: SQL | None = None
            if p.default_domain:
                terms, success = builder.build_default_domain_sql("m", p.default_domain)
                if not success:
                    # Unsupported operators in default_domain
                    return None
                if terms:
                    where_sql = builder.where_and(terms)

            # Build the aggregate query using SQLBuilder
            return builder.select_grouped_aggregate(
                through_table=through_table,
                through_alias="m",
                child_subquery=child_sql,
                parent_col=p.parent_field,
                link_col=p.link_field,
                agg_func=p.agg_type.upper(),
                agg_field=p.agg_field,
                child_table=child_table,
                having_op=p.op,
                having_value=p.rhs,
                where=where_sql,
            )
        except Exception as e:
            self._logger.debug("[CEL SQL] Failed to build aggregate SQL: %s", e)
            return None

    def _plan_to_sql(self, model: str, plan: Any) -> SQL | None:
        """Convert a QueryPlan to SQL subquery if possible.

        Returns SQL object or None if SQL conversion is not possible.
        """
        if isinstance(plan, LeafDomain):
            if plan.model != model:
                return None
            return self._domain_to_id_sql(plan.model, plan.domain)

        if isinstance(plan, ExistsThrough):
            return self._exists_to_sql(plan)

        if isinstance(plan, CountThrough):
            return self._count_to_sql(plan)

        if isinstance(plan, FieldAggregateThrough):
            return self._aggregate_to_sql(plan)

        if isinstance(plan, AND):
            # AND of SQL subqueries = INTERSECT
            sqls: list[SQL] = []
            for node in flatten_and(plan.nodes):
                sql = self._plan_to_sql(model, node)
                if sql is None:
                    return None
                sqls.append(sql)
            if not sqls:
                return None
            if len(sqls) == 1:
                return sqls[0]
            # Use INTERSECT for AND
            result = sqls[0]
            for sql in sqls[1:]:
                result = SQL("(%s INTERSECT %s)", result, sql)
            return result

        if isinstance(plan, OR):
            # OR of SQL subqueries = UNION
            sqls = []
            for node in plan.nodes:
                sql = self._plan_to_sql(model, node)
                if sql is None:
                    return None
                sqls.append(sql)
            if not sqls:
                return None
            if len(sqls) == 1:
                return sqls[0]
            result = sqls[0]
            for sql in sqls[1:]:
                result = SQL("(%s UNION %s)", result, sql)
            return result

        # NOT, MetricCompare, etc. - fall back to Python execution
        return None

    def _check_metrics_available(self, metric_name=None):
        """Check if metrics/cache infrastructure is available. Raise CELMetricsUnavailableError if not."""
        # Check for new cache table first, then legacy
        if "spp.data.value" not in self.env and "spp.indicator" not in self.env:
            raise CELMetricsUnavailableError(metric_name)

    def _get_cache_table_info(self) -> dict[str, str]:
        """Determine which cache table to use for metric lookups.

        Returns dict with:
            - table: SQL table name
            - model: Odoo model name
            - metric_field: Field name for metric/variable name

        Prefers spp.data.value (new) over spp.indicator.value (legacy).
        """
        # Prefer new unified cache table
        if "spp.data.value" in self.env:
            return {
                "table": "spp_data_value",
                "model": "spp.data.value",
                "metric_field": "variable_name",
            }
        # Fallback to legacy indicator cache
        elif "spp.indicator.value" in self.env:
            return {
                "table": "spp_indicator_value",
                "model": "spp.indicator.value",
                "metric_field": "metric",
            }
        else:
            # Should not reach here if _check_metrics_available is called first
            return {
                "table": "spp_data_value",
                "model": "spp.data.value",
                "metric_field": "variable_name",
            }

    @api.model
    def compile_and_preview(
        self,
        model: str,
        expr: str,
        limit: int = 50,
        offset: int = 0,
        fields: list[str] | None = None,
        materialize_sql: bool = False,
    ) -> dict[str, Any]:
        import uuid

        cfg = self.env.context.get("cel_cfg") or {}
        translator = self.env["spp.cel.translator"]
        plan, explain = translator.translate(model, expr, cfg)
        # Compose base domain
        base_domain = cfg.get("base_domain", [])
        metrics_info: list[dict[str, Any]] = []
        request_id = str(uuid.uuid4())
        domain, requires_exec = self._plan_to_domain(model, plan)
        final_domain = self._and_domains(base_domain, domain)
        count, ids = 0, []
        sql_path_used = False
        if requires_exec:
            # Try SQL fast path first (scales to millions of records)
            sql_subquery = self._plan_to_sql(model, plan)
            if sql_subquery is not None and not materialize_sql:
                # SQL path succeeded - use subquery instead of materializing IDs
                final_domain = self._and_domains(base_domain, [("id", "in", sql_subquery)])
                sql_path_used = True
                self._logger.info("[CEL SQL] Using SQL fast path for expr=%s", expr)
            else:
                # Fall back to Python execution (may be slow for large datasets)
                self._logger.info(
                    "[CEL SQL] SQL fast path unavailable, falling back to Python for expr=%s",
                    expr,
                )
                exec_self = self.with_context(cel_mode="preview", cel_request_id=request_id)
                ids = exec_self._execute_plan(model, plan, metrics_info, as_root=True)
                # If a fast-path domain override was provided in metrics_info, use it instead of materializing ids
                override_domain: list[Any] | None = None
                for mi in metrics_info:
                    od = mi.get("override_domain") if isinstance(mi, dict) else None
                    if od:
                        override_domain = od
                        break
                if override_domain:
                    final_domain = self._and_domains(base_domain, override_domain)
                else:
                    final_domain = self._and_domains(base_domain, [("id", "in", ids)])
        # Determine execution path for logging and response
        path = "sql" if sql_path_used else ("python" if requires_exec else "domain")
        warnings: list[str] = []

        # Add warning for Python path (scalability concern)
        if path == "python":
            warnings.append("Using Python path. May be slow for large datasets.")

        # Log for visibility during tests (truncate large ID lists)
        try:
            self._logger.info(
                "[CEL EXEC] model=%s expr=%s explain=%s domain=%s path=%s",
                model,
                expr,
                explain,
                self._format_domain_for_log(final_domain),
                path,
            )
        except Exception:
            pass

        # SCALABILITY FIX: Use search_count() + search(limit=N) instead of loading all IDs
        # This bounds memory usage regardless of result set size
        count = self.env[model].search_count(final_domain)
        # limit=None means count-only mode (no IDs), limit=0 uses default, limit>0 is explicit
        preview_data: list[dict[str, Any]] = []
        if limit is None:
            preview_ids = []  # Count-only mode
        elif limit == 0:
            # Use the default from the method signature (50)
            preview_recordset = self.env[model].search(final_domain, limit=50, offset=offset)
            preview_ids = preview_recordset.ids
        else:
            preview_recordset = self.env[model].search(final_domain, limit=limit, offset=offset)
            preview_ids = preview_recordset.ids

        # Read full record data if fields requested (for JSON-safe preview)
        if preview_ids and fields:
            # Replace phone_number_ids with phone for reading, then enrich
            read_fields = [f for f in fields if f != "phone_number_ids"]
            preview_data = preview_recordset.read(read_fields)
            if "phone_number_ids" in fields:
                for rec_data in preview_data:
                    rec_id = rec_data["id"]
                    partner = preview_recordset.filtered(lambda r, rid=rec_id: r.id == rid)
                    phones = partner.phone_number_ids.filtered(lambda p: not p.disabled).mapped("phone_no")
                    rec_data["phone_numbers"] = phones
        # Enrich explanation with metrics info if any
        metrics_section = ""
        if metrics_info:
            parts = []
            for mi in metrics_info:
                # Add lightweight warnings for metrics
                mi_warnings = []
                cov = float(mi.get("coverage") or 0.0)
                if cov < 0.8:
                    mi_warnings.append("LOW_COVERAGE")
                if int(mi.get("misses") or 0) > 0:
                    mi_warnings.append("CACHE_MISSES")
                if mi.get("provider_missing"):
                    mi_warnings.append("PROVIDER_MISSING")
                if mi.get("cache_any_provider_used"):
                    mi_warnings.append("CACHE_ANY_PROVIDER")
                mi["warnings"] = mi_warnings
                parts.append(
                    f"metric={mi.get('metric')} period={mi.get('period_key')} "
                    f"requested={mi.get('requested')} cache_hits={mi.get('cache_hits')} "
                    f"fresh={mi.get('fresh_fetches')} coverage={round(cov * 100, 1)}%"
                    + (f" warnings={','.join(mi_warnings)}" if mi_warnings else "")
                )
            metrics_section = " | Metrics: " + "; ".join(parts)
            explain = f"{explain}{metrics_section}"
        return {
            "domain": final_domain,
            "domain_text": str(final_domain),
            "explain": explain,
            "explain_struct": {
                "metrics": metrics_info,
                "request_id": request_id,
            },
            "count": count,
            "preview_records": preview_data,  # Full record data (JSON-safe)
            "preview_ids": preview_ids,  # New field per spec
            "ids": preview_ids,  # Backward compatibility (deprecated)
            "path": path,  # Execution path: sql|python|domain
            "warnings": warnings,  # Scalability warnings
        }

    @api.model
    def compile_for_batch(self, model: str, expr: str, batch_size: int = 5000) -> Iterator[list[int]]:
        """Compile expression and yield batches of matching IDs.

        For processing millions of records without memory exhaustion.
        Uses cursor-based pagination (keyset pagination).

        Yields:
            Lists of IDs, each up to batch_size length

        Example:
            for batch_ids in executor.compile_for_batch("res.partner", expr):
                process_batch(batch_ids)  # Process 5000 at a time
        """
        cfg = self.env.context.get("cel_cfg") or {}
        translator = self.env["spp.cel.translator"]
        plan, explain = translator.translate(model, expr, cfg)
        base_domain = cfg.get("base_domain", [])

        # Try SQL fast path first
        sql_subquery = self._plan_to_sql(model, plan)

        if sql_subquery is not None:
            # SQL path - use cursor-based pagination
            domain = self._and_domains(base_domain, [("id", "in", sql_subquery)])

            # Use keyset pagination (cursor-based)
            last_id = 0
            while True:
                batch_domain = self._and_domains(domain, [("id", ">", last_id)])
                batch = self.env[model].search(batch_domain, limit=batch_size, order="id")

                if not batch:
                    break

                yield batch.ids
                last_id = batch.ids[-1]

                if len(batch) < batch_size:
                    break
        else:
            # Python fallback - execute once and paginate results in memory
            domain, requires_exec = self._plan_to_domain(model, plan)

            if requires_exec:
                # Execute plan to get all IDs
                ids = self._execute_plan(model, plan)
                # Apply base domain to filter
                final_domain = self._and_domains(base_domain, [("id", "in", ids)])
                all_ids = self.env[model].search(final_domain).ids
            else:
                # Simple domain path
                final_domain = self._and_domains(base_domain, domain)
                all_ids = self.env[model].search(final_domain).ids

            # Paginate results in memory
            for i in range(0, len(all_ids), batch_size):
                yield all_ids[i : i + batch_size]

    @api.model
    def compile_count_only(self, model: str, expr: str) -> dict[str, Any]:
        """Get count of matching records without loading any IDs.

        Most efficient method when you only need the count.

        Returns:
            count: Number of matching records
            path: "sql" | "python" | "domain"
            warnings: List of warnings
        """
        cfg = self.env.context.get("cel_cfg") or {}
        translator = self.env["spp.cel.translator"]
        plan, explain = translator.translate(model, expr, cfg)
        base_domain = cfg.get("base_domain", [])

        # Try SQL fast path first
        sql_subquery = self._plan_to_sql(model, plan)

        if sql_subquery is not None:
            # SQL path - efficient count
            domain = self._and_domains(base_domain, [("id", "in", sql_subquery)])
            count = self.env[model].search_count(domain)
            return {"count": count, "path": "sql", "warnings": []}

        # Check if simple domain (no execution needed)
        domain, requires_exec = self._plan_to_domain(model, plan)

        if not requires_exec:
            # Simple domain path - efficient count without loading IDs
            final_domain = self._and_domains(base_domain, domain)
            count = self.env[model].search_count(final_domain)
            return {"count": count, "path": "domain", "warnings": []}

        # Python fallback - must execute plan to get IDs
        ids = self._execute_plan(model, plan)
        # Apply base domain to filter
        final_domain = self._and_domains(base_domain, [("id", "in", ids)])
        # Use search_count for efficiency (respects record rules and base_domain)
        count = self.env[model].search_count(final_domain)

        return {
            "count": count,
            "path": "python",
            "warnings": ["Count required Python execution"],
        }

    # Plan → Domain (best effort)
    def _plan_to_domain(self, model: str, plan: Any) -> tuple[list[Any], bool]:
        if isinstance(plan, LeafDomain):
            if plan.model != model:
                # different model; cannot express as dotted safely
                return [], True
            return plan.domain, False
        if isinstance(plan, AND):
            domains: list[Any] = []
            needs_exec = False
            for n in flatten_and(plan.nodes):
                d, e = self._plan_to_domain(model, n)
                needs_exec = needs_exec or e
                if d:
                    domains = self._and_domains(domains, d)
            return domains, needs_exec
        if isinstance(plan, OR):
            # if any side requires exec, mark as exec
            left, le = self._plan_to_domain(model, plan.nodes[0])
            right, re = self._plan_to_domain(model, plan.nodes[1])
            if le or re:
                return [], True
            return ["|", *left, *right], False
        if isinstance(plan, NOT):
            d, e = self._plan_to_domain(model, plan.node)
            if e:
                return [], True
            return ["!", *d], False
        if isinstance(plan, ExistsThrough | CountThrough | FieldAggregateThrough):
            return [], True
        return [], True

    def _and_domains(self, a: list[Any], b: list[Any]) -> list[Any]:
        da = self._ensure_domain_list(a)
        db = self._ensure_domain_list(b)
        if not da:
            return db
        if not db:
            return da

        # Check if any domain contains SQL objects - if so, don't use Domain.AND
        # as it serializes SQL objects incorrectly (converts them to string repr)
        def contains_sql(domain):
            for term in domain:
                if isinstance(term, tuple | list) and len(term) == 3:
                    if isinstance(term[2], SQL):
                        return True
            return False

        if contains_sql(da) or contains_sql(db):
            # Manual AND: just concatenate (implicit AND in Odoo domains)
            # This preserves SQL objects without serialization
            return da + db

        return list(Domain.AND([da, db]))

    def _ensure_domain_list(self, domain: list[Any]) -> list[Any]:
        if not domain:
            return []
        # Handle Odoo 19 Domain objects - convert to list first
        if isinstance(domain, Domain):
            domain = list(domain)
        if isinstance(domain, list):
            normalized: list[Any] = []
            for term in list(domain):
                if (
                    isinstance(term, list)
                    and len(term) == 3
                    and term
                    and isinstance(term[0], str)
                    and term[0] not in {"&", "|", "!", "not"}
                ):
                    normalized.append(tuple(term))
                else:
                    normalized.append(term)
            return normalized
        return [domain]

    # Execute
    def _execute_plan(
        self,
        model: str,
        plan: Any,
        metrics_info: list[dict[str, Any]] | None = None,
        as_root: bool = False,
    ) -> list[int]:  # noqa: C901
        if isinstance(plan, LeafDomain):
            return self.env[plan.model].search(plan.domain).ids
        if isinstance(plan, AND):
            # intersection
            id_sets = [set(self._execute_plan(model, p, metrics_info)) for p in flatten_and(plan.nodes)]
            if not id_sets:
                return []
            s = id_sets[0]
            for other in id_sets[1:]:
                s = s.intersection(other)
            return list(s)
        if isinstance(plan, OR):
            ids = set()
            for p in plan.nodes:
                ids.update(self._execute_plan(model, p, metrics_info))
            return list(ids)
        if isinstance(plan, NOT):
            # CRITICAL FIX: Do not load all IDs into memory (DoS risk on large datasets)
            domain, requires_exec = self._plan_to_domain(model, plan.node)
            if requires_exec:
                raise NotImplementedError(
                    "Negating complex expressions (like 'exists' or 'count') is not supported "
                    "due to performance constraints. Please restructure your expression to avoid "
                    "negating subqueries. For example, instead of 'not members.exists(m, P)', "
                    "try to express the positive condition."
                )
            # Use native Odoo domain negation instead of memory-based set operations
            negated_domain = ["!"] + domain
            return self.env[model].search(negated_domain).ids
        if isinstance(plan, ExistsThrough):
            return self._exec_exists(plan)
        if isinstance(plan, CountThrough):
            return self._exec_count(plan)
        if isinstance(plan, MetricCompare):
            return self._exec_metric(model, plan, metrics_info, as_root=as_root)
        if isinstance(plan, CoverageRequire):
            # Only support gating on MetricCompare results for now
            if not isinstance(plan.node, MetricCompare):
                raise NotImplementedError("require_coverage currently supports only metric() comparisons")
            # Evaluate metric comparison and get stats for coverage check
            tmp_stats: list[dict[str, Any]] = []
            ids = self._exec_metric(model, plan.node, tmp_stats)
            cov = 0.0
            if tmp_stats:
                cov = float(tmp_stats[-1].get("coverage") or 0.0)
                if metrics_info is not None:
                    metrics_info.extend(tmp_stats)
            if cov < float(plan.min_coverage or 0.0):
                return []
            return ids
        if isinstance(plan, AggMetricCompare):
            return self._exec_agg_metric(model, plan, metrics_info)
        if isinstance(plan, FieldAggregateThrough):
            return self._exec_field_aggregate(plan)
        return []

    def _exec_exists(self, p: ExistsThrough) -> list[int]:
        # Build membership domain, splitting child predicates to through-model vs child-model
        dom: list[Any] = []
        if p.default_domain:
            dom = self._and_domains(dom, p.default_domain)
        mem_dom, child_subplan = self._split_child_membership(p.through_model, p.child_plan)
        if mem_dom:
            dom = self._and_domains(dom, mem_dom)
        if child_subplan is not None:
            child_domain, requires_exec_child = self._plan_to_domain(p.child_model, child_subplan)
            try:
                self._logger.info(
                    "[CEL EXISTS] child_subplan model=%s plan=%s requires_exec=%s",
                    getattr(child_subplan, "model", None),
                    getattr(child_subplan, "domain", None),
                    requires_exec_child,
                )
            except Exception:
                pass
            if requires_exec_child:
                child_ids = self._execute_plan(p.child_model, child_subplan)
            else:
                child_domain = self._ensure_domain_list(child_domain)
                try:
                    self._logger.info(
                        "[CEL EXISTS] applying child domain=%s on model=%s",
                        self._format_domain_for_log(child_domain),
                        p.child_model,
                    )
                except Exception:
                    pass
                child_ids = self.env[p.child_model].search(child_domain).ids
            child_ids = [int(i) for i in child_ids if i]
            if not child_ids:
                try:
                    self._logger.info(
                        "[CEL DEBUG EXISTS] child filter empty through=%s parent=%s child_model=%s "
                        "domain=%s requires_exec=%s",
                        p.through_model,
                        p.parent_field,
                        p.child_model,
                        self._format_domain_for_log(child_domain),
                        requires_exec_child,
                    )
                except Exception:
                    pass
                return []
            dom = self._and_domains(dom, [(p.link_field, "in", child_ids)])
        rows = self.env[p.through_model].search(dom)
        # Debug: log domain size for troubleshooting (truncate large ID lists)
        try:
            self._logger.info(
                "[CEL EXEC EXISTS] through=%s parent=%s link=%s mem_dom=%s child_subplan=%s rows=%s",
                p.through_model,
                p.parent_field,
                p.link_field,
                self._format_domain_for_log(dom),
                child_subplan.__class__.__name__ if child_subplan else None,
                len(rows),
            )
        except Exception:
            pass
        return list(set(rows.mapped(p.parent_field).ids))

    def _exec_count(self, p: CountThrough) -> list[int]:  # noqa: C901
        cfg = self.env.context.get("cel_cfg") or {}
        dom: list[Any] = []
        if p.default_domain:
            dom = self._and_domains(dom, p.default_domain)
        mem_dom, child_subplan = self._split_child_membership(p.through_model, p.child_plan)
        if mem_dom:
            dom = self._and_domains(dom, mem_dom)

        parent_model_name = None
        parent_field_desc = self.env[p.through_model]._fields.get(p.parent_field)
        if parent_field_desc is not None:
            parent_model_name = getattr(parent_field_desc, "comodel_name", None)

        base_domain: list[Any] = []
        if parent_model_name and cfg.get("root_model") == parent_model_name:
            if isinstance(cfg.get("base_domain"), list):
                base_domain = cfg.get("base_domain")

        candidate_parents: set[int] = set()
        if parent_model_name and base_domain:
            candidate_parents = set(int(pid) for pid in self.env[parent_model_name].search(base_domain).ids)

        if child_subplan is not None:
            child_domain, requires_exec_child = self._plan_to_domain(p.child_model, child_subplan)
            if requires_exec_child:
                child_ids = self._execute_plan(p.child_model, child_subplan)
            else:
                child_domain = self._ensure_domain_list(child_domain)
                try:
                    self._logger.info(
                        "[CEL COUNT] applying child domain=%s on model=%s",
                        self._format_domain_for_log(child_domain),
                        p.child_model,
                    )
                except Exception:
                    pass
                child_ids = self.env[p.child_model].search(child_domain).ids
            child_ids = [int(i) for i in child_ids if i]
            try:
                self._logger.info(
                    "[CEL COUNT] child filter results child_model=%s count=%s sample_ids=%s",
                    p.child_model,
                    len(child_ids),
                    child_ids[:10],
                )
            except Exception:
                pass
            if not child_ids:
                # No matching children; counts are zero for all candidate parents
                if not candidate_parents and parent_model_name:
                    search_domain = base_domain if base_domain else []
                    candidate_parents = set(int(pid) for pid in self.env[parent_model_name].search(search_domain).ids)
                return [pid for pid in candidate_parents if self._compare(0, p.op, p.rhs)]
            dom = self._and_domains(dom, [(p.link_field, "in", child_ids)])

        rows = self.env[p.through_model].read_group(dom, [p.parent_field], [p.parent_field])
        counts: dict[int, int] = {}
        for r in rows:
            count = int(r.get(f"{p.parent_field}_count") or 0)
            pid = r.get(p.parent_field)
            if isinstance(pid, tuple):
                pid = pid[0]
            if pid:
                counts[int(pid)] = count

        parent_ids: set[int] = set(counts.keys())
        if candidate_parents:
            parent_ids |= candidate_parents
        if not parent_ids and parent_model_name:
            search_domain = base_domain if base_domain else []
            parent_ids = set(int(pid) for pid in self.env[parent_model_name].search(search_domain).ids)

        res: list[int] = []
        for pid in parent_ids:
            if self._compare(counts.get(pid, 0), p.op, p.rhs):
                res.append(pid)
        return res

    def _compare(self, a: int, op: str, b: int) -> bool:
        return {
            "=": a == b,
            "==": a == b,
            ">": a > b,
            ">=": a >= b,
            "<": a < b,
            "<=": a <= b,
            "!=": a != b,
        }[op]

    def _exec_field_aggregate(self, p: FieldAggregateThrough) -> list[int]:  # noqa: C901
        """Execute a field aggregation query (sum, avg, min, max).

        This method aggregates a numeric field over members matching a filter
        and returns parent IDs where the aggregate value matches the comparison.

        Strategy:
        - Build membership domain with default_domain and child filter
        - Get matching child IDs
        - Read field values from children
        - Group by parent and compute aggregate
        - Compare against rhs and return matching parent IDs
        """
        cfg = self.env.context.get("cel_cfg") or {}
        dom: list[Any] = []
        if p.default_domain:
            dom = self._and_domains(dom, p.default_domain)
        mem_dom, child_subplan = self._split_child_membership(p.through_model, p.child_plan)
        if mem_dom:
            dom = self._and_domains(dom, mem_dom)

        parent_model_name = None
        parent_field_desc = self.env[p.through_model]._fields.get(p.parent_field)
        if parent_field_desc is not None:
            parent_model_name = getattr(parent_field_desc, "comodel_name", None)

        base_domain: list[Any] = []
        if parent_model_name and cfg.get("root_model") == parent_model_name:
            if isinstance(cfg.get("base_domain"), list):
                base_domain = cfg.get("base_domain")

        candidate_parents: set[int] = set()
        if parent_model_name and base_domain:
            candidate_parents = set(int(pid) for pid in self.env[parent_model_name].search(base_domain).ids)

        # Get matching child IDs based on filter
        child_ids: list[int] = []
        if child_subplan is not None:
            child_domain, requires_exec_child = self._plan_to_domain(p.child_model, child_subplan)
            if requires_exec_child:
                child_ids = self._execute_plan(p.child_model, child_subplan)
            else:
                child_domain = self._ensure_domain_list(child_domain)
                child_ids = self.env[p.child_model].search(child_domain).ids
            child_ids = [int(i) for i in child_ids if i]
            if not child_ids:
                # No matching children; aggregate values are 0/null for all parents
                if not candidate_parents and parent_model_name:
                    search_domain = base_domain if base_domain else []
                    candidate_parents = set(int(pid) for pid in self.env[parent_model_name].search(search_domain).ids)
                # For sum, no children means 0; compare 0 against rhs
                return [pid for pid in candidate_parents if self._cmp_value(0, p.op, p.rhs)]
            dom = self._and_domains(dom, [(p.link_field, "in", child_ids)])

        # Get membership records to build parent -> children mapping
        memberships = self.env[p.through_model].search(dom)
        if not memberships:
            return []

        # Build parent -> [child_ids] mapping
        parent_map: dict[int, list[int]] = {}
        for r in memberships:
            try:
                pid = int(
                    getattr(r, p.parent_field).id
                    if hasattr(getattr(r, p.parent_field), "id")
                    else getattr(r, p.parent_field)
                )
                cid = int(
                    getattr(r, p.link_field).id if hasattr(getattr(r, p.link_field), "id") else getattr(r, p.link_field)
                )
            except Exception:
                continue
            parent_map.setdefault(pid, []).append(cid)

        # Get all unique child IDs
        all_child_ids = sorted({cid for lst in parent_map.values() for cid in lst})
        if not all_child_ids:
            return []

        # Read field values for all children
        child_records = self.env[p.child_model].browse(all_child_ids)
        child_values: dict[int, float] = {}
        for rec in child_records:
            try:
                val = getattr(rec, p.agg_field, None)
                if val is not None:
                    child_values[rec.id] = float(val)
            except (ValueError, TypeError):
                pass  # Skip non-numeric values

        # Compute aggregate per parent
        winners: list[int] = []
        for pid, cids in parent_map.items():
            vals = [child_values[cid] for cid in cids if cid in child_values]
            if not vals:
                # No values means aggregate is 0 for sum, undefined for others
                if p.agg_type == "sum":
                    agg_val = 0.0
                else:
                    continue  # Skip this parent for avg/min/max with no values
            else:
                if p.agg_type == "sum":
                    agg_val = sum(vals)
                elif p.agg_type == "avg":
                    agg_val = sum(vals) / len(vals)
                elif p.agg_type == "min":
                    agg_val = min(vals)
                elif p.agg_type == "max":
                    agg_val = max(vals)
                else:
                    continue

            if self._cmp_value(agg_val, p.op, p.rhs):
                winners.append(pid)

        return winners

    def _split_child_membership(self, through_model: str, child_plan: Any) -> tuple[list[Any], Any]:
        """Split child_plan into membership-domain leaves (on through_model) and the residual
        child subplan to be evaluated on the child model. Only flattens simple AND plans.

        Returns (membership_domain, residual_plan_or_None).
        """
        # Direct leaf on through model
        if isinstance(child_plan, LeafDomain) and getattr(child_plan, "model", None) == through_model:
            return self._ensure_domain_list(child_plan.domain), None
        # For an AND, collect through-model leaves and keep the rest as residual
        if isinstance(child_plan, AND):
            mem_dom: list[Any] = []
            residual_nodes: list[Any] = []
            for n in flatten_and(child_plan.nodes):
                if isinstance(n, LeafDomain) and getattr(n, "model", None) == through_model:
                    sub_domain = self._ensure_domain_list(n.domain)
                    if sub_domain:
                        mem_dom = self._and_domains(mem_dom, sub_domain)
                else:
                    residual_nodes.append(n)
            if not residual_nodes:
                return mem_dom, None
            if len(residual_nodes) == 1:
                return mem_dom, residual_nodes[0]
            return mem_dom, AND(residual_nodes)
        # Fallback: cannot split
        return [], child_plan

    def _exec_metric(
        self,
        model: str,
        p: MetricCompare,
        metrics_info: list[dict[str, Any]] | None = None,
        as_root: bool = False,
    ) -> list[int]:
        """Evaluate metric comparison and return matching subject IDs for current model.

        Uses openspp.metrics service with mode=fallback.

        ``as_root`` is True only when this comparison IS the whole plan: in
        that case the fresh-cache SQL shortcut may return no ids and stash an
        ``override_domain`` for the caller. Composed inside and/or/not, the
        ids must be materialized so set composition stays correct.
        """
        # Check metrics availability
        self._check_metrics_available(p.metric)

        # Flush any pending invalidations to ensure cache consistency
        if "spp.indicator.invalidation.buffer" in self.env:
            buffer = self.env["spp.indicator.invalidation.buffer"]
            # Use sync for small batches to ensure immediate consistency
            if buffer.pending_count() < 100:
                buffer.flush(force_async=False)
            # For large batches, flush async and proceed with possibly stale cache
            # (CEL's existing stale handling will deal with it)
            elif buffer.pending_count() > 0:
                buffer.flush(force_async=True)

        cfg = self.env.context.get("cel_cfg") or {}
        base_dom = cfg.get("base_domain", []) if isinstance(cfg.get("base_domain"), list) else []
        period_key = str(p.period_key or "current")
        subject_model = model
        # Resolve flags
        ICP = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        enable_sql = bool(int(ICP.get_param("cel.enable_sql_metrics", "1")))
        preview_cache_only = bool(int(ICP.get_param("cel.preview_cache_only", "0")))
        async_threshold = int(ICP.get_param("cel.async_threshold", "50000") or 50000)
        allow_any_provider = self._allow_any_provider_fallback()
        # Provider resolution
        provider, return_type = self._metric_registry_info(p.metric)
        # Parameterized metrics: hash the params so the cache lookup is keyed by
        # them (must match how upsert_values hashed them on write). No params -> "".
        params_hash = self.env["spp.data.value"]._hash_params(p.params) if getattr(p, "params", None) else ""
        # Preflight completeness/freshness
        status = self._metric_cache_status_sql(
            subject_model,
            base_dom,
            p.metric,
            period_key,
            provider,
            params_hash,
            allow_any_provider,
        )
        path = "python"
        # SQL fast path
        rhs = p.rhs
        if enable_sql and status.get("status") == "fresh" and self._metric_cmp_supported(p.op, rhs, return_type):
            sql = self._metric_inselect_sql(
                subject_model,
                p.metric,
                period_key,
                provider,
                params_hash,
                p.op,
                rhs,
                return_type,
                allow_any_provider,
            )
            domain = [("id", "in", sql)]
            path = "sql"
            if metrics_info is not None:
                mi = dict(status)
                mi.update(
                    {
                        "metric": p.metric,
                        "period_key": period_key,
                        "path": path,
                    }
                )
                if as_root:
                    mi["override_domain"] = domain
                metrics_info.append(mi)
            if as_root:
                # The comparison is the whole plan: return [] and let
                # compile_and_preview use override_domain to avoid
                # materializing ids into a huge 'in' list.
                return []
            # Composed inside and/or/not: materialize the matching ids so
            # set composition (intersection/union) stays correct.
            return self.env[subject_model].search(self._and_domains(base_dom, domain)).ids
        # Preview mode behavior when not fresh
        cel_mode = self.env.context.get("cel_mode")
        preview_cache_only_mode = cel_mode == "preview" and preview_cache_only
        # Evaluate/batch or preview fallback (small cohorts): compute via service
        # Compute candidate size cheaply via search_count
        base_count = self.env[subject_model].search_count(base_dom)

        # Check for evaluation service (legacy spp.indicator for now)
        # TODO: Fully migrate to spp.data.cache.manager (Phase 4 of ADR-017 complete)
        if "spp.indicator" not in self.env:
            # No evaluation service available - can only use SQL fast path
            # If we reach here, cache is not fresh and we can't compute
            self._logger.warning(
                "[CEL Metrics] No evaluation service available for metric=%s. "
                "SQL fast path requires fresh cache. Consider installing spp_indicators module.",
                p.metric,
            )
            return []

        svc = self.env["spp.indicator"]
        default_mode = "refresh" if (base_count < async_threshold) else "fallback"
        if default_mode == "fallback" and status.get("status") != "fresh" and not preview_cache_only_mode:
            # large + not fresh → enqueue refresh and report queued
            svc.enqueue_refresh_from_domain(p.metric, subject_model, list(base_dom), period_key)
            if metrics_info is not None:
                mi = dict(status)
                mi.update({"metric": p.metric, "period_key": period_key, "path": "queued"})
                metrics_info.append(mi)
            return []
        # Small cohort (or already fresh) → refresh synchronously then filter in Python
        aggregated_values: dict[int, Any] = {}
        stats_total: dict[str, Any] = {
            "requested": 0,
            "cache_hits": 0,
            "misses": 0,
            "fresh_fetches": 0,
            "coverage": 0.0,
            "metric": p.metric,
            "period_key": period_key,
            "provider": provider,
            "params_hash": params_hash,
            "company_id": self.env.company.id,
            "provider_missing": False,
            "cache_any_provider_used": False,
        }
        if preview_cache_only_mode:
            eval_mode = "cache_only"
        else:
            eval_mode = "refresh" if status.get("status") != "fresh" else "fallback"
        total_requested = 0
        for batch_ids in self._iter_domain_ids(subject_model, base_dom):
            if not batch_ids:
                continue
            total_requested += len(batch_ids)
            batch_values, batch_stats = svc.evaluate(
                p.metric, subject_model, batch_ids, period_key, mode=eval_mode, params=getattr(p, "params", None)
            )
            aggregated_values.update(batch_values)
            if batch_stats:
                stats_total["cache_hits"] += int(batch_stats.get("cache_hits") or 0)
                stats_total["misses"] += int(batch_stats.get("misses") or 0)
                stats_total["fresh_fetches"] += int(batch_stats.get("fresh_fetches") or 0)
                stats_total["cache_any_provider_used"] = stats_total["cache_any_provider_used"] or bool(
                    batch_stats.get("cache_any_provider_used")
                )
                stats_total["provider_missing"] = stats_total["provider_missing"] or bool(
                    batch_stats.get("provider_missing")
                )
                stats_total["provider"] = batch_stats.get("provider") or stats_total["provider"]
        if total_requested:
            stats_total["requested"] = total_requested
            stats_total["coverage"] = len(aggregated_values) / float(base_count or 1)
        incomplete_cache = eval_mode == "cache_only" and total_requested and len(aggregated_values) < total_requested
        if eval_mode == "cache_only":
            path_flag = "cache_only"
        else:
            path_flag = "python" if status.get("status") != "fresh" else "cache"
        stats_total.update({"path": path_flag})
        if incomplete_cache:
            if metrics_info is not None:
                metrics_info.append(stats_total)
            return []
        if metrics_info is not None:
            metrics_info.append(stats_total)
        res = []
        for sid, val in aggregated_values.items():
            v = val
            if self._cmp_value(v, p.op, p.rhs):
                res.append(int(sid))
        return res

    def _metric_registry_info(self, metric: str) -> tuple[str, str]:
        # Check metrics availability
        self._check_metrics_available(metric)
        # ADR-017: Support spp.indicator.registry (legacy) or spp.data.value (new)
        if "spp.indicator.registry" in self.env:
            info = self.env["spp.indicator.registry"].get(metric) or {}
            provider = info.get("provider") or metric
            return_type = info.get("return_type") or "json"
        else:
            # Using spp.data.value - provider is the metric name itself
            provider = metric
            return_type = "json"
        return provider, return_type

    def _metric_cmp_supported(self, op: str, rhs: Any, return_type: str) -> bool:
        if isinstance(rhs, int | float):
            return op in {"==", "!=", ">", ">=", "<", "<="}
        if isinstance(rhs, str):
            return op in {"==", "!="}
        # non-scalar comparisons not supported in SQL fast path yet
        return False

    def _metric_cache_status_sql(
        self,
        model: str,
        base_domain: list[Any],
        metric: str,
        period_key: str,
        provider: str,
        params_hash: str,
        allow_any_provider: bool,
    ) -> dict[str, Any]:
        # base count with record rules
        base_count = self.env[model].search_count(base_domain)
        # subquery for “have any row” irrespective of expiry
        have_dom = self._and_domains(
            list(base_domain),
            [
                (
                    "id",
                    "in",
                    self._feature_value_subquery(
                        metric,
                        model,
                        period_key,
                        provider,
                        params_hash,
                        "",
                        allow_any_provider,
                    ),
                )
            ],
        )
        have_count = self.env[model].search_count(have_dom)
        # subquery for stale rows
        stale_dom = self._and_domains(
            list(base_domain),
            [
                (
                    "id",
                    "in",
                    self._feature_value_subquery(
                        metric,
                        model,
                        period_key,
                        provider,
                        params_hash,
                        "AND fv.expires_at IS NOT NULL AND fv.expires_at <= NOW()",
                        allow_any_provider,
                    ),
                )
            ],
        )
        stale_count = self.env[model].search_count(stale_dom)
        status = "fresh"
        if have_count < base_count:
            status = "incomplete"
        if stale_count > 0:
            status = "stale"
        self._logger.info(
            "[CEL Metrics] cache status model=%s metric=%s period=%s provider=%s base=%s have=%s stale=%s status=%s",
            model,
            metric,
            period_key,
            provider,
            base_count,
            have_count,
            stale_count,
            status,
        )
        return {
            "status": status,
            "base": base_count,
            "have": have_count,
            "stale": stale_count,
        }

    def _metric_inselect_sql(
        self,
        model: str,
        metric: str,
        period_key: str,
        provider: str,
        params_hash: str,
        op: str,
        rhs: Any,
        return_type: str,
        allow_any_provider: bool,
    ) -> SQL:
        """Generate SQL for metric comparison (fast path).

        Automatically uses spp_data_value (new) or spp_indicator_value (legacy)
        based on what's available.
        """
        cache_info = self._get_cache_table_info()
        table_name = cache_info["table"]
        metric_field = cache_info["metric_field"]

        num_ops = {"==": "=", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<="}
        str_ops = {"==": "=", "!=": "!="}
        clause, clause_args = self._provider_clause(provider, params_hash, allow_any_provider)
        base_sql = (
            f"SELECT DISTINCT fv.subject_id FROM {table_name} fv "  # nosec B608 — table/field names from Odoo model metadata, not user input
            f"WHERE fv.company_id = %s AND fv.{metric_field} = %s AND fv.subject_model = %s "
            "AND fv.period_key = %s AND ("
            + clause
            + ") AND fv.error_code IS NULL AND (fv.expires_at IS NULL OR fv.expires_at > NOW()) "
        )
        base_args: tuple[Any, ...] = (
            self.env.company.id,
            metric,
            model,
            period_key,
            *clause_args,
        )
        if isinstance(rhs, int | float):
            # bool is a subclass of int. Postgres rejects `numeric = boolean`, so
            # coerce a boolean RHS (true/false) to 1/0 for the numeric comparison.
            # Boolean metric values are likewise stored as 1/0.
            rhs_value = int(rhs) if isinstance(rhs, bool) else rhs
            # Handle both scalar numbers and {"value": number} objects
            # COALESCE extracts from object first, then tries scalar cast
            return SQL(
                "(%s)",
                SQL(
                    base_sql
                    + "AND (CASE "
                    + "WHEN jsonb_typeof(fv.value_json) = 'object' THEN (fv.value_json ->> 'value')::numeric "
                    + "WHEN jsonb_typeof(fv.value_json) = 'number' THEN (fv.value_json)::numeric "
                    + "END) "
                    + num_ops[op]
                    + " %s",
                    *base_args,
                    rhs_value,
                ),
            )
        if isinstance(rhs, str):
            # Handle both scalar strings and {"value": string} objects
            return SQL(
                "(%s)",
                SQL(
                    base_sql + "AND (CASE "
                    "WHEN jsonb_typeof(fv.value_json) = 'object' THEN fv.value_json ->> 'value' "
                    "WHEN jsonb_typeof(fv.value_json) = 'string' THEN fv.value_json #>> '{}' "
                    "END) " + str_ops[op] + " %s",
                    *base_args,
                    rhs,
                ),
            )
        # Fallback should not be called for unsupported types
        return SQL(
            "(%s)",
            SQL(base_sql + "AND 1=0", *base_args),
        )

    def _feature_value_subquery(
        self,
        metric: str,
        model: str,
        period_key: str,
        provider: str,
        params_hash: str,
        extra_clause: str,
        allow_any_provider: bool,
    ) -> SQL:
        """Generate SQL subquery for cache lookups.

        Automatically uses spp_data_value (new) or spp_indicator_value (legacy)
        based on what's available.
        """
        cache_info = self._get_cache_table_info()
        table_name = cache_info["table"]
        metric_field = cache_info["metric_field"]

        clause, clause_args = self._provider_clause(provider, params_hash, allow_any_provider)
        tail = f" {extra_clause}" if extra_clause else ""
        sql = (
            f"SELECT DISTINCT fv.subject_id FROM {table_name} fv "  # nosec B608 — table/field names from Odoo model metadata, not user input
            f"WHERE fv.company_id = %s AND fv.{metric_field} = %s AND fv.subject_model = %s "
            "AND fv.period_key = %s AND (" + clause + ") AND fv.error_code IS NULL" + tail
        )
        args: tuple[Any, ...] = (
            self.env.company.id,
            metric,
            model,
            period_key,
            *clause_args,
        )
        return SQL("(%s)", SQL(sql, *args))

    def _provider_clause(self, provider: str, params_hash: str, allow_any_provider: bool) -> tuple[str, list[Any]]:
        provider = provider or ""
        params_hash = params_hash or ""
        combos: list[tuple[str, str]] = [
            (provider, params_hash),
        ]
        if provider:
            # Relax the provider (a routing/registry detail) but keep the requested
            # params_hash. Params are a semantic filter, not a provider detail: a
            # non-empty params_hash must never fall back to params_hash "" rows, or a
            # parameterized metric would match unparameterized/legacy cache rows. When
            # params_hash == "" this combo already covers the unparameterized rows.
            combos.append(("", params_hash))
        # Deduplicate while preserving order
        seen = set()
        uniq_combos: list[tuple[str, str]] = []
        for combo in combos:
            if combo not in seen:
                seen.add(combo)
                uniq_combos.append(combo)
        clauses: list[str] = []
        args: list[Any] = []
        for prov, phash in uniq_combos:
            clauses.append("(fv.provider = %s AND fv.params_hash = %s)")
            args.extend([prov, phash])
        if allow_any_provider:
            clauses.append("(fv.params_hash = %s)")
            args.append(params_hash)
        return " OR ".join(clauses), args

    def _allow_any_provider_fallback(self) -> bool:
        try:
            # nosemgrep: odoo-sudo-without-context
            value = self.env["ir.config_parameter"].sudo().get_param("spp_indicator.allow_any_provider_fallback", "1")
            return bool(int(value or "1"))
        except Exception:
            return True

    def _iter_domain_ids(self, model: str, domain: list[Any], batch_size: int = 2000) -> Iterable[list[int]]:
        Model = self.env[model]
        base_domain = self._ensure_domain_list(domain)
        last_id = 0
        while True:
            if last_id:
                batch_domain = self._and_domains(base_domain, [("id", ">", last_id)])
            else:
                batch_domain = list(base_domain)
            records = Model.search(batch_domain, limit=batch_size, order="id")
            if not records:
                break
            ids = [int(i) for i in records.ids]
            yield ids
            last_id = ids[-1]
            if len(ids) < batch_size:
                break

    def _cmp_value(self, a: Any, op: str, b: Any) -> bool:
        # Attempt numeric comparison when possible
        def to_num(x):
            try:
                return float(x)
            except Exception:
                return x

        ax = to_num(a)
        bx = to_num(b)
        ops = {
            "==": lambda x, y: x == y,
            "!=": lambda x, y: x != y,
            ">": lambda x, y: x > y,
            ">=": lambda x, y: x >= y,
            "<": lambda x, y: x < y,
            "<=": lambda x, y: x <= y,
        }
        try:
            return ops[op](ax, bx)
        except Exception:
            return False

    def _exec_agg_metric(  # noqa: C901
        self, model: str, p: AggMetricCompare, metrics_info: list[dict[str, Any]] | None
    ) -> list[int]:
        """Evaluate an aggregate of a metric over a through relation.

        Strategy:
        - Collect membership rows (default_domain applied)
        - Build parent -> [child_ids] mapping
        - Evaluate metric for union(child_ids)
        - Compute aggregator per parent and compare vs rhs
        """
        # Check metrics availability
        self._check_metrics_available(p.metric)

        # Flush any pending invalidations to ensure cache consistency
        if "spp.indicator.invalidation.buffer" in self.env:
            buffer = self.env["spp.indicator.invalidation.buffer"]
            # Use sync for small batches to ensure immediate consistency
            if buffer.pending_count() < 100:
                buffer.flush(force_async=False)
            # For large batches, flush async and proceed with possibly stale cache
            # (CEL's existing stale handling will deal with it)
            elif buffer.pending_count() > 0:
                buffer.flush(force_async=True)

        dom: list[Any] = []
        if p.default_domain:
            dom.extend(p.default_domain)
        rows = self.env[p.through_model].search(dom)
        if not rows:
            return []
        parent_map: dict[int, list[int]] = {}
        for r in rows:
            try:
                pid = int(
                    getattr(r, p.parent_field).id
                    if hasattr(getattr(r, p.parent_field), "id")
                    else getattr(r, p.parent_field)
                )
                cid = int(
                    getattr(r, p.link_field).id if hasattr(getattr(r, p.link_field), "id") else getattr(r, p.link_field)
                )
            except Exception:
                continue
            parent_map.setdefault(pid, []).append(cid)
        # Evaluate the metric for all distinct child ids
        all_child_ids = sorted({cid for lst in parent_map.values() for cid in lst})
        if not all_child_ids:
            return []

        # Check for evaluation service (legacy spp.indicator for now)
        # TODO: Fully migrate to spp.data.cache.manager (Phase 4 of ADR-017 complete)
        if "spp.indicator" not in self.env:
            self._logger.warning(
                "[CEL Metrics] No evaluation service available for aggregate metric=%s",
                p.metric,
            )
            return []

        svc = self.env["spp.indicator"]
        values, stats = svc.evaluate(
            p.metric,
            p.child_model,
            all_child_ids,
            str(p.period_key or "default"),
            mode="fallback",
        )
        if metrics_info is not None and stats:
            metrics_info.append(dict(stats, metric=p.metric, period_key=str(p.period_key or "default")))
        winners: list[int] = []
        for pid, cids in parent_map.items():
            vals = []
            present = 0
            for cid in cids:
                v = values.get(cid)
                if v is not None:
                    present += 1
                    vals.append(v)
            if p.agg == "avg":
                nums: list[float] = []
                for v in vals:
                    try:
                        nums.append(float(v))
                    except Exception:
                        continue
                if not nums:
                    continue
                agg_val = sum(nums) / len(nums)
            elif p.agg == "coverage":
                denom = len(cids) or 1
                agg_val = float(present) / float(denom)
            else:  # all
                # Treat missing as False (fail-closed)
                ok = True
                for cid in cids:
                    v = values.get(cid)
                    if v is None:
                        ok = False
                        break
                    if not self._cmp_value(v, p.op, p.rhs):
                        ok = False
                        break
                if ok:
                    winners.append(pid)
                continue
            if self._cmp_value(agg_val, p.op, p.rhs):
                winners.append(pid)
        return winners
