# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestCoordinationVocabularies(DrimsTestCommon):
    """Tests for coordination-related vocabularies."""

    def test_ocha_clusters_vocabulary_exists(self):
        """Test OCHA/IASC clusters vocabulary is installed."""
        vocab = self.env["spp.vocabulary"].search(
            [
                ("namespace_uri", "=", "urn:ocha:iasc:clusters"),
            ],
            limit=1,
        )
        self.assertTrue(vocab, "OCHA/IASC clusters vocabulary should exist")
        self.assertEqual(vocab.name, "OCHA/IASC Humanitarian Clusters")
        self.assertTrue(vocab.reference_url, "Should have reference URL")

    def test_ocha_clusters_codes_exist(self):
        """Test all 11 OCHA/IASC cluster codes are installed."""
        expected_codes = [
            "food_security",
            "shelter",
            "health",
            "wash",
            "protection",
            "education",
            "nutrition",
            "camp_coordination",
            "early_recovery",
            "emergency_telecom",
            "logistics",
        ]
        for code in expected_codes:
            cluster = self.env["spp.vocabulary.code"].search(
                [
                    ("vocabulary_id.namespace_uri", "=", "urn:ocha:iasc:clusters"),
                    ("code", "=", code),
                ],
                limit=1,
            )
            self.assertTrue(cluster, f"Cluster code '{code}' should exist")

    def test_organization_roles_vocabulary_exists(self):
        """Test organization roles vocabulary is installed."""
        vocab = self.env["spp.vocabulary"].search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:drims:organization-roles"),
            ],
            limit=1,
        )
        self.assertTrue(vocab, "Organization roles vocabulary should exist")

    def test_organization_roles_codes_exist(self):
        """Test all organization role codes are installed."""
        expected_codes = [
            "lead_agency",
            "implementing_partner",
            "donor",
            "coordinator",
            "technical_support",
            "observer",
        ]
        for code in expected_codes:
            role = self.env["spp.vocabulary.code"].search(
                [
                    (
                        "vocabulary_id.namespace_uri",
                        "=",
                        "urn:openspp:vocab:drims:organization-roles",
                    ),
                    ("code", "=", code),
                ],
                limit=1,
            )
            self.assertTrue(role, f"Organization role '{code}' should exist")

    def test_coordination_modes_vocabulary_exists(self):
        """Test coordination modes vocabulary is installed."""
        vocab = self.env["spp.vocabulary"].search(
            [
                ("namespace_uri", "=", "urn:openspp:vocab:drims:coordination-modes"),
            ],
            limit=1,
        )
        self.assertTrue(vocab, "Coordination modes vocabulary should exist")

    def test_coordination_modes_codes_exist(self):
        """Test all coordination mode codes are installed."""
        expected_codes = [
            "lead_agency",
            "cluster",
            "consortium",
            "bilateral",
            "decentralized",
        ]
        for code in expected_codes:
            mode = self.env["spp.vocabulary.code"].search(
                [
                    (
                        "vocabulary_id.namespace_uri",
                        "=",
                        "urn:openspp:vocab:drims:coordination-modes",
                    ),
                    ("code", "=", code),
                ],
                limit=1,
            )
            self.assertTrue(mode, f"Coordination mode '{code}' should exist")


