# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Server-side authorization for applying change requests.

``action_apply()`` sudoes the apply strategy (which writes ``spp.group.membership``
as superuser, bypassing the ACLs that make membership read-only for CR roles).
The manager restriction used to live only on the XML button, but Odoo object
methods are RPC-callable, so a plain ``group_cr_user`` could invoke
``action_apply()`` directly on an approved CR and drive superuser membership
writes. The public entrypoint must enforce ``group_cr_manager`` server-side,
while the internal apply mechanism (used by auto-apply-on-approve, which runs
as the approving validator) stays reachable.
"""

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type


class TestApplyAuthorization(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        P = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.cr_model = cls.env["spp.change.request"]

        cls.group = P.create({"name": "Authz Household", "is_registrant": True, "is_group": True})
        cls.member = P.create({"name": "Authz Member", "is_registrant": True, "is_group": False})
        cls.membership = cls.membership_model.create(
            {"group": cls.group.id, "individual": cls.member.id, "start_date": fields.Datetime.now()}
        )
        cls.cr_type = get_or_create_cr_type(cls.env, "remove_member")

        base_user = cls.env.ref("base.group_user")

        def _user(login, group_xmlid):
            return cls.env["res.users"].create(
                {
                    "name": login,
                    "login": login,
                    "email": f"{login}@example.com",
                    "group_ids": [
                        Command.link(base_user.id),
                        Command.link(cls.env.ref(group_xmlid).id),
                    ],
                }
            )

        cls.cr_user = _user("authz_cr_user", "spp_change_request_v2.group_cr_user")
        cls.cr_manager = _user("authz_cr_manager", "spp_change_request_v2.group_cr_manager")
        cls.cr_validator = _user("authz_cr_validator", "spp_change_request_v2.group_cr_validator")

    def _make_approved_cr(self, owner=None):
        """Create an approved remove_member CR.

        ``owner`` sets create_uid so the CR passes the cr_user ownership record
        rule (``rule_cr_user``) — otherwise a non-owning cr_user is blocked by
        that rule (a read AccessError) and the apply-authorization gate under
        test would never be reached. Approval is stamped via sudo to simulate a
        CR already approved through the workflow.
        """
        cr_model = self.cr_model.with_user(owner) if owner else self.cr_model
        cr = cr_model.create({"request_type_id": self.cr_type.id, "registrant_id": self.group.id})
        cr.get_detail().write(
            {
                "individual_id": self.member.id,
                "membership_id": self.membership.id,
                "end_reason": "left_household",
            }
        )
        cr.sudo().approval_state = "approved"
        return cr

    def test_cr_user_cannot_apply_over_rpc(self):
        """A non-manager cr_user calling action_apply directly on their OWN
        approved CR must be denied by the server-side manager gate, and no
        membership write must occur."""
        cr = self._make_approved_cr(owner=self.cr_user)
        with self.assertRaises(AccessError):
            cr.with_user(self.cr_user).action_apply()
        self.assertFalse(cr.is_applied)
        self.assertFalse(self.membership.ended_date, "membership must be untouched when apply is denied")

    def test_validator_cannot_apply_directly(self):
        """A validator (not a manager) is also blocked from calling action_apply
        directly. Validators cause an apply only by approving (auto-apply via
        _on_approve), not by invoking the manager-only public entrypoint."""
        cr = self._make_approved_cr()
        with self.assertRaises(AccessError):
            cr.with_user(self.cr_validator).action_apply()
        self.assertFalse(cr.is_applied)

    def test_manager_can_apply(self):
        """A cr_manager may apply (regression)."""
        cr = self._make_approved_cr()
        cr.with_user(self.cr_manager).action_apply()
        self.assertTrue(cr.is_applied)
        self.assertTrue(self.membership.ended_date)

    def test_auto_apply_runs_the_public_apply_entry_point(self):
        """``action_apply`` is the extension point downstream modules override.

        Auto-apply used to bypass it, so any override hung off apply silently
        stopped running on approval -- no error, just missing side effects.
        """
        from unittest.mock import patch

        cr = self._make_approved_cr()
        cr.request_type_id.auto_apply_on_approve = True

        seen = []
        original = type(cr).action_apply

        def spy(records):
            seen.append(tuple(records.ids))
            return original(records)

        with patch.object(type(cr), "action_apply", spy):
            cr.with_user(self.cr_validator)._on_approve()

        self.assertTrue(seen, "auto-apply must go through the public action_apply")
        self.assertTrue(cr.is_applied)

    def test_auto_apply_records_the_real_approver(self):
        """sudo() sets su without changing uid, so attribution is preserved."""
        cr = self._make_approved_cr()
        cr.request_type_id.auto_apply_on_approve = True
        cr.with_user(self.cr_validator)._on_approve()
        self.assertEqual(
            cr.applied_by_id,
            self.cr_validator,
            "applying under sudo must still record the approver, not the superuser",
        )

    def test_auto_apply_on_approve_runs_for_non_manager_approver(self):
        """Auto-apply-on-approve must still work when the approver is a
        validator (not a manager): ``_on_approve`` reaches the public
        ``action_apply`` through ``sudo()``, and the manager gate exempts
        superuser callers."""
        cr = self._make_approved_cr()
        cr.request_type_id.auto_apply_on_approve = True
        cr.with_user(self.cr_validator)._on_approve()
        self.assertTrue(cr.is_applied)
        self.assertTrue(self.membership.ended_date)
