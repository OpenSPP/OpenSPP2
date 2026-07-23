# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI Administrator security group."""

import importlib.util
from pathlib import Path

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDCIAdminGroup(TransactionCase):
    """The DCI admin group is consumed by every spp_dci_* view that gates
    raw payloads or PII. If the xml_id disappears or the group is replaced
    silently, those view gates degrade to "visible to everyone" - this
    pinning test catches that.

    The group must NEVER imply base.group_system: implied_ids grants the
    implied groups to members, so such a link would turn a scoped PII
    visibility role into full Settings/System administration.
    """

    def test_dci_admin_group_exists(self):
        group = self.env.ref("spp_dci.group_dci_admin", raise_if_not_found=False)
        self.assertTrue(group, "spp_dci.group_dci_admin must exist")
        self.assertEqual(group.name, "DCI Administrator")

    def test_dci_admin_does_not_grant_system(self):
        """Granting DCI Administrator must not escalate to system admin."""
        group = self.env.ref("spp_dci.group_dci_admin")
        system = self.env.ref("base.group_system")
        self.assertNotIn(system, group.implied_ids)
        # Guard the transitive closure too, so the escalation cannot come
        # back through an intermediate group.
        self.assertNotIn(system, group.all_implied_ids)

        user = self.env["res.users"].create(
            {
                "name": "DCI Admin Only",
                "login": "dci_admin_only",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(group.id),
                ],
            }
        )
        self.assertTrue(user.has_group("spp_dci.group_dci_admin"))
        self.assertFalse(
            user.has_group("base.group_system"),
            "DCI Administrator membership must not confer system administration",
        )

    def test_spp_admin_implies_dci_admin(self):
        """OpenSPP admins (and thus system admins) keep PII visibility."""
        group = self.env.ref("spp_dci.group_dci_admin")
        spp_admin = self.env.ref("spp_security.group_spp_admin")
        self.assertIn(group, spp_admin.all_implied_ids)

        admin_user = self.env["res.users"].create(
            {
                "name": "DCI System Admin",
                "login": "dci_system_admin",
                "group_ids": [Command.link(self.env.ref("base.group_system").id)],
            }
        )
        self.assertTrue(admin_user.has_group("spp_dci.group_dci_admin"))

    def test_migration_removes_escalation(self):
        """The 19.0.2.0.2 migration strips base.group_system from the
        noupdate'd group record on databases installed before the fix."""
        migration_path = Path(__file__).parent.parent / "migrations" / "19.0.2.0.2" / "post-migration.py"
        spec = importlib.util.spec_from_file_location("spp_dci_migration_19_0_2_0_2", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        group = self.env.ref("spp_dci.group_dci_admin")
        system = self.env.ref("base.group_system")
        # Recreate the released (vulnerable) state: the escalating link and
        # the stale comment that the noupdate record would have preserved.
        group.write(
            {
                "implied_ids": [Command.link(system.id)],
                "comment": "Sensitive. Members must already be system administrators.",
            }
        )
        self.assertIn(system, group.implied_ids)

        with self.assertLogs("spp_dci_migration_19_0_2_0_2", level="WARNING") as capture:
            migration.migrate(self.env.cr, "19.0.2.0.1")
        self.assertIn("Removed the base.group_system implication", capture.output[0])

        group.invalidate_recordset()
        self.assertNotIn(system, group.implied_ids)
        self.assertNotIn(system, group.all_implied_ids)
        self.assertNotIn("must already be system administrators", group.comment)

        # Idempotent: a second run finds the link absent and the comment
        # already refreshed, so it makes no changes and stays silent.
        with self.assertNoLogs("spp_dci_migration_19_0_2_0_2", level="WARNING"):
            migration.migrate(self.env.cr, "19.0.2.0.1")
