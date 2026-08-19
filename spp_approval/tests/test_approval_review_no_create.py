# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OP#1167: a review is never created by hand, so no view offers a New button.

The approval mixin creates a review when a record is submitted, and
``create()`` builds the tier reviews from the definition. A review typed into a
blank form would need a model name, a record id and a definition entered by
hand, and would point at nothing — which is why the New button on **My Pending
Approvals** was reported as not meant to work there.

Both actions on ``spp.approval.review`` share these two views, so the attribute
belongs on the views rather than on one action's context.
"""

from lxml import etree

from odoo.tests import TransactionCase, tagged

VIEWS = [
    ("spp_approval.approval_review_view_tree", "list"),
    ("spp_approval.approval_review_view_form", "form"),
]

ACTIONS = [
    "spp_approval.approval_review_my_pending_action",
    "spp_approval.approval_review_action",
]


@tagged("post_install", "-at_install")
class TestApprovalReviewNoCreate(TransactionCase):
    def test_no_view_offers_a_new_button(self):
        """`create` on the root node is what the New button reads.

        For a plain list or form, ``activeActions.create`` comes straight from
        this attribute (web/views/utils.js). An action context of
        ``{'create': False}`` is not a separate mechanism — it rewrites this
        same attribute (web/views/view.js) — so setting it on the view covers
        every action that uses the view, including any added later.
        """
        for xml_id, view_type in VIEWS:
            with self.subTest(view=xml_id):
                view = self.env.ref(xml_id)
                # The combined arch, not the record's own: spp_approval's
                # multitier views inherit both of these, and it is the merged
                # result the client renders.
                combined = self.env["spp.approval.review"].get_view(view.id, view_type)
                root = etree.fromstring(combined["arch"])

                self.assertEqual(root.tag, view_type)
                self.assertEqual(
                    root.get("create"),
                    "0",
                    f"{xml_id} would still offer New once inheritance is applied",
                )

    def test_both_actions_use_those_views(self):
        """Guards the reason the attribute lives on the views.

        The report was about My Pending Approvals, but the sibling Approval
        Reviews action lists the same model through the same views and had the
        same button. If an action ever stops using them, this fails and the
        create-suppression needs revisiting rather than silently lapsing.
        """
        for xml_id in ACTIONS:
            with self.subTest(action=xml_id):
                action = self.env.ref(xml_id)

                self.assertEqual(action.res_model, "spp.approval.review")
                self.assertFalse(
                    action.view_id,
                    f"{xml_id} pins a specific view; check it denies create too",
                )
                self.assertEqual(action.view_mode, "list,form")

    def test_a_review_still_reaches_the_list(self):
        """The views are read-only entry points, not disabled ones.

        create="0" must not stop reviews created by the approval flow from
        being listed and opened — that is the whole purpose of the view.
        """
        definition = self.env["spp.approval.definition"].search([], limit=1)
        if not definition:
            self.skipTest("no approval definition available in this database")

        review = self.env["spp.approval.review"].create(
            {
                "model": "spp.approval.definition",
                "res_id": definition.id,
                "definition_id": definition.id,
            }
        )

        self.assertIn(review, self.env["spp.approval.review"].search([]))
