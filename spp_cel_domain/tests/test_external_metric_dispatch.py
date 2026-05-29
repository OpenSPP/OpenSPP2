# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the external-variable dispatch path in `spp.cel.executor._exec_metric`.

These cover two framework touches needed by the Notary integration:

- Touch #3: provider hook on cache miss. When a metric corresponds to a
  `source_type='external'` variable with a configured provider, the executor
  dispatches cache misses to `provider._compute_external_values(...)` instead
  of warning and returning [].
- Touch #5: provider scoping in metric lookup. External variables MUST NOT
  fall back across providers; a value cached under Provider A is not
  interchangeable with the same accessor under Provider B.
"""

import time
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from .common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestExternalVariableLookup(TransactionCase, CELTestDataMixin):
    """`_external_variable_for_metric` should return only external+provider variables."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.executor = cls.env["spp.cel.executor"]
        cls.Provider = cls.env["spp.data.provider"]
        cls.provider = cls.Provider.create(
            {
                "name": "Test Provider",
                "code": f"test_lookup_{cls._test_id}",
            }
        )
        cls.category = cls._create_test_category()

    def test_returns_variable_when_external_with_provider(self):
        name = f"ext_with_provider_{self._test_id}"
        var = self._create_test_variable(
            name=name,
            source_type="external",
            category=self.category,
            external_provider_id=self.provider.id,
        )
        result = self.executor._external_variable_for_metric(name)
        self.assertTrue(result)
        self.assertEqual(result.id, var.id)

    def test_returns_empty_when_field_variable(self):
        name = f"field_var_{self._test_id}"
        self._create_test_variable(
            name=name,
            source_type="field",
            source_field="email",
            category=self.category,
        )
        result = self.executor._external_variable_for_metric(name)
        self.assertFalse(result)

    def test_returns_empty_when_metric_unknown(self):
        result = self.executor._external_variable_for_metric(f"unknown_metric_{self._test_id}")
        self.assertFalse(result)


@tagged("post_install", "-at_install")
class TestExternalMetricDispatch(TransactionCase, CELTestDataMixin):
    """`_exec_metric` should batch cache misses through the provider hook."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.executor = cls.env["spp.cel.executor"]
        cls.Provider = cls.env["spp.data.provider"]
        cls.DataValue = cls.env["spp.data.value"]
        cls.service = cls.env["spp.cel.service"]
        cls.category = cls._create_test_category()
        cls.provider = cls.Provider.create(
            {
                "name": "Notary-like Provider",
                "code": f"notary_like_{cls._test_id}",
            }
        )
        cls.partner_a = cls._create_test_partner(name=f"A {cls._test_id}")
        cls.partner_b = cls._create_test_partner(name=f"B {cls._test_id}")
        cls.partner_c = cls._create_test_partner(name=f"C {cls._test_id}")
        cls.variable = cls._create_test_variable(
            name=f"ext_metric_{cls._test_id}",
            cel_accessor=f"ext_metric_{cls._test_id}",
            source_type="external",
            value_type="number",
            cache_strategy="ttl",
            category=cls.category,
            external_provider_id=cls.provider.id,
        )

    def setUp(self):
        super().setUp()
        # Clear any cached values from previous runs in the same DB.
        self.DataValue.search(
            [
                ("variable_name", "=", self.variable.cel_accessor),
                ("company_id", "=", self.env.company.id),
            ]
        ).unlink()

    def test_compute_hook_invoked_once_for_cache_misses(self):
        """Empty cache calls provider._compute_external_values once per domain batch."""
        base_domain = [
            (
                "id",
                "in",
                [self.partner_a.id, self.partner_b.id, self.partner_c.id],
            )
        ]
        # Return a value for A and B; None for C (no upstream evidence).
        per_subject = {
            self.partner_a.id: 90,
            self.partner_b.id: 60,
            self.partner_c.id: None,
        }

        def fake_compute(self_provider, variable, subject_ids, period_key):
            return {subject_id: per_subject.get(subject_id) for subject_id in subject_ids}

        with patch.object(
            type(self.provider),
            "_compute_external_values",
            autospec=True,
            side_effect=fake_compute,
        ) as mocked:
            result = self.service.compile_expression(
                f"{self.variable.cel_accessor} > 75",
                "registry_individuals",
                base_domain=base_domain,
            )

        mocked.assert_called_once()
        args, _kwargs = mocked.call_args
        self.assertEqual(args[1].id, self.variable.id)
        self.assertEqual(set(args[2]), {self.partner_a.id, self.partner_b.id, self.partner_c.id})
        self.assertTrue(result["valid"], result.get("error"))
        matching_ids = result["ids"]
        self.assertIn(self.partner_a.id, matching_ids)
        self.assertNotIn(self.partner_b.id, matching_ids)
        self.assertNotIn(self.partner_c.id, matching_ids)


@tagged("post_install", "-at_install")
class TestExternalProviderCacheIsolation(TransactionCase, CELTestDataMixin):
    """Cached values under Provider A must not satisfy a query against Provider B."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.Provider = cls.env["spp.data.provider"]
        cls.DataValue = cls.env["spp.data.value"]
        cls.service = cls.env["spp.cel.service"]
        cls.category = cls._create_test_category()
        cls.provider_a = cls.Provider.create(
            {
                "name": "Provider A",
                "code": f"prov_a_{cls._test_id}",
            }
        )
        cls.provider_b = cls.Provider.create(
            {
                "name": "Provider B",
                "code": f"prov_b_{cls._test_id}",
            }
        )
        cls.partner = cls._create_test_partner(name=f"Iso {cls._test_id}")

    def _create_variable(self, suffix, provider):
        name = f"shared_acc_{suffix}_{self._test_id}"
        return self._create_test_variable(
            name=name,
            cel_accessor=name,
            source_type="external",
            value_type="number",
            cache_strategy="ttl",
            category=self.category,
            external_provider_id=provider.id,
        )

    def test_cached_value_under_other_provider_not_matched(self):
        """Variable bound to Provider B, but cache row under Provider A. No fallback."""
        # Variable is bound to Provider B.
        var = self._create_variable("b", self.provider_b)
        # But a cache row exists under Provider A (e.g. legacy data, or
        # another deployment's value bleeding through). Without the scope
        # tightening this row would satisfy the lookup.
        self.DataValue.create(
            {
                "variable_name": var.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": self.partner.id,
                "period_key": "current",
                "value_json": {"value": 999},
                "source_type": "external",
                "provider": self.provider_a.code,
            }
        )

        # Mock Provider B's compute hook so we can detect whether the executor
        # had to refresh (it should, because A's row must not satisfy B).
        with patch.object(
            type(self.provider_b),
            "_compute_external_values",
            autospec=True,
            return_value={self.partner.id: 10},
        ) as mocked:
            result = self.service.compile_expression(
                f"{var.cel_accessor} > 100",
                "registry_individuals",
                base_domain=[("id", "=", self.partner.id)],
            )

        self.assertTrue(result["valid"], result.get("error"))
        # Provider B's compute hook MUST be invoked since the cache lookup
        # under B's code was empty.
        mocked.assert_called_once()
        # And the partner must NOT match: B returned 10, threshold is > 100.
        self.assertNotIn(self.partner.id, result["ids"])
