# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Building the API V2 FastAPI app must not abort on a stale router import.

``fastapi.endpoint._get_fastapi_routers()`` runs during app construction, which
FastAPI dispatch performs for a request to the API root *before* endpoint-level
OAuth/JWT checks. A broken import here (e.g. a router module renamed without
updating the importer) therefore turns into an unauthenticated failure that
takes the whole API V2 endpoint down. This test calls the router aggregation
for the api_v2 app and asserts the simulation ``/aggregation`` router is
included without raising.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSimulationFastapiRouterInclusion(TransactionCase):
    def test_api_v2_routers_build_and_include_aggregation(self):
        endpoint = self.env["fastapi.endpoint"].search([("app", "=", "api_v2")], limit=1)
        self.assertTrue(
            endpoint,
            "The api_v2 fastapi.endpoint record must exist (shipped by spp_api_v2)",
        )

        # Must not raise ModuleNotFoundError from a stale router import.
        routers = endpoint._get_fastapi_routers()

        prefixes = [getattr(r, "prefix", "") for r in routers]
        self.assertIn(
            "/aggregation",
            prefixes,
            "The simulation aggregation router must be included in the API V2 app",
        )
