from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import BridgeTestBase, make_dr_search_response


@tagged("post_install", "-at_install")
class TestFailurePolicy(BridgeTestBase):
    """Verify the three external_failure_policy values behave correctly."""

    def _patch_client(self, mock_client_class, side_effect=None, return_value=None):
        mock_client = MagicMock()
        if side_effect is not None:
            mock_client.search_by_id.side_effect = side_effect
        else:
            mock_client.search_by_id.return_value = return_value or make_dr_search_response()
        mock_client_class.return_value = mock_client
        return mock_client

    # ------------------------------------------------------------------ null

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_null_policy_swallows_per_subject_errors(self, mock_client_class):
        # Dispatcher succeeds for partner_a, errors for partner_b
        responses = iter([make_dr_search_response(True), Exception("boom")])

        def side_effect(**_):
            r = next(responses)
            if isinstance(r, Exception):
                raise r
            return r

        self._patch_client(mock_client_class, side_effect=side_effect)
        self.variable.external_failure_policy = "null"

        cache_mgr = self.env["spp.data.cache.manager"]
        result = cache_mgr._compute_dci_values(
            self.variable,
            [self.partner_a.id, self.partner_b.id],
            "current",
            program_id=None,
        )

        # null policy: errored subject has no entry (CEL sees null/false)
        self.assertEqual(result, {self.partner_a.id: True})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_null_policy_returns_empty_on_wholesale_failure(self, mock_client_class):
        # Simulate the dispatcher itself raising (e.g., bad config caught late)
        with patch.object(
            self.env["spp.cel.dci.dispatcher"].__class__,
            "fetch_values_for_variable",
            side_effect=RuntimeError("dispatcher broke"),
        ):
            self.variable.external_failure_policy = "null"
            cache_mgr = self.env["spp.data.cache.manager"]
            result = cache_mgr._compute_dci_values(
                self.variable,
                [self.partner_a.id],
                "current",
                program_id=None,
            )

        self.assertEqual(result, {})

    # -------------------------------------------------------------- fail

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_fail_policy_propagates_wholesale_exception(self, mock_client_class):
        with patch.object(
            self.env["spp.cel.dci.dispatcher"].__class__,
            "fetch_values_for_variable",
            side_effect=RuntimeError("dispatcher broke"),
        ):
            self.variable.external_failure_policy = "fail"
            cache_mgr = self.env["spp.data.cache.manager"]

            with self.assertRaises(UserError):
                cache_mgr._compute_dci_values(
                    self.variable,
                    [self.partner_a.id],
                    "current",
                    program_id=None,
                )

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_fail_policy_succeeds_when_dispatcher_succeeds(self, mock_client_class):
        # Even with fail policy, a clean run returns values normally
        self._patch_client(mock_client_class, return_value=make_dr_search_response(True))
        self.variable.external_failure_policy = "fail"

        cache_mgr = self.env["spp.data.cache.manager"]
        result = cache_mgr._compute_dci_values(
            self.variable,
            [self.partner_a.id],
            "current",
            program_id=None,
        )

        self.assertEqual(result, {self.partner_a.id: True})

    # --------------------------------------------------------- last_known

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_last_known_policy_uses_prior_cached_value(self, mock_client_class):
        # Pre-seed a known value in spp.data.value
        DataValue = self.env["spp.data.value"]
        DataValue.create(
            {
                "variable_name": self.variable.name,
                "subject_model": "res.partner",
                "subject_id": self.partner_a.id,
                "period_key": "current",
                "value_json": {"value": True},
                "value_type": "boolean",
                "source_type": "external",
                "provider": self.provider.code,
            }
        )

        # Simulate a wholesale failure
        with patch.object(
            self.env["spp.cel.dci.dispatcher"].__class__,
            "fetch_values_for_variable",
            side_effect=RuntimeError("dispatcher broke"),
        ):
            self.variable.external_failure_policy = "last_known"
            cache_mgr = self.env["spp.data.cache.manager"]
            result = cache_mgr._compute_dci_values(
                self.variable,
                [self.partner_a.id],
                "current",
                program_id=None,
            )

        # Should surface the previously-cached value
        self.assertEqual(result, {self.partner_a.id: True})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_last_known_policy_no_prior_value_yields_empty(self, mock_client_class):
        with patch.object(
            self.env["spp.cel.dci.dispatcher"].__class__,
            "fetch_values_for_variable",
            side_effect=RuntimeError("dispatcher broke"),
        ):
            self.variable.external_failure_policy = "last_known"
            cache_mgr = self.env["spp.data.cache.manager"]
            result = cache_mgr._compute_dci_values(
                self.variable,
                [self.partner_a.id],
                "current",
                program_id=None,
            )

        # No prior cached value, so result remains empty
        self.assertEqual(result, {})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_last_known_skips_null_prior_values(self, mock_client_class):
        DataValue = self.env["spp.data.value"]
        DataValue.create(
            {
                "variable_name": self.variable.name,
                "subject_model": "res.partner",
                "subject_id": self.partner_a.id,
                "period_key": "current",
                "value_json": {"value": None},
                "value_type": "boolean",
                "source_type": "external",
                "provider": self.provider.code,
            }
        )

        with patch.object(
            self.env["spp.cel.dci.dispatcher"].__class__,
            "fetch_values_for_variable",
            side_effect=RuntimeError("dispatcher broke"),
        ):
            self.variable.external_failure_policy = "last_known"
            cache_mgr = self.env["spp.data.cache.manager"]
            result = cache_mgr._compute_dci_values(
                self.variable,
                [self.partner_a.id],
                "current",
                program_id=None,
            )

        # Null prior values are not surfaced as "last known"
        self.assertEqual(result, {})

    @patch("odoo.addons.spp_dci_client_dr.services.dr_service.DCIClient")
    def test_last_known_fills_only_missing_subjects(self, mock_client_class):
        """Partial success: live fetch returns partner_a, last_known fills partner_b."""
        DataValue = self.env["spp.data.value"]
        DataValue.create(
            {
                "variable_name": self.variable.name,
                "subject_model": "res.partner",
                "subject_id": self.partner_b.id,
                "period_key": "current",
                "value_json": {"value": False},
                "value_type": "boolean",
                "source_type": "external",
                "provider": self.provider.code,
            }
        )

        # Live fetch returns A but errors B
        responses = iter([make_dr_search_response(True), Exception("partial fail")])

        def side_effect(**_):
            r = next(responses)
            if isinstance(r, Exception):
                raise r
            return r

        self._patch_client(mock_client_class, side_effect=side_effect)
        self.variable.external_failure_policy = "last_known"

        cache_mgr = self.env["spp.data.cache.manager"]
        result = cache_mgr._compute_dci_values(
            self.variable,
            [self.partner_a.id, self.partner_b.id],
            "current",
            program_id=None,
        )

        # A: live fetch True; B: last_known False
        self.assertEqual(
            result,
            {self.partner_a.id: True, self.partner_b.id: False},
        )
