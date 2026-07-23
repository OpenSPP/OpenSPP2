# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Regression tests: an upgraded database must not keep using the old shared
compliance bearer token.

Earlier module versions (19.0.1.0.0) created an ``spp.dci.data.source`` record
carrying the well-known token ``compliance-test-api-key-12345``. The 19.0.1.0.1
post-migration only removed the ``ir.config_parameter`` copy, leaving the data
source usable through the ``auth='none'`` trigger routes. These tests cover the
two safeguards added in 19.0.1.0.2:

- ``_purge_default_compliance_bearer_token`` (used by the migration) deletes
  data sources that still hold the known default token, and leaves re-keyed
  records untouched.
- ``_get_test_data_source`` in the trigger controller refuses to serve a record
  still holding the default token, so a skipped migration cannot re-expose it.
- ``_get_compliance_bearer_token`` rejects the well-known default token when it
  is configured, so the create path cannot mint a fresh default-token record.
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci_client_compliance.models.data_source import (
    DEFAULT_COMPLIANCE_BEARER_TOKEN,
)

BEARER_TOKEN_PARAM = "dci.client_compliance.bearer_token"
MOCK_URL_PARAM = "dci.client_compliance.mock_registry_url"


def _ds_vals(code, token, **overrides):
    vals = {
        "name": "DCI Compliance Test",
        "code": code,
        "base_url": "http://mock_registry:3335",
        "registry_type": "social",
        "our_sender_id": "spmis.compliance.test",
        "our_callback_uri": "http://openspp.dci.local:8069/dci/callback",
        "is_compliance_test": True,
        "state": "active",
        "auth_type": "bearer",
        "bearer_token": token,
    }
    vals.update(overrides)
    return vals


@tagged("post_install", "-at_install")
class TestPurgeDefaultBearerToken(TransactionCase):
    """Unit-test the cleanup helper the 19.0.1.0.2 migration invokes."""

    def test_purge_removes_record_with_default_token(self):
        DataSource = self.env["spp.dci.data.source"].sudo()
        stale = DataSource.create(_ds_vals("dci_compliance_stale", DEFAULT_COMPLIANCE_BEARER_TOKEN))

        removed = DataSource._purge_default_compliance_bearer_token()

        self.assertEqual(removed, 1)
        self.assertFalse(stale.exists(), "Data source holding the default token must be deleted")

    def test_purge_keeps_record_with_operator_token(self):
        DataSource = self.env["spp.dci.data.source"].sudo()
        rekeyed = DataSource.create(_ds_vals("dci_compliance_rekeyed", "operator-real-token"))

        removed = DataSource._purge_default_compliance_bearer_token()

        self.assertEqual(removed, 0)
        self.assertTrue(rekeyed.exists(), "A record re-keyed with a real token must be left untouched")

    def test_purge_only_removes_default_token_records(self):
        DataSource = self.env["spp.dci.data.source"].sudo()
        stale = DataSource.create(_ds_vals("dci_compliance_stale", DEFAULT_COMPLIANCE_BEARER_TOKEN))
        rekeyed = DataSource.create(_ds_vals("dci_compliance_rekeyed", "operator-real-token"))

        removed = DataSource._purge_default_compliance_bearer_token()

        self.assertEqual(removed, 1)
        self.assertFalse(stale.exists())
        self.assertTrue(rekeyed.exists())

    def test_purge_matches_on_token_only_not_flag_or_name(self):
        # A default-token record that is neither flagged nor named as a
        # compliance record must still be purged - the match is token-only.
        DataSource = self.env["spp.dci.data.source"].sudo()
        unflagged = DataSource.create(
            _ds_vals(
                "dci_compliance_unflagged",
                DEFAULT_COMPLIANCE_BEARER_TOKEN,
                name="Some Other Data Source",
                is_compliance_test=False,
            )
        )

        removed = DataSource._purge_default_compliance_bearer_token()

        self.assertEqual(removed, 1)
        self.assertFalse(unflagged.exists())


