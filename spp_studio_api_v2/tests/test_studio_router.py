# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Studio API router endpoints."""

import json
from datetime import datetime

from odoo.tests.common import HttpCase

from odoo.addons.spp_api_v2.tests.common import ApiV2TestCase


class TestStudioRouterEndpoints(ApiV2TestCase, HttpCase):
    """Test Studio API router endpoints with security and functional tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test data
        cls.test_individual = cls.create_test_individual(
            name="Test Individual",
            identifier_value="IND-STUDIO-001",
        )
        cls.test_group = cls.create_test_group(
            name="Test Group",
            identifier_value="GRP-STUDIO-001",
        )

        # Create Studio field
        cls.placement_zone = cls.env["spp.studio.placement.zone"].create(
            {
                "name": "Custom Fields",
                "code": "custom_fields",
                "sequence": 10,
                "tab_name": "Custom",
                "xpath_expression": "//page[@name='custom_fields']",
            }
        )

        cls.studio_field = cls.env["spp.studio.field"].create(
            {
                "label": "Farm Size",
                "technical_name": "x_farm_size",
                "field_type": "decimal",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "placement_zone_id": cls.placement_zone.id,
                "help_text": "Size of farm in hectares",
                "is_required": False,
            }
        )

        # Get or create CEL variable category
        cls.variable_category = cls.env["spp.cel.variable.category"].search([("code", "=", "demographics")], limit=1)
        if not cls.variable_category:
            cls.variable_category = cls.env["spp.cel.variable.category"].create(
                {
                    "name": "Demographics",
                    "code": "demographics",
                    "sequence": 1,
                }
            )

        # Get or create CEL variable (avoid unique constraint on cel_accessor)
        cls.cel_variable = cls.env["spp.cel.variable"].search(
            [("cel_accessor", "=", "age"), ("applies_to", "=", "individual")], limit=1
        )
        if not cls.cel_variable:
            cls.cel_variable = cls.env["spp.cel.variable"].create(
                {
                    "name": "Age",
                    "cel_accessor": "age",
                    "source_type": "field",
                    "value_type": "number",
                    "state": "active",
                    "applies_to": "individual",
                    "source_model": "res.partner",
                    "source_field": "age",
                    "period_granularity": "current",
                    "supports_historical": False,
                    "category_id": cls.variable_category.id,
                }
            )
        else:
            # Update existing variable to use the test category
            cls.cel_variable.write(
                {
                    "category_id": cls.variable_category.id,
                    "state": "active",
                }
            )

        # Create data value for variable
        cls.data_value = cls.env["spp.data.value"].create(
            {
                "variable_name": "age",
                "subject_model": "res.partner",
                "subject_id": cls.test_individual.id,
                "period_key": "current",
                "value_json": {"value": 34},
                "value_type": "number",
                "source_type": "computed",
                "recorded_at": datetime.now(),
                "is_stale": False,
            }
        )

    def setUp(self):
        super().setUp()
        self.api_base_url = "/api/v2/spp/Studio"

        # Create API client with studio scope (required by router)
        self.client = self.create_api_client(
            name="Studio API Client",
            scopes=[
                {"resource": "studio", "action": "read"},
            ],
        )

        # Generate token
        self.token = self.generate_jwt_token(self.client)

    def _get_headers(self, token=None):
        """Get HTTP headers with authorization."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token or self.token}",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStudioAuthenticationRequired(TestStudioRouterEndpoints):
    """Test that all endpoints require authentication."""

    def test_fields_requires_authentication(self):
        """GET /fields without token returns 401."""
        url = f"{self.api_base_url}/fields"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)

    def test_variables_requires_authentication(self):
        """GET /variables without token returns 401."""
        url = f"{self.api_base_url}/variables"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)

    def test_subject_variables_requires_authentication(self):
        """GET /variables/{resource_type}/{identifier} without token returns 401."""
        url = f"{self.api_base_url}/variables/Individual/urn:openspp:vocab:id-type|IND-STUDIO-001"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS - FIELDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStudioFieldsFunctional(TestStudioRouterEndpoints):
    """Test Studio fields endpoint functional behavior."""

    def test_list_fields_returns_active_fields(self):
        """GET /fields returns active Studio fields."""
        url = f"{self.api_base_url}/fields"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertGreater(data["total"], 0)

        # Check field structure
        field_item = next(
            (item for item in data["items"] if item["technicalName"] == "x_farm_size"),
            None,
        )
        self.assertIsNotNone(field_item)
        self.assertEqual(field_item["label"], "Farm Size")
        self.assertEqual(field_item["fieldType"], "decimal")
        self.assertEqual(field_item["targetType"], "individual")
        self.assertEqual(field_item["helpText"], "Size of farm in hectares")
        self.assertFalse(field_item["isRequired"])
        self.assertEqual(field_item["placementZone"], "custom_fields")
        self.assertTrue(field_item["apiExposed"])

    def test_list_fields_filters_by_target_type(self):
        """GET /fields?target_type=individual filters by target registry."""
        # Create a group-only field
        self.env["spp.studio.field"].create(
            {
                "label": "Group Type",
                "technical_name": "x_group_type",
                "field_type": "text",
                "target_type": "group",
                "state": "active",
                "api_exposed": True,
                "placement_zone_id": self.placement_zone.id,
            }
        )

        # Filter for individual fields
        url = f"{self.api_base_url}/fields?target_type=individual"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # All returned fields should be for individuals
        for item in data["items"]:
            self.assertEqual(item["targetType"], "individual")

        # Should not include group field
        group_field = next(
            (item for item in data["items"] if item["technicalName"] == "x_group_type"),
            None,
        )
        self.assertIsNone(group_field)

    def test_list_fields_excludes_non_api_exposed(self):
        """GET /fields excludes fields with api_exposed=False by default."""
        # Create a non-API field
        self.env["spp.studio.field"].create(
            {
                "label": "Internal Field",
                "technical_name": "x_internal",
                "field_type": "text",
                "target_type": "individual",
                "state": "active",
                "api_exposed": False,
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        # Should not include non-API field
        internal_field = next(
            (item for item in data["items"] if item["technicalName"] == "x_internal"),
            None,
        )
        self.assertIsNone(internal_field)

    def test_list_fields_includes_non_api_exposed_when_requested(self):
        """GET /fields?api_exposed_only=false includes all fields."""
        # Create a non-API field
        self.env["spp.studio.field"].create(
            {
                "label": "Internal Field",
                "technical_name": "x_internal",
                "field_type": "text",
                "target_type": "individual",
                "state": "active",
                "api_exposed": False,
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields?api_exposed_only=false"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        # Should include non-API field
        internal_field = next(
            (item for item in data["items"] if item["technicalName"] == "x_internal"),
            None,
        )
        self.assertIsNotNone(internal_field)

    def test_list_fields_includes_enhanced_metadata(self):
        """GET /fields returns enhanced metadata for all field types."""
        # Create a selection field with options
        self.env["spp.studio.field"].create(
            {
                "label": "Marital Status",
                "technical_name": "x_marital_status",
                "field_type": "selection",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "placement_zone_id": self.placement_zone.id,
                "selection_options": "single|Single\nmarried|Married\ndivorced|Divorced",
                "is_readonly": True,
                "is_searchable": True,
                "sequence": 5,
            }
        )

        # Create a link field
        ir_model_partner = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        self.env["spp.studio.field"].create(
            {
                "label": "Related Person",
                "technical_name": "x_related_person",
                "field_type": "link",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "placement_zone_id": self.placement_zone.id,
                "link_model_id": ir_model_partner.id,
                "link_domain": "[('is_group', '=', False)]",
                "sequence": 20,
            }
        )

        # Create a field with conditional visibility
        age_field = self.env["ir.model.fields"].search([("model", "=", "res.partner"), ("name", "=", "age")], limit=1)
        self.env["spp.studio.field"].create(
            {
                "label": "Spouse Name",
                "technical_name": "x_spouse_name",
                "field_type": "text",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "placement_zone_id": self.placement_zone.id,
                "visibility_condition": "conditional",
                "visibility_field_id": age_field.id if age_field else False,
                "visibility_operator": "equals",
                "visibility_value": "married",
                "is_required": True,
                "sequence": 15,
            }
        )

        url = f"{self.api_base_url}/fields"

        response = self.url_open(url, headers=self._get_headers())
        data = json.loads(response.content)

        # Check selection field metadata
        selection_field = next(
            (item for item in data["items"] if item["technicalName"] == "x_marital_status"),
            None,
        )
        self.assertIsNotNone(selection_field)
        self.assertIsNotNone(selection_field.get("selectionOptions"))
        self.assertEqual(len(selection_field["selectionOptions"]), 3)
        self.assertEqual(selection_field["selectionOptions"][0]["value"], "single")
        self.assertEqual(selection_field["selectionOptions"][0]["label"], "Single")
        self.assertEqual(selection_field["selectionOptions"][1]["value"], "married")
        self.assertEqual(selection_field["selectionOptions"][1]["label"], "Married")
        self.assertTrue(selection_field["isReadonly"])
        self.assertTrue(selection_field["isSearchable"])
        self.assertEqual(selection_field["sequence"], 5)

        # Check link field metadata
        link_field = next(
            (item for item in data["items"] if item["technicalName"] == "x_related_person"),
            None,
        )
        self.assertIsNotNone(link_field)
        self.assertEqual(link_field.get("linkModel"), "res.partner")
        self.assertEqual(link_field.get("linkDomain"), "[('is_group', '=', False)]")
        self.assertEqual(link_field["sequence"], 20)

        # Check conditional visibility metadata
        visibility_field = next(
            (item for item in data["items"] if item["technicalName"] == "x_spouse_name"),
            None,
        )
        self.assertIsNotNone(visibility_field)
        if age_field:
            self.assertEqual(visibility_field.get("visibilityField"), "age")
            self.assertEqual(visibility_field.get("visibilityOperator"), "equals")
            self.assertEqual(visibility_field.get("visibilityValue"), "married")
        self.assertTrue(visibility_field["isRequired"])
        self.assertEqual(visibility_field["sequence"], 15)


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS - FIELD SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════


class TestStudioFieldSchemaFunctional(TestStudioRouterEndpoints):
    """Test Studio field schema endpoint functional behavior."""

    def test_get_field_schema_numeric_field(self):
        """GET /fields/{technical_name}/schema returns schema for numeric field."""
        # Create numeric field
        self.env["spp.studio.field"].create(
            {
                "label": "Farm Size",
                "technical_name": "x_farm_size_hectares",
                "field_type": "decimal",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Farm size in hectares",
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_farm_size_hectares/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["technicalName"], "x_farm_size_hectares")
        self.assertEqual(data["type"], "number")
        self.assertEqual(data["description"], "Farm size in hectares")
        self.assertFalse(data["required"])
        self.assertIsNone(data.get("format"))
        # Decimal fields don't have minimum by default (only integers do)
        self.assertIsNone(data.get("minimum"))

    def test_get_field_schema_integer_field(self):
        """GET /fields/{technical_name}/schema returns schema for integer field with minimum."""
        # Create integer field
        self.env["spp.studio.field"].create(
            {
                "label": "Household Members",
                "technical_name": "x_household_members",
                "field_type": "integer",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Number of household members",
                "is_required": True,
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_household_members/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["technicalName"], "x_household_members")
        self.assertEqual(data["type"], "number")
        self.assertEqual(data["description"], "Number of household members")
        self.assertTrue(data["required"])
        self.assertEqual(data["minimum"], 0)

    def test_get_field_schema_text_field(self):
        """GET /fields/{technical_name}/schema returns schema for text field with maxLength."""
        # Create text field
        self.env["spp.studio.field"].create(
            {
                "label": "Notes",
                "technical_name": "x_notes",
                "field_type": "text",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Additional notes",
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_notes/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["technicalName"], "x_notes")
        self.assertEqual(data["type"], "string")
        self.assertEqual(data["maxLength"], 255)
        self.assertEqual(data["description"], "Additional notes")

    def test_get_field_schema_long_text_field(self):
        """GET /fields/{technical_name}/schema returns schema for long text field."""
        # Create long text field
        self.env["spp.studio.field"].create(
            {
                "label": "Description",
                "technical_name": "x_description",
                "field_type": "long_text",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Detailed description",
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_description/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["technicalName"], "x_description")
        self.assertEqual(data["type"], "string")
        self.assertEqual(data["maxLength"], 65535)

    def test_get_field_schema_selection_field(self):
        """GET /fields/{technical_name}/schema returns schema with enum for selection field."""
        # Create selection field
        self.env["spp.studio.field"].create(
            {
                "label": "Crop Type",
                "technical_name": "x_crop_type",
                "field_type": "selection",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Primary crop type",
                "selection_options": "rice|Rice\ncorn|Corn\nwheat|Wheat",
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_crop_type/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["technicalName"], "x_crop_type")
        self.assertEqual(data["type"], "string")
        self.assertEqual(data["description"], "Primary crop type")
        self.assertIsNotNone(data.get("enum"))
        self.assertEqual(len(data["enum"]), 3)
        self.assertIn("rice", data["enum"])
        self.assertIn("corn", data["enum"])
        self.assertIn("wheat", data["enum"])
        self.assertIsNotNone(data.get("enumDisplay"))
        self.assertEqual(data["enumDisplay"]["rice"], "Rice")
        self.assertEqual(data["enumDisplay"]["corn"], "Corn")
        self.assertEqual(data["enumDisplay"]["wheat"], "Wheat")

    def test_get_field_schema_boolean_field(self):
        """GET /fields/{technical_name}/schema returns schema for boolean field."""
        # Create boolean field
        self.env["spp.studio.field"].create(
            {
                "label": "Is Verified",
                "technical_name": "x_is_verified",
                "field_type": "boolean",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Whether verified",
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_is_verified/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["technicalName"], "x_is_verified")
        self.assertEqual(data["type"], "boolean")
        self.assertEqual(data["description"], "Whether verified")

    def test_get_field_schema_date_field(self):
        """GET /fields/{technical_name}/schema returns schema for date field."""
        # Create date field
        self.env["spp.studio.field"].create(
            {
                "label": "Birth Date",
                "technical_name": "x_birth_date",
                "field_type": "date",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Date of birth",
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_birth_date/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["technicalName"], "x_birth_date")
        self.assertEqual(data["type"], "string")
        self.assertEqual(data["format"], "date")
        self.assertEqual(data["description"], "Date of birth")

    def test_get_field_schema_datetime_field(self):
        """GET /fields/{technical_name}/schema returns schema for datetime field."""
        # Create datetime field
        self.env["spp.studio.field"].create(
            {
                "label": "Last Contact",
                "technical_name": "x_last_contact",
                "field_type": "datetime",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Last contact timestamp",
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_last_contact/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["technicalName"], "x_last_contact")
        self.assertEqual(data["type"], "string")
        self.assertEqual(data["format"], "date-time")

    def test_get_field_schema_link_field(self):
        """GET /fields/{technical_name}/schema returns schema for link field."""
        # Create link field
        ir_model_area = self.env["ir.model"].search([("model", "=", "spp.area")], limit=1)
        self.env["spp.studio.field"].create(
            {
                "label": "Area",
                "technical_name": "x_area_id",
                "field_type": "link",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Administrative area",
                "link_model_id": ir_model_area.id if ir_model_area else False,
                "link_domain": "[('level', '=', 3)]",
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_area_id/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["technicalName"], "x_area_id")
        self.assertEqual(data["type"], "object")
        self.assertEqual(data["format"], "reference")
        self.assertEqual(data["description"], "Administrative area")
        if ir_model_area:
            self.assertEqual(data["linkModel"], "spp.area")
            self.assertEqual(data["linkDomain"], "[('level', '=', 3)]")

    def test_get_field_schema_multi_select_field(self):
        """GET /fields/{technical_name}/schema returns schema for multi_select field."""
        # Create multi_select field
        self.env["spp.studio.field"].create(
            {
                "label": "Languages",
                "technical_name": "x_languages",
                "field_type": "multi_select",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Languages spoken",
                "selection_options": "en|English\nfr|French\nes|Spanish",
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_languages/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["technicalName"], "x_languages")
        self.assertEqual(data["type"], "array")
        self.assertIsNotNone(data.get("enum"))
        self.assertIn("en", data["enum"])
        self.assertEqual(data["enumDisplay"]["en"], "English")

    def test_get_field_schema_not_found(self):
        """GET /fields/{technical_name}/schema returns 404 for non-existent field."""
        url = f"{self.api_base_url}/fields/x_nonexistent/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn("detail", data)
        self.assertIn("not found", data["detail"].lower())

    def test_get_field_schema_inactive_field(self):
        """GET /fields/{technical_name}/schema returns 404 for inactive field."""
        # Create inactive field
        self.env["spp.studio.field"].create(
            {
                "label": "Inactive Field",
                "technical_name": "x_inactive",
                "field_type": "text",
                "target_type": "individual",
                "state": "draft",
                "api_exposed": True,
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_inactive/schema"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn("not found or not active", data["detail"])

    def test_get_field_schema_uses_help_text_as_description(self):
        """GET /fields/{technical_name}/schema uses help_text when available."""
        # Create field with help text
        self.env["spp.studio.field"].create(
            {
                "label": "Income",
                "technical_name": "x_income",
                "field_type": "decimal",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": "Monthly income in local currency",
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_income/schema"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)
        self.assertEqual(data["description"], "Monthly income in local currency")

    def test_get_field_schema_falls_back_to_label(self):
        """GET /fields/{technical_name}/schema uses label when help_text is empty."""
        # Create field without help text
        self.env["spp.studio.field"].create(
            {
                "label": "Custom Field",
                "technical_name": "x_custom",
                "field_type": "text",
                "target_type": "individual",
                "state": "active",
                "api_exposed": True,
                "help_text": False,
                "placement_zone_id": self.placement_zone.id,
            }
        )

        url = f"{self.api_base_url}/fields/x_custom/schema"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)
        self.assertEqual(data["description"], "Custom Field")

    def test_get_field_schema_requires_authentication(self):
        """GET /fields/{technical_name}/schema requires authentication."""
        url = f"{self.api_base_url}/fields/x_farm_size/schema"

        response = self.url_open(
            url,
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 401)

    def test_get_field_schema_requires_studio_read_scope(self):
        """GET /fields/{technical_name}/schema requires studio:read scope."""
        # Create client without studio scope
        client_no_scope = self.create_api_client(
            name="No Studio Scope",
            scopes=[
                {"resource": "individual", "action": "read"},
            ],
        )
        token_no_scope = self.generate_jwt_token(client_no_scope)

        url = f"{self.api_base_url}/fields/x_farm_size/schema"

        response = self.url_open(url, headers=self._get_headers(token_no_scope))

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("scope", data["detail"].lower())


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS - VARIABLES
# ═══════════════════════════════════════════════════════════════════════════════


class TestStudioVariablesFunctional(TestStudioRouterEndpoints):
    """Test Studio variables endpoint functional behavior."""

    def test_list_variables_returns_active_variables(self):
        """GET /variables returns active CEL variables."""
        url = f"{self.api_base_url}/variables"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertGreater(data["total"], 0)

        # Check variable structure
        var_item = next(
            (item for item in data["items"] if item["name"] == "age"),
            None,
        )
        self.assertIsNotNone(var_item)
        self.assertIn("Age", var_item["label"])  # May be "Age" or "Age (Years)"
        self.assertEqual(var_item["valueType"], "number")
        # sourceType may be "field" or "computed" depending on demo data
        self.assertIn(var_item["sourceType"], ["field", "computed"])
        self.assertIn(var_item["appliesTo"], ["individual", "both"])
        self.assertIn(
            var_item["periodGranularity"],
            ["current", "none", "daily", "monthly", "yearly"],
        )
        # Category may or may not be Demographics depending on demo data
        if var_item.get("category"):
            self.assertIsInstance(var_item["category"], str)

    def test_list_variables_filters_by_applies_to(self):
        """GET /variables?applies_to=individual filters by context."""
        # Create a group-only variable
        self.env["spp.cel.variable"].create(
            {
                "name": "Member Count",
                "cel_accessor": "member_count",
                "source_type": "computed",
                "value_type": "number",
                "state": "active",
                "applies_to": "group",
            }
        )

        # Filter for individual variables
        url = f"{self.api_base_url}/variables?applies_to=individual"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # All returned variables should apply to individual or both
        for item in data["items"]:
            self.assertIn(item["appliesTo"], ["individual", "both"])

        # Should not include group-only variable
        group_var = next(
            (item for item in data["items"] if item["name"] == "member_count"),
            None,
        )
        self.assertIsNone(group_var)

    def test_list_variables_filters_by_source_type(self):
        """GET /variables?source_type=field filters by source type."""
        # Create a computed variable
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

        url = f"{self.api_base_url}/variables?source_type=field"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        # All returned variables should be field type
        for item in data["items"]:
            self.assertEqual(item["sourceType"], "field")

    def test_list_variables_filters_by_category(self):
        """GET /variables?category=Demographics filters by category."""
        # Create another category and variable
        other_category = self.env["spp.cel.variable.category"].create(
            {
                "name": "Financial",
                "code": "financial",
                "sequence": 2,
            }
        )
        self.env["spp.cel.variable"].create(
            {
                "name": "Income",
                "cel_accessor": "income",
                "source_type": "field",
                "value_type": "number",
                "state": "active",
                "applies_to": "both",
                "category_id": other_category.id,
            }
        )

        url = f"{self.api_base_url}/variables?category=Demographics"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        # All returned variables should be in Demographics category
        for item in data["items"]:
            if item.get("category"):
                self.assertEqual(item["category"], "Demographics")


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS - SUBJECT VARIABLES
# ═══════════════════════════════════════════════════════════════════════════════


class TestStudioSubjectVariablesFunctional(TestStudioRouterEndpoints):
    """Test Studio subject variables endpoint functional behavior."""

    def test_get_subject_variables_individual(self):
        """GET /variables/Individual/{id} returns cached values for individual."""
        url = f"{self.api_base_url}/variables/Individual/urn:openspp:vocab:id-type|IND-STUDIO-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["subjectId"], "urn:openspp:vocab:id-type|IND-STUDIO-001")
        self.assertEqual(data["periodKey"], "current")
        self.assertIn("variables", data)

        # Check age variable
        self.assertIn("age", data["variables"])
        age_data = data["variables"]["age"]
        self.assertEqual(age_data["value"], 34)
        self.assertEqual(age_data["periodKey"], "current")
        self.assertFalse(age_data["isStale"])
        self.assertEqual(age_data["sourceType"], "computed")

    def test_get_subject_variables_group(self):
        """GET /variables/Group/{id} returns cached values for group."""
        # Create data value for group
        self.env["spp.data.value"].create(
            {
                "variable_name": "member_count",
                "subject_model": "res.partner",
                "subject_id": self.test_group.id,
                "period_key": "current",
                "value_json": {"value": 4},
                "value_type": "number",
                "source_type": "computed",
                "recorded_at": datetime.now(),
                "is_stale": False,
            }
        )

        url = f"{self.api_base_url}/variables/Group/urn:openspp:vocab:id-type|GRP-STUDIO-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["subjectId"], "urn:openspp:vocab:id-type|GRP-STUDIO-001")

    def test_get_subject_variables_not_found(self):
        """GET /variables/{type}/{id} returns 404 for non-existent subject."""
        url = f"{self.api_base_url}/variables/Individual/urn:openspp:vocab:id-type|NONEXISTENT"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn("detail", data)

    def test_get_subject_variables_invalid_identifier(self):
        """GET /variables/{type}/{id} returns 400 for malformed identifier."""
        url = f"{self.api_base_url}/variables/Individual/INVALID-FORMAT"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("detail", data)
        self.assertIn("Invalid identifier format", data["detail"])

    def test_get_subject_variables_type_mismatch(self):
        """GET /variables/{type}/{id} returns 400 when ID refers to wrong type."""
        # Try to access individual with Group resource type
        url = f"{self.api_base_url}/variables/Group/urn:openspp:vocab:id-type|IND-STUDIO-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("detail", data)
        self.assertIn("Individual", data["detail"])

    def test_get_subject_variables_invalid_resource_type(self):
        """GET /variables/{type}/{id} returns 400 for invalid resource type."""
        url = f"{self.api_base_url}/variables/InvalidType/urn:openspp:vocab:id-type|IND-STUDIO-001"

        response = self.url_open(url, headers=self._get_headers())

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("detail", data)

    def test_get_subject_variables_filter_by_names(self):
        """GET /variables/{type}/{id}?variables=age filters returned variables."""
        # Create another variable value
        self.env["spp.data.value"].create(
            {
                "variable_name": "income",
                "subject_model": "res.partner",
                "subject_id": self.test_individual.id,
                "period_key": "current",
                "value_json": {"value": 5000},
                "value_type": "number",
                "source_type": "computed",
                "recorded_at": datetime.now(),
            }
        )

        url = f"{self.api_base_url}/variables/Individual/urn:openspp:vocab:id-type|IND-STUDIO-001?variables=age"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        # Should only include age
        self.assertIn("age", data["variables"])
        self.assertNotIn("income", data["variables"])

    def test_get_subject_variables_multiple_filter(self):
        """GET /variables/{type}/{id}?variables=age,income returns multiple variables."""
        # Create another variable value
        self.env["spp.data.value"].create(
            {
                "variable_name": "income",
                "subject_model": "res.partner",
                "subject_id": self.test_individual.id,
                "period_key": "current",
                "value_json": {"value": 5000},
                "value_type": "number",
                "source_type": "computed",
                "recorded_at": datetime.now(),
            }
        )

        url = f"{self.api_base_url}/variables/Individual/urn:openspp:vocab:id-type|IND-STUDIO-001?variables=age,income"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        # Should include both
        self.assertIn("age", data["variables"])
        self.assertIn("income", data["variables"])

    def test_get_subject_variables_custom_period_key(self):
        """GET /variables/{type}/{id}?period_key=2024-12 uses custom period."""
        # Create value for specific period
        self.env["spp.data.value"].create(
            {
                "variable_name": "age",
                "subject_model": "res.partner",
                "subject_id": self.test_individual.id,
                "period_key": "2024-12",
                "value_json": {"value": 33},
                "value_type": "number",
                "source_type": "computed",
                "recorded_at": datetime.now(),
            }
        )

        url = f"{self.api_base_url}/variables/Individual/urn:openspp:vocab:id-type|IND-STUDIO-001?period_key=2024-12"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        self.assertEqual(data["periodKey"], "2024-12")
        self.assertIn("age", data["variables"])
        self.assertEqual(data["variables"]["age"]["value"], 33)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGINATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStudioPagination(TestStudioRouterEndpoints):
    """Test pagination for fields and variables endpoints."""

    def test_fields_pagination_count(self):
        """GET /fields?_count=1 returns correct number of items."""
        # Create multiple fields
        for i in range(3):
            self.env["spp.studio.field"].create(
                {
                    "label": f"Field {i}",
                    "technical_name": f"x_field_{i}",
                    "field_type": "text",
                    "target_type": "individual",
                    "state": "active",
                    "api_exposed": True,
                    "placement_zone_id": self.placement_zone.id,
                }
            )

        url = f"{self.api_base_url}/fields?_count=1"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        # Should return only 1 item but total shows all
        self.assertEqual(len(data["items"]), 1)
        self.assertGreaterEqual(data["total"], 3)

    def test_fields_pagination_cursor(self):
        """GET /fields?_lastId=X uses cursor-based pagination."""
        # Create multiple fields
        for i in range(3):
            self.env["spp.studio.field"].create(
                {
                    "label": f"Field {i}",
                    "technical_name": f"x_field_{i}",
                    "field_type": "text",
                    "target_type": "individual",
                    "state": "active",
                    "api_exposed": True,
                    "placement_zone_id": self.placement_zone.id,
                }
            )

        # Get first page
        url1 = f"{self.api_base_url}/fields?_count=1"
        response1 = self.url_open(url1, headers=self._get_headers())
        data1 = json.loads(response1.content)
        first_item = data1["items"][0]["technicalName"]
        next_page_id = data1.get("nextPageId")

        # Should have a nextPageId for cursor pagination
        self.assertIsNotNone(next_page_id)

        # Get second page using cursor
        url2 = f"{self.api_base_url}/fields?_count=1&_lastId={next_page_id}"
        response2 = self.url_open(url2, headers=self._get_headers())
        data2 = json.loads(response2.content)
        second_item = data2["items"][0]["technicalName"]

        # Should be different items
        self.assertNotEqual(first_item, second_item)

    def test_variables_pagination_count(self):
        """GET /variables?_count=1 returns correct number of items."""
        # Create multiple variables
        for i in range(3):
            self.env["spp.cel.variable"].create(
                {
                    "name": f"Var {i}",
                    "cel_accessor": f"var_{i}",
                    "source_type": "field",
                    "value_type": "number",
                    "state": "active",
                    "applies_to": "both",
                }
            )

        url = f"{self.api_base_url}/variables?_count=1"

        response = self.url_open(url, headers=self._get_headers())

        data = json.loads(response.content)

        # Should return only 1 item but total shows all
        self.assertEqual(len(data["items"]), 1)
        self.assertGreaterEqual(data["total"], 3)

    def test_variables_pagination_cursor(self):
        """GET /variables?_lastId=X uses cursor-based pagination."""
        # Create multiple variables
        for i in range(3):
            self.env["spp.cel.variable"].create(
                {
                    "name": f"Var {i}",
                    "cel_accessor": f"var_{i}",
                    "source_type": "field",
                    "value_type": "number",
                    "state": "active",
                    "applies_to": "both",
                }
            )

        # Get first page
        url1 = f"{self.api_base_url}/variables?_count=1"
        response1 = self.url_open(url1, headers=self._get_headers())
        data1 = json.loads(response1.content)
        first_item = data1["items"][0]["name"]
        next_page_id = data1.get("nextPageId")

        # Should have a nextPageId for cursor pagination
        self.assertIsNotNone(next_page_id)

        # Get second page using cursor
        url2 = f"{self.api_base_url}/variables?_count=1&_lastId={next_page_id}"
        response2 = self.url_open(url2, headers=self._get_headers())
        data2 = json.loads(response2.content)
        second_item = data2["items"][0]["name"]

        # Should be different items
        self.assertNotEqual(first_item, second_item)
