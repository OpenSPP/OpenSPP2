# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Coverage tests for models/fastapi_endpoint_sr.py.

The module only overrides _get_fastapi_routers() which has two branches:
- app == "dci_api": appends sr_callback_router
- app != "dci_api": returns super() result unchanged

50% coverage means neither branch (or only one) was hit.
"""

from odoo.tests import TransactionCase, tagged

from fastapi import APIRouter


@tagged("post_install", "-at_install")
class TestSppDCIClientSREndpoint(TransactionCase):
    """Test _get_fastapi_routers() for the SR endpoint extension."""

    def setUp(self):
        super().setUp()
        self.Endpoint = self.env["fastapi.endpoint"]

    def test_dci_api_includes_sr_callback_router(self):
        """When app == 'dci_api', the SR callback router's /sr/on-search path is present.

        The 'dci_api' selection key is registered by spp_dci_server, which is
        not in this module's dependency graph, so create() would reject it -
        use an in-memory record, which is all _get_fastapi_routers() needs.
        """
        endpoint = self.Endpoint.new({"name": "test-sr-dci-endpoint", "app": "dci_api"})
        routers = endpoint._get_fastapi_routers()

        all_paths = []
        for router in routers:
            if isinstance(router, APIRouter):
                for route in router.routes:
                    all_paths.append(getattr(route, "path", ""))
                # Also check routes on nested sub-routers.
                for inner in getattr(router, "routes", []):
                    for sub_route in getattr(inner, "routes", []):
                        all_paths.append(getattr(sub_route, "path", ""))

        # The sr_callback_router registers /sr/on-search, /sr/on-subscribe, /sr/on-notify.
        self.assertTrue(
            any("/sr/on-search" in p for p in all_paths),
            f"Expected /sr/on-search in router paths, got: {all_paths}",
        )

    def test_non_dci_api_app_does_not_add_sr_router(self):
        """When app != 'dci_api', super() is returned unchanged (no SR router appended)."""
        endpoint = self.Endpoint.new({"name": "test-sr-demo-endpoint", "app": "demo"})
        routers = endpoint._get_fastapi_routers()

        all_paths = []
        for router in routers:
            if isinstance(router, APIRouter):
                for route in router.routes:
                    all_paths.append(getattr(route, "path", ""))

        self.assertFalse(
            any("/sr/on-search" in p for p in all_paths),
            "SR callback router must not be present for non-dci_api apps",
        )
