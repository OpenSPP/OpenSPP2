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
