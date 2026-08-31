# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Unit tests for the params-compatibility guard used before calling the
legacy/external evaluation service (spp.indicator.evaluate).

The metric compute path passes the metric's params to svc.evaluate only when
that method accepts a `params` kwarg, so a parameterized refresh is computed
with the right params without risking a TypeError on an older service that
predates the kwarg. See _evaluate_accepts_params / _svc_evaluate_batch in
cel_executor.py.
"""

from odoo.tests.common import TransactionCase, tagged


class _EvalWithParams:
    def evaluate(self, metric, model, ids, period_key, mode="fallback", params=None):
        return {}, {}


class _EvalWithKwargs:
    def evaluate(self, metric, model, ids, period_key, **kwargs):
        return {}, {}


class _EvalNoParams:
    def evaluate(self, metric, model, ids, period_key, mode="fallback"):
        return {}, {}


class _NonCallableEvaluate:
    evaluate = 42  # inspect.signature() raises TypeError -> degrade to False


@tagged("post_install", "-at_install")
class TestEvaluateAcceptsParams(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.executor = cls.env["spp.cel.executor"]

    def test_explicit_params_arg_supported(self):
        self.assertTrue(self.executor._evaluate_accepts_params(_EvalWithParams()))

    def test_var_keyword_supported(self):
        self.assertTrue(self.executor._evaluate_accepts_params(_EvalWithKwargs()))

    def test_no_params_not_supported(self):
        self.assertFalse(self.executor._evaluate_accepts_params(_EvalNoParams()))

    def test_uninspectable_evaluate_degrades_to_false(self):
        self.assertFalse(self.executor._evaluate_accepts_params(_NonCallableEvaluate()))
