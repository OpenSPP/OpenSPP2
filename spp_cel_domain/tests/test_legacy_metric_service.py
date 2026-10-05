# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The executor resolves the legacy metric evaluation service by capability.

``spp.indicator`` is a model name shared by two unrelated things: the retired
``spp_indicators`` evaluation service (``evaluate()`` and
``enqueue_refresh_from_domain()``) the executor was written against, and
OpenSPP2's ``spp_indicator`` configuration model. Only the former may be used
as the service; the latter must be treated as "no service", which is the
graceful path ``TestCELExecutorCacheLookup`` asserts and the path a full stack
with ``spp_indicator`` installed used to crash on.
"""

from unittest.mock import patch

from odoo.api import Environment
from odoo.tests import TransactionCase, tagged


class _LegacyService:
    """The shape of the retired service: both methods, both callable."""

    def evaluate(self, *args, **kwargs):
        return {}, {}

    def enqueue_refresh_from_domain(self, *args, **kwargs):
        return None


class _EvaluateOnly:
    def evaluate(self, *args, **kwargs):
        return {}, {}


@tagged("post_install", "-at_install")
class TestLegacyMetricService(TransactionCase):
    def setUp(self):
        super().setUp()
        self.executor = self.env["spp.cel.executor"]

    def test_no_service_in_this_database(self):
        """No module in the repository provides the service, with or without
        spp_indicator installed, so the probe must report none either way."""
        self.assertIsNone(self.executor._legacy_metric_service())

    def test_real_model_without_the_methods_is_not_the_service(self):
        """A genuine Odoo model that merely carries the name is not the service."""
        with patch.object(Environment, "get", return_value=self.env["res.partner"]) as env_get:
            self.assertIsNone(self.executor._legacy_metric_service())
        env_get.assert_called_once_with("spp.indicator")

    def test_evaluate_alone_is_not_enough(self):
        """The executor also enqueues refreshes; both methods are required."""
        with patch.object(Environment, "get", return_value=_EvaluateOnly()):
            self.assertIsNone(self.executor._legacy_metric_service())

    def test_model_with_both_methods_is_the_service(self):
        service = _LegacyService()
        with patch.object(Environment, "get", return_value=service) as env_get:
            self.assertIs(self.executor._legacy_metric_service(), service)
        env_get.assert_called_once_with("spp.indicator")
