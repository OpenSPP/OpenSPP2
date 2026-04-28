# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Regression tests for OP#929: aggregate `spp.cel.variable` references in CEL.

Before the fix, a comparison like `hh_total_income < poverty_line` where
`hh_total_income` is a `source_type='aggregate'` variable compiled to a
`('hh_total_income', '<', 2500)` triple on `res.partner` and the ORM rejected
it with `ValueError: Invalid field res.partner.hh_total_income`.

The translator now rewrites the bare ident into the equivalent
`members.<agg>(m, m.<field>, <filter>)` AST and reuses the existing
aggregate-handler path, producing a subquery the ORM accepts.
"""

from datetime import date, timedelta

from odoo.tests.common import TransactionCase


class TestCelAggregateVariable(TransactionCase):
    """Aggregate variables referenced as bare idents in comparisons."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # H1: total income 5000+3000+0 = 8000, 1 minor.
        cls.h1 = cls.env["res.partner"].create({"name": "H1", "is_registrant": True, "is_group": True})
        for nm, age, inc in [
            ("Head H1", 40, 5000),
            ("Spouse H1", 38, 3000),
            ("Child H1", 10, 0),
        ]:
            ind = cls.env["res.partner"].create(
                {
                    "name": nm,
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date.today() - timedelta(days=age * 365),
                    "income": inc,
                }
            )
            cls.env["spp.group.membership"].create({"group": cls.h1.id, "individual": ind.id})

        # H2: total income 1000+800 = 1800, no minors.
        cls.h2 = cls.env["res.partner"].create({"name": "H2", "is_registrant": True, "is_group": True})
        for nm, age, inc in [
            ("Head H2", 50, 1000),
            ("Spouse H2", 48, 800),
        ]:
            ind = cls.env["res.partner"].create(
                {
                    "name": nm,
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date.today() - timedelta(days=age * 365),
                    "income": inc,
                }
            )
            cls.env["spp.group.membership"].create({"group": cls.h2.id, "individual": ind.id})

        cls.cfg = {
            "root_model": "res.partner",
            "base_domain": [("is_registrant", "=", True), ("is_group", "=", True)],
            "symbols": {
                "r": {"model": "res.partner"},
                "members": {
                    "relation": "rel",
                    "through": "spp.group.membership",
                    "parent": "group",
                    "link_to": "individual",
                    "default_domain": [("is_ended", "=", False)],
                },
            },
        }

        # Aggregate variables under test.
        Var = cls.env["spp.cel.variable"]
        cls.hh_total_income = Var.create(
            {
                "name": "hh_total_income",
                "cel_accessor": "hh_total_income",
                "source_type": "aggregate",
                "aggregate_type": "sum",
                "aggregate_target": "members",
                "aggregate_field": "income",
                "aggregate_filter": "true",
                "value_type": "money",
                "applies_to": "group",
                "active": True,
                "state": "active",
            }
        )
        cls.child_count = Var.create(
            {
                "name": "child_count",
                "cel_accessor": "child_count",
                "source_type": "aggregate",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "age_years(m.birthdate) < 18",
                "value_type": "number",
                "applies_to": "group",
                "active": True,
                "state": "active",
            }
        )

    def test_sum_variable_in_comparison(self):
        """`hh_total_income < 2500` filters households whose summed member
        income is below 2500. H1 (8000) excluded, H2 (1800) included.

        Before OP#929 fix, the translator emitted a domain referencing a
        non-existent field on `res.partner` and the ORM raised ValueError.
        """
        executor = self.env["spp.cel.executor"]
        result = executor.with_context(cel_cfg=self.cfg).compile_and_preview(
            "res.partner",
            "hh_total_income < 2500",
            limit=100,
        )
        self.assertNotIn(self.h1.id, result["ids"])
        self.assertIn(self.h2.id, result["ids"])

    def test_count_variable_in_comparison(self):
        """`child_count > 0` filters households with at least one minor.
        H1 has 1, H2 has 0.
        """
        executor = self.env["spp.cel.executor"]
        result = executor.with_context(cel_cfg=self.cfg).compile_and_preview(
            "res.partner",
            "child_count > 0",
            limit=100,
        )
        self.assertIn(self.h1.id, result["ids"])
        self.assertNotIn(self.h2.id, result["ids"])

    def test_combined_aggregate_variables(self):
        """Combine two aggregate variables — the original failing case from
        OP#929: `r.is_group && hh_total_income < 2500 && child_count > 0`.

        H1: 8000 / 1 minor → fails income gate.
        H2: 1800 / 0 minors → fails child gate.
        Neither matches the AND.
        """
        executor = self.env["spp.cel.executor"]
        result = executor.with_context(cel_cfg=self.cfg).compile_and_preview(
            "res.partner",
            "r.is_group && hh_total_income < 2500 && child_count > 0",
            limit=100,
        )
        self.assertNotIn(self.h1.id, result["ids"])
        self.assertNotIn(self.h2.id, result["ids"])

    def test_unknown_ident_still_raises(self):
        """Bare ident that resolves to nothing must keep raising — the new
        branch must not silently swallow typos as aggregate vars.
        """
        executor = self.env["spp.cel.executor"]
        with self.assertRaises(ValueError):
            executor.with_context(cel_cfg=self.cfg).compile_and_preview(
                "res.partner",
                "totally_unknown_var < 100",
                limit=100,
            )