@tagged("post_install", "-at_install")
class TestControllerRejectsDefaultToken(TransactionCase):
    """The controller must not serve a retained default-token data source.

    Even if the migration is skipped, ``_get_test_data_source`` must treat a
    record still holding the known default token as absent and fall through to
    the fail-closed create path (which requires an operator-configured token).
    """

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_client_compliance.controllers.trigger import (
            DCIClientTriggerController,
        )

        self.controller = DCIClientTriggerController()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(BEARER_TOKEN_PARAM, "operator-real-token")
        ICP.set_param(MOCK_URL_PARAM, "http://mock_registry:3335")

    def _run_with_request(self):
        import odoo.addons.spp_dci_client_compliance.controllers.trigger as mod

        class FakeRequest:
            env = self.env

        original = mod.__dict__["request"]
        mod.request = FakeRequest()
        try:
            return self.controller._get_test_data_source()
        finally:
            mod.request = original

    def test_default_token_record_is_not_served(self):
        DataSource = self.env["spp.dci.data.source"].sudo()
        DataSource.create(_ds_vals("dci_compliance_stale", DEFAULT_COMPLIANCE_BEARER_TOKEN))

        result = self._run_with_request()

        self.assertNotEqual(
            result.bearer_token,
            DEFAULT_COMPLIANCE_BEARER_TOKEN,
            "Controller must not return a data source still holding the default token",
        )
        self.assertEqual(result.bearer_token, "operator-real-token")

    def test_default_token_record_matched_by_name_is_not_served(self):
        # is_compliance_test=False so only the by-name fallback can find it.
        DataSource = self.env["spp.dci.data.source"].sudo()
        DataSource.create(
            _ds_vals(
                "dci_compliance_named",
                DEFAULT_COMPLIANCE_BEARER_TOKEN,
                is_compliance_test=False,
            )
        )

        result = self._run_with_request()

        self.assertNotEqual(result.bearer_token, DEFAULT_COMPLIANCE_BEARER_TOKEN)
        self.assertEqual(result.bearer_token, "operator-real-token")

    def test_operator_token_record_is_served(self):
        DataSource = self.env["spp.dci.data.source"].sudo()
        rekeyed = DataSource.create(_ds_vals("dci_compliance_rekeyed", "operator-real-token"))

        result = self._run_with_request()

        self.assertEqual(result.id, rekeyed.id, "A properly configured record must still be used")


@tagged("post_install", "-at_install")
class TestCreatePathRejectsDefaultToken(TransactionCase):
    """The create path must refuse the well-known default token when configured.

    Guarding only the search paths is not enough: if an operator sets
    ``dci.client_compliance.bearer_token`` to the public default (as the module
    docs previously suggested), the create path would mint a fresh data source
    carrying it - recreating the exposure through the front door.
    ``_get_compliance_bearer_token`` therefore rejects the default value.
    """

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_client_compliance.controllers.trigger import (
            DCIClientTriggerController,
        )

        self.controller = DCIClientTriggerController()
        self.ICP = self.env["ir.config_parameter"].sudo()
        self.ICP.set_param(MOCK_URL_PARAM, "http://mock_registry:3335")

    def _run(self, method_name):
        import odoo.addons.spp_dci_client_compliance.controllers.trigger as mod

        class FakeRequest:
            env = self.env

        original = mod.__dict__["request"]
        mod.request = FakeRequest()
        try:
            return getattr(self.controller, method_name)()
        finally:
            mod.request = original

    def test_get_bearer_token_rejects_default(self):
        self.ICP.set_param(BEARER_TOKEN_PARAM, DEFAULT_COMPLIANCE_BEARER_TOKEN)
        with self.assertRaises(UserError):
            self.controller._get_compliance_bearer_token(self.env)

    def test_create_path_refuses_to_mint_default_token_record(self):
        self.ICP.set_param(BEARER_TOKEN_PARAM, DEFAULT_COMPLIANCE_BEARER_TOKEN)
        with self.assertRaises(UserError):
            self._run("_create_test_data_source")
        # Nothing was created carrying the default token.
        count = (
            self.env["spp.dci.data.source"]
            .sudo()
            .search_count([("bearer_token", "=", DEFAULT_COMPLIANCE_BEARER_TOKEN)])
        )
        self.assertEqual(count, 0)

    def test_create_path_succeeds_with_private_token(self):
        self.ICP.set_param(BEARER_TOKEN_PARAM, "operator-real-token")
        result = self._run("_create_test_data_source")
        self.assertTrue(result)
        self.assertEqual(result.bearer_token, "operator-real-token")
