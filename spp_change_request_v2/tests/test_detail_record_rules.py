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

    def test_every_concrete_detail_model_is_fully_scoped(self):
        """Guard against a detail model shipping without complete ownership rules.

        Asserts, for every concrete ``spp.cr.detail.*`` model reachable by
        ``group_cr_user`` (via ACL), that ``group_cr_user`` is scoped on EVERY
        operation the ACL grants it — read/write/create **and unlink** — a rule
        missing only ``perm_write`` would still leave a tamper path, and one
        missing ``perm_unlink`` leaves other users' rows deletable — and that
        the higher
        roles each retain a permissive rule (else the group hierarchy would
        cage them behind the restrictive user rule).

        Models the CR user role has NO ACL path to (e.g. the farmer-registry
        and studio detail models, gated by their own group models) are out of
        scope here: cr_user cannot reach them at all, and their ownership
        scoping needs per-module analysis (tracked as a separate follow-up).
        """
        models = self.env["ir.model"].search([("model", "=like", "spp.cr.detail.%")])
        self.assertTrue(models, "expected at least one spp.cr.detail.* model")
        Access = self.env["ir.model.access"]
        Rule = self.env["ir.rule"]
        higher_roles = [
            ("validator", self.validator_group),
            ("validator_hq", self.env.ref("spp_change_request_v2.group_cr_validator_hq")),
            ("manager", self.env.ref("spp_change_request_v2.group_cr_manager")),
        ]
        problems = []
        checked = 0
        for model in models:
            # Transient models (wizards) enforce creator-only access in the
            # ORM itself — non-superusers may only reach records they created
            # — so they need no ir.rule.
            if self.env[model.model]._abstract or self.env[model.model]._transient:
                continue
            # Skip models cr_user has no ACL path to (global no-group ACLs
            # count as a path): in a full-stack DB other apps' detail models
            # (different group models, no cr_* ACLs) would otherwise fail
            # assertions about a role that cannot touch them anyway.
            acls = Access.search(
                [("model_id", "=", model.id), "|", ("group_id", "=", False), ("group_id", "=", self.user_group.id)]
            )
            if not acls:
                continue
            checked += 1
            rules = Rule.search([("model_id", "=", model.id)])

            def grants(group, perm, _rules=rules):
                return any(group in r.groups and getattr(r, perm) for r in _rules)

            # Derive the operations to check from what the ACL actually grants,
            # so a model shipping an extra permission (e.g. unlink) cannot slip
            # through unscoped just because this list was written before it.
            for perm in ("perm_read", "perm_write", "perm_create", "perm_unlink"):
                if not any(getattr(acl, perm) for acl in acls):
                    continue
                if not grants(self.user_group, perm):
                    problems.append(f"{model.model}: group_cr_user missing {perm} rule (bypass)")
            # Same treatment for the higher roles, and for the same reason: they
            # all imply group_cr_user, so if a permission is granted to them by
            # ACL but no permissive rule of theirs carries it, the restrictive
            # user rule is the only one left and it cages them. Checking only
            # read would miss exactly that.
            for label, group in higher_roles:
                role_acls = Access.search(
                    [("model_id", "=", model.id), "|", ("group_id", "=", False), ("group_id", "=", group.id)]
                )
                for perm in ("perm_read", "perm_write", "perm_create", "perm_unlink"):
                    if not any(getattr(acl, perm) for acl in role_acls):
                        continue
                    if not grants(group, perm):
                        problems.append(
                            f"{model.model}: {label} granted {perm} by ACL but no rule carries it "
                            f"(caged by the restrictive user rule)"
                        )
            # A global (no-group) read rule mirrors the parent CR area filter.
            if not any(not r.groups and r.perm_read for r in rules):
                problems.append(f"{model.model}: missing global area-filter rule")
        self.assertTrue(checked, "expected at least one cr_user-reachable spp.cr.detail.* model")
        self.assertFalse(problems, "detail model rule gaps:\n  " + "\n  ".join(problems))

    # ------------------------------------------------------------------
    # Functional: area scoping (mirrors the parent CR area filter)
    # ------------------------------------------------------------------

    def test_area_filter_scopes_detail_by_registrant_area(self):
        """An area-scoped user cannot reach details of out-of-area CRs they own.

        Ownership is held constant (the area user creates both CRs while
        unrestricted), so this isolates the area dimension: once the user is
        restricted to area_1, only the in-area detail remains readable.
        """
        Area = self.env["spp.area"]
        area_1 = Area.create({"draft_name": "CR Detail Area 1"})
        area_2 = Area.create({"draft_name": "CR Detail Area 2"})
        reg_in = self.Partner.create(
            {"name": "Reg In Area", "is_registrant": True, "is_group": False, "area_id": area_1.id}
        )
        reg_out = self.Partner.create(
            {"name": "Reg Out Area", "is_registrant": True, "is_group": False, "area_id": area_2.id}
        )
        # user_a has no center areas yet -> unrestricted create; owns both CRs.
        cr_in = self.CR.with_user(self.user_a).create(
            {"request_type_id": self.edit_type.id, "registrant_id": reg_in.id}
        )
        cr_out = self.CR.with_user(self.user_a).create(
            {"request_type_id": self.edit_type.id, "registrant_id": reg_out.id}
        )
        detail_in = cr_in.with_user(self.user_a).get_detail()
        detail_out = cr_out.with_user(self.user_a).get_detail()

        # Unrestricted (no center areas): both readable — global roles unaffected.
        self.assertTrue(detail_out.with_user(self.user_a).read(["change_request_id"]))

        # Restrict user_a to area_1 (center_area_ids is a stored computed field;
        # write it directly, after creation, to isolate the area dimension).
        self.user_a.sudo().center_area_ids = [(6, 0, [area_1.id])]
        self.assertEqual(self.user_a.center_area_ids, area_1)
        # ir.rule evaluates and caches its domain per (model, mode); the earlier
        # unrestricted read cached an empty domain, so drop the cache to pick up
        # the new center-area scope (a real role change invalidates this too).
        self.env.registry.clear_cache()

        self.assertTrue(detail_in.with_user(self.user_a).read(["change_request_id"]))
        with self.assertRaises(AccessError):
            detail_out.with_user(self.user_a).read(["change_request_id"])

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
