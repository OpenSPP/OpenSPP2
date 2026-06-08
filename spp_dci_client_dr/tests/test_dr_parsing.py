# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pure-function tests for dr_parsing helpers.

These tests do not need the Odoo env, but inherit from ``TransactionCase``
so the Odoo test runner picks them up at post_install."""

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestUnwrapSearchData(TransactionCase):
    """Tests for unwrap_search_data."""

    def _fn(self, data):
        from odoo.addons.spp_dci_client_dr.services.dr_parsing import unwrap_search_data

        return unwrap_search_data(data)

    def test_none_returns_empty_list(self):
        self.assertEqual(self._fn(None), [])

    def test_empty_dict_returns_empty_list(self):
        self.assertEqual(self._fn({}), [])

    def test_spec_envelope_returns_reg_records(self):
        data = {
            "version": "1.0.0",
            "reg_record_type": "PERSON",
            "reg_records": [{"x": 1}, {"x": 2}],
        }
        self.assertEqual(self._fn(data), [{"x": 1}, {"x": 2}])

    def test_spec_envelope_empty_reg_records_returns_empty_list(self):
        data = {
            "version": "1.0.0",
            "reg_record_type": "PERSON",
            "reg_records": [],
        }
        self.assertEqual(self._fn(data), [])

    def test_spec_envelope_missing_reg_records_returns_empty_list(self):
        data = {
            "version": "1.0.0",
            "reg_record_type": "PERSON",
        }
        self.assertEqual(self._fn(data), [])

    def test_spec_envelope_none_reg_records_returns_empty_list(self):
        data = {
            "version": "1.0.0",
            "reg_records": None,
        }
        self.assertEqual(self._fn(data), [])

    def test_unexpected_list_returns_empty_and_warns(self):
        with self.assertLogs("odoo.addons.spp_dci_client_dr.services.dr_parsing", level="WARNING"):
            result = self._fn([{"a": 1}])
        self.assertEqual(result, [])

    def test_unexpected_int_returns_empty_and_warns(self):
        with self.assertLogs("odoo.addons.spp_dci_client_dr.services.dr_parsing", level="WARNING"):
            result = self._fn(42)
        self.assertEqual(result, [])

    def test_unexpected_string_returns_empty_and_warns(self):
        with self.assertLogs("odoo.addons.spp_dci_client_dr.services.dr_parsing", level="WARNING"):
            result = self._fn("not-a-dict")
        self.assertEqual(result, [])

    def test_reg_records_non_list_returns_empty_and_warns(self):
        """If reg_records is present but not a list, return [] and warn rather than
        passing garbage downstream where records[0].get(...) would crash."""
        data = {
            "version": "1.0.0",
            "reg_records": "oops",
        }
        with self.assertLogs("odoo.addons.spp_dci_client_dr.services.dr_parsing", level="WARNING"):
            result = self._fn(data)
        self.assertEqual(result, [])


@tagged("post_install", "-at_install")
class TestExtractDisabilityData(TransactionCase):
    """Tests for extract_disability_data."""

    def _fn(self, record):
        from odoo.addons.spp_dci_client_dr.services.dr_parsing import extract_disability_data

        return extract_disability_data(record)

    def test_approved_with_impairments(self):
        record = {
            "disability_status": "Approved",
            "disability_details": [{"impairment_type": "Physical"}],
        }
        result = self._fn(record)
        self.assertTrue(result["has_disability"])
        self.assertEqual(result["disability_types"], ["Physical"])
        self.assertEqual(result["functional_scores"], {})
        self.assertIs(result["raw_data"], record)

    def test_approved_no_disability_details(self):
        record = {
            "disability_status": "Approved",
        }
        result = self._fn(record)
        self.assertTrue(result["has_disability"])
        self.assertEqual(result["disability_types"], [])

    def test_rejected_impairments_still_false(self):
        """Explicit rejection overrides impairment list."""
        record = {
            "disability_status": "Rejected",
            "disability_details": [{"impairment_type": "Physical"}],
        }
        result = self._fn(record)
        self.assertFalse(result["has_disability"])

    def test_empty_status_with_impairments_is_true(self):
        """Empty status is ambiguous; fall back to impairment list signal."""
        record = {
            "disability_status": "",
            "disability_details": [{"impairment_type": "X"}],
        }
        result = self._fn(record)
        self.assertTrue(result["has_disability"])

    def test_empty_status_no_impairments_is_false(self):
        """Empty status with no impairments resolves to False."""
        record = {
            "disability_status": "",
        }
        result = self._fn(record)
        self.assertFalse(result["has_disability"])

    def test_unknown_status_with_impairments_warns_and_is_true(self):
        """Unknown non-empty status emits a WARNING and falls back to impairment list."""
        record = {
            "disability_status": "Pending",
            "disability_details": [{"impairment_type": "X"}],
        }
        with self.assertLogs("odoo.addons.spp_dci_client_dr.services.dr_parsing", level="WARNING") as cm:
            result = self._fn(record)
        self.assertTrue(result["has_disability"])
        self.assertTrue(any("Pending" in line for line in cm.output))

    def test_unknown_status_no_impairments_warns_and_is_false(self):
        """Unknown status with no impairments resolves to False after warning."""
        record = {
            "disability_status": "Pending",
        }
        with self.assertLogs("odoo.addons.spp_dci_client_dr.services.dr_parsing", level="WARNING") as cm:
            result = self._fn(record)
        self.assertFalse(result["has_disability"])
        self.assertTrue(any("Pending" in line for line in cm.output))

    def test_case_insensitive_approved(self):
        record = {"disability_status": "approved"}
        result = self._fn(record)
        self.assertTrue(result["has_disability"])

    def test_case_insensitive_rejected(self):
        record = {"disability_status": "REJECTED"}
        result = self._fn(record)
        self.assertFalse(result["has_disability"])

    def test_case_insensitive_registered(self):
        record = {"disability_status": "Registered"}
        result = self._fn(record)
        self.assertTrue(result["has_disability"])

    def test_assessment_date_from_last_updated(self):
        record = {
            "disability_status": "Approved",
            "last_updated": "2024-01-01T00:00:00Z",
        }
        result = self._fn(record)
        self.assertEqual(result["assessment_date"], date(2024, 1, 1))

    def test_assessment_date_fallback_to_registration_date(self):
        record = {
            "disability_status": "Approved",
            "registration_date": "2023-06-15T00:00:00Z",
        }
        result = self._fn(record)
        self.assertEqual(result["assessment_date"], date(2023, 6, 15))

    def test_last_updated_takes_precedence_over_registration_date(self):
        record = {
            "disability_status": "Approved",
            "last_updated": "2024-01-01T00:00:00Z",
            "registration_date": "2023-06-15T00:00:00Z",
        }
        result = self._fn(record)
        self.assertEqual(result["assessment_date"], date(2024, 1, 1))

    def test_assessment_date_plain_iso_date(self):
        record = {
            "disability_status": "Approved",
            "last_updated": "2024-03-10",
        }
        result = self._fn(record)
        self.assertEqual(result["assessment_date"], date(2024, 3, 10))

    def test_assessment_date_unparseable_returns_none_and_warns(self):
        record = {
            "disability_status": "Approved",
            "last_updated": "not a date",
        }
        with self.assertLogs("odoo.addons.spp_dci_client_dr.services.dr_parsing", level="WARNING"):
            result = self._fn(record)
        self.assertIsNone(result["assessment_date"])

    def test_assessment_date_missing_returns_none(self):
        record = {"disability_status": "Approved"}
        result = self._fn(record)
        self.assertIsNone(result["assessment_date"])

    def test_disability_details_none_returns_empty_list(self):
        """Explicit null on the wire must not crash the parser."""
        record = {
            "disability_status": "Approved",
            "disability_details": None,
        }
        result = self._fn(record)
        self.assertEqual(result["disability_types"], [])
        self.assertTrue(result["has_disability"])

    def test_legacy_truthy_token_no_longer_approved(self):
        """`yes` / `true` are not spec status tokens. Treated as unknown,
        which logs a WARN and falls back to the impairment list."""
        record = {"disability_status": "yes"}
        with self.assertLogs("odoo.addons.spp_dci_client_dr.services.dr_parsing", level="WARNING"):
            result = self._fn(record)
        self.assertFalse(result["has_disability"])

    def test_disability_details_missing_impairment_type_skipped(self):
        record = {
            "disability_status": "Approved",
            "disability_details": [
                {"impairment_level": "Severe"},  # no impairment_type
                {"impairment_type": "Vision"},
            ],
        }
        result = self._fn(record)
        self.assertEqual(result["disability_types"], ["Vision"])

    def test_source_registry_field(self):
        record = {
            "disability_status": "Approved",
            "source_registry": "National DR",
        }
        result = self._fn(record)
        self.assertEqual(result["source_registry"], "National DR")

    def test_source_registry_fallback_to_registry_name(self):
        record = {
            "disability_status": "Approved",
            "registry_name": "Regional DR",
        }
        result = self._fn(record)
        self.assertEqual(result["source_registry"], "Regional DR")


@tagged("post_install", "-at_install")
class TestExtractFunctionalScores(TransactionCase):
    """Tests for extract_functional_scores."""

    def _fn(self, record):
        from odoo.addons.spp_dci_client_dr.services.dr_parsing import extract_functional_scores

        return extract_functional_scores(record)

    def test_spec_record_returns_empty_dict(self):
        record = {
            "disability_status": "Approved",
            "disability_details": [{"impairment_type": "Physical"}],
        }
        self.assertEqual(self._fn(record), {})

    def test_empty_record_returns_empty_dict(self):
        self.assertEqual(self._fn({}), {})

    def test_record_with_arbitrary_keys_returns_empty_dict(self):
        """The function is intentionally a no-op until the spec adds numeric scores."""
        record = {
            "functional_vision": 3,
            "hearing_score": 1,
            "mobility": 4,
            "disability_details": [{"impairment_level": "Severe"}],
        }
        self.assertEqual(self._fn(record), {})
