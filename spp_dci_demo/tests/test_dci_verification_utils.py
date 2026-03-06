# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestParseDCIResponse(TransactionCase):
    """Tests for parse_dci_response standalone function."""

    def _get_function(self):
        from odoo.addons.spp_dci_demo.utils.dci_verification import (
            parse_dci_response,
        )

        return parse_dci_response

    def test_dci_format_success_with_data(self):
        """Standard DCI response with successful status and data returns 'verified'."""
        parse = self._get_function()
        response = {
            "header": {"status": "succ"},
            "message": {
                "search_response": [
                    {
                        "status": "succ",
                        "data": [{"name": {"given_name": "John"}}],
                    }
                ]
            },
        }
        self.assertEqual(parse(response), "verified")

    def test_dci_format_success_no_data(self):
        """DCI response with success status but empty data returns 'not_found'."""
        parse = self._get_function()
        response = {
            "header": {"status": "succ"},
            "message": {
                "search_response": [
                    {
                        "status": "succ",
                        "data": [],
                    }
                ]
            },
        }
        self.assertEqual(parse(response), "not_found")

    def test_dci_format_rejected_header(self):
        """DCI response with rejected header status returns 'error'."""
        parse = self._get_function()
        response = {
            "header": {"status": "rjct"},
            "message": {"search_response": []},
        }
        self.assertEqual(parse(response), "error")

    def test_dci_format_rejected_search_response(self):
        """DCI response with rejected search_response item returns 'error'."""
        parse = self._get_function()
        response = {
            "header": {"status": "succ"},
            "message": {
                "search_response": [
                    {
                        "status": "rjct",
                        "data": [],
                    }
                ]
            },
        }
        self.assertEqual(parse(response), "error")

    def test_dci_format_empty_search_response(self):
        """DCI response with empty search_response list returns 'not_found'."""
        parse = self._get_function()
        response = {
            "header": {"status": "succ"},
            "message": {"search_response": []},
        }
        self.assertEqual(parse(response), "not_found")

    def test_opencrvs_direct_format_with_identifier(self):
        """OpenCRVS direct response with 'identifier' key returns 'verified'."""
        parse = self._get_function()
        response = {
            "identifier": "BRN-12345",
            "name": {"given_name": "John", "surname": "Doe"},
        }
        self.assertEqual(parse(response), "verified")

    def test_opencrvs_direct_format_with_name_only(self):
        """OpenCRVS direct response with 'name' key returns 'verified'."""
        parse = self._get_function()
        response = {
            "name": {"given_name": "John", "surname": "Doe"},
        }
        self.assertEqual(parse(response), "verified")

    def test_unexpected_format_returns_not_found(self):
        """Unknown response structure returns 'not_found'."""
        parse = self._get_function()
        response = {"something_else": True}
        self.assertEqual(parse(response), "not_found")

    def test_empty_dict_returns_not_found(self):
        """Empty dict returns 'not_found'."""
        parse = self._get_function()
        self.assertEqual(parse({}), "not_found")


@tagged("post_install", "-at_install")
class TestExtractPersonFromDCIResponse(TransactionCase):
    """Tests for extract_person_from_dci_response standalone function."""

    def _get_function(self):
        from odoo.addons.spp_dci_demo.utils.dci_verification import (
            extract_person_from_dci_response,
        )

        return extract_person_from_dci_response

    def test_dci_format_list_data(self):
        """Extract person from standard DCI format with data as list."""
        extract = self._get_function()
        response = {
            "message": {
                "search_response": [
                    {
                        "status": "succ",
                        "data": [
                            {
                                "name": {"given_name": "Jane", "surname": "Doe"},
                                "birth_date": "2024-01-15",
                                "sex": "Female",
                            }
                        ],
                    }
                ]
            },
        }
        result = extract(response)
        self.assertIsNotNone(result)
        self.assertEqual(result["given_name"], "JANE")
        self.assertEqual(result["family_name"], "DOE")
        self.assertEqual(result["birth_date"], "2024-01-15")
        self.assertEqual(result["sex"], "female")

    def test_dci_format_dict_data(self):
        """Extract person from DCI format with data as dict."""
        extract = self._get_function()
        response = {
            "message": {
                "search_response": [
                    {
                        "status": "succ",
                        "data": {
                            "name": {"given_name": "Bob", "surname": "Smith"},
                            "birthdate": "2023-06-01",
                            "gender": "Male",
                        },
                    }
                ]
            },
        }
        result = extract(response)
        self.assertIsNotNone(result)
        self.assertEqual(result["given_name"], "BOB")
        self.assertEqual(result["family_name"], "SMITH")
        self.assertEqual(result["birth_date"], "2023-06-01")
        self.assertEqual(result["sex"], "male")

    def test_opencrvs_direct_format(self):
        """Extract person from OpenCRVS direct response format."""
        extract = self._get_function()
        response = {
            "identifier": "BRN-12345",
            "name": {"given_name": "Alice", "surname": "Johnson"},
            "birth_date": "2024-03-20",
            "sex": "Female",
        }
        result = extract(response)
        self.assertIsNotNone(result)
        self.assertEqual(result["given_name"], "ALICE")
        self.assertEqual(result["family_name"], "JOHNSON")
        self.assertEqual(result["birth_date"], "2024-03-20")
        self.assertEqual(result["sex"], "female")

    def test_name_as_string(self):
        """Extract person when name is a plain string."""
        extract = self._get_function()
        response = {
            "name": "John Doe",
        }
        result = extract(response)
        self.assertIsNotNone(result)
        self.assertEqual(result["given_name"], "JOHN DOE")
        self.assertNotIn("family_name", result)

    def test_no_person_data(self):
        """Return None when no person data can be extracted."""
        extract = self._get_function()
        response = {"something_else": True}
        self.assertIsNone(extract(response))

    def test_empty_search_response(self):
        """Return None when search_response is empty."""
        extract = self._get_function()
        response = {
            "message": {"search_response": []},
        }
        self.assertIsNone(extract(response))

    def test_empty_data_in_search_response(self):
        """Return None when data in search_response is empty."""
        extract = self._get_function()
        response = {
            "message": {
                "search_response": [
                    {"status": "succ", "data": []},
                ]
            },
        }
        self.assertIsNone(extract(response))


