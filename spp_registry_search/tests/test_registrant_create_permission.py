# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OP#1124: Registry-search create buttons must be gated on the registry
create-permission roles, not generic res.partner create access."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRegistrantCreatePermission(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ViewHistory = cls.env["spp.registry.view.history"]

    def _make_user(self, login, group_xmlids):
        groups = []
        for xmlid in group_xmlids:
            grp = self.env.ref(xmlid, raise_if_not_found=False)
            if grp:
                groups.append(grp.id)
        return self.env["res.users"].create({"name": login, "login": login, "group_ids": [(6, 0, groups)]})

    def test_registry_officer_can_create(self):
        user = self._make_user("t_1124_officer", ["base.group_user", "spp_registry.group_registry_officer"])
        self.assertTrue(self.ViewHistory.with_user(user).check_registrant_create_permission())

    def test_registry_manager_can_create(self):
        user = self._make_user("t_1124_manager", ["base.group_user", "spp_registry.group_registry_manager"])
        self.assertTrue(self.ViewHistory.with_user(user).check_registrant_create_permission())

    def test_partner_creator_without_registry_role_cannot_create(self):
        """A user with generic res.partner create access but NO registry role —
        like the validator in OP#1124 — must be denied. This is the crux: the
        old check keyed off res.partner create (which such a user passes)."""
        user = self._make_user("t_1124_partmgr", ["base.group_user", "base.group_partner_manager"])
        # Sanity: the old, too-broad basis (res.partner create) WOULD allow this user.
        self.assertTrue(self.env["res.partner"].with_user(user).check_access_rights("create", raise_exception=False))
        # The new, correct gate denies it (not a registry create role).
        self.assertFalse(self.ViewHistory.with_user(user).check_registrant_create_permission())
