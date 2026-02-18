# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Thresholds for disparity detection
DISPARITY_THRESHOLD = 0.80
DISPARITY_WARNING_THRESHOLD = 0.70


class FairnessService(models.AbstractModel):
    """
    Service for computing fairness/parity metrics across demographic groups.

    Analyzes whether targeting reaches different demographic groups proportionally.
    Uses configurable DemographicDimension records for analysis.
    """

    _name = "spp.metrics.fairness"
    _description = "Fairness Analysis Service"

    @api.model
    def compute_fairness(self, registrant_ids, base_domain=None, dimensions=None):
        """
        Compute fairness metrics for a set of registrants.

        Analyzes disparity across demographic dimensions:
        - Gender
        - Disability status
        - Age group
        - And other configured dimensions

        :param registrant_ids: List of partner IDs (beneficiaries)
        :param base_domain: Domain for the population baseline
        :param dimensions: List of dimension names to analyze (or None for all)
        :returns: Dictionary with equity score and per-attribute breakdowns
        :rtype: dict
        """
        if not registrant_ids:
            return self._empty_fairness()

        beneficiary_set = set(registrant_ids)
        total_beneficiaries = len(beneficiary_set)

        # Get population baseline
        partner_model = self.env["res.partner"]
        population_domain = base_domain or [("is_registrant", "=", True)]
        total_population = partner_model.search_count(population_domain)

        if total_population == 0:
            return self._empty_fairness()

        overall_coverage = total_beneficiaries / total_population

        # Get dimensions to analyze
        dimension_records = self._get_dimensions(dimensions)

        attributes = {}
        equity_score = 100.0
        has_disparity = False

        # Analyze each demographic dimension
        for dimension in dimension_records:
            attr_result = self._analyze_dimension(
                dimension,
                beneficiary_set,
                population_domain,
                overall_coverage,
                partner_model,
            )
            if attr_result:
                attributes[dimension.name] = attr_result
                worst_ratio = attr_result.get("worst_ratio", 1.0)

                if worst_ratio < DISPARITY_WARNING_THRESHOLD:
                    equity_score -= 20
                    has_disparity = True
                elif worst_ratio < DISPARITY_THRESHOLD:
                    equity_score -= 5
                    has_disparity = True

        equity_score = max(0.0, equity_score)

        return {
            "equity_score": equity_score,
            "has_disparity": has_disparity,
            "overall_coverage": overall_coverage,
            "total_beneficiaries": total_beneficiaries,
            "total_population": total_population,
            "attributes": attributes,
        }

    @api.model
    def _empty_fairness(self):
        """Return empty fairness result."""
        return {
            "equity_score": 100.0,
            "has_disparity": False,
            "overall_coverage": 0,
            "total_beneficiaries": 0,
            "total_population": 0,
            "attributes": {},
        }

    def _get_dimensions(self, dimension_names=None):
        """
        Get dimension records to analyze.

        Uses sudo() since dimensions are configuration data that should be
        readable by all users who can compute aggregations.

        :param dimension_names: List of dimension names, or None for all active
        :returns: Recordset of dimensions
        """
        # Use sudo() - dimensions are configuration data, like menu items
        dimension_model = self.env["spp.demographic.dimension"].sudo()  # nosemgrep: odoo-sudo-without-context
        if dimension_names:
            return dimension_model.search(
                [
                    ("name", "in", dimension_names),
                    ("active", "=", True),
                ]
            )
        return dimension_model.search([("active", "=", True)])

    def _analyze_dimension(
        self,
        dimension,
        beneficiary_set,
        base_domain,
        overall_coverage,
        partner_model,
    ):
        """
        Analyze a single demographic dimension for fairness.

        :param dimension: spp.demographic.dimension record
        :param beneficiary_set: Set of beneficiary partner IDs
        :param base_domain: Population domain
        :param overall_coverage: Overall coverage rate
        :param partner_model: res.partner model
        :returns: Dictionary with analysis results or None if not applicable
        """
        if dimension.dimension_type == "field":
            return self._analyze_field_dimension(
                dimension, beneficiary_set, base_domain, overall_coverage, partner_model
            )
        else:
            return self._analyze_expression_dimension(
                dimension, beneficiary_set, base_domain, overall_coverage, partner_model
            )

    def _analyze_field_dimension(
        self,
        dimension,
        beneficiary_set,
        base_domain,
        overall_coverage,
        partner_model,
    ):
        """Analyze a field-based dimension (e.g., gender_id.code)."""
        field_path = dimension.field_path
        if not field_path:
            return None

        # Parse field path
        parts = field_path.split(".")
        base_field = parts[0]

        # Check if field exists
        if base_field not in partner_model._fields:
            dimension_name = dimension.name
            _logger.warning("Field %s not found on res.partner for dimension %s", base_field, dimension_name)
            return None

        field = partner_model._fields[base_field]

        # Handle Many2one fields
        if field.type == "many2one":
            return self._analyze_many2one_dimension(
                dimension, base_field, beneficiary_set, base_domain, overall_coverage, partner_model
            )

        # Handle Selection fields
        if field.type == "selection":
            return self._analyze_selection_dimension(
                dimension, base_field, beneficiary_set, base_domain, overall_coverage, partner_model
            )

        # Handle Boolean fields
        if field.type == "boolean":
            return self._analyze_boolean_dimension(
                dimension, base_field, beneficiary_set, base_domain, overall_coverage, partner_model
            )

        dimension_name = dimension.name
        _logger.warning("Unsupported field type %s for dimension %s", field.type, dimension_name)
        return None

    def _analyze_many2one_dimension(
        self,
        dimension,
        field_name,
        beneficiary_set,
        base_domain,
        overall_coverage,
        partner_model,
    ):
        """Analyze a Many2one field dimension.

        Uses read_group to count population and beneficiaries per group in two
        database queries rather than loading all records into memory.
        """
        group_results = []
        worst_ratio = 1.0

        # Population counts per group - one query
        population_groups = partner_model.read_group(base_domain, [field_name], [field_name])
        # Beneficiary counts per group - one query
        beneficiary_domain = base_domain + [("id", "in", list(beneficiary_set))]
        beneficiary_groups = partner_model.read_group(beneficiary_domain, [field_name], [field_name])

        # Build lookup dict from group value -> beneficiary count
        # read_group returns the Many2one field as (id, display_name) tuple or False
        beneficiary_counts = {}
        for row in beneficiary_groups:
            value = row[field_name]
            value_id = value[0] if value else False
            beneficiary_counts[value_id] = row[f"{field_name}_count"]

        for row in population_groups:
            value = row[field_name]
            if not value:
                continue
            value_id, display_name = value
            group_total = row[f"{field_name}_count"]

            if group_total == 0:
                continue

            group_beneficiaries = beneficiary_counts.get(value_id, 0)
            group_coverage = group_beneficiaries / group_total

            disparity_ratio = self._compute_disparity_ratio(group_coverage, overall_coverage)
            worst_ratio = min(worst_ratio, disparity_ratio)

            status = self._get_disparity_status(disparity_ratio)
            # For Many2one fields, prefer display_name over dimension label mapping
            # since label mappings may use codes rather than database IDs
            label = display_name or dimension.get_label_for_value(str(value_id))

            group_results.append(
                {
                    "key": str(value_id),
                    "label": label,
                    "population": group_total,
                    "beneficiaries": group_beneficiaries,
                    "coverage": round(group_coverage * 100, 2),
                    "disparity_ratio": round(disparity_ratio, 4),
                    "status": status,
                }
            )

        if not group_results:
            return None

        return {
            "attribute": dimension.name,
            "display_name": dimension.label,
            "groups": group_results,
            "worst_ratio": worst_ratio,
            "has_disparity": worst_ratio < DISPARITY_THRESHOLD,
        }

    def _analyze_selection_dimension(
        self,
        dimension,
        field_name,
        beneficiary_set,
        base_domain,
        overall_coverage,
        partner_model,
    ):
        """Analyze a Selection field dimension.

        Uses read_group to count population and beneficiaries per group in two
        database queries rather than one search_count pair per selection value.
        """
        group_results = []
        worst_ratio = 1.0

        field = partner_model._fields[field_name]
        selection = field.selection
        if callable(selection):
            selection = selection(partner_model)
        # Build label lookup from the field's selection values
        label_by_key = dict(selection)

        # Population counts per group - one query
        population_groups = partner_model.read_group(base_domain, [field_name], [field_name])
        # Beneficiary counts per group - one query
        beneficiary_domain = base_domain + [("id", "in", list(beneficiary_set))]
        beneficiary_groups = partner_model.read_group(beneficiary_domain, [field_name], [field_name])

        # Build lookup dict from selection key -> beneficiary count
        beneficiary_counts = {row[field_name]: row[f"{field_name}_count"] for row in beneficiary_groups}

        for row in population_groups:
            key = row[field_name]
            if key is False:
                continue
            group_total = row[f"{field_name}_count"]

            if group_total == 0:
                continue

            group_beneficiaries = beneficiary_counts.get(key, 0)
            group_coverage = group_beneficiaries / group_total

            disparity_ratio = self._compute_disparity_ratio(group_coverage, overall_coverage)
            worst_ratio = min(worst_ratio, disparity_ratio)

            status = self._get_disparity_status(disparity_ratio)
            display_label = dimension.get_label_for_value(key) or label_by_key.get(key, key)

            group_results.append(
                {
                    "key": key,
                    "label": display_label,
                    "population": group_total,
                    "beneficiaries": group_beneficiaries,
                    "coverage": round(group_coverage * 100, 2),
                    "disparity_ratio": round(disparity_ratio, 4),
                    "status": status,
                }
            )

        if not group_results:
            return None

        return {
            "attribute": dimension.name,
            "display_name": dimension.label,
            "groups": group_results,
            "worst_ratio": worst_ratio,
            "has_disparity": worst_ratio < DISPARITY_THRESHOLD,
        }

    def _analyze_boolean_dimension(
        self,
        dimension,
        field_name,
        beneficiary_set,
        base_domain,
        overall_coverage,
        partner_model,
    ):
        """Analyze a Boolean field dimension.

        Uses read_group to count population and beneficiaries per group in two
        database queries rather than one search_count pair per boolean value.
        """
        group_results = []
        worst_ratio = 1.0

        # Population counts per group - one query
        population_groups = partner_model.read_group(base_domain, [field_name], [field_name])
        # Beneficiary counts per group - one query
        beneficiary_domain = base_domain + [("id", "in", list(beneficiary_set))]
        beneficiary_groups = partner_model.read_group(beneficiary_domain, [field_name], [field_name])

        # Build lookup dict from boolean value -> beneficiary count
        beneficiary_counts = {row[field_name]: row[f"{field_name}_count"] for row in beneficiary_groups}

        for row in population_groups:
            value = row[field_name]
            group_total = row[f"{field_name}_count"]

            if group_total == 0:
                continue

            group_beneficiaries = beneficiary_counts.get(value, 0)
            group_coverage = group_beneficiaries / group_total

            disparity_ratio = self._compute_disparity_ratio(group_coverage, overall_coverage)
            worst_ratio = min(worst_ratio, disparity_ratio)

            status = self._get_disparity_status(disparity_ratio)
            key = "true" if value else "false"
            label = dimension.get_label_for_value(key) or ("Yes" if value else "No")

            group_results.append(
                {
                    "key": key,
                    "label": label,
                    "population": group_total,
                    "beneficiaries": group_beneficiaries,
                    "coverage": round(group_coverage * 100, 2),
                    "disparity_ratio": round(disparity_ratio, 4),
                    "status": status,
                }
            )

        if not group_results:
            return None

        return {
            "attribute": dimension.name,
            "display_name": dimension.label,
            "groups": group_results,
            "worst_ratio": worst_ratio,
            "has_disparity": worst_ratio < DISPARITY_THRESHOLD,
        }

    def _analyze_expression_dimension(
        self,
        dimension,
        beneficiary_set,
        base_domain,
        overall_coverage,
        partner_model,
    ):
        """
        Analyze a CEL expression-based dimension.

        Evaluates the expression for each registrant to categorize them,
        then computes fairness metrics per category.

        Note: CEL expressions must be evaluated per-record, so some iteration
        is unavoidable. We optimize by batching the domain search.
        """
        cel_service = self.env.get("spp.cel.service")
        if not cel_service:
            dimension_name = dimension.name
            _logger.warning("CEL service not available for dimension %s", dimension_name)
            return None

        # Categorize all registrants in population
        # Prefetch all records at once to minimize queries
        population = partner_model.search(base_domain)
        categories = {}

        # Check if cache service available for batch evaluation
        cache_service = self.env.get("spp.metrics.dimension.cache")
        if cache_service:
            # Use batch evaluation with caching
            evaluations = cache_service.evaluate_dimension_batch(dimension, population.ids)
            for partner_id in population.ids:
                category = evaluations.get(partner_id, dimension.default_value or "unknown")
                if category not in categories:
                    categories[category] = {"population": 0, "beneficiaries": 0}
                categories[category]["population"] += 1
                if partner_id in beneficiary_set:
                    categories[category]["beneficiaries"] += 1
        else:
            # Fallback: evaluate per-record (slower but works without cache)
            for partner in population:
                category = dimension.evaluate_for_record(partner)
                if category not in categories:
                    categories[category] = {"population": 0, "beneficiaries": 0}
                categories[category]["population"] += 1
                if partner.id in beneficiary_set:
                    categories[category]["beneficiaries"] += 1

        if not categories:
            return None

        group_results = []
        worst_ratio = 1.0

        for category_key, counts in categories.items():
            population_count = counts["population"]
            beneficiary_count = counts["beneficiaries"]

            if population_count == 0:
                continue

            group_coverage = beneficiary_count / population_count
            disparity_ratio = self._compute_disparity_ratio(group_coverage, overall_coverage)
            worst_ratio = min(worst_ratio, disparity_ratio)

            status = self._get_disparity_status(disparity_ratio)
            label = dimension.get_label_for_value(category_key) or category_key

            group_results.append(
                {
                    "key": category_key,
                    "label": label,
                    "population": population_count,
                    "beneficiaries": beneficiary_count,
                    "coverage": round(group_coverage * 100, 2),
                    "disparity_ratio": round(disparity_ratio, 4),
                    "status": status,
                }
            )

        return {
            "attribute": dimension.name,
            "display_name": dimension.label,
            "groups": group_results,
            "worst_ratio": worst_ratio,
            "has_disparity": worst_ratio < DISPARITY_THRESHOLD,
        }

    @api.model
    def _compute_disparity_ratio(self, group_coverage, overall_coverage):
        """
        Compute the disparity ratio for a group.

        :param group_coverage: Coverage rate for the group (0.0 to 1.0)
        :param overall_coverage: Overall coverage rate (0.0 to 1.0)
        :returns: Disparity ratio (group_coverage / overall_coverage)
        :rtype: float
        """
        if overall_coverage == 0:
            return 0.0
        return group_coverage / overall_coverage

    @api.model
    def _get_disparity_status(self, disparity_ratio):
        """
        Get the disparity status label for a ratio.

        :param disparity_ratio: The disparity ratio
        :returns: Status string
        :rtype: str
        """
        if disparity_ratio < DISPARITY_WARNING_THRESHOLD:
            return "under_represented"
        elif disparity_ratio < DISPARITY_THRESHOLD:
            return "low_coverage"
        return "proportional"
