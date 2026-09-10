# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the data classification security groups."""

from odoo import Command
from odoo.tests.common import TransactionCase


class TestClassificationSecurityGroups(TransactionCase):
    """The classification groups gate the registry menus and ACLs.

    The admin group must NEVER imply base.group_system: implied_ids grants
    the implied groups to members, so such a link would turn a scoped
    classification role into full Settings/System administration.
    """

    def test_admin_group_does_not_grant_system(self):
        """Granting Data Classification Admin must not escalate to system admin."""
        group = self.env.ref("spp_data_classification.group_classification_admin")
        system = self.env.ref("base.group_system")
        self.assertNotIn(system, group.implied_ids)
        # Guard the transitive closure too, so the escalation cannot come
        # back through an intermediate group.
        self.assertNotIn(system, group.all_implied_ids)

        user = self.env["res.users"].create(
            {
                "name": "Classification Admin Only",
                "login": "classification_admin_only",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(group.id),
                ],
            }
        )
        self.assertTrue(user.has_group("spp_data_classification.group_classification_admin"))
        self.assertFalse(
            user.has_group("base.group_system"),
            "Data Classification Admin membership must not confer system administration",
        )

    def test_admin_implies_manager(self):
        """Admins get the manager role (and thus the menus gated on it)."""
        admin = self.env.ref("spp_data_classification.group_classification_admin")
        manager = self.env.ref("spp_data_classification.group_classification_manager")
        internal = self.env.ref("base.group_user")
        self.assertIn(manager, admin.all_implied_ids)
        self.assertIn(internal, admin.all_implied_ids)

    def test_admin_group_full_access_on_registry_models(self):
        """An admin-only user can administer all three registry models."""
        group = self.env.ref("spp_data_classification.group_classification_admin")
        user = self.env["res.users"].create(
            {
                "name": "Classification Admin ACL",
                "login": "classification_admin_acl",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(group.id),
                ],
            }
        )
        for model in (
            "spp.data.classification.level",
            "spp.field.classification",
            "spp.classification.pattern",
        ):
            for operation in ("read", "write", "create", "unlink"):
                self.assertTrue(
                    self.env[model].with_user(user).has_access(operation),
                    f"Classification admin should have {operation} access on {model}",
                )
