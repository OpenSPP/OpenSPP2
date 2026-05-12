# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Coverage for the res.partner extension that adds the Scores smart button
and Score Registrant action on registrant forms."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResPartnerScoring(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringResult = cls.env["spp.scoring.result"]

        cls.registrant = cls.Partner.create(
            {"name": "Test Score Registrant", "is_registrant": True, "is_group": False}
        )
        cls.other_registrant = cls.Partner.create(
            {"name": "Second Score Registrant", "is_registrant": True, "is_group": False}
        )

        # Minimal scoring model so we can attach results — no indicators
        # needed; we only need a valid model_id for spp.scoring.result.
        cls.model = cls.ScoringModel.create(
            {
                "name": "Smart-button test model",
                "code": "SMART_BTN",
                "calculation_method": "weighted_sum",
                "expected_total_weight": 1.0,
                "is_active": True,
            }
        )

    # ─── scoring_result_count compute ────────────────────────────────

    def test_scoring_result_count_zero_when_none(self):
        self.assertEqual(self.registrant.scoring_result_count, 0)

    def test_scoring_result_count_reflects_results(self):
        self.ScoringResult.create(
            {
                "model_id": self.model.id,
                "registrant_id": self.registrant.id,
                "score": 1.0,
                "is_complete": True,
            }
        )
        self.ScoringResult.create(
            {
                "model_id": self.model.id,
                "registrant_id": self.registrant.id,
                "score": 2.0,
                "is_complete": True,
            }
        )
        # Recompute and assert
        self.registrant.invalidate_recordset(fnames=["scoring_result_count"])
        self.assertEqual(self.registrant.scoring_result_count, 2)
        # Sibling unaffected
        self.assertEqual(self.other_registrant.scoring_result_count, 0)

    # ─── action_view_scoring_results ─────────────────────────────────

    def test_action_view_scoring_results_returns_act_window(self):
        action = self.registrant.action_view_scoring_results()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.scoring.result")
        self.assertEqual(action["name"], self.registrant.name)
        self.assertIn(("registrant_id", "=", self.registrant.id), action["domain"])
        self.assertEqual(action["context"]["default_registrant_id"], self.registrant.id)

    # ─── action_score_registrant (single + multi) ────────────────────

    def test_action_score_registrant_single_seeds_domain(self):
        action = self.registrant.action_score_registrant()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.batch.scoring.wizard")
        self.assertEqual(action["target"], "new")
        ctx = action["context"]
        self.assertEqual(ctx["default_registrant_ids"], [self.registrant.id])
        # Single-record path also seeds the readable Domain field.
        self.assertIn("default_registrant_domain", ctx)
        self.assertIn(str(self.registrant.id), ctx["default_registrant_domain"])

    def test_action_score_registrant_multi_seeds_only_m2m(self):
        records = self.registrant | self.other_registrant
        action = records.action_score_registrant()
        self.assertEqual(action["res_model"], "spp.batch.scoring.wizard")
        ctx = action["context"]
        self.assertEqual(set(ctx["default_registrant_ids"]), set(records.ids))
        # Multi-record path skips the redundant default_domain.
        self.assertNotIn("default_registrant_domain", ctx)

    def test_action_score_registrant_empty_recordset_returns_false(self):
        action = self.Partner.browse().action_score_registrant()
        self.assertFalse(action)
