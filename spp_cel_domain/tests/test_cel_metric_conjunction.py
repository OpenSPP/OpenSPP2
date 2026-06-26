# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Composing multiple metric() comparisons with and/or.

The fresh-cache SQL shortcut for a single metric comparison returns no ids
and stashes an override domain for the caller. That shortcut is only valid
when the comparison IS the whole plan: inside a conjunction or disjunction
the override of the first metric must not replace the composed result
(live-found: `metricA == true and metricB == true` matched everyone that
matched metricA alone).
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCelMetricConjunction(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc = cls.env["spp.cel.service"]
        Partner = cls.env["res.partner"]
        cls.a = Partner.create({"name": "Conj A", "is_registrant": True, "is_group": False})
        cls.b = Partner.create({"name": "Conj B", "is_registrant": True, "is_group": False})
        cls.c = Partner.create({"name": "Conj C", "is_registrant": True, "is_group": False})
        # Complete, fresh cache for both metrics across all three subjects:
        # m1: A=1, B=1, C=0   /   m2: A=1, B=0, C=1
        rows = []
        for metric, values in (
            ("zz.conj.m1", {cls.a: 1, cls.b: 1, cls.c: 0}),
            ("zz.conj.m2", {cls.a: 1, cls.b: 0, cls.c: 1}),
        ):
            for partner, value in values.items():
                rows.append(
                    {
                        "variable_name": metric,
                        "subject_model": "res.partner",
                        "subject_id": partner.id,
                        "period_key": "current",
                        "value_json": {"value": value},
                        "value_type": "number",
                        "source_type": "external",
                        "ttl_seconds": 3600,
                    }
                )
        cls.env["spp.data.value"].upsert_values(rows)

    def _match(self, expr):
        r = self.svc.compile_expression(
            expr,
            profile="registry_individuals",
            base_domain=[("id", "in", (self.a | self.b | self.c).ids)],
            limit=0,
            materialize_sql=True,
        )
        self.assertTrue(r.get("valid"), r.get("error"))
        return self.env["res.partner"].search(r["domain"])

    def test_metric_and_metric_intersects(self):
        matched = self._match("metric('zz.conj.m1', me) >= 1 and metric('zz.conj.m2', me) >= 1")
        self.assertEqual(matched, self.a, f"AND must intersect both metrics, got {matched.mapped('name')}")

    def test_metric_or_metric_unions(self):
        matched = self._match("metric('zz.conj.m1', me) >= 1 or metric('zz.conj.m2', me) >= 1")
        self.assertEqual(
            matched,
            self.a | self.b | self.c,
            f"OR must union both metrics, got {matched.mapped('name')}",
        )

    def test_single_metric_shortcut_still_works(self):
        """The root-level single-metric shortcut keeps its behavior."""
        matched = self._match("metric('zz.conj.m1', me) >= 1")
        self.assertEqual(matched, self.a | self.b)
