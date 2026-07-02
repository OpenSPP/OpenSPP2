# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for FastAPI endpoint compliance model.

Covers models/fastapi_endpoint_compliance.py:
- _get_fastapi_routers() adds the verification router when test_mode is on
- _get_fastapi_routers() adds the verification router when config param is set
- _get_fastapi_routers() does NOT add the router in production mode
- _get_fastapi_routers() only acts on 'dci_api' app records, not others
"""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from fastapi import APIRouter


@tagged("post_install", "-at_install")
class TestFastapiEndpointCompliance(TransactionCase):
    """Test the compliance endpoint gating logic in FastAPIEndpointCompliance."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Endpoint = cls.env["fastapi.endpoint"]
        cls.ConfigParam = cls.env["ir.config_parameter"].sudo()

    def _create_dci_endpoint(self, suffix=""):
        """Create a minimal dci_api FastAPI endpoint record."""
        return self.Endpoint.create(
            {
                "name": f"test-compliance-endpoint{suffix}",
                "app": "dci_api",
                "root_path": f"/test-compliance{suffix}",
            }
        )

    def _compliance_router_paths(self, endpoint):
        """Return all route paths from the compliance (verification) router."""
        routers = endpoint._get_fastapi_routers()
        paths = []
        for router in routers:
            if isinstance(router, APIRouter):
                for route in router.routes:
                    paths.append(getattr(route, "path", ""))
        return paths

    def _has_compliance_router(self, endpoint):
        """Return True if the verification_router's /test prefix is present."""
        paths = self._compliance_router_paths(endpoint)
        return any("/test" in p for p in paths)

    def test_compliance_router_added_in_test_mode(self):
        """When tools.config['test_enable'] is truthy, the /test/* router is added."""
        endpoint = self._create_dci_endpoint("-tm")
        with patch("odoo.addons.spp_dci_compliance.models.fastapi_endpoint_compliance.tools.config") as mock_cfg:
            mock_cfg.get = lambda key, default=None: True if key == "test_enable" else default
            result = self._has_compliance_router(endpoint)
        self.assertTrue(result, "Compliance router must be added when test_enable=True")

    def test_compliance_router_added_when_param_enabled(self):
        """When 'dci.enable_compliance_endpoints' param is 'true', router is added."""
        endpoint = self._create_dci_endpoint("-param")
        self.ConfigParam.set_param("dci.enable_compliance_endpoints", "true")
        try:
            with patch("odoo.addons.spp_dci_compliance.models.fastapi_endpoint_compliance.tools.config") as mock_cfg:
                mock_cfg.get = lambda key, default=None: False if key == "test_enable" else default
                result = self._has_compliance_router(endpoint)
            self.assertTrue(result, "Compliance router must be added when param is 'true'")
        finally:
            self.ConfigParam.set_param("dci.enable_compliance_endpoints", "false")

    def test_compliance_router_not_added_in_production(self):
        """With test_enable=False and param not set, the compliance router is absent."""
        endpoint = self._create_dci_endpoint("-prod")
        self.ConfigParam.set_param("dci.enable_compliance_endpoints", "false")
        with patch("odoo.addons.spp_dci_compliance.models.fastapi_endpoint_compliance.tools.config") as mock_cfg:
            mock_cfg.get = lambda key, default=None: False if key == "test_enable" else default
            result = self._has_compliance_router(endpoint)
        self.assertFalse(result, "Compliance router must NOT be added in production mode")

    def test_non_dci_app_guard_skips_router_injection(self):
        """The 'if self.app == "dci_api"' guard means non-dci apps get no extra routes.

        We verify this by patching the endpoint model's _get_fastapi_routers via
        a subclassed check — the guard `if self.app == "dci_api"` is the unit
        under test.  We simulate a non-dci app by patching the `app` property
        on the endpoint's class so that ORM field access returns a different value.
        """
        endpoint = self._create_dci_endpoint("-guard")

        # Patch the ORM field's __get__ on the endpoint class so reads of `.app`
        # return "other_app" during this test only.
        with patch.object(type(endpoint), "app", new=property(lambda self: "other_app")):
            with patch("odoo.addons.spp_dci_compliance.models.fastapi_endpoint_compliance.tools.config") as mock_cfg:
                mock_cfg.get = lambda key, default=None: True if key == "test_enable" else default
                result = self._has_compliance_router(endpoint)
        self.assertFalse(result, "Compliance router must not be added to non-dci endpoints")

    def test_super_routers_are_preserved(self):
        """The compliance extension must not drop routers from the parent class."""
        endpoint = self._create_dci_endpoint("-super")
        with patch("odoo.addons.spp_dci_compliance.models.fastapi_endpoint_compliance.tools.config") as mock_cfg:
            mock_cfg.get = lambda key, default=None: True if key == "test_enable" else default
            routers = endpoint._get_fastapi_routers()
        # There must be at least two routers: the parent's + the compliance router.
        api_routers = [r for r in routers if isinstance(r, APIRouter)]
        self.assertGreater(len(api_routers), 1, "Parent routers must be preserved alongside compliance router")
