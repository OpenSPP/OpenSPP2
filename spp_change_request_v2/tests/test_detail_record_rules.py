# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: CR detail models must enforce parent-CR ownership via ir.rule.

Regression tests for the missing-record-rule vulnerability: a separate detail
model does not inherit the parent ``spp.change.request`` record rules, so a
low-privileged ``group_cr_user`` could read/write detail rows of change
requests they do not own (directly via RPC, bypassing the UI). Each concrete
detail model must ship its own ir.rule mirroring the parent's ownership scope.
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import CRTestCase, get_or_create_cr_type


@tagged("post_install", "-at_install")
class TestDetailRecordRules(CRTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_group = cls.env.ref("base.group_user")
        cls.user_group = cls.env.ref("spp_change_request_v2.group_cr_user")
        cls.validator_group = cls.env.ref("spp_change_request_v2.group_cr_validator")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.user_a = Users.create(
            {
                "name": "CR User A",
                "login": "cr_detail_user_a",
                "email": "cr_detail_user_a@test.com",
                "group_ids": [(4, cls.internal_group.id), (4, cls.user_group.id)],
            }
        )
        cls.user_b = Users.create(
            {
                "name": "CR User B",
                "login": "cr_detail_user_b",
                "email": "cr_detail_user_b@test.com",
                "group_ids": [(4, cls.internal_group.id), (4, cls.user_group.id)],
            }
        )
        cls.validator = Users.create(
            {
                "name": "CR Validator",
                "login": "cr_detail_validator",
                "email": "cr_detail_validator@test.com",
                "group_ids": [(4, cls.internal_group.id), (4, cls.validator_group.id)],
            }
        )
        cls.edit_type = get_or_create_cr_type(cls.env, "edit_individual")

    def _make_detail_owned_by(self, user):
        """Create a CR (owned by ``user``) and return its detail record."""
        cr = self.CR.with_user(user).create(
            {
                "request_type_id": self.edit_type.id,
                "registrant_id": self.test_individual.id,
            }
        )
        detail = cr.with_user(user).get_detail()
        return cr, detail

    # ------------------------------------------------------------------
    # Completeness: every concrete detail model must be scoped
    # ------------------------------------------------------------------

    def test_every_concrete_detail_model_has_user_rule(self):
        """Guard against a detail model shipping without an ownership rule."""
        models = self.env["ir.model"].search([("model", "=like", "spp.cr.detail.%")])
        self.assertTrue(models, "expected at least one spp.cr.detail.* model")
        Rule = self.env["ir.rule"]
        unscoped = []
        for model in models:
            if self.env[model.model]._abstract:
                continue
            rules = Rule.search([("model_id", "=", model.id)])
            user_rules = rules.filtered(lambda r: self.user_group in r.groups and r.perm_read)
            if not user_rules:
                unscoped.append(model.model)
        self.assertFalse(
            unscoped,
            "detail models missing a group_cr_user ir.rule (ownership bypass): %s" % ", ".join(unscoped),
        )

    # ------------------------------------------------------------------
    # Functional: cross-user isolation (edit_individual as a representative)
    # ------------------------------------------------------------------

    def test_cr_user_cannot_read_others_detail(self):
        _cr, detail = self._make_detail_owned_by(self.user_a)
        # A different cr_user cannot even see it via search.
        found = self.env["spp.cr.detail.edit_individual"].with_user(self.user_b).search([("id", "=", detail.id)])
        self.assertFalse(found, "user B must not see user A's detail row")
        # Direct read of the known id is denied.
        with self.assertRaises(AccessError):
            detail.with_user(self.user_b).read(["change_request_id"])

    def test_cr_user_cannot_write_others_detail(self):
        _cr, detail = self._make_detail_owned_by(self.user_a)
        # Writing even a same-value field triggers the record-rule check.
        with self.assertRaises(AccessError):
            detail.with_user(self.user_b).write({"change_request_id": detail.change_request_id.id})

    def test_cr_user_can_access_own_detail(self):
        _cr, detail = self._make_detail_owned_by(self.user_a)
        # The owner reads their own detail without error.
        self.assertTrue(detail.with_user(self.user_a).read(["change_request_id"]))

    def test_validator_can_access_any_detail(self):
        _cr, detail = self._make_detail_owned_by(self.user_a)
        # Validators (implying cr_user) retain full visibility, matching the parent CR rule.
        self.assertTrue(detail.with_user(self.validator).read(["change_request_id"]))
