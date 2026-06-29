# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DRIMS predefined user roles (OP#974).

One res.users.role per DRIMS group (1:1), so roles are the unit assigned to
users and can later gain more groups in one place.
"""

from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestDrimsUserRoles(TransactionCase):
    ROLE_TO_GROUP = {
        "spp_drims.role_drims_viewer": "spp_drims.group_drims_viewer",
        "spp_drims.role_drims_officer": "spp_drims.group_drims_officer",
        "spp_drims.role_drims_warehouse_worker": "spp_drims.group_drims_warehouse_worker",
        "spp_drims.role_drims_field_officer": "spp_drims.group_drims_field_officer",
        "spp_drims.role_drims_coordinator_supervisor": "spp_drims.group_drims_coordinator_supervisor",
        "spp_drims.role_drims_approver": "spp_drims.group_drims_approver",
        "spp_drims.role_drims_manager": "spp_drims.group_drims_manager",
    }

    def test_each_role_maps_one_to_one_to_its_group(self):
        """Each DRIMS role implies base.group_user + exactly its one DRIMS group."""
        base_user = self.env.ref("base.group_user")
        for role_xmlid, group_xmlid in self.ROLE_TO_GROUP.items():
            role = self.env.ref(role_xmlid)
            group = self.env.ref(group_xmlid)
            self.assertIn(group, role.implied_ids, f"{role_xmlid} must imply {group_xmlid}")
            self.assertIn(base_user, role.implied_ids, f"{role_xmlid} must imply base.group_user")

    def test_assigning_role_grants_its_group(self):
        """Assigning a DRIMS role to a user grants the mapped DRIMS group."""
        role = self.env.ref("spp_drims.role_drims_warehouse_worker")
        group = self.env.ref("spp_drims.group_drims_warehouse_worker")
        user = new_test_user(self.env, login="drims_role_assignment_test")
        user.write({"role_line_ids": [(0, 0, {"role_id": role.id})]})
        role.update_users()
        self.assertIn(group, user.group_ids, "assigning the role must grant its DRIMS group")