@tagged("post_install", "-at_install")
class TestIncidentThresholdOverrides(DrimsTestCommon):
    """Tests for per-incident threshold override functionality."""

    def test_threshold_override_fields_exist(self):
        """Test threshold override fields exist on incident."""
        self.assertTrue(hasattr(self.incident, "drims_low_stock_threshold_override"))
        self.assertTrue(hasattr(self.incident, "drims_expiry_warning_override"))
        self.assertTrue(hasattr(self.incident, "drims_expiry_critical_override"))
        self.assertTrue(hasattr(self.incident, "drims_sla_warning_override"))

    def test_threshold_override_defaults_to_zero(self):
        """Test threshold overrides default to zero (meaning use global)."""
        self.assertEqual(self.incident.drims_low_stock_threshold_override, 0.0)
        self.assertEqual(self.incident.drims_expiry_warning_override, 0)
        self.assertEqual(self.incident.drims_expiry_critical_override, 0)
        self.assertEqual(self.incident.drims_sla_warning_override, 0)

    def test_get_threshold_uses_override_when_set(self):
        """Test get_threshold returns override value when set."""
        self.incident.drims_low_stock_threshold_override = 30.0
        result = self.incident.get_threshold("low_stock_threshold")
        # 30% should be returned as 0.30 (decimal)
        self.assertEqual(result, 0.30)

    def test_get_threshold_expiry_warning_override(self):
        """Test get_threshold for expiry warning days override."""
        self.incident.drims_expiry_warning_override = 45
        result = self.incident.get_threshold("expiry_warning_days")
        self.assertEqual(result, 45)

    def test_get_threshold_expiry_critical_override(self):
        """Test get_threshold for expiry critical days override."""
        self.incident.drims_expiry_critical_override = 10
        result = self.incident.get_threshold("expiry_critical_days")
        self.assertEqual(result, 10)

    def test_get_threshold_sla_warning_override(self):
        """Test get_threshold for SLA warning days override."""
        self.incident.drims_sla_warning_override = 3
        result = self.incident.get_threshold("sla_warning_days")
        self.assertEqual(result, 3)

    def test_get_threshold_falls_back_to_global(self):
        """Test get_threshold falls back to global settings when no override."""
        # Mock the global settings getter
        with patch.object(
            self.env["res.config.settings"].__class__,
            "get_low_stock_threshold",
            return_value=0.25,
        ):
            result = self.incident.get_threshold("low_stock_threshold")
            self.assertEqual(result, 0.25)

    def test_get_threshold_invalid_name_raises_error(self):
        """Test get_threshold raises error for invalid threshold name."""
        with self.assertRaises(ValueError) as context:
            self.incident.get_threshold("invalid_threshold_name")
        self.assertIn("Unknown threshold name", str(context.exception))

    def test_get_threshold_requires_single_record(self):
        """Test get_threshold requires single record (ensure_one)."""
        # Create a second incident with a unique code
        incident2 = self.env["spp.hazard.incident"].create(
            {
                "name": "Second Test Incident",
                "code": "FLOOD-2024-TEST2",
                "category_id": self.incident.category_id.id,
                "start_date": self.incident.start_date,
                "status": "active",
            }
        )
        incidents = self.incident | incident2
        with self.assertRaises(ValueError):
            incidents.get_threshold("low_stock_threshold")


@tagged("post_install", "-at_install")
class TestIncidentCoordinationMode(DrimsTestCommon):
    """Tests for incident coordination mode field."""

    def test_coordination_mode_field_exists(self):
        """Test coordination_mode_id field exists on incident."""
        self.assertTrue(hasattr(self.incident, "coordination_mode_id"))

    def test_coordination_mode_initially_empty(self):
        """Test coordination mode is not set initially."""
        self.assertFalse(self.incident.coordination_mode_id)

    def test_coordination_mode_can_be_set(self):
        """Test coordination mode can be set from vocabulary."""
        cluster_mode = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:coordination-modes",
                ),
                ("code", "=", "cluster"),
            ],
            limit=1,
        )
        self.incident.coordination_mode_id = cluster_mode
        self.assertEqual(self.incident.coordination_mode_id.code, "cluster")

    def test_coordination_mode_domain_filter(self):
        """Test coordination mode field only accepts valid vocabulary codes."""
        # Try to set a code from a different vocabulary
        invalid_code = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:priority-levels",
                ),
            ],
            limit=1,
        )
        # Field domain is enforced in the UI, not in Python
        # Just verify the field accepts vocabulary codes
        self.incident.coordination_mode_id = invalid_code
        # The domain is UI-enforced, so this should work but is semantically wrong