@tagged("post_install", "-at_install")
class TestCheckDataMatches(TransactionCase):
    """Tests for check_data_matches standalone function."""

    def _get_function(self):
        from odoo.addons.spp_dci_demo.utils.dci_verification import (
            check_data_matches,
        )

        return check_data_matches

    def test_all_fields_match(self):
        """All fields matching returns (True, [])."""
        check = self._get_function()
        person_data = {
            "given_name": "JOHN",
            "family_name": "DOE",
            "birth_date": "2024-01-15",
            "sex": "male",
        }
        matches, mismatches = check(
            person_data,
            given_name="John",
            family_name="Doe",
            birthdate=date(2024, 1, 15),
            gender_display="Male",
        )
        self.assertTrue(matches)
        self.assertEqual(mismatches, [])

    def test_given_name_mismatch(self):
        """Given name mismatch returns (False, [mismatch info])."""
        check = self._get_function()
        person_data = {
            "given_name": "JOHN",
            "family_name": "DOE",
        }
        matches, mismatches = check(
            person_data,
            given_name="Jane",
            family_name="Doe",
            birthdate=None,
            gender_display=None,
        )
        self.assertFalse(matches)
        self.assertEqual(len(mismatches), 1)
        self.assertIn("given_name", mismatches[0])

    def test_family_name_mismatch(self):
        """Family name mismatch returns (False, [mismatch info])."""
        check = self._get_function()
        person_data = {
            "given_name": "JOHN",
            "family_name": "DOE",
        }
        matches, mismatches = check(
            person_data,
            given_name="John",
            family_name="Smith",
            birthdate=None,
            gender_display=None,
        )
        self.assertFalse(matches)
        self.assertEqual(len(mismatches), 1)
        self.assertIn("family_name", mismatches[0])

    def test_birthdate_mismatch(self):
        """Birthdate mismatch returns (False, [mismatch info])."""
        check = self._get_function()
        person_data = {
            "birth_date": "2024-01-15",
        }
        matches, mismatches = check(
            person_data,
            given_name=None,
            family_name=None,
            birthdate=date(2024, 6, 20),
            gender_display=None,
        )
        self.assertFalse(matches)
        self.assertEqual(len(mismatches), 1)
        self.assertIn("birthdate", mismatches[0])

    def test_gender_mismatch(self):
        """Gender mismatch returns (False, [mismatch info])."""
        check = self._get_function()
        person_data = {
            "sex": "male",
        }
        matches, mismatches = check(
            person_data,
            given_name=None,
            family_name=None,
            birthdate=None,
            gender_display="Female",
        )
        self.assertFalse(matches)
        self.assertEqual(len(mismatches), 1)
        self.assertIn("gender", mismatches[0])

    def test_multiple_mismatches(self):
        """Multiple mismatches returns all mismatch details."""
        check = self._get_function()
        person_data = {
            "given_name": "JOHN",
            "family_name": "DOE",
            "birth_date": "2024-01-15",
            "sex": "male",
        }
        matches, mismatches = check(
            person_data,
            given_name="Jane",
            family_name="Smith",
            birthdate=date(2024, 6, 20),
            gender_display="Female",
        )
        self.assertFalse(matches)
        self.assertEqual(len(mismatches), 4)

    def test_missing_dci_fields_still_match(self):
        """When DCI data doesn't have a field, it's not considered a mismatch."""
        check = self._get_function()
        person_data = {
            "given_name": "JOHN",
        }
        matches, mismatches = check(
            person_data,
            given_name="John",
            family_name="Doe",
            birthdate=date(2024, 1, 15),
            gender_display="Male",
        )
        self.assertTrue(matches)
        self.assertEqual(mismatches, [])

    def test_missing_cr_fields_still_match(self):
        """When CR data is None/empty, those fields are not compared."""
        check = self._get_function()
        person_data = {
            "given_name": "JOHN",
            "family_name": "DOE",
            "birth_date": "2024-01-15",
            "sex": "male",
        }
        matches, mismatches = check(
            person_data,
            given_name="John",
            family_name="Doe",
            birthdate=None,
            gender_display=None,
        )
        self.assertTrue(matches)
        self.assertEqual(mismatches, [])

    def test_case_insensitive_name_comparison(self):
        """Name comparison is case-insensitive."""
        check = self._get_function()
        person_data = {
            "given_name": "JOHN",
            "family_name": "DOE",
        }
        matches, mismatches = check(
            person_data,
            given_name="john",
            family_name="doe",
            birthdate=None,
            gender_display=None,
        )
        self.assertTrue(matches)
        self.assertEqual(mismatches, [])

    def test_whitespace_stripped_from_names(self):
        """Leading/trailing whitespace is stripped before comparison."""
        check = self._get_function()
        person_data = {
            "given_name": "JOHN",
        }
        matches, mismatches = check(
            person_data,
            given_name="  John  ",
            family_name=None,
            birthdate=None,
            gender_display=None,
        )
        self.assertTrue(matches)
        self.assertEqual(mismatches, [])
