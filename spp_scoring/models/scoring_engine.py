import json
import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Optional job_worker import for async batch processing
try:
    from odoo.addons.job_worker.delay import group
except ImportError:
    group = None

_logger = logging.getLogger(__name__)

# Threshold for async processing (process synchronously below this)
ASYNC_BATCH_THRESHOLD = 1000
# Batch chunk size for async jobs
ASYNC_CHUNK_SIZE = 500


class SppScoringEngine(models.AbstractModel):
    """
    Central scoring engine that calculates scores for registrants.

    This is an abstract model providing the scoring calculation service.
    It can be called from anywhere to score registrants against models.
    """

    _name = "spp.scoring.engine"
    _description = "Scoring Calculation Engine"

    @api.model
    def calculate_score(self, registrant, scoring_model, mode="manual"):
        """
        Calculate a score for a registrant using a scoring model.

        Args:
            registrant: res.partner record (registrant)
            scoring_model: spp.scoring.model record
            mode: 'manual', 'batch', or 'automatic'

        Returns:
            spp.scoring.result record with the calculated score
        """
        # Validate inputs
        if not registrant:
            raise ValidationError(_("Registrant is required."))
        if not scoring_model:
            raise ValidationError(_("Scoring model is required."))

        # Check model is active
        today = date.today()
        if not scoring_model.is_active_on_date(today):
            raise UserError(_("Scoring model '%s' is not active on %s.") % (scoring_model.name, today))

        # Prefetch all related data to avoid N+1 queries
        scoring_model = self._prefetch_model_data(scoring_model)

        # Cache model-level values accessed in the loop
        is_strict_mode = scoring_model.is_strict_mode
        calculation_method = scoring_model.calculation_method

        # Initialize calculation
        total_score = 0.0
        breakdown = []
        errors = []
        inputs_snapshot = {}
        detail_vals = []

        # Get sorted indicators (prefetched)
        indicators = scoring_model.indicator_ids.sorted(key=lambda i: i.sequence)

        # Process each indicator
        for indicator in indicators:
            result = self._calculate_indicator(indicator, registrant)

            # Accumulate results
            if result.get("error"):
                errors.append(result["error"])
                if is_strict_mode and indicator.is_required:
                    continue

            total_score += result.get("weighted_score", 0.0)

            # Store in snapshot
            inputs_snapshot[indicator.code] = result.get("field_value")

            # Build breakdown
            breakdown.append(
                {
                    "indicator_code": indicator.code,
                    "indicator_name": indicator.name,
                    "field_value": str(result.get("field_value", "")),
                    "indicator_score": result.get("indicator_score", 0.0),
                    "weight": indicator.weight,
                    "weighted_score": result.get("weighted_score", 0.0),
                    "error": result.get("error"),
                }
            )

            # Build detail record
            detail_vals.append(
                {
                    "indicator_id": indicator.id,
                    "field_value": str(result.get("field_value", "")),
                    "indicator_score": result.get("indicator_score", 0.0),
                    "weighted_score": result.get("weighted_score", 0.0),
                    "has_error": bool(result.get("error")),
                    "notes": result.get("error"),
                }
            )

        # Handle CEL formula calculation method
        if calculation_method == "cel_formula":
            total_score = self._calculate_cel_total(scoring_model, registrant, inputs_snapshot)

        # Determine classification (thresholds already prefetched)
        classification = self._get_classification(total_score, scoring_model)

        # Check for errors in strict mode
        is_complete = True
        if errors and is_strict_mode:
            is_complete = False

        # Create result record
        Result = self.env["spp.scoring.result"]
        result = Result.create(
            {
                "registrant_id": registrant.id,
                "model_id": scoring_model.id,
                "score": total_score,
                "classification_code": classification.get("code"),
                "classification_label": classification.get("label"),
                "classification_color": classification.get("color"),
                "calculation_mode": mode,
                "inputs_snapshot": json.dumps(inputs_snapshot),
                "breakdown_json": json.dumps(breakdown),
                "is_complete": is_complete,
                "error_messages": "\n".join(errors) if errors else False,
                "model_version": scoring_model.version,
            }
        )

        # Create detail records
        for detail in detail_vals:
            detail["result_id"] = result.id
        self.env["spp.scoring.result.detail"].create(detail_vals)

        _logger.info(
            "Calculated score for registrant %s using model %s: %.2f (%s)",
            registrant.id,
            scoring_model.code,
            total_score,
            classification.get("code", "UNCLASSIFIED"),
        )

        return result

    def _prefetch_model_data(self, scoring_model):
        """
        Prefetch all related data for scoring model to avoid N+1 queries.

        This ensures indicators, value mappings, and thresholds are loaded
        in a minimal number of queries before processing.
        """
        # Prefetch indicators with their value mappings
        scoring_model.indicator_ids.mapped("value_mapping_ids")

        # Prefetch thresholds
        list(scoring_model.threshold_ids)

        # Prefetch model_id on indicators for CEL profile access
        scoring_model.indicator_ids.mapped("model_id.cel_profile")

        return scoring_model

    def _calculate_indicator(self, indicator, registrant):
        """
        Calculate a single indicator score.

        Returns dict with:
            - field_value: raw value from registrant
            - indicator_score: score before weight
            - weighted_score: score * weight
            - error: error message if any
        """
        result = {
            "field_value": None,
            "indicator_score": 0.0,
            "weighted_score": 0.0,
            "error": None,
        }

        try:
            # Get field value
            if indicator.calculation_type == "formula":
                # For formula type, pass the registrant to CEL
                field_value = self._evaluate_indicator_formula(indicator, registrant)
            elif indicator.calculation_type == "derived":
                # For derived, call the calculation directly
                field_value = indicator._calculate_derived(registrant)
            else:
                # Get field value from registrant
                field_value = indicator.get_field_value(registrant)

            result["field_value"] = field_value

            # Handle missing values
            if field_value is None:
                if indicator.is_required:
                    result["error"] = _("Required field '%s' is missing.") % indicator.field_path
                    return result
                field_value = indicator._convert_default_value()

            # Calculate indicator score
            if indicator.calculation_type == "formula":
                # Formula already calculated above
                indicator_score = field_value if isinstance(field_value, int | float) else 0.0
            else:
                indicator_score = indicator.calculate_score(field_value)

            result["indicator_score"] = indicator_score
            result["weighted_score"] = indicator_score * indicator.weight

        except (ValueError, TypeError, AttributeError) as e:
            _logger.warning(
                "Error calculating indicator %s for registrant %s: %s",
                indicator.code,
                registrant.id,
                str(e),
            )
            result["error"] = str(e)
        except Exception as e:
            # Catch-all for unexpected errors (CEL failures, etc.)
            _logger.error(
                "Unexpected error calculating indicator %s for registrant %s: %s",
                indicator.code,
                registrant.id,
                str(e),
                exc_info=True,
            )
            result["error"] = str(e)

        return result

    def _evaluate_indicator_formula(self, indicator, registrant):
        """Evaluate a CEL formula for an indicator."""
        if not indicator.cel_expression:
            return None

        try:
            cel_service = self.env["spp.cel.service"]
            profile = indicator.model_id.cel_profile or "registry_individuals"

            # Build context from registrant - use safe primitives only
            context = self._build_cel_context(registrant)

            result = cel_service.evaluate_expression(indicator.cel_expression, profile, context)

            if result.get("success"):
                return result.get("value")

            _logger.debug(
                "CEL evaluation returned error for indicator %s: %s",
                indicator.code,
                result.get("error", "Unknown"),
            )
            return None
        except (KeyError, AttributeError, TypeError) as e:
            _logger.warning(
                "Error evaluating CEL for indicator %s: %s",
                indicator.code,
                str(e),
            )
            return None
        except Exception as e:
            _logger.error(
                "Unexpected error evaluating CEL for indicator %s: %s",
                indicator.code,
                str(e),
                exc_info=True,
            )
            return None

    def _calculate_cel_total(self, scoring_model, registrant, indicators_data):
        """Calculate total score using CEL formula."""
        if not scoring_model.cel_expression:
            return 0.0

        try:
            cel_service = self.env["spp.cel.service"]
            profile = scoring_model.cel_profile or "registry_individuals"

            # Build context with indicators data
            context = self._build_cel_context(registrant)
            context["indicators"] = indicators_data

            result = cel_service.evaluate_expression(scoring_model.cel_expression, profile, context)

            if result.get("success"):
                return float(result.get("value", 0.0))

            return 0.0
        except Exception as e:
            _logger.warning(
                "Error evaluating CEL total for model %s: %s",
                scoring_model.code,
                str(e),
            )
            return 0.0

    def _build_cel_context(self, registrant):
        """
        Build a CEL context dict from a registrant.

        SECURITY: Only expose primitive values, not ORM objects.
        This prevents CEL expressions from accessing arbitrary model methods.
        """
        context = {
            # Core identification (primitives only)
            "id": registrant.id,
            "name": registrant.name or "",
            "is_group": bool(registrant.is_group),
            "is_registrant": bool(registrant.is_registrant),
        }

        # Add common fields as primitives only
        common_fields = ["age", "gender", "address", "email", "phone"]
        for field_name in common_fields:
            if hasattr(registrant, field_name):
                value = getattr(registrant, field_name, None)
                # Convert to primitive - don't expose recordsets
                if value is None:
                    context[field_name] = None
                elif isinstance(value, str | int | float | bool):
                    context[field_name] = value
                elif hasattr(value, "id"):
                    # For Many2one fields, just expose the ID
                    context[field_name] = value.id if value else None
                else:
                    # Convert to string for safety
                    context[field_name] = str(value) if value else ""

        return context

    def _get_classification(self, score, scoring_model):
        """Determine classification based on score and thresholds."""
        for threshold in scoring_model.threshold_ids.sorted(key=lambda t: t.min_score):
            if threshold.matches_score(score):
                return threshold.get_classification()

        # Score outside all thresholds
        return {
            "code": "UNCLASSIFIED",
            "label": _("Unclassified"),
            "color": "gray",
        }

    @api.model
    def batch_score(self, registrants, scoring_model, options=None):
        """
        Score multiple registrants in batch.

        For large batches (>ASYNC_BATCH_THRESHOLD), uses job_worker for
        asynchronous processing if available.

        Args:
            registrants: recordset of res.partner
            scoring_model: spp.scoring.model record
            options: dict with optional settings:
                - fail_fast: stop on first error (default False)
                - force_async: force async processing (default False)
                - force_sync: force sync processing (default False)

        Returns:
            dict with results summary (sync) or job info (async)
        """
        options = options or {}
        count = len(registrants)

        # Determine if we should use async processing
        use_async = (
            group is not None and count >= ASYNC_BATCH_THRESHOLD and not options.get("force_sync")
        ) or options.get("force_async")

        if use_async and group is not None:
            return self._batch_score_async(registrants, scoring_model, options)

        return self._batch_score_sync(registrants, scoring_model, options)

    def _batch_score_sync(self, registrants, scoring_model, options):
        """Synchronous batch scoring for smaller datasets."""
        results = []
        errors = []

        for registrant in registrants:
            try:
                result = self.calculate_score(
                    registrant,
                    scoring_model,
                    mode="batch",
                )
                results.append(result)

            except Exception as e:
                _logger.warning(
                    "Error scoring registrant %s: %s",
                    registrant.id,
                    str(e),
                )
                if options.get("fail_fast"):
                    raise
                errors.append(
                    {
                        "registrant_id": registrant.id,
                        "registrant_name": registrant.name,
                        "error": str(e),
                    }
                )

        return {
            "results": results,
            "errors": errors,
            "summary": {
                "total": len(registrants),
                "successful": len(results),
                "failed": len(errors),
            },
            "async": False,
        }

    def _batch_score_async(self, registrants, scoring_model, options):
        """Asynchronous batch scoring for large datasets using job_worker."""
        registrant_ids = registrants.ids
        total = len(registrant_ids)

        _logger.info(
            "Starting async batch scoring: %d registrants with model %s",
            total,
            scoring_model.code,
        )

        # Create batch job record to track progress
        batch = self.env["spp.scoring.batch.job"].create(
            {
                "model_id": scoring_model.id,
                "total_count": total,
                "state": "pending",
            }
        )

        # Create chunk jobs
        jobs = []
        for i in range(0, total, ASYNC_CHUNK_SIZE):
            chunk_ids = registrant_ids[i : i + ASYNC_CHUNK_SIZE]
            jobs.append(
                self.delayable(
                    channel="root.scoring.batch",
                    description=f"Batch scoring chunk {i // ASYNC_CHUNK_SIZE + 1}",
                )._process_scoring_chunk(
                    chunk_ids,
                    scoring_model.id,
                    batch.id,
                    options,
                )
            )

        # Group jobs and set completion callback
        main_job = group(*jobs)
        main_job.on_done(
            self.delayable(
                channel="root.scoring.batch",
            )._finalize_batch_scoring(batch.id)
        )
        main_job.delay()

        return {
            "async": True,
            "batch_id": batch.id,
            "total": total,
            "chunks": len(jobs),
            "message": _("Batch scoring started. %d registrants will be processed in %d chunks.")
            % (
                total,
                len(jobs),
            ),
        }

    def _process_scoring_chunk(self, registrant_ids, model_id, batch_id, options):
        """Process a chunk of registrants (called by job_worker)."""
        scoring_model = self.env["spp.scoring.model"].browse(model_id)
        registrants = self.env["res.partner"].browse(registrant_ids)
        batch = self.env["spp.scoring.batch.job"].browse(batch_id)

        successful = 0
        failed = 0
        errors = []

        for registrant in registrants:
            try:
                self.calculate_score(registrant, scoring_model, mode="batch")
                successful += 1
            except Exception as e:
                failed += 1
                _logger.warning(
                    "Error scoring registrant %s in batch %s: %s",
                    registrant.id,
                    batch_id,
                    str(e),
                )
                errors.append(
                    {
                        "registrant_id": registrant.id,
                        "registrant_name": registrant.name,
                        "error": str(e),
                    }
                )
                if options.get("fail_fast"):
                    break

        # Update batch job progress
        batch.sudo().write(  # nosemgrep
            {
                "successful_count": batch.successful_count + successful,
                "failed_count": batch.failed_count + failed,
            }
        )

        return {
            "successful": successful,
            "failed": failed,
            "errors": errors,
        }

    def _finalize_batch_scoring(self, batch_id):
        """Finalize batch scoring job (called when all chunks complete)."""
        batch = self.env["spp.scoring.batch.job"].browse(batch_id)
        batch.sudo().write(  # nosemgrep
            {
                "state": "done",
                "completed_date": fields.Datetime.now(),
            }
        )

        _logger.info(
            "Batch scoring %s completed: %d successful, %d failed",
            batch_id,
            batch.successful_count,
            batch.failed_count,
        )

    @api.model
    def compare_scores(self, registrant, model_v1, model_v2):
        """
        Compare scores for a registrant between two model versions.

        Returns dict with comparison data.
        """
        score_v1 = self.calculate_score(registrant, model_v1)
        score_v2 = self.calculate_score(registrant, model_v2)

        return {
            "old_score": score_v1.score,
            "new_score": score_v2.score,
            "old_classification": {
                "code": score_v1.classification_code,
                "label": score_v1.classification_label,
            },
            "new_classification": {
                "code": score_v2.classification_code,
                "label": score_v2.classification_label,
            },
            "score_change": score_v2.score - score_v1.score,
            "classification_changed": (score_v1.classification_code != score_v2.classification_code),
        }

    @api.model
    def get_or_calculate_score(self, registrant, scoring_model, max_age_days=None):
        """
        Get existing score if fresh enough, otherwise calculate new one.

        Args:
            registrant: res.partner record
            scoring_model: spp.scoring.model record
            max_age_days: maximum age of existing score (None = always recalculate)

        Returns:
            spp.scoring.result record
        """
        Result = self.env["spp.scoring.result"]

        # max_age_days > 0: reuse cached score if fresh enough
        # max_age_days = 0 or None: always recalculate
        if max_age_days and max_age_days > 0:
            existing = Result.get_latest_score(registrant, scoring_model, max_age_days)
            if existing:
                return existing

        return self.calculate_score(registrant, scoring_model)
