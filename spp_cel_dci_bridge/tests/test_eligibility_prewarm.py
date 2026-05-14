"""Verify that _prepare_eligible_domain pre-warms the cache.

The cycle-based eligibility flow calls _precompute_cycle_cached_variables
on its own. The program-level Import Eligible / Enroll Eligible flow
does NOT — without this override, the executor hits an "incomplete cache"
state and falls back to a legacy Python path (spp.indicator.evaluate)
that no longer exists in Odoo 19.

This test confirms:
  - _prepare_eligible_domain calls cache_mgr.precompute_cached_variables
    when the manager carries a CEL expression
  - It does NOT call precompute when there's no CEL expression (back-compat)
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEligibilityPreWarm(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.program = cls.env["spp.program"].create({"name": "Pre-Warm Test Program", "target_type": "individual"})
        cls.manager_default = cls.env["spp.program.membership.manager.default"].create(
            {"name": "Pre-Warm EM", "program_id": cls.program.id}
        )
        em = cls.env["spp.eligibility.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"{cls.manager_default._name},{cls.manager_default.id}",
            }
        )
        cls.program.write({"eligibility_manager_ids": [(4, em.id)]})

    def test_no_cel_expression_no_prewarm(self):
        """When the manager has no CEL expression, the parent flow runs
        and we must NOT touch the cache manager — that path may not even
        have cached variables installed."""
        self.manager_default.cel_expression = False
        with patch.object(
            self.env["spp.data.cache.manager"].__class__,
            "precompute_cached_variables",
        ) as mock_pre:
            self.manager_default._prepare_eligible_domain(membership=None)
            mock_pre.assert_not_called()

    def test_cel_expression_triggers_prewarm(self):
        """When the manager has a CEL expression, pre-warm fires BEFORE
        compile_expression, ensuring the SQL fast path is available."""
        # The cohort search needs at least one registrant matching the base
        # domain (is_registrant=True, is_group=False, disabled=False) —
        # otherwise pre-warm short-circuits on empty subject_ids.
        self.env["res.partner"].create(
            {
                "name": "Cohort Member",
                "is_registrant": True,
                "is_group": False,
            }
        )
        self.manager_default.cel_expression = "true"  # trivially valid
        with patch.object(
            self.env["spp.data.cache.manager"].__class__,
            "precompute_cached_variables",
            return_value={"success": True, "variables_processed": 0},
        ) as mock_pre:
            self.manager_default._prepare_eligible_domain(membership=None)
            mock_pre.assert_called_once()
            # Verify call signature matches what cycle_manager_base uses
            call_kwargs = mock_pre.call_args.kwargs
            self.assertEqual(call_kwargs.get("period_key"), "current")
            self.assertEqual(call_kwargs.get("program_id"), self.program.id)

    def test_empty_cohort_skips_prewarm(self):
        """When no partner matches the base domain, pre-warm is a no-op
        (early return before calling the cache manager) — saves a no-op
        call into spp_cel_domain."""
        # Ensure no registrants exist that match the base domain
        self.env["res.partner"].search([("is_registrant", "=", True), ("is_group", "=", False)]).write(
            {"is_registrant": False}
        )

        self.manager_default.cel_expression = "true"
        with patch.object(
            self.env["spp.data.cache.manager"].__class__,
            "precompute_cached_variables",
        ) as mock_pre:
            self.manager_default._prepare_eligible_domain(membership=None)
            mock_pre.assert_not_called()

    def test_prewarm_does_not_raise_when_cache_manager_fails(self):
        """A pre-warm failure must not block eligibility evaluation. The
        CEL evaluator will report its own error if the cache is still
        incomplete after."""
        self.manager_default.cel_expression = "true"
        with patch.object(
            self.env["spp.data.cache.manager"].__class__,
            "precompute_cached_variables",
            side_effect=RuntimeError("simulated cache failure"),
        ):
            # Must not raise
            self.manager_default._prepare_eligible_domain(membership=None)

    def test_prewarm_scopes_cohort_to_membership_when_provided(self):
        """If membership is passed, pre-warm only those partners — saves
        the cost of fetching for the entire registrant base."""
        partner = self.env["res.partner"].create({"name": "Test Reg", "is_registrant": True, "is_group": False})
        membership = self.env["spp.program.membership"].create(
            {"partner_id": partner.id, "program_id": self.program.id, "state": "draft"}
        )
        self.manager_default.cel_expression = "true"
        with patch.object(
            self.env["spp.data.cache.manager"].__class__,
            "precompute_cached_variables",
            return_value={"success": True, "variables_processed": 0},
        ) as mock_pre:
            self.manager_default._prepare_eligible_domain(membership=membership)
            mock_pre.assert_called_once()
            args = mock_pre.call_args.args
            # First positional arg is subject_ids — must include the partner
            self.assertIn(partner.id, args[0])
