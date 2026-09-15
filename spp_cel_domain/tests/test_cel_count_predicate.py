# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""`members.count(predicate)` must honour its predicate when compared.

Both call styles are supported: a single argument is the predicate with `m`
implicit (ADR-008), two arguments are an explicit loop variable and predicate.
The comparison path used to read the first argument as the loop variable
whichever style was used, substituting a `True` predicate when there was no
second one. `members.count(pred) > n` therefore counted every member.

Nothing raised. Every aggregate `count` variable -- child_count,
elderly_count, working_age_count -- silently returned the household size, so
any program targeting on one matched every household.
"""

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCountPredicate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.cel.service"]

        def individual(name, years):
            return cls.env["res.partner"].create(
                {
                    "name": name,
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date.today() - relativedelta(years=years, days=30),
                }
            )

        # One household of adults only, one with a child. A predicate that is
        # honoured separates them; one that is dropped cannot.
        cls.adults_only = cls.env["res.partner"].create(
            {"name": "COUNT Adults Only [TEST]", "is_registrant": True, "is_group": True}
        )
        cls.with_child = cls.env["res.partner"].create(
            {"name": "COUNT With Child [TEST]", "is_registrant": True, "is_group": True}
        )
        cls.members = {
            cls.adults_only: [individual("COUNT Adult A [TEST]", 40), individual("COUNT Adult B [TEST]", 38)],
            cls.with_child: [individual("COUNT Adult C [TEST]", 35), individual("COUNT Child [TEST]", 4)],
        }
        for group, members in cls.members.items():
            for member in members:
                cls.env["spp.group.membership"].create({"group": group.id, "individual": member.id})

    def _matches(self, expression):
        result = self.service.compile_expression(expression, "registry_groups", limit=0, materialize_sql=True)
        self.assertTrue(result["valid"], f"{expression!r} did not compile: {result.get('error')}")
        matched = self.env["res.partner"].search(result["domain"] or [])
        return matched

    def test_single_argument_count_honours_its_predicate(self):
        """The regression: `members.count(pred) > 0` used to ignore pred."""
        matched = self._matches("members.count(age_years(m.birthdate) < 18) > 0")

        self.assertIn(self.with_child, matched, "the household with a child should match")
        self.assertNotIn(
            self.adults_only,
            matched,
            "an adults-only household matched a child predicate, so the predicate was dropped",
        )

    def test_both_call_styles_agree(self):
        """Explicit loop variable and implicit `m` must give the same answer."""
        implicit = self._matches("members.count(age_years(m.birthdate) < 18) > 0")
        explicit = self._matches("members.count(m, age_years(m.birthdate) < 18) > 0")

        self.assertEqual(set(implicit.ids), set(explicit.ids))

    def test_count_agrees_with_the_equivalent_exists(self):
        """`count(pred) > 0` and `exists(m, pred)` answer the same question.

        exists() was always right, which is why variables built on it kept
        working while every count-based one did not.
        """
        counted = self._matches("members.count(age_years(m.birthdate) < 18) > 0")
        existed = self._matches("members.exists(m, age_years(m.birthdate) < 18)")

        self.assertEqual(set(counted.ids), set(existed.ids))

    def test_a_bare_loop_variable_still_counts_everyone(self):
        """`members.count(m) > 1` has no predicate and must not gain one."""
        matched = self._matches("members.count(m) > 1")

        self.assertIn(self.adults_only, matched)
        self.assertIn(self.with_child, matched)


@tagged("post_install", "-at_install")
class TestArithmeticOverAggregates(TransactionCase):
    """Arithmetic containing an aggregate has to keep the aggregate's meaning.

    No Odoo domain can express `(child_count + elderly_count) / max(1,
    working_age_count) >= 1.5`, and the translator used to resolve the whole
    left-hand side to the field `id`. `dependency_ratio >= 1.5` became
    `('id', '>=', 1.5)`: every record, silently.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.cel.service"]

        def individual(name, years):
            return cls.env["res.partner"].create(
                {
                    "name": name,
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date.today() - relativedelta(years=years, days=30),
                }
            )

        def household(name, ages):
            group = cls.env["res.partner"].create({"name": name, "is_registrant": True, "is_group": True})
            for index, years in enumerate(ages):
                member = individual(f"{name} m{index} [TEST]", years)
                cls.env["spp.group.membership"].create({"group": group.id, "individual": member.id})
            return group

        # dependents / workers: 2/2 = 1.0, and 3/1 = 3.0
        cls.low_ratio = household("ARITH Low Ratio [TEST]", [40, 38, 10, 8])
        cls.high_ratio = household("ARITH High Ratio [TEST]", [40, 10, 8, 70])

    def _matches(self, expression):
        result = self.service.compile_expression(expression, "registry_groups", limit=0, materialize_sql=True)
        self.assertTrue(result["valid"], f"{expression!r} did not compile: {result.get('error')}")
        return self.env["res.partner"].search(result["domain"] or [])

    # Written out rather than using child_count / elderly_count: those
    # variables are defined in spp_studio, and this module's tests must not
    # depend on it being installed.
    CHILDREN = "members.count(age_years(m.birthdate) < 18)"
    ELDERLY = "members.count(age_years(m.birthdate) >= 60)"
    WORKING = "members.count(age_years(m.birthdate) >= 18 && age_years(m.birthdate) < 60)"

    def test_a_count_inside_arithmetic_keeps_its_predicate(self):
        """Adding `+ 0` must not change the answer."""
        plain = self._matches(f"{self.CHILDREN} > 0")
        with_arithmetic = self._matches(f"{self.CHILDREN} + 0 > 0")

        self.assertEqual(set(plain.ids), set(with_arithmetic.ids))
        self.assertIn(self.low_ratio, plain, "this household has two children")

    def test_a_sum_of_two_aggregates_is_not_a_count_of_everyone(self):
        """Each aggregate has to keep its own predicate, not share one."""
        dependents = self._matches(f"({self.CHILDREN} + {self.ELDERLY}) >= 3")

        # low_ratio has 2 children and no elderly; high_ratio has 2 children
        # and 1 elderly member.
        self.assertIn(self.high_ratio, dependents)
        self.assertNotIn(self.low_ratio, dependents)

    def test_a_ratio_of_aggregates_discriminates(self):
        """The dependency-ratio shape, on households built to sit either side."""
        matched = self._matches(f"({self.CHILDREN} + {self.ELDERLY}) / max(1, {self.WORKING}) >= 1.5")

        self.assertIn(self.high_ratio, matched, "3 dependents to 1 worker is a ratio of 3.0")
        self.assertNotIn(self.low_ratio, matched, "2 dependents to 2 workers is a ratio of 1.0")

    def test_division_by_a_zero_aggregate_does_not_explode(self):
        """max(1, ...) is the usual guard, but the evaluator must be safe without it."""
        result = self.service.compile_expression(
            f"{self.CHILDREN} / {self.ELDERLY} > 1", "registry_groups", limit=0, materialize_sql=True
        )

        self.assertTrue(result["valid"], f"did not compile: {result.get('error')}")

    def test_an_unresolvable_comparison_is_refused_not_ignored(self):
        """The failure mode that caused all of this must be loud.

        An expression the translator cannot resolve used to become a
        comparison on `id`, which matches every record with a positive
        threshold. Returning nothing, or raising, is recoverable; silently
        matching everyone is not.
        """
        result = self.service.compile_expression(
            "no_such_variable_xyz > 0", "registry_groups", limit=0, materialize_sql=True
        )

        if result.get("valid"):
            matched = self.env["res.partner"].search(result["domain"] or [])
            everyone = self.env["res.partner"].search([("is_registrant", "=", True), ("is_group", "=", True)])
            self.assertNotEqual(
                set(matched.ids),
                set(everyone.ids),
                "an unresolvable expression matched every record",
            )