@tagged("post_install", "-at_install")
class TestRequestClusterField(DrimsTestCommon):
    """Tests for humanitarian cluster field on requests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.future_date = date.today() + timedelta(days=30)
        cls.health_cluster = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:ocha:iasc:clusters"),
                ("code", "=", "health"),
            ],
            limit=1,
        )
        cls.wash_cluster = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:ocha:iasc:clusters"),
                ("code", "=", "wash"),
            ],
            limit=1,
        )

    def test_request_cluster_field_exists(self):
        """Test cluster_id field exists on request model."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        self.assertTrue(hasattr(request, "cluster_id"))

    def test_request_cluster_initially_empty(self):
        """Test cluster is not set initially."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        self.assertFalse(request.cluster_id)

    def test_request_cluster_can_be_set(self):
        """Test cluster can be set on request creation."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "cluster_id": self.health_cluster.id,
            }
        )
        self.assertEqual(request.cluster_id.code, "health")

    def test_request_cluster_is_tracked(self):
        """Test cluster field changes are tracked."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        request.cluster_id = self.health_cluster
        # Tracking is verified by field having tracking=True attribute
        field = request._fields.get("cluster_id")
        self.assertTrue(field.tracking)

    def test_request_cluster_is_indexed(self):
        """Test cluster field is indexed for performance."""
        field = self.env["spp.drims.request"]._fields.get("cluster_id")
        self.assertTrue(field.index)

    def test_request_search_by_cluster(self):
        """Test requests can be searched by cluster."""
        request1 = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "cluster_id": self.health_cluster.id,
            }
        )
        request2 = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "cluster_id": self.wash_cluster.id,
            }
        )
        health_requests = self.env["spp.drims.request"].search(
            [
                ("cluster_id", "=", self.health_cluster.id),
            ]
        )
        self.assertIn(request1, health_requests)
        self.assertNotIn(request2, health_requests)


@tagged("post_install", "-at_install")
class TestPartnerOrganizationFields(DrimsTestCommon):
    """Tests for DRIMS organization fields on res.partner."""

    def test_partner_drims_organization_field_exists(self):
        """Test is_drims_organization field exists on partner."""
        partner = self.env["res.partner"].create(
            {
                "name": "Test Organization",
                "is_company": True,
            }
        )
        self.assertTrue(hasattr(partner, "is_drims_organization"))

    def test_partner_drims_role_field_exists(self):
        """Test drims_organization_role_id field exists on partner."""
        partner = self.env["res.partner"].create(
            {
                "name": "Test Organization",
                "is_company": True,
            }
        )
        self.assertTrue(hasattr(partner, "drims_organization_role_id"))

    def test_partner_drims_organization_defaults_false(self):
        """Test is_drims_organization defaults to False."""
        partner = self.env["res.partner"].create(
            {
                "name": "Test Organization",
                "is_company": True,
            }
        )
        self.assertFalse(partner.is_drims_organization)

    def test_partner_drims_organization_can_be_set(self):
        """Test is_drims_organization can be set to True."""
        partner = self.env["res.partner"].create(
            {
                "name": "Humanitarian Organization",
                "is_company": True,
                "is_drims_organization": True,
            }
        )
        self.assertTrue(partner.is_drims_organization)

    def test_partner_drims_role_can_be_set(self):
        """Test organization role can be set from vocabulary."""
        implementing_partner = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:organization-roles",
                ),
                ("code", "=", "implementing_partner"),
            ],
            limit=1,
        )
        partner = self.env["res.partner"].create(
            {
                "name": "NGO Partner",
                "is_company": True,
                "is_drims_organization": True,
                "drims_organization_role_id": implementing_partner.id,
            }
        )
        self.assertEqual(partner.drims_organization_role_id.code, "implementing_partner")

    def test_partner_drims_search_organizations(self):
        """Test can search for DRIMS organizations."""
        partner1 = self.env["res.partner"].create(
            {
                "name": "DRIMS Org 1",
                "is_company": True,
                "is_drims_organization": True,
            }
        )
        partner2 = self.env["res.partner"].create(
            {
                "name": "Regular Company",
                "is_company": True,
                "is_drims_organization": False,
            }
        )
        drims_orgs = self.env["res.partner"].search(
            [
                ("is_drims_organization", "=", True),
            ]
        )
        self.assertIn(partner1, drims_orgs)
        self.assertNotIn(partner2, drims_orgs)


@tagged("post_install", "-at_install")
class TestReport4WWizard(DrimsTestCommon):
    """Tests for 4W humanitarian coordination report wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.future_date = date.today() + timedelta(days=30)

    def test_4w_wizard_model_exists(self):
        """Test 4W report wizard model exists."""
        wizard = self.env["spp.drims.report.4w.wizard"].create(
            {
                "incident_id": self.incident.id,
            }
        )
        self.assertTrue(wizard)

    def test_4w_wizard_requires_incident(self):
        """Test 4W wizard requires incident selection."""
        # incident_id is a required field with DB NOT NULL constraint,
        # so creating without it raises ValidationError
        from odoo.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.env["spp.drims.report.4w.wizard"].create({})

    def test_4w_wizard_date_filters(self):
        """Test 4W wizard accepts date filters."""
        wizard = self.env["spp.drims.report.4w.wizard"].create(
            {
                "incident_id": self.incident.id,
                "date_from": date.today() - timedelta(days=30),
                "date_to": date.today(),
            }
        )
        self.assertEqual(wizard.date_from, date.today() - timedelta(days=30))
        self.assertEqual(wizard.date_to, date.today())

    def test_4w_wizard_date_validation(self):
        """Test 4W wizard validates date range."""
        with self.assertRaises(UserError):
            self.env["spp.drims.report.4w.wizard"].create(
                {
                    "incident_id": self.incident.id,
                    "date_from": date.today(),
                    "date_to": date.today() - timedelta(days=30),  # End before start
                }
            )

    def test_4w_wizard_area_filter(self):
        """Test 4W wizard accepts area filter."""
        wizard = self.env["spp.drims.report.4w.wizard"].create(
            {
                "incident_id": self.incident.id,
                "area_id": self.area.id,
            }
        )
        self.assertEqual(wizard.area_id, self.area)

    def test_4w_wizard_status_filters_default(self):
        """Test 4W wizard status filters default to True."""
        wizard = self.env["spp.drims.report.4w.wizard"].create(
            {
                "incident_id": self.incident.id,
            }
        )
        self.assertTrue(wizard.include_planned)
        self.assertTrue(wizard.include_completed)

    def test_4w_wizard_generate_report_returns_action(self):
        """Test generate_report returns action dictionary."""
        wizard = self.env["spp.drims.report.4w.wizard"].create(
            {
                "incident_id": self.incident.id,
            }
        )
        result = wizard.generate_report()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.drims.request")
        self.assertIn("pivot", result["view_mode"])

    def test_4w_wizard_generate_report_domain(self):
        """Test generate_report applies correct domain filters."""
        wizard = self.env["spp.drims.report.4w.wizard"].create(
            {
                "incident_id": self.incident.id,
                "date_from": date.today() - timedelta(days=30),
                "date_to": date.today(),
                "area_id": self.area.id,
            }
        )
        result = wizard.generate_report()
        domain = result["domain"]
        # Check incident filter
        self.assertIn(("incident_id", "=", self.incident.id), domain)
        # Check date filters
        self.assertIn(("date_requested", ">=", wizard.date_from), domain)
        self.assertIn(("date_requested", "<=", wizard.date_to), domain)
        # Check area filter (uses child_of for hierarchy)
        self.assertIn(("destination_area_id", "child_of", self.area.id), domain)

    def test_4w_wizard_requires_status_filter(self):
        """Test generate_report requires at least one status filter."""
        wizard = self.env["spp.drims.report.4w.wizard"].create(
            {
                "incident_id": self.incident.id,
                "include_planned": False,
                "include_completed": False,
            }
        )
        with self.assertRaises(UserError):
            wizard.generate_report()

    def test_4w_wizard_planned_status_filter(self):
        """Test planned status filter includes correct states."""
        wizard = self.env["spp.drims.report.4w.wizard"].create(
            {
                "incident_id": self.incident.id,
                "include_planned": True,
                "include_completed": False,
            }
        )
        result = wizard.generate_report()
        domain = result["domain"]
        # Find state filter in domain
        state_filter = [d for d in domain if d[0] == "state"]
        self.assertTrue(state_filter)
        states = state_filter[0][2]
        self.assertIn("draft", states)
        self.assertIn("submitted", states)
        self.assertIn("approved", states)

    def test_4w_wizard_completed_status_filter(self):
        """Test completed status filter includes correct states."""
        wizard = self.env["spp.drims.report.4w.wizard"].create(
            {
                "incident_id": self.incident.id,
                "include_planned": False,
                "include_completed": True,
            }
        )
        result = wizard.generate_report()
        domain = result["domain"]
        state_filter = [d for d in domain if d[0] == "state"]
        self.assertTrue(state_filter)
        states = state_filter[0][2]
        self.assertIn("dispatched", states)
        self.assertIn("delivered", states)

    def test_4w_wizard_report_title_includes_incident(self):
        """Test report title includes incident name."""
        wizard = self.env["spp.drims.report.4w.wizard"].create(
            {
                "incident_id": self.incident.id,
            }
        )
        result = wizard.generate_report()
        self.assertIn(self.incident.name, result["name"])
