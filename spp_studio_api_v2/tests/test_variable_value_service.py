# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for VariableValueService."""

import time
from datetime import datetime

from odoo import fields
from odoo.tests.common import TransactionCase


class TestVariableValueService(TransactionCase):
    """Test cases for VariableValueService."""

    def setUp(self):
        super().setUp()
        # Use unique ID suffix to avoid collisions with other tests
        self._test_id = int(time.time() * 1000)
        self._var_name = f"test_var_{self._test_id}"

        # Create test partner
        self.test_partner = self.env["res.partner"].create(
            {
                "name": f"Test Subject {self._test_id}",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create test variable with unique name
        self.test_variable = self.env["spp.cel.variable"].create(
            {
                "name": self._var_name,
                "cel_accessor": self._var_name,
                "source_type": "field",
                "value_type": "number",
                "state": "active",
                "applies_to": "both",
            }
        )

        # Create test data value
        self.test_value = self.env["spp.data.value"].create(
            {
                "variable_name": self._var_name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "period_key": "current",
                "value_json": {"value": 42},
                "value_type": "number",
                "source_type": "computed",
                "recorded_at": fields.Datetime.now(),
            }
        )

    def test_get_values_for_subject(self):
        """Test fetching variable values for a subject."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        result = service.get_values_for_subject(
            self.test_partner.id,
            variable_names=[self._var_name],
            period_key="current",
        )

        self.assertIn(self._var_name, result)
        self.assertEqual(result[self._var_name]["value"], 42)
        self.assertEqual(result[self._var_name]["periodKey"], "current")
        self.assertEqual(result[self._var_name]["sourceType"], "computed")

    def test_get_values_for_subject_all_variables(self):
        """Test fetching all variable values for a subject."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        # Using None should return all cached values
        result = service.get_values_for_subject(
            self.test_partner.id,
            variable_names=None,
            period_key="current",
        )

        self.assertIn(self._var_name, result)

    def test_get_values_nonexistent_variable(self):
        """Test fetching values for non-existent variable."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        result = service.get_values_for_subject(
            self.test_partner.id,
            variable_names=["nonexistent_var"],
            period_key="current",
        )

        self.assertEqual(result, {})

    def test_get_values_for_subjects_bulk(self):
        """Test bulk fetching of variable values."""
        from ..services.variable_value_service import VariableValueService

        # Create another partner with a value
        partner2 = self.env["res.partner"].create(
            {
                "name": f"Test Subject 2 {self._test_id}",
                "is_registrant": True,
            }
        )
        self.env["spp.data.value"].create(
            {
                "variable_name": self._var_name,
                "subject_model": "res.partner",
                "subject_id": partner2.id,
                "period_key": "current",
                "value_json": {"value": 100},
                "value_type": "number",
                "source_type": "computed",
                "recorded_at": fields.Datetime.now(),
            }
        )

        service = VariableValueService(self.env)

        result = service.get_values_for_subjects(
            [self.test_partner.id, partner2.id],
            variable_names=[self._var_name],
            period_key="current",
        )

        self.assertIn(self.test_partner.id, result)
        self.assertIn(partner2.id, result)
        self.assertEqual(result[self.test_partner.id][self._var_name]["value"], 42)
        self.assertEqual(result[partner2.id][self._var_name]["value"], 100)

    def test_get_available_variables(self):
        """Test listing available variables."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        result = service.get_available_variables(resource_type="both")

        # Should include our test variable
        var_names = [v["name"] for v in result]
        self.assertIn(self._var_name, var_names)

    def test_stale_value_handling(self):
        """Test handling of stale (expired) values."""
        from ..services.variable_value_service import VariableValueService

        # Mark value as stale
        self.test_value.write({"is_stale": True})

        service = VariableValueService(self.env)

        # Should include stale by default
        result = service.get_values_for_subject(
            self.test_partner.id,
            variable_names=[self._var_name],
            include_stale=True,
        )
        self.assertIn(self._var_name, result)
        self.assertTrue(result[self._var_name]["isStale"])

        # Should exclude when include_stale=False
        result = service.get_values_for_subject(
            self.test_partner.id,
            variable_names=[self._var_name],
            include_stale=False,
        )
        self.assertEqual(result, {})

        # Reset for other tests
        self.test_value.write({"is_stale": False})


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestVariableValueServiceEdgeCases(TransactionCase):
    """Test edge cases and error handling for VariableValueService."""

    def test_invalid_partner_id_negative(self):
        """Test handling of negative partner_id."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        # Negative ID should return empty dict
        result = service.get_values_for_subject(
            partner_id=-1,
            variable_names=["test_var"],
            period_key="current",
        )

        self.assertEqual(result, {})

    def test_invalid_partner_id_zero(self):
        """Test handling of zero partner_id."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        # Zero ID should return empty dict
        result = service.get_values_for_subject(
            partner_id=0,
            variable_names=["test_var"],
            period_key="current",
        )

        self.assertEqual(result, {})

    def test_nonexistent_partner_id(self):
        """Test handling of non-existent partner_id."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        # Very large ID that doesn't exist should return empty dict
        result = service.get_values_for_subject(
            partner_id=999999999,
            variable_names=["test_var"],
            period_key="current",
        )

        self.assertEqual(result, {})

    def test_batch_size_limit_enforced(self):
        """Test that large batch is handled correctly without errors."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        # Create a large list of partner IDs
        large_batch = list(range(1, 1001))

        # Should not raise an error with large batch
        result = service.get_values_for_subjects(
            partner_ids=large_batch,
            variable_names=["some_var"],
            period_key="current",
        )

        # Service should return a dict (empty or with entries, depending on model availability)
        self.assertIsInstance(result, dict)
        # If model is available, should have entries for all IDs
        # If model is not available (edge case), result may be empty
        self.assertTrue(len(result) == 0 or len(result) == len(large_batch))

    def test_empty_partner_ids_list(self):
        """Test handling of empty partner_ids list."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        result = service.get_values_for_subjects(
            partner_ids=[],
            variable_names=["test_var"],
            period_key="current",
        )

        self.assertEqual(result, {})

    def test_variable_name_empty_string(self):
        """Test handling of empty string in variable names."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        # Create test partner
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )

        # Empty string in variable names should be handled
        result = service.get_values_for_subject(
            partner_id=partner.id,
            variable_names=["", "test_var"],
            period_key="current",
        )

        # Should not include empty string key
        self.assertNotIn("", result)

    def test_period_key_special_characters(self):
        """Test handling of period_key with special characters."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        # Create test partner
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )

        # Period key with special chars should work (it's just a string)
        result = service.get_values_for_subject(
            partner_id=partner.id,
            variable_names=["test_var"],
            period_key="2024-Q1/special",
        )

        # Should return empty dict (no values for this period)
        self.assertEqual(result, {})

    def test_value_json_without_value_key(self):
        """Test handling of value_json that doesn't have 'value' key."""
        import time

        from ..services.variable_value_service import VariableValueService

        unique_id = int(time.time() * 1000)
        var_name = f"raw_var_{unique_id}"

        # Create test partner
        partner = self.env["res.partner"].create(
            {
                "name": f"Test Partner {unique_id}",
                "is_registrant": True,
            }
        )

        # Create data value with non-standard value_json
        self.env["spp.data.value"].create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": partner.id,
                "period_key": "current",
                "value_json": 42,  # Direct value, not {"value": 42}
                "value_type": "number",
                "source_type": "computed",
                "recorded_at": fields.Datetime.now(),
            }
        )

        service = VariableValueService(self.env)

        result = service.get_values_for_subject(
            partner_id=partner.id,
            variable_names=[var_name],
            period_key="current",
        )

        # Should use the raw value
        self.assertIn(var_name, result)
        self.assertEqual(result[var_name]["value"], 42)

    def test_value_json_complex_structure(self):
        """Test handling of complex value_json structure."""
        import time

        from ..services.variable_value_service import VariableValueService

        unique_id = int(time.time() * 1000)
        var_name = f"complex_var_{unique_id}"

        # Create test partner
        partner = self.env["res.partner"].create(
            {
                "name": f"Test Partner {unique_id}",
                "is_registrant": True,
            }
        )

        # Create data value with complex value_json
        complex_value = {
            "value": {"nested": {"data": "here"}, "count": 5},
        }
        self.env["spp.data.value"].create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": partner.id,
                "period_key": "current",
                "value_json": complex_value,
                "value_type": "json",
                "source_type": "computed",
                "recorded_at": fields.Datetime.now(),
            }
        )

        service = VariableValueService(self.env)

        result = service.get_values_for_subject(
            partner_id=partner.id,
            variable_names=[var_name],
            period_key="current",
        )

        # Should extract the complex value correctly
        self.assertIn(var_name, result)
        self.assertEqual(result[var_name]["value"]["count"], 5)

    def test_get_available_variables_no_category(self):
        """Test get_available_variables with variables that have no category."""
        import time

        from ..services.variable_value_service import VariableValueService

        unique_id = int(time.time() * 1000)
        accessor_name = f"no_cat_var_{unique_id}"

        # Create variable without category
        self.env["spp.cel.variable"].create(
            {
                "name": f"No Category Var {unique_id}",
                "cel_accessor": accessor_name,
                "source_type": "field",
                "value_type": "string",
                "state": "active",
                "applies_to": "both",
                # No category_id
            }
        )

        service = VariableValueService(self.env)

        result = service.get_available_variables(resource_type="both")

        # Should include variable without category
        no_cat_var = next(
            (v for v in result if v["name"] == accessor_name),
            None,
        )
        self.assertIsNotNone(no_cat_var)
        self.assertIsNone(no_cat_var.get("category"))

    def test_compute_variable_value_nonexistent_variable(self):
        """Test compute_variable_value with non-existent variable."""
        from ..services.variable_value_service import VariableValueService

        service = VariableValueService(self.env)

        # Create test partner
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )

        result = service.compute_variable_value(
            partner_id=partner.id,
            variable_name="nonexistent_variable",
        )

        self.assertIsNone(result)

    def test_compute_variable_value_inactive_variable(self):
        """Test compute_variable_value with inactive variable."""
        from ..services.variable_value_service import VariableValueService

        # Create inactive variable
        self.env["spp.cel.variable"].create(
            {
                "name": "Inactive Var",
                "cel_accessor": "inactive_var",
                "source_type": "field",
                "value_type": "string",
                "state": "inactive",
                "applies_to": "both",
                "source_model": "res.partner",
                "source_field": "name",
            }
        )

        # Create test partner
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )

        service = VariableValueService(self.env)

        result = service.compute_variable_value(
            partner_id=partner.id,
            variable_name="inactive_var",
        )

        # Should return None for inactive variable
        self.assertIsNone(result)

    def test_compute_variable_value_non_field_type(self):
        """Test compute_variable_value with non-field variable type."""
        from ..services.variable_value_service import VariableValueService

        # Create computed variable (not field type)
        self.env["spp.cel.variable"].create(
            {
                "name": "Computed Var",
                "cel_accessor": "computed_var",
                "source_type": "computed",
                "value_type": "number",
                "state": "active",
                "applies_to": "both",
            }
        )

        # Create test partner
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )

        service = VariableValueService(self.env)

        result = service.compute_variable_value(
            partner_id=partner.id,
            variable_name="computed_var",
        )

        # Should return None for non-field variables
        self.assertIsNone(result)
