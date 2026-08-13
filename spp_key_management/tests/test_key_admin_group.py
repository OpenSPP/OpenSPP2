# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the Key Management security groups."""

import importlib.util
from pathlib import Path

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestKeyAdminGroup(TransactionCase):
    """Key Management Admin gates control of the platform's encryption
    keys (providers, rotation, key records).

    The group must NEVER imply base.group_system: implied_ids grants the
    implied groups to members, so such a link would turn the key
    management role into full Settings/System administration.
    """

    def _create_user(self, login, groups):
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "group_ids": [Command.link(g.id) for g in groups],
            }
        )

    def test_key_admin_group_exists(self):
        group = self.env.ref("spp_key_management.group_key_admin", raise_if_not_found=False)
        self.assertTrue(group, "spp_key_management.group_key_admin must exist")
        self.assertEqual(group.name, "Key Management Admin")

    def test_key_admin_does_not_grant_system(self):
        """Granting Key Management Admin must not escalate to system admin."""
        group = self.env.ref("spp_key_management.group_key_admin")
        system = self.env.ref("base.group_system")
        self.assertNotIn(system, group.implied_ids)
        # Guard the transitive closure too, so the escalation cannot come
        # back through an intermediate group.
        self.assertNotIn(system, group.all_implied_ids)

        user = self._create_user(
            "key_admin_only",
            [self.env.ref("base.group_user"), group],
        )
        self.assertTrue(user.has_group("spp_key_management.group_key_admin"))
        self.assertFalse(
            user.has_group("base.group_system"),
            "Key Management Admin membership must not confer system administration",
        )

    def test_key_admin_implies_operator(self):
        """Admin is a superset of operator (and stays an internal user)."""
        group = self.env.ref("spp_key_management.group_key_admin")
        operator = self.env.ref("spp_key_management.group_key_operator_officer")
        internal = self.env.ref("base.group_user")
        self.assertIn(operator, group.all_implied_ids)
        self.assertIn(internal, group.all_implied_ids)

    def test_key_admin_reads_encrypted_key(self):
        """Key admins keep field access to the KMS-wrapped key material
        (the AWS/Azure providers read it in the calling user's context);
        operators do not."""
        key = self.env["spp.encryption.key"].create(
            {
                "key_id": "test-field-gate",
                "encrypted_key": "d3JhcHBlZA==",
            }
        )
        admin_user = self._create_user(
            "key_admin_field",
            [
                self.env.ref("base.group_user"),
                self.env.ref("spp_key_management.group_key_admin"),
            ],
        )
        operator_user = self._create_user(
            "key_operator_field",
            [
                self.env.ref("base.group_user"),
                self.env.ref("spp_key_management.group_key_operator_officer"),
            ],
        )
        self.assertEqual(key.with_user(admin_user).encrypted_key, "d3JhcHBlZA==")
        with self.assertRaises(AccessError):
            key.with_user(operator_user).encrypted_key  # noqa: B018

    def test_system_admin_retains_key_access(self):
        """System administrators keep key access without holding the key
        admin group: the field gate and menu root both list
        base.group_system, and the ACL grants system its own rows. This
        pins the other half of the design - removing the escalation must
        not cost real system admins anything."""
        key = self.env["spp.encryption.key"].create(
            {
                "key_id": "test-system-access",
                "encrypted_key": "d3JhcHBlZA==",
            }
        )
        system_user = self._create_user(
            "key_system_admin",
            [self.env.ref("base.group_system")],
        )
        # Access is retained via base.group_system, NOT via the key group.
        self.assertFalse(system_user.has_group("spp_key_management.group_key_admin"))
        self.assertEqual(key.with_user(system_user).encrypted_key, "d3JhcHBlZA==")
        root = self.env.ref("spp_key_management.menu_key_management_root")
        menus = self.env["ir.ui.menu"].with_user(system_user).load_menus(False)
        self.assertIn(root.id, menus)

    def test_key_admin_sees_key_management_menu(self):
        """A user holding only the key admin role must be able to reach the
        Key Management menu. Odoo drops menus whose ancestors are invisible,
        so parenting under Settings (base.group_erp_manager) would hide the
        whole subtree from dedicated key-custody users."""
        user = self._create_user(
            "key_admin_menu",
            [
                self.env.ref("base.group_user"),
                self.env.ref("spp_key_management.group_key_admin"),
            ],
        )
        root = self.env.ref("spp_key_management.menu_key_management_root")
        # load_menus is what the web client uses; unlike _visible_menu_ids
        # it also prunes menus whose ancestors are invisible ("not related
        # to an app"), which is exactly the failure mode being pinned.
        menus = self.env["ir.ui.menu"].with_user(user).load_menus(False)
        self.assertIn(
            root.id,
            menus,
            "Key Management menu must be reachable for key admins",
        )
        # A top-level app needs an icon: without web_icon the app switcher
        # shows a generic placeholder tile. load_menus does not check this,
        # so pin it on the record itself.
        self.assertTrue(
            root.web_icon_data,
            "Key Management root menu must carry a web icon",
        )

    def test_migration_removes_escalation(self):
        """The 19.0.2.0.1 migration strips base.group_system from the
        group on databases installed before the fix (removing the XML
        line alone never unlinks an existing relation)."""
        migration_path = Path(__file__).parent.parent / "migrations" / "19.0.2.0.1" / "post-migration.py"
        spec = importlib.util.spec_from_file_location("spp_key_management_migration_19_0_2_0_1", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        group = self.env.ref("spp_key_management.group_key_admin")
        system = self.env.ref("base.group_system")
        # Recreate the released (vulnerable) state.
        group.write({"implied_ids": [Command.link(system.id)]})
        self.assertIn(system, group.implied_ids)

        with self.assertLogs("spp_key_management_migration_19_0_2_0_1", level="WARNING") as capture:
            migration.migrate(self.env.cr, "19.0.2.0.0")
        self.assertIn("Removed the base.group_system implication", capture.output[0])

        group.invalidate_recordset()
        self.assertNotIn(system, group.implied_ids)
        self.assertNotIn(system, group.all_implied_ids)

        # Idempotent: a second run finds the link absent and stays silent.
        with self.assertNoLogs("spp_key_management_migration_19_0_2_0_1", level="WARNING"):
            migration.migrate(self.env.cr, "19.0.2.0.0")
