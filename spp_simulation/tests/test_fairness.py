# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestFairness(SimulationTestCommon):
    """Tests for fairness computation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Gender vocabulary codes are shipped by spp_vocabulary (vocabulary_gender.xml)
        cls.gender_female = cls.env.ref("spp_vocabulary.code_gender_female")
        cls.gender_male = cls.env.ref("spp_vocabulary.code_gender_male")

        # Assign genders to test registrants
        for i, partner in enumerate(cls.group_registrants):
            if i % 2 == 0:
                partner.gender_id = cls.gender_female.id
            else:
                partner.gender_id = cls.gender_male.id

    def _get_service(self):
        """Get the fairness service.

        NOTE: Updated to use spp.metric.fairness directly (Phase 6 cleanup).
        The old spp.simulation.fairness.service has been removed.
        """
        return self.env["spp.metric.fairness"]

    def test_fairness_empty_beneficiaries(self):
        """Test fairness with no beneficiaries."""
        service = self._get_service()
        result = service.compute_fairness([], base_domain=[("is_registrant", "=", True), ("is_group", "=", True)])
        self.assertEqual(result["equity_score"], 100.0)
        self.assertFalse(result["has_disparity"])

    def test_fairness_returns_required_keys(self):
        """Test that fairness result has all required keys."""
        service = self._get_service()
        base_domain = [("is_registrant", "=", True), ("is_group", "=", True)]
        result = service.compute_fairness(self.group_registrants.ids, base_domain=base_domain)
        self.assertIn("equity_score", result)
        self.assertIn("has_disparity", result)
        self.assertIn("overall_coverage", result)
        self.assertIn("total_beneficiaries", result)
        self.assertIn("total_population", result)
        self.assertIn("attributes", result)

    def test_equity_score_range(self):
        """Test that equity score is between 0 and 100."""
        service = self._get_service()
        base_domain = [("is_registrant", "=", True), ("is_group", "=", True)]
        result = service.compute_fairness(self.group_registrants.ids, base_domain=base_domain)
        self.assertGreaterEqual(result["equity_score"], 0)
        self.assertLessEqual(result["equity_score"], 100)

    def test_disparity_ratio_computation(self):
        """Test disparity ratio computation directly."""
        service = self._get_service()
        # Equal coverage should give ratio of 1.0
        ratio = service._compute_disparity_ratio(0.5, 0.5)
        self.assertAlmostEqual(ratio, 1.0)

        # Zero overall coverage should give 0
        ratio = service._compute_disparity_ratio(0.5, 0.0)
        self.assertEqual(ratio, 0.0)

        # Group at half the overall coverage
        ratio = service._compute_disparity_ratio(0.25, 0.5)
        self.assertAlmostEqual(ratio, 0.5)

    def test_demographic_groups_defined(self):
        """Test that demographic dimensions are configured.

        NOTE: This test was updated for Phase 4a migration to spp_aggregation.
        The old _get_demographic_groups() method is deprecated. Demographic
        groups are now configured through spp.demographic.dimension records.
        """
        # Check that demographic dimensions exist
        dimension_model = self.env["spp.demographic.dimension"]
        dimensions = dimension_model.search([("active", "=", True)])
        self.assertGreater(len(dimensions), 0, "At least one demographic dimension should be defined")

        # Gender dimension should exist
        gender_dim = dimension_model.search([("name", "=", "gender")], limit=1)
        self.assertTrue(gender_dim, "Gender dimension should be configured")

    def test_group_status_classification(self):
        """Test that groups are classified with valid status values."""
        service = self._get_service()
        base_domain = [("is_registrant", "=", True), ("is_group", "=", True)]
        result = service.compute_fairness(self.group_registrants.ids, base_domain=base_domain)
        valid_statuses = ["proportional", "low_coverage", "under_represented"]
        for _attr_name, attr_data in result.get("attributes", {}).items():
            for group in attr_data.get("groups", []):
                self.assertIn(
                    group["status"],
                    valid_statuses,
                    f"Invalid status for group {group['label']}",
                )

    def test_fairness_disparity_detected(self):
        """Test that fairness service detects disparity when one gender is overrepresented."""
        # Create 10 female and 10 male registrants for a controlled test
        female_registrants = self.env["res.partner"]
        male_registrants = self.env["res.partner"]

        for i in range(10):
            female = self.env["res.partner"].create(
                {
                    "name": f"Female Registrant {i + 1}",
                    "is_registrant": True,
                    "is_group": True,
                    "gender_id": self.gender_female.id,
                }
            )
            female_registrants |= female

            male = self.env["res.partner"].create(
                {
                    "name": f"Male Registrant {i + 1}",
                    "is_registrant": True,
                    "is_group": True,
                    "gender_id": self.gender_male.id,
                }
            )
            male_registrants |= male

        # Set up scenario to target all 20 registrants (population)
        _scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Disparity Test Scenario",
                "target_type": "group",
                "targeting_expression": "true",  # All registrants are in the population
                "state": "ready",
            }
        )

        # But only female registrants are beneficiaries (100% female, 0% male)
        service = self._get_service()
        base_domain = [("is_registrant", "=", True), ("is_group", "=", True)]
        result = service.compute_fairness(female_registrants.ids, base_domain=base_domain)

        # Should detect disparity
        self.assertTrue(result["has_disparity"], "Expected disparity to be detected")
        self.assertLess(
            result["equity_score"],
            100.0,
            "Expected equity score to be less than 100 when disparity exists",
        )

        # Check that female group has higher coverage than overall
        if "gender" in result["attributes"]:
            gender_groups = result["attributes"]["gender"]["groups"]
            female_group = next((g for g in gender_groups if g["label"] == "Female"), None)
            if female_group:
                # Female coverage should be 100% (all females are beneficiaries)
                self.assertGreater(
                    female_group["coverage"],
                    result["overall_coverage"],
                    "Female coverage should be higher than overall when only females are beneficiaries",
                )
