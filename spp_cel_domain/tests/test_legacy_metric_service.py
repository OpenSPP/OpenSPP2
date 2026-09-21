# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The executor resolves the legacy metric evaluation service by capability.

``spp.indicator`` is a model name shared by two unrelated things: the retired
``spp_indicators`` evaluation service (``evaluate()``) the executor was written
against, and OpenSPP2's ``spp_indicator`` configuration model. Only the former
may be used as the service; the latter must be treated as "no service", which
is the graceful path ``TestCELExecutorCacheLookup`` asserts and the path a full
stack with ``spp_indicator`` installed used to crash on.
"""

from unittest.mock import MagicMock, patch

from odoo.api import Environment
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLegacyMetricService(TransactionCase):
    def setUp(self):
        super().setUp()
        self.executor = self.env["spp.cel.executor"]

    def test_no_model_means_no_service(self):
        """Without any spp.indicator model the probe reports no service."""
        if "spp.indicator" in self.env:
            self.skipTest("spp_indicator is installed in this database")
        self.assertIsNone(self.executor._legacy_metric_service())

    def test_model_without_evaluate_is_not_the_service(self):
        """A model that merely carries the name is not the evaluation service."""
        config_model = MagicMock(spec=[])  # no attributes at all, like spp_indicator's model
        with patch.object(Environment, "get", return_value=config_model):
            self.assertIsNone(self.executor._legacy_metric_service())

    def test_model_with_evaluate_is_the_service(self):
        """A model exposing evaluate() is returned as-is."""
        service = MagicMock(spec=["evaluate"])
        with patch.object(Environment, "get", return_value=service):
            self.assertIs(self.executor._legacy_metric_service(), service)
