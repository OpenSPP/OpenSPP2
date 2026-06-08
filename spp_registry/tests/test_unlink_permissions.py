# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Officer / registrar deletion-protection on res.partner.

Covers spp_registry/models/registrant.py::unlink — which raises AccessError
when the acting user is a Registry Officer (or the legacy
``group_spp_registrar``) and is **not** also a Manager / SPP Admin / admin.

This is a security boundary: it prevents officers from destroying registry
data while letting managers (and the back-compat registrar+manager combo)
do so.
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import RegistryCommon


@tagged("post_install", "-at_install")
class TestRegistrantUnlinkPermissions(RegistryCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target = cls.Partner.create({"name": "Deletable Partner", "is_registrant": True, "is_group": False})

    def _target_for(self, user):
        """Return ``self.target`` bound to ``user`` (must use with_user)."""
        return self.target.with_user(user)

    def test_officer_alone_cannot_unlink(self):
        """Officer without manager / admin must be blocked."""
        officer = self._make_user("officer_only", ["spp_registry.group_registry_officer"])
        with self.assertRaises(AccessError):
            self._target_for(officer).unlink()
        # Record still exists.
        self.assertTrue(self.target.exists())

    def test_legacy_registrar_alone_cannot_unlink(self):
        """``group_spp_registrar`` is kept for backward compat — same rule."""
        if not self.env.ref("spp_registry.group_spp_registrar", raise_if_not_found=False):
            self.skipTest("legacy group_spp_registrar not present in this build")
        registrar = self._make_user("legacy_registrar", ["spp_registry.group_spp_registrar"])
        with self.assertRaises(AccessError):
            self._target_for(registrar).unlink()

    def test_manager_can_unlink(self):
        """Manager implies Officer + Config Admin — must succeed."""
        manager = self._make_user("manager", ["spp_registry.group_registry_manager"])
        self._target_for(manager).unlink()
        self.assertFalse(self.target.exists())

    def test_officer_plus_manager_can_unlink(self):
        """Officer+Manager combo passes the second clause of the guard."""
        partner = self.Partner.create({"name": "Officer+Manager Target", "is_registrant": True})
        user = self._make_user(
            "officer_plus_manager",
            [
                "spp_registry.group_registry_officer",
                "spp_registry.group_registry_manager",
            ],
        )
        partner.with_user(user).unlink()
        self.assertFalse(partner.exists())

    def test_spp_admin_can_unlink(self):
        """``spp_security.group_spp_admin`` bypasses the officer block."""
        partner = self.Partner.create({"name": "Admin Target", "is_registrant": True})
        admin = self._make_user(
            "spp_admin_unlink",
            [
                "spp_registry.group_registry_officer",
                "spp_security.group_spp_admin",
            ],
        )
        partner.with_user(admin).unlink()
        self.assertFalse(partner.exists())

    def test_superuser_can_unlink(self):
        """``_is_admin()`` (uid 1) short-circuits the check."""
        partner = self.Partner.create({"name": "Root Target", "is_registrant": True})
        partner.with_user(self.env.ref("base.user_admin")).unlink()
        self.assertFalse(partner.exists())

    def test_non_registry_user_falls_through_to_default_acl(self):
        """A user without *any* registry group should hit standard ACLs, not
        our custom raise — i.e. the guard's first ``if`` is False.

        Whether the unlink then succeeds or fails depends on
        ir.model.access.csv rules, not on our override. Test only that the
        AccessError raised here is NOT the one with our custom message.
        """
        # TODO: pick a stock internal user (e.g. base.group_user only) and
        # assert that any AccessError raised does *not* carry our message.
        self.skipTest("not yet implemented — see TODO")
