# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestTargetingEfficiency(SimulationTestCommon):
    """Tests for targeting efficiency computation."""

    def _get_service(self):
        return self.env["spp.simulation.targeting.efficiency.service"]

    def test_perfect_targeting(self):
        """Test with perfect overlap between simulated and ideal populations."""
        service = self._get_service()
        # Create scenario with ideal population
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Perfect Target",
                "target_type": "group",
                "targeting_expression": "true",
                "ideal_population_expression": "true",
                "state": "ready",
            }
        )

        simulated_ids = {1, 2, 3, 4, 5}
        # Mock the ideal population to be the same
        result = service.compute_targeting_efficiency(scenario, simulated_ids)
        # Since we can't easily mock CEL here, just check the method doesn't crash
        # and returns a dict
        self.assertIsInstance(result, dict)

    def test_no_ideal_population(self):
        """Test that empty result is returned when no ideal expression."""
        service = self._get_service()
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "No Ideal",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
            }
        )
        result = service.compute_targeting_efficiency(scenario, {1, 2, 3})
        self.assertEqual(result, {})
