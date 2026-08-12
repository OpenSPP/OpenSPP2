# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDemographicDimension(TransactionCase):
    """Test demographic dimension model methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["res.partner"]

        # Create test registrants (individuals and groups)
        cls.group = cls.partner_model.create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.individual = cls.partner_model.create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.dim_model = cls.env["spp.demographic.dimension"]

        # Create field-based dimension for is_group (boolean)
        cls.bool_dim = cls.dim_model.create(
            {
                "name": "test_is_group",
                "label": "Is Group",
                "dimension_type": "field",
                "field_path": "is_group",
                "applies_to": "all",
            }
        )

        # Create dimension that applies only to individuals
        cls.indiv_dim = cls.dim_model.create(
            {
                "name": "test_indiv_only",
                "label": "Individual Only",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "individuals",
            }
        )

        # Create dimension that applies only to groups
        cls.group_dim = cls.dim_model.create(
            {
                "name": "test_group_only",
                "label": "Group Only",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "groups",
            }
        )

    # -------------------------------------------------------------------------
    # evaluate_for_record
    # -------------------------------------------------------------------------

    def test_evaluate_boolean_field_true(self):
        """Boolean field on a group record returns 'true'."""
        result = self.bool_dim.evaluate_for_record(self.group)
        self.assertEqual(result, "true")

    def test_evaluate_boolean_field_false(self):
        """Boolean field on an individual record returns 'false'."""
        result = self.bool_dim.evaluate_for_record(self.individual)
        self.assertEqual(result, "false")

    def test_evaluate_applicability_individual_dim_on_group(self):
        """Individual-only dimension evaluated on a group returns default."""
        result = self.indiv_dim.evaluate_for_record(self.group)
        self.assertEqual(result, self.indiv_dim.default_value or "n/a")

    def test_evaluate_applicability_group_dim_on_individual(self):
        """Group-only dimension evaluated on an individual returns default."""
        result = self.group_dim.evaluate_for_record(self.individual)
        self.assertEqual(result, self.group_dim.default_value or "n/a")

    def test_evaluate_applicability_match_individual(self):
        """Individual-only dimension on individual evaluates normally."""
        result = self.indiv_dim.evaluate_for_record(self.individual)
        self.assertEqual(result, "Test Individual")

    def test_evaluate_applicability_match_group(self):
        """Group-only dimension on group evaluates normally."""
        result = self.group_dim.evaluate_for_record(self.group)
        self.assertEqual(result, "Test Group")

    # -------------------------------------------------------------------------
    # _evaluate_field: dot notation
    # -------------------------------------------------------------------------

    def test_evaluate_field_dot_notation_none_intermediate(self):
        """Dot notation where intermediate value is falsy returns default or str."""
        dim = self.dim_model.create(
            {
                "name": "test_dot_none",
                "label": "Dot None",
                "dimension_type": "field",
                "field_path": "parent_id.name",
                "applies_to": "all",
            }
        )
        # individual has no parent_id, so parent_id is a falsy recordset
        # _evaluate_field may return default_value or a string representation
        result = dim.evaluate_for_record(self.individual)
        self.assertIsInstance(result, str)

    def test_evaluate_field_dot_notation_many2one(self):
        """Dot notation traversing a Many2one (company_id.name)."""
        company = self.env["res.company"].search([], limit=1)
        partner = self.partner_model.create(
            {
                "name": "With Company",
                "is_registrant": True,
                "is_group": False,
                "company_id": company.id,
            }
        )
        dim = self.dim_model.create(
            {
                "name": "test_company_name",
                "label": "Company Name",
                "dimension_type": "field",
                "field_path": "company_id.name",
                "applies_to": "all",
            }
        )
        result = dim.evaluate_for_record(partner)
        self.assertEqual(result, company.name)

    def test_evaluate_field_many2one_with_code(self):
        """Many2one field where related record has a 'code' attribute."""
        # company_id is Many2one and res.company doesn't have 'code' normally,
        # but we can test through the field that returns a record with .id
        dim = self.dim_model.create(
            {
                "name": "test_company_m2o",
                "label": "Company",
                "dimension_type": "field",
                "field_path": "company_id",
                "applies_to": "all",
            }
        )
        company = self.env["res.company"].search([], limit=1)
        partner = self.partner_model.create(
            {
                "name": "Company Partner",
                "is_registrant": True,
                "is_group": False,
                "company_id": company.id,
            }
        )
        result = dim.evaluate_for_record(partner)
        # company_id has .id, so it's a Many2one. res.company has no .code
        # so it should return display_name or str(id)
        self.assertIn(result, [company.display_name, str(company.id)])

    def test_evaluate_field_missing_attribute(self):
        """Field path with non-existent attribute returns default."""
        dim = self.dim_model.create(
            {
                "name": "test_missing_attr",
                "label": "Missing",
                "dimension_type": "field",
                "field_path": "nonexistent_field_xyz",
                "applies_to": "all",
                "default_value": "fallback",
            }
        )
        result = dim.evaluate_for_record(self.individual)
        self.assertEqual(result, "fallback")

    def test_evaluate_field_string_value(self):
        """Direct string field returns the string value."""
        dim = self.dim_model.create(
            {
                "name": "test_name_field",
                "label": "Name",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
            }
        )
        result = dim.evaluate_for_record(self.individual)
        self.assertEqual(result, "Test Individual")

    # -------------------------------------------------------------------------
    # _evaluate_expression
    # -------------------------------------------------------------------------

    def test_evaluate_expression_cel_service_not_available(self):
        """Expression dimension when CEL service not available returns default."""
        dim = self.dim_model.create(
            {
                "name": "test_expr_no_cel",
                "label": "No CEL",
                "dimension_type": "expression",
                "cel_expression": "true",
                "applies_to": "all",
                "default_value": "no_cel",
            }
        )
        # Temporarily make the CEL service unavailable by patching env
        with patch.object(type(self.env), "__getitem__", side_effect=KeyError("spp.cel.service")):
            result = dim._evaluate_expression(self.individual)
        self.assertEqual(result, "no_cel")

    def test_evaluate_expression_returns_value(self):
        """Expression-based dimension returns a string result."""
        dim = self.dim_model.create(
            {
                "name": "test_expr_val",
                "label": "Expr Val",
                "dimension_type": "expression",
                "cel_expression": "true",
                "applies_to": "all",
                "default_value": "no_cel",
            }
        )
        # Call evaluate_for_record which dispatches to _evaluate_expression
        # If CEL service is available, it evaluates; if not, returns default
        result = dim.evaluate_for_record(self.individual)
        self.assertIsInstance(result, str)

    def test_evaluate_expression_returns_none(self):
        """Expression returning None uses default_value."""
        dim = self.dim_model.create(
            {
                "name": "test_expr_none",
                "label": "None Expr",
                "dimension_type": "expression",
                "cel_expression": "null_expr",
                "applies_to": "all",
                "default_value": "unset",
            }
        )
        cel_service = self.env.get("spp.cel.service")
        if cel_service:
            with patch.object(type(cel_service), "evaluate_expression", return_value=None):
                result = dim._evaluate_expression(self.individual)
            self.assertEqual(result, "unset")

    # -------------------------------------------------------------------------
    # evaluate_for_record error handling
    # -------------------------------------------------------------------------

    def test_evaluate_for_record_catches_error(self):
        """Errors during evaluation return default_value or 'error'."""
        dim = self.dim_model.create(
            {
                "name": "test_error_dim",
                "label": "Error Dim",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
                "default_value": "err_default",
            }
        )
        # Force an error during field evaluation
        with patch.object(type(dim), "_evaluate_field", side_effect=AttributeError("test error")):
            result = dim.evaluate_for_record(self.individual)
        self.assertEqual(result, "err_default")

    def test_evaluate_for_record_error_no_default(self):
        """Error with no default_value returns 'error'."""
        dim = self.dim_model.create(
            {
                "name": "test_error_no_default",
                "label": "Error No Default",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
                "default_value": "",
            }
        )
        with patch.object(type(dim), "_evaluate_field", side_effect=TypeError("test error")):
            result = dim.evaluate_for_record(self.individual)
        self.assertEqual(result, "error")

    # -------------------------------------------------------------------------
    # get_label_for_value
    # -------------------------------------------------------------------------

    def test_evaluate_field_empty_many2one_returns_default(self):
        """Empty Many2one (unset field) returns default_value, not 'False'."""
        dim = self.dim_model.create(
            {
                "name": "test_empty_m2o",
                "label": "Empty M2O",
                "dimension_type": "field",
                "field_path": "company_id",
                "applies_to": "all",
                "default_value": "unset",
            }
        )
        # Individual with company_id explicitly cleared
        partner = self.partner_model.create(
            {
                "name": "No Company",
                "is_registrant": True,
                "is_group": False,
                "company_id": False,
            }
        )
        result = dim.evaluate_for_record(partner)
        self.assertEqual(result, "unset")

    def test_get_label_for_value_m2o_dynamic_lookup(self):
        """get_label_for_value dynamically looks up Many2one display_name."""
        # Use company_id which doesn't have a 'code' field on res.company
        dim = self.dim_model.create(
            {
                "name": "test_m2o_label_lookup",
                "label": "Area Label",
                "dimension_type": "field",
                "field_path": "company_id",
                "applies_to": "all",
            }
        )
        # For a field without code, dynamic lookup won't match
        # (res.company has no code field), so it falls back to raw value
        result = dim.get_label_for_value("some_code")
        self.assertEqual(result, "some_code")

    def test_get_label_for_value_static_takes_precedence(self):
        """Static value_labels_json takes precedence over dynamic lookup."""
        dim = self.dim_model.create(
            {
                "name": "test_static_precedence",
                "label": "Static",
                "dimension_type": "field",
                "field_path": "company_id",
                "applies_to": "all",
                "value_labels_json": {"MY_CODE": "My Display Name"},
            }
        )
        result = dim.get_label_for_value("MY_CODE")
        self.assertEqual(result, "My Display Name")

    def test_get_label_for_value_with_json_mapping(self):
        """Value label lookup from JSON mapping."""
        dim = self.dim_model.create(
            {
                "name": "test_labels_json",
                "label": "Labels",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
                "value_labels_json": {"M": "Male", "F": "Female"},
            }
        )
        self.assertEqual(dim.get_label_for_value("M"), "Male")
        self.assertEqual(dim.get_label_for_value("F"), "Female")

    def test_get_label_for_value_no_mapping(self):
        """Without mapping, returns the raw value."""
        result = self.bool_dim.get_label_for_value("true")
        self.assertEqual(result, "true")

    def test_get_label_for_value_missing_key(self):
        """Value not in mapping returns original value."""
        dim = self.dim_model.create(
            {
                "name": "test_labels_miss",
                "label": "Labels Miss",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
                "value_labels_json": {"A": "Alpha"},
            }
        )
        self.assertEqual(dim.get_label_for_value("Z"), "Z")

    def test_get_label_for_value_none_value(self):
        """None value looks up 'null' in the mapping."""
        dim = self.dim_model.create(
            {
                "name": "test_labels_null",
                "label": "Labels Null",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
                "value_labels_json": {"null": "Not Set"},
            }
        )
        self.assertEqual(dim.get_label_for_value(None), "Not Set")

    def test_get_label_for_value_string_json(self):
        """String JSON in value_labels_json is parsed."""
        dim = self.dim_model.create(
            {
                "name": "test_labels_str",
                "label": "Labels Str",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
                "value_labels_json": {"X": "Unknown"},
            }
        )
        # Force value_labels_json to be a string (simulating edge case)
        # Odoo Json field normally returns dict, but we test the string branch
        with patch.object(
            type(dim),
            "value_labels_json",
            new_callable=lambda: property(lambda self: json.dumps({"X": "Unknown"})),
        ):
            result = dim.get_label_for_value("X")
        self.assertEqual(result, "Unknown")

    def test_get_label_for_value_invalid_string_json(self):
        """Invalid string JSON returns the raw value."""
        dim = self.dim_model.create(
            {
                "name": "test_labels_bad_json",
                "label": "Labels Bad",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
                "value_labels_json": {"placeholder": "val"},
            }
        )
        with patch.object(
            type(dim),
            "value_labels_json",
            new_callable=lambda: property(lambda self: "not valid json{{{"),
        ):
            result = dim.get_label_for_value("test")
        self.assertEqual(result, "test")

    # -------------------------------------------------------------------------
    # get_by_name
    # -------------------------------------------------------------------------

    def test_get_by_name_existing(self):
        """get_by_name returns a record for an existing dimension."""
        result = self.dim_model.get_by_name("test_is_group")
        self.assertTrue(result)
        self.assertEqual(result.name, "test_is_group")

    def test_get_by_name_nonexistent(self):
        """get_by_name returns empty recordset for non-existing name."""
        result = self.dim_model.get_by_name("definitely_not_a_dimension_xyz")
        self.assertFalse(result)

    def test_get_by_name_inactive(self):
        """get_by_name does not return inactive dimensions."""
        dim = self.dim_model.create(
            {
                "name": "test_inactive_dim",
                "label": "Inactive",
                "dimension_type": "field",
                "field_path": "name",
                "active": False,
            }
        )
        result = self.dim_model.get_by_name("test_inactive_dim")
        self.assertFalse(result)
        # cleanup
        dim.unlink()

    # -------------------------------------------------------------------------
    # get_active_dimensions
    # -------------------------------------------------------------------------

    def test_get_active_dimensions_no_filter(self):
        """get_active_dimensions without filter returns all active dims."""
        result = self.dim_model.get_active_dimensions()
        # Should include our test dimensions
        names = result.mapped("name")
        self.assertIn("test_is_group", names)
        self.assertIn("test_indiv_only", names)
        self.assertIn("test_group_only", names)

    def test_get_active_dimensions_filter_individuals(self):
        """Filtering by 'individuals' returns 'all' + 'individuals' dims."""
        result = self.dim_model.get_active_dimensions(applies_to="individuals")
        names = result.mapped("name")
        self.assertIn("test_is_group", names)  # applies_to = 'all'
        self.assertIn("test_indiv_only", names)  # applies_to = 'individuals'
        self.assertNotIn("test_group_only", names)  # applies_to = 'groups'

    def test_get_active_dimensions_filter_groups(self):
        """Filtering by 'groups' returns 'all' + 'groups' dims."""
        result = self.dim_model.get_active_dimensions(applies_to="groups")
        names = result.mapped("name")
        self.assertIn("test_is_group", names)  # applies_to = 'all'
        self.assertNotIn("test_indiv_only", names)  # applies_to = 'individuals'
        self.assertIn("test_group_only", names)  # applies_to = 'groups'

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    def test_constraint_field_type_without_field_path(self):
        """Field type without field_path raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.dim_model.create(
                {
                    "name": "test_no_path",
                    "label": "No Path",
                    "dimension_type": "field",
                    "field_path": "",
                }
            )

    def test_constraint_expression_type_without_expression(self):
        """Expression type without cel_expression raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.dim_model.create(
                {
                    "name": "test_no_expr",
                    "label": "No Expr",
                    "dimension_type": "expression",
                    "cel_expression": "",
                }
            )

    def test_constraint_unique_name(self):
        """Duplicate dimension name raises an error (SQL unique constraint)."""
        with self.assertRaises(Exception):  # noqa: B017
            with self.env.cr.savepoint():
                self.dim_model.create(
                    {
                        "name": "test_is_group",  # already exists
                        "label": "Duplicate",
                        "dimension_type": "field",
                        "field_path": "name",
                    }
                )

    # -------------------------------------------------------------------------
    # write() and unlink() cache invalidation
    # -------------------------------------------------------------------------

    def test_write_clears_cache(self):
        """write() calls clear_dimension_cache."""
        dim = self.dim_model.create(
            {
                "name": "test_cache_write",
                "label": "Cache Write",
                "dimension_type": "field",
                "field_path": "name",
            }
        )
        cache_service = self.env["spp.metric.dimension.cache"]
        with patch.object(type(cache_service), "clear_dimension_cache") as mock_clear:
            dim.write({"label": "Updated Label"})
            mock_clear.assert_called()

    def test_unlink_clears_cache(self):
        """unlink() calls clear_dimension_cache."""
        dim = self.dim_model.create(
            {
                "name": "test_cache_unlink",
                "label": "Cache Unlink",
                "dimension_type": "field",
                "field_path": "name",
            }
        )
        cache_service = self.env["spp.metric.dimension.cache"]
        with patch.object(type(cache_service), "clear_dimension_cache") as mock_clear:
            dim.unlink()
            mock_clear.assert_called()


@tagged("post_install", "-at_install")
class TestFairnessServiceDimensions(TransactionCase):
    """Test fairness service dimension-specific analysis methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["res.partner"]
        cls.fairness_service = cls.env["spp.metric.fairness"]
        cls.dim_model = cls.env["spp.demographic.dimension"]

        # Create test registrants: mix of groups and individuals
        cls.individuals = cls.partner_model.browse()
        cls.groups = cls.partner_model.browse()

        for i in range(5):
            ind = cls.partner_model.create(
                {
                    "name": f"Fairness Individual {i}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            cls.individuals |= ind

        for i in range(3):
            grp = cls.partner_model.create(
                {
                    "name": f"Fairness Group {i}",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
            cls.groups |= grp

        cls.all_registrants = cls.individuals | cls.groups
        cls.all_ids = cls.all_registrants.ids

        # Create boolean dimension on is_group
        cls.bool_dim = cls.dim_model.create(
            {
                "name": "fairness_is_group",
                "label": "Is Group",
                "dimension_type": "field",
                "field_path": "is_group",
                "applies_to": "all",
            }
        )

    def test_empty_fairness_structure(self):
        """_empty_fairness returns proper dict structure."""
        result = self.fairness_service._empty_fairness()
        self.assertEqual(result["equity_score"], 100.0)
        self.assertFalse(result["has_disparity"])
        self.assertEqual(result["overall_coverage"], 0)
        self.assertEqual(result["total_beneficiaries"], 0)
        self.assertEqual(result["total_population"], 0)
        self.assertIsInstance(result["attributes"], dict)
        self.assertEqual(len(result["attributes"]), 0)

    def test_analyze_boolean_dimension(self):
        """_analyze_boolean_dimension returns groups with true/false keys."""
        beneficiary_set = set(self.individuals.ids[:3])
        base_domain = [("id", "in", self.all_ids)]
        overall_coverage = len(beneficiary_set) / len(self.all_ids)

        result = self.fairness_service._analyze_boolean_dimension(
            self.bool_dim,
            "is_group",
            beneficiary_set,
            base_domain,
            overall_coverage,
            self.partner_model,
        )

        self.assertIsNotNone(result)
        self.assertIn("groups", result)
        self.assertIn("worst_ratio", result)

        keys = [g["key"] for g in result["groups"]]
        self.assertIn("true", keys)
        self.assertIn("false", keys)

    def test_analyze_field_dimension_routing_boolean(self):
        """_analyze_field_dimension routes boolean fields correctly."""
        beneficiary_set = set(self.individuals.ids[:2])
        base_domain = [("id", "in", self.all_ids)]
        overall_coverage = len(beneficiary_set) / len(self.all_ids)

        result = self.fairness_service._analyze_field_dimension(
            self.bool_dim,
            beneficiary_set,
            base_domain,
            overall_coverage,
            self.partner_model,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["attribute"], "fairness_is_group")

    def test_analyze_field_dimension_unsupported_type(self):
        """_analyze_field_dimension with unsupported field type returns None."""
        # 'name' is a char field, which is not handled by _analyze_field_dimension
        dim = self.dim_model.create(
            {
                "name": "fairness_name_dim",
                "label": "Name Dim",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
            }
        )
        beneficiary_set = set(self.individuals.ids[:2])
        base_domain = [("id", "in", self.all_ids)]
        overall_coverage = len(beneficiary_set) / len(self.all_ids)

        result = self.fairness_service._analyze_field_dimension(
            dim,
            beneficiary_set,
            base_domain,
            overall_coverage,
            self.partner_model,
        )

        self.assertIsNone(result)

    def test_analyze_field_dimension_missing_field(self):
        """_analyze_field_dimension with non-existent field returns None."""
        dim = self.dim_model.create(
            {
                "name": "fairness_nonexistent",
                "label": "Nonexistent",
                "dimension_type": "field",
                "field_path": "this_field_does_not_exist",
                "applies_to": "all",
            }
        )
        beneficiary_set = set(self.individuals.ids[:2])
        base_domain = [("id", "in", self.all_ids)]
        overall_coverage = len(beneficiary_set) / len(self.all_ids)

        result = self.fairness_service._analyze_field_dimension(
            dim,
            beneficiary_set,
            base_domain,
            overall_coverage,
            self.partner_model,
        )

        self.assertIsNone(result)

    def test_analyze_field_dimension_no_field_path(self):
        """_analyze_field_dimension with empty field_path returns None."""
        dim = self.dim_model.create(
            {
                "name": "fairness_empty_path",
                "label": "Empty Path",
                "dimension_type": "field",
                "field_path": "name",
                "applies_to": "all",
            }
        )
        # Use SQL to bypass the constraint and set field_path to empty
        self.env.cr.execute(
            "UPDATE spp_demographic_dimension SET field_path = NULL WHERE id = %s",
            (dim.id,),
        )
        dim.invalidate_recordset()

        beneficiary_set = set(self.individuals.ids[:2])
        base_domain = [("id", "in", self.all_ids)]
        overall_coverage = len(beneficiary_set) / len(self.all_ids)

        result = self.fairness_service._analyze_field_dimension(
            dim,
            beneficiary_set,
            base_domain,
            overall_coverage,
            self.partner_model,
        )

        self.assertIsNone(result)

    def test_get_dimensions_all(self):
        """_get_dimensions without names returns all active dimensions."""
        result = self.fairness_service._get_dimensions()
        self.assertTrue(len(result) > 0)
        names = result.mapped("name")
        self.assertIn("fairness_is_group", names)

    def test_get_dimensions_specific_names(self):
        """_get_dimensions with specific names returns only those."""
        result = self.fairness_service._get_dimensions(["fairness_is_group"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result.name, "fairness_is_group")

    def test_get_dimensions_nonexistent_name(self):
        """_get_dimensions with non-existent name returns empty."""
        result = self.fairness_service._get_dimensions(["nonexistent_xyz_999"])
        self.assertEqual(len(result), 0)

    def test_compute_disparity_ratio_zero_coverage(self):
        """_compute_disparity_ratio with zero overall coverage returns 0."""
        result = self.fairness_service._compute_disparity_ratio(0.5, 0)
        self.assertEqual(result, 0.0)

    def test_compute_disparity_ratio_normal(self):
        """_compute_disparity_ratio returns group/overall ratio."""
        result = self.fairness_service._compute_disparity_ratio(0.3, 0.5)
        self.assertAlmostEqual(result, 0.6)

    def test_get_disparity_status_proportional(self):
        """Ratio >= 0.80 is 'proportional'."""
        self.assertEqual(self.fairness_service._get_disparity_status(0.85), "proportional")

    def test_get_disparity_status_low_coverage(self):
        """Ratio between 0.70 and 0.80 is 'low_coverage'."""
        self.assertEqual(self.fairness_service._get_disparity_status(0.75), "low_coverage")

    def test_get_disparity_status_under_represented(self):
        """Ratio < 0.70 is 'under_represented'."""
        self.assertEqual(self.fairness_service._get_disparity_status(0.5), "under_represented")

    def test_analyze_many2one_dimension(self):
        """_analyze_many2one_dimension produces group results."""
        # Use company_id as a many2one field
        company = self.env["res.company"].search([], limit=1)
        for ind in self.individuals:
            ind.write({"company_id": company.id})

        dim = self.dim_model.create(
            {
                "name": "fairness_company",
                "label": "Company",
                "dimension_type": "field",
                "field_path": "company_id",
                "applies_to": "all",
            }
        )
        beneficiary_set = set(self.individuals.ids[:3])
        base_domain = [("id", "in", self.individuals.ids)]
        overall_coverage = len(beneficiary_set) / len(self.individuals.ids)

        result = self.fairness_service._analyze_many2one_dimension(
            dim,
            "company_id",
            beneficiary_set,
            base_domain,
            overall_coverage,
            self.partner_model,
        )

        self.assertIsNotNone(result)
        self.assertIn("groups", result)
        self.assertTrue(len(result["groups"]) > 0)

    def test_analyze_selection_dimension(self):
        """_analyze_selection_dimension with 'type' selection field."""
        dim = self.dim_model.create(
            {
                "name": "fairness_partner_type",
                "label": "Partner Type",
                "dimension_type": "field",
                "field_path": "type",
                "applies_to": "all",
            }
        )
        beneficiary_set = set(self.individuals.ids[:3])
        base_domain = [("id", "in", self.individuals.ids)]
        overall_coverage = len(beneficiary_set) / len(self.individuals.ids)

        result = self.fairness_service._analyze_selection_dimension(
            dim,
            "type",
            beneficiary_set,
            base_domain,
            overall_coverage,
            self.partner_model,
        )

        # May return None if all have same type (no False values filtered out)
        # or a valid result dict
        if result is not None:
            self.assertIn("groups", result)

    def test_compute_fairness_no_population(self):
        """compute_fairness with zero population returns empty fairness."""
        result = self.fairness_service.compute_fairness(
            self.individuals.ids,
            base_domain=[("id", "=", -1)],  # matches nothing
        )
        self.assertEqual(result["equity_score"], 100.0)
        self.assertEqual(result["total_population"], 0)


@tagged("post_install", "-at_install")
class TestPrivacyServiceExtended(TransactionCase):
    """Test privacy service additional methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.privacy_service = cls.env["spp.metric.privacy"]

    # -------------------------------------------------------------------------
    # _find_cells_in_slice
    # -------------------------------------------------------------------------

    def test_find_cells_in_slice_basic(self):
        """_find_cells_in_slice returns cells sharing same dim value."""
        breakdown = {
            "male|urban": {"count": 10},
            "male|rural": {"count": 20},
            "female|urban": {"count": 15},
            "female|rural": {"count": 25},
        }
        result = self.privacy_service._find_cells_in_slice("male|urban", 0, breakdown)
        self.assertIn("male|urban", result)
        self.assertIn("male|rural", result)
        self.assertNotIn("female|urban", result)
        self.assertNotIn("female|rural", result)

    def test_find_cells_in_slice_second_dim(self):
        """_find_cells_in_slice on dim_idx=1 groups by second dimension."""
        breakdown = {
            "male|urban": {"count": 10},
            "male|rural": {"count": 20},
            "female|urban": {"count": 15},
            "female|rural": {"count": 25},
        }
        result = self.privacy_service._find_cells_in_slice("male|urban", 1, breakdown)
        self.assertIn("male|urban", result)
        self.assertIn("female|urban", result)
        self.assertNotIn("male|rural", result)
        self.assertNotIn("female|rural", result)

    def test_find_cells_in_slice_dim_idx_out_of_range(self):
        """_find_cells_in_slice with out-of-range dim_idx returns empty."""
        breakdown = {
            "male|urban": {"count": 10},
            "female|urban": {"count": 15},
        }
        result = self.privacy_service._find_cells_in_slice("male|urban", 5, breakdown)
        self.assertEqual(result, [])

    # -------------------------------------------------------------------------
    # _find_dimension_siblings
    # -------------------------------------------------------------------------

    def test_find_dimension_siblings_basic(self):
        """_find_dimension_siblings returns siblings sharing dim value."""
        breakdown = {
            "male|urban": {"count": 10},
            "male|rural": {"count": 20},
            "female|urban": {"count": 15},
        }
        result = self.privacy_service._find_dimension_siblings("male|urban", 0, breakdown)
        self.assertIn("male|rural", result)
        self.assertNotIn("male|urban", result)  # excludes self
        self.assertNotIn("female|urban", result)

    def test_find_dimension_siblings_dim_idx_out_of_range(self):
        """_find_dimension_siblings with out-of-range dim_idx returns empty."""
        breakdown = {
            "male|urban": {"count": 10},
            "male|rural": {"count": 20},
        }
        result = self.privacy_service._find_dimension_siblings("male|urban", 5, breakdown)
        self.assertEqual(result, [])

    def test_find_dimension_siblings_different_dim_count(self):
        """_find_dimension_siblings ignores keys with different dim count."""
        breakdown = {
            "male|urban": {"count": 10},
            "male|rural": {"count": 20},
            "male": {"count": 30},  # single dimension - should be ignored
        }
        result = self.privacy_service._find_dimension_siblings("male|urban", 0, breakdown)
        self.assertIn("male|rural", result)
        self.assertNotIn("male", result)

    # -------------------------------------------------------------------------
    # _find_siblings
    # -------------------------------------------------------------------------

    def test_find_siblings_single_dimension(self):
        """_find_siblings with single dimension finds all other keys."""
        breakdown = {
            "male": {"count": 10},
            "female": {"count": 20},
            "other": {"count": 5},
        }
        result = self.privacy_service._find_siblings("male", breakdown)
        self.assertIn("female", result)
        self.assertIn("other", result)
        self.assertNotIn("male", result)

    def test_find_siblings_multi_dimension(self):
        """_find_siblings with multi dimension finds keys differing by one part."""
        breakdown = {
            "male|urban": {"count": 10},
            "male|rural": {"count": 20},
            "female|urban": {"count": 15},
            "female|rural": {"count": 25},
        }
        result = self.privacy_service._find_siblings("male|urban", breakdown)
        # Differs by exactly one part
        self.assertIn("male|rural", result)  # differs in 2nd
        self.assertIn("female|urban", result)  # differs in 1st
        self.assertNotIn("female|rural", result)  # differs in both

    # -------------------------------------------------------------------------
    # _get_smallest_sibling
    # -------------------------------------------------------------------------

    def test_get_smallest_sibling(self):
        """_get_smallest_sibling returns key with smallest count."""
        breakdown = {
            "male": {"count": 10},
            "female": {"count": 3},
            "other": {"count": 7},
        }
        result = self.privacy_service._get_smallest_sibling(["male", "female", "other"], breakdown)
        self.assertEqual(result, "female")

    def test_get_smallest_sibling_empty(self):
        """_get_smallest_sibling with empty list returns None."""
        result = self.privacy_service._get_smallest_sibling([], {})
        self.assertIsNone(result)

    def test_get_smallest_sibling_non_dict_cell(self):
        """_get_smallest_sibling skips non-dict cells."""
        breakdown = {
            "male": "not a dict",
            "female": {"count": 3},
        }
        result = self.privacy_service._get_smallest_sibling(["male", "female"], breakdown)
        self.assertEqual(result, "female")

    def test_get_smallest_sibling_suppressed_count(self):
        """_get_smallest_sibling skips cells with non-int count (already suppressed)."""
        breakdown = {
            "male": {"count": "<5", "suppressed": True},
            "female": {"count": 8},
        }
        result = self.privacy_service._get_smallest_sibling(["male", "female"], breakdown)
        self.assertEqual(result, "female")

    # -------------------------------------------------------------------------
    # is_count_suppressed / format_suppressed_count
    # -------------------------------------------------------------------------

    def test_is_count_suppressed_below_threshold(self):
        """Count below threshold is suppressed."""
        self.assertTrue(self.privacy_service.is_count_suppressed(3))

    def test_is_count_suppressed_at_threshold(self):
        """Count at threshold is not suppressed."""
        self.assertFalse(self.privacy_service.is_count_suppressed(5))

    def test_is_count_suppressed_above_threshold(self):
        """Count above threshold is not suppressed."""
        self.assertFalse(self.privacy_service.is_count_suppressed(10))

    def test_is_count_suppressed_non_int(self):
        """Non-int count is not suppressed."""
        self.assertFalse(self.privacy_service.is_count_suppressed("<5"))

    def test_is_count_suppressed_custom_threshold(self):
        """Custom threshold works."""
        self.assertTrue(self.privacy_service.is_count_suppressed(8, k_threshold=10))
        self.assertFalse(self.privacy_service.is_count_suppressed(12, k_threshold=10))

    def test_format_suppressed_count_not_suppressed(self):
        """Non-suppressed count returns str(count)."""
        result = self.privacy_service.format_suppressed_count(10)
        self.assertEqual(result, "10")

    def test_format_suppressed_count_less_than(self):
        """Default display mode is less_than."""
        result = self.privacy_service.format_suppressed_count(3)
        self.assertEqual(result, "<5")

    def test_format_suppressed_count_null(self):
        """Null display mode returns None."""
        result = self.privacy_service.format_suppressed_count(3, display_mode="null")
        self.assertIsNone(result)

    def test_format_suppressed_count_asterisk(self):
        """Asterisk display mode returns '*'."""
        result = self.privacy_service.format_suppressed_count(3, display_mode="asterisk")
        self.assertEqual(result, "*")

    # -------------------------------------------------------------------------
    # _apply_k_anonymity complementary suppression
    # -------------------------------------------------------------------------

    def test_apply_k_anonymity_empty_breakdown(self):
        """Empty breakdown passes through."""
        result = self.privacy_service._apply_k_anonymity({}, 5)
        self.assertEqual(result, {})

    def test_apply_k_anonymity_multi_dim_complementary(self):
        """Multi-dimensional complementary suppression works."""
        breakdown = {
            "male|urban": {"count": 2},  # below threshold
            "male|rural": {"count": 50},
            "female|urban": {"count": 40},
            "female|rural": {"count": 60},
        }
        result = self.privacy_service._apply_k_anonymity(breakdown, 5)
        # male|urban should be suppressed (primary)
        self.assertTrue(result["male|urban"].get("suppressed"))
        # At least one sibling should also be suppressed (complementary)
        suppressed_count = sum(1 for k, v in result.items() if isinstance(v, dict) and v.get("suppressed"))
        self.assertGreaterEqual(suppressed_count, 2)

    def test_apply_k_anonymity_preserves_labels(self):
        """Suppression preserves label/display_name metadata."""
        breakdown = {
            "male": {"count": 2, "label": "Male"},
            "female": {"count": 50, "label": "Female"},
        }
        result = self.privacy_service._apply_k_anonymity(breakdown, 5)
        self.assertEqual(result["male"].get("label"), "Male")


@tagged("post_install", "-at_install")
class TestDistributionServiceEdgeCases(TransactionCase):
    """Test distribution service edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dist_service = cls.env["spp.metric.distribution"]

    def test_empty_distribution(self):
        """_empty_distribution returns zeroed structure."""
        result = self.dist_service._empty_distribution()
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["gini_coefficient"], 0)
        self.assertEqual(result["lorenz_deciles"], [])
        self.assertIn("percentiles", result)
        self.assertEqual(result["percentiles"]["p50"], 0)

    def test_single_value(self):
        """Distribution with a single value computes correctly."""
        result = self.dist_service.compute_distribution([100])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["minimum"], 100)
        self.assertEqual(result["maximum"], 100)
        self.assertEqual(result["mean"], 100)
        self.assertEqual(result["median"], 100)
        self.assertEqual(result["standard_deviation"], 0)
        self.assertEqual(result["gini_coefficient"], 0)

    def test_two_values_even_median(self):
        """Distribution with two values computes median correctly."""
        result = self.dist_service.compute_distribution([100, 200])
        self.assertEqual(result["median"], 150)

    def test_all_zeros_gini(self):
        """Gini coefficient for all-zero amounts is 0."""
        result = self.dist_service.compute_distribution([0, 0, 0])
        self.assertEqual(result["gini_coefficient"], 0)

    def test_perfect_inequality_gini(self):
        """Gini coefficient approaches 1 for extreme inequality."""
        # One person has everything, rest have 0
        amounts = [0] * 99 + [10000]
        result = self.dist_service.compute_distribution(amounts)
        self.assertGreater(result["gini_coefficient"], 0.9)

    def test_lorenz_deciles_count(self):
        """Lorenz deciles always have 10 entries."""
        amounts = list(range(1, 101))
        result = self.dist_service.compute_distribution(amounts)
        self.assertEqual(len(result["lorenz_deciles"]), 10)
        # Last decile should be 100%
        self.assertEqual(result["lorenz_deciles"][-1]["population_share"], 100)
        self.assertAlmostEqual(result["lorenz_deciles"][-1]["income_share"], 100.0)

    def test_percentile_edge(self):
        """Percentile computation on small dataset."""
        result = self.dist_service.compute_distribution([10, 20])
        self.assertEqual(result["percentiles"]["p50"], 15.0)


@tagged("post_install", "-at_install")
class TestPrivacyServiceStripIds(TransactionCase):
    """Test privacy service _strip_individual_ids and enforce access levels."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.privacy_service = cls.env["spp.metric.privacy"]

    # -------------------------------------------------------------------------
    # _strip_individual_ids
    # -------------------------------------------------------------------------

    def test_strip_individual_ids_removes_registrant_ids(self):
        """_strip_individual_ids removes 'registrant_ids' key from result."""
        result = {"total": 10, "registrant_ids": [1, 2, 3]}
        stripped = self.privacy_service._strip_individual_ids(result)
        self.assertNotIn("registrant_ids", stripped)
        self.assertEqual(stripped["total"], 10)

    def test_strip_individual_ids_removes_partner_ids(self):
        """_strip_individual_ids removes 'partner_ids' key from result."""
        result = {"total": 5, "partner_ids": [4, 5]}
        stripped = self.privacy_service._strip_individual_ids(result)
        self.assertNotIn("partner_ids", stripped)

    def test_strip_individual_ids_removes_ids(self):
        """_strip_individual_ids removes 'ids' key from result."""
        result = {"total": 5, "ids": [6, 7, 8]}
        stripped = self.privacy_service._strip_individual_ids(result)
        self.assertNotIn("ids", stripped)

    def test_strip_individual_ids_no_ids_present(self):
        """_strip_individual_ids on result without ID keys returns unchanged."""
        result = {"total": 10, "breakdown": {"male": {"count": 10}}}
        stripped = self.privacy_service._strip_individual_ids(result)
        self.assertIn("total", stripped)
        self.assertIn("breakdown", stripped)

    def test_strip_individual_ids_does_not_modify_original(self):
        """_strip_individual_ids does not mutate the input dict."""
        original = {"total": 10, "registrant_ids": [1, 2]}
        original_copy = dict(original)
        self.privacy_service._strip_individual_ids(original)
        self.assertEqual(original, original_copy)

    def test_strip_individual_ids_removes_ids_from_breakdown_cells(self):
        """_strip_individual_ids removes ID keys from nested breakdown cells."""
        result = {
            "total": 20,
            "breakdown": {
                "male": {"count": 10, "registrant_ids": [1, 2], "partner_ids": [3]},
                "female": {"count": 10, "ids": [4, 5]},
            },
        }
        stripped = self.privacy_service._strip_individual_ids(result)
        male_cell = stripped["breakdown"]["male"]
        female_cell = stripped["breakdown"]["female"]
        self.assertNotIn("registrant_ids", male_cell)
        self.assertNotIn("partner_ids", male_cell)
        self.assertNotIn("ids", female_cell)
        self.assertEqual(male_cell["count"], 10)

    def test_strip_individual_ids_skips_non_dict_breakdown_cells(self):
        """_strip_individual_ids skips breakdown values that are not dicts."""
        result = {
            "total": 10,
            "breakdown": {
                "male": "not a dict",
                "female": {"count": 10, "registrant_ids": [1]},
            },
        }
        # Should not raise an error
        stripped = self.privacy_service._strip_individual_ids(result)
        self.assertEqual(stripped["breakdown"]["male"], "not a dict")
        self.assertNotIn("registrant_ids", stripped["breakdown"]["female"])

    # -------------------------------------------------------------------------
    # enforce() with access_level
    # -------------------------------------------------------------------------

    def test_enforce_individual_access_level_preserves_ids(self):
        """enforce with access_level='individual' does not strip registrant_ids."""
        result = {
            "total": 20,
            "registrant_ids": [1, 2, 3],
            "breakdown": {
                "male": {"count": 10},
                "female": {"count": 10},
            },
        }
        protected = self.privacy_service.enforce(result, access_level="individual")
        self.assertIn("registrant_ids", protected)
        self.assertEqual(protected["registrant_ids"], [1, 2, 3])

    def test_enforce_aggregate_access_level_strips_ids(self):
        """enforce with access_level='aggregate' removes registrant_ids."""
        result = {
            "total": 20,
            "registrant_ids": [1, 2, 3],
            "breakdown": {
                "male": {"count": 10},
                "female": {"count": 10},
            },
        }
        protected = self.privacy_service.enforce(result, access_level="aggregate")
        self.assertNotIn("registrant_ids", protected)

    def test_enforce_aggregate_applies_k_anonymity(self):
        """enforce with access_level='aggregate' applies k-anonymity to breakdown."""
        result = {
            "total": 20,
            "breakdown": {
                "male": {"count": 2},  # below threshold
                "female": {"count": 18},
            },
        }
        protected = self.privacy_service.enforce(result, k_threshold=5, access_level="aggregate")
        self.assertTrue(protected["breakdown"]["male"].get("suppressed"))

    def test_enforce_custom_k_threshold(self):
        """enforce with custom k_threshold suppresses at that threshold."""
        result = {
            "total": 30,
            "breakdown": {
                "male": {"count": 8},  # below custom threshold of 10
                "female": {"count": 22},
            },
        }
        protected = self.privacy_service.enforce(result, k_threshold=10, access_level="aggregate")
        self.assertTrue(protected["breakdown"]["male"].get("suppressed"))

    def test_enforce_custom_k_threshold_not_suppressed(self):
        """enforce with custom k_threshold does not suppress counts above it."""
        result = {
            "total": 30,
            "breakdown": {
                "male": {"count": 15},
                "female": {"count": 15},
            },
        }
        protected = self.privacy_service.enforce(result, k_threshold=10, access_level="aggregate")
        self.assertFalse(protected["breakdown"]["male"].get("suppressed", False))

    def test_enforce_no_breakdown_key(self):
        """enforce on result without 'breakdown' key works without error."""
        result = {"total": 100, "registrant_ids": [1, 2]}
        protected = self.privacy_service.enforce(result, access_level="aggregate")
        self.assertNotIn("breakdown", protected)
        self.assertNotIn("registrant_ids", protected)

    def test_enforce_does_not_modify_original(self):
        """enforce does not mutate the input result dict."""
        result = {
            "total": 10,
            "registrant_ids": [1],
            "breakdown": {"male": {"count": 2}},
        }
        original_ids = result["registrant_ids"][:]
        self.privacy_service.enforce(result, access_level="aggregate")
        # Original should be unchanged
        self.assertIn("registrant_ids", result)
        self.assertEqual(result["registrant_ids"], original_ids)


@tagged("post_install", "-at_install")
class TestDimensionCacheMakeKey(TransactionCase):
    """Test dimension cache _make_registrant_key method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cache_service = cls.env["spp.metric.dimension.cache"]

    def test_make_registrant_key_returns_string(self):
        """_make_registrant_key returns a string."""
        key = self.cache_service._make_registrant_key([1, 2, 3])
        self.assertIsInstance(key, str)

    def test_make_registrant_key_consistent(self):
        """_make_registrant_key returns the same hash for the same IDs."""
        key1 = self.cache_service._make_registrant_key([1, 2, 3])
        key2 = self.cache_service._make_registrant_key([1, 2, 3])
        self.assertEqual(key1, key2)

    def test_make_registrant_key_order_independent(self):
        """_make_registrant_key returns the same hash regardless of input order."""
        key1 = self.cache_service._make_registrant_key([3, 1, 2])
        key2 = self.cache_service._make_registrant_key([1, 2, 3])
        self.assertEqual(key1, key2)

    def test_make_registrant_key_different_ids_differ(self):
        """_make_registrant_key produces different hashes for different ID sets."""
        key1 = self.cache_service._make_registrant_key([1, 2, 3])
        key2 = self.cache_service._make_registrant_key([4, 5, 6])
        self.assertNotEqual(key1, key2)

    def test_make_registrant_key_accepts_frozenset(self):
        """_make_registrant_key accepts a frozenset of IDs."""
        key_list = self.cache_service._make_registrant_key([1, 2, 3])
        key_frozenset = self.cache_service._make_registrant_key(frozenset([1, 2, 3]))
        self.assertEqual(key_list, key_frozenset)

    def test_make_registrant_key_single_id(self):
        """_make_registrant_key works with a single ID."""
        key = self.cache_service._make_registrant_key([42])
        self.assertIsInstance(key, str)
        self.assertTrue(len(key) > 0)

    def test_make_registrant_key_empty_list(self):
        """_make_registrant_key works with an empty list."""
        key = self.cache_service._make_registrant_key([])
        self.assertIsInstance(key, str)

    def test_make_registrant_key_is_md5_length(self):
        """_make_registrant_key returns a 32-character MD5 hex string."""
        key = self.cache_service._make_registrant_key([1, 2, 3])
        self.assertEqual(len(key), 32)


@tagged("post_install", "-at_install")
class TestFairnessExpressionDimension(TransactionCase):
    """Test fairness service _analyze_expression_dimension method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.fairness_service = cls.env["spp.metric.fairness"]
        cls.dim_model = cls.env["spp.demographic.dimension"]

        # Create test registrants
        cls.registrants = cls.partner_model.browse()
        for i in range(6):
            reg = cls.partner_model.create(
                {
                    "name": f"Expr Fairness Registrant {i}",
                    "is_registrant": True,
                    "is_group": i % 2 == 0,
                }
            )
            cls.registrants |= reg

        cls.all_ids = cls.registrants.ids

        # Create expression-type dimension
        cls.expr_dim = cls.dim_model.create(
            {
                "name": "fairness_expr_dim",
                "label": "Expression Dimension",
                "dimension_type": "expression",
                "cel_expression": "record.is_group ? 'group' : 'individual'",
                "applies_to": "all",
                "default_value": "unknown",
            }
        )

    def test_analyze_expression_dimension_no_cel_service(self):
        """_analyze_expression_dimension returns None when CEL service unavailable."""
        beneficiary_set = set(self.all_ids[:3])
        base_domain = [("id", "in", self.all_ids)]
        overall_coverage = len(beneficiary_set) / len(self.all_ids)

        # Patch env.get to return None for CEL service
        with patch.object(type(self.env), "get", return_value=None):
            result = self.fairness_service._analyze_expression_dimension(
                self.expr_dim,
                beneficiary_set,
                base_domain,
                overall_coverage,
                self.partner_model,
            )
        self.assertIsNone(result)

    def test_analyze_expression_dimension_fallback_without_cache(self):
        """_analyze_expression_dimension uses per-record fallback when no cache service."""
        beneficiary_set = set(self.all_ids[:3])
        base_domain = [("id", "in", self.all_ids)]
        overall_coverage = len(beneficiary_set) / len(self.all_ids)

        cel_service = self.env.get("spp.cel.service")
        if not cel_service:
            self.skipTest("CEL service not available")

        # Patch env.get to return cel_service for spp.cel.service but None for cache
        def mock_get(key):
            if key == "spp.cel.service":
                return cel_service
            return None

        with patch.object(type(self.env), "get", side_effect=mock_get):
            result = self.fairness_service._analyze_expression_dimension(
                self.expr_dim,
                beneficiary_set,
                base_domain,
                overall_coverage,
                self.partner_model,
            )

        # If CEL evaluates successfully, result should be a dict with groups
        # If CEL expression fails, evaluate_for_record returns default
        if result is not None:
            self.assertIn("groups", result)
            self.assertIn("attribute", result)
            self.assertEqual(result["attribute"], "fairness_expr_dim")

    def test_analyze_expression_dimension_empty_categories(self):
        """_analyze_expression_dimension returns None when no categories found."""
        beneficiary_set = set(self.all_ids[:3])
        # Domain that matches nothing
        base_domain = [("id", "=", -1)]
        overall_coverage = 0.5

        cel_service = self.env.get("spp.cel.service")
        if not cel_service:
            self.skipTest("CEL service not available")

        result = self.fairness_service._analyze_expression_dimension(
            self.expr_dim,
            beneficiary_set,
            base_domain,
            overall_coverage,
            self.partner_model,
        )
        # Empty population means no categories, so result is None
        self.assertIsNone(result)

    def test_analyze_dimension_routes_to_expression(self):
        """_analyze_dimension routes expression-type dimensions correctly."""
        beneficiary_set = set(self.all_ids[:3])
        base_domain = [("id", "in", self.all_ids)]
        overall_coverage = len(beneficiary_set) / len(self.all_ids)

        # Patch _analyze_expression_dimension to verify it is called
        with patch.object(
            type(self.fairness_service),
            "_analyze_expression_dimension",
            return_value=None,
        ) as mock_method:
            self.fairness_service._analyze_dimension(
                self.expr_dim,
                beneficiary_set,
                base_domain,
                overall_coverage,
                self.partner_model,
            )
            mock_method.assert_called_once()


@tagged("post_install", "-at_install")
class TestBreakdownServiceComprehensive(TransactionCase):
    """Comprehensive tests for breakdown service compute_breakdown."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.breakdown_service = cls.env["spp.metric.breakdown"]
        cls.dim_model = cls.env["spp.demographic.dimension"]

        # Create test registrants: mix of groups and individuals
        cls.individuals = cls.partner_model.browse()
        cls.groups = cls.partner_model.browse()

        for i in range(4):
            ind = cls.partner_model.create(
                {
                    "name": f"Breakdown Individual {i}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            cls.individuals |= ind

        for i in range(3):
            grp = cls.partner_model.create(
                {
                    "name": f"Breakdown Group {i}",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
            cls.groups |= grp

        cls.all_registrants = cls.individuals | cls.groups
        cls.all_ids = cls.all_registrants.ids

        # Create two boolean dimensions for multi-dimensional breakdown
        cls.is_group_dim = cls.dim_model.create(
            {
                "name": "breakdown_is_group",
                "label": "Is Group",
                "dimension_type": "field",
                "field_path": "is_group",
                "applies_to": "all",
            }
        )
        cls.is_registrant_dim = cls.dim_model.create(
            {
                "name": "breakdown_is_registrant",
                "label": "Is Registrant",
                "dimension_type": "field",
                "field_path": "is_registrant",
                "applies_to": "all",
            }
        )

    def test_compute_breakdown_empty_registrant_ids(self):
        """compute_breakdown with empty registrant_ids returns empty dict."""
        result = self.breakdown_service.compute_breakdown([], ["breakdown_is_group"])
        self.assertEqual(result, {})

    def test_compute_breakdown_empty_group_by(self):
        """compute_breakdown with empty group_by returns empty dict."""
        result = self.breakdown_service.compute_breakdown(self.all_ids, [])
        self.assertEqual(result, {})

    def test_compute_breakdown_nonexistent_dimension(self):
        """compute_breakdown with only non-existent dimension names returns empty dict."""
        result = self.breakdown_service.compute_breakdown(self.all_ids, ["this_dimension_does_not_exist_xyz"])
        self.assertEqual(result, {})

    def test_compute_breakdown_single_dimension(self):
        """compute_breakdown with one dimension produces keyed breakdown."""
        result = self.breakdown_service.compute_breakdown(self.all_ids, ["breakdown_is_group"])
        self.assertIsInstance(result, dict)
        self.assertTrue(len(result) > 0)

        # Keys should be single-part (no pipes)
        for key in result:
            self.assertNotIn("|", key)

        # Counts should sum to total
        total = sum(cell["count"] for cell in result.values())
        self.assertEqual(total, len(self.all_ids))

    def test_compute_breakdown_multi_dimensional(self):
        """compute_breakdown with two dimensions produces pipe-separated keys."""
        result = self.breakdown_service.compute_breakdown(
            self.all_ids, ["breakdown_is_group", "breakdown_is_registrant"]
        )
        self.assertIsInstance(result, dict)
        self.assertTrue(len(result) > 0)

        # All keys should be pipe-separated with exactly one pipe
        for key in result:
            parts = key.split("|")
            self.assertEqual(len(parts), 2)

        # Counts should sum to total
        total = sum(cell["count"] for cell in result.values())
        self.assertEqual(total, len(self.all_ids))

    def test_compute_breakdown_cell_structure(self):
        """compute_breakdown cells contain count, statistics, and labels."""
        result = self.breakdown_service.compute_breakdown(self.all_ids, ["breakdown_is_group"])
        for cell in result.values():
            self.assertIn("count", cell)
            self.assertIn("statistics", cell)
            self.assertIn("labels", cell)
            self.assertIsInstance(cell["count"], int)
            self.assertIsInstance(cell["statistics"], dict)
            self.assertIsInstance(cell["labels"], dict)

    def test_compute_breakdown_labels_structure(self):
        """compute_breakdown labels contain value and display for each dimension."""
        result = self.breakdown_service.compute_breakdown(self.all_ids, ["breakdown_is_group"])
        for cell in result.values():
            self.assertIn("breakdown_is_group", cell["labels"])
            dim_label = cell["labels"]["breakdown_is_group"]
            self.assertIn("value", dim_label)
            self.assertIn("display", dim_label)

    def test_compute_breakdown_multi_dim_labels_structure(self):
        """compute_breakdown multi-dim cells contain labels for each dimension."""
        result = self.breakdown_service.compute_breakdown(
            self.all_ids, ["breakdown_is_group", "breakdown_is_registrant"]
        )
        for cell in result.values():
            self.assertIn("breakdown_is_group", cell["labels"])
            self.assertIn("breakdown_is_registrant", cell["labels"])

    def test_compute_breakdown_partial_nonexistent_dimension(self):
        """compute_breakdown with mixed valid/nonexistent names uses only valid ones."""
        result = self.breakdown_service.compute_breakdown(
            self.all_ids,
            ["breakdown_is_group", "nonexistent_dimension_xyz"],
        )
        # Only the valid dimension is used, so keys should be single-part
        self.assertIsInstance(result, dict)
        self.assertTrue(len(result) > 0)
        for key in result:
            # Only the valid dimension is used
            self.assertNotIn("|", key)
