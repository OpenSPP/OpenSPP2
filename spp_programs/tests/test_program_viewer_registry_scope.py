# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The Program Viewer role must be able to read registrant data for program
cross-references, but must NOT carry the Tier-2 ``group_registry_viewer``
group, which gates the standalone Registry Search portal menu
(``spp_registry_search.menu_registry_search``) — an over-broad registrant PII
enumeration surface for a read-only program role.

The role is switched to the Tier-3 ``group_registry_read`` technical group,
which grants the same registrant read ACLs (defined in ``spp_base_common``)
without the Registry app menu.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProgramViewerRegistryScope(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create(
            {
                "name": "Program Viewer Test",
                "login": "program_viewer_scope_test",
                "email": "pv_scope@example.com",
            }
        )
        cls.env["res.users.role.line"].create(
            {
                "user_id": cls.user.id,
                "role_id": cls.env.ref("spp_programs.global_role_program_viewer").id,
            }
        )
        cls.user.set_groups_from_roles()

        # A registrant with an ID number and phone (the sensitive PII models).
        cls.registrant = cls.env["res.partner"].create(
            {"name": "PV Registrant", "is_registrant": True, "is_group": False}
        )
        cls.reg_id = cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.registrant.id,
                "id_type_id": cls.env.ref("spp_vocabulary.code_id_type_national_id").id,
                "value": "PV-123",
            }
        )
        cls.phone = cls.env["spp.phone.number"].create({"partner_id": cls.registrant.id, "phone_no": "09170000000"})

    def test_program_viewer_lacks_tier2_registry_viewer(self):
        """The role must not carry group_registry_viewer (gates the Registry
        Search portal menu)."""
        self.assertFalse(
            self.user.has_group("spp_registry.group_registry_viewer"),
            "Program Viewer must not have the Tier-2 registry viewer group (it gates the registry search portal menu)",
        )

    def test_program_viewer_keeps_registrant_read(self):
        """Registrant read must be preserved via Tier-3 group_registry_read."""
        self.assertTrue(self.user.has_group("spp_registry.group_registry_read"))
        # Functional read of the sensitive PII models as the role user.
        self.registrant.with_user(self.user).read(["name"])
        self.reg_id.with_user(self.user).read(["value"])
        self.phone.with_user(self.user).read(["phone_no"])

    def test_program_viewer_keeps_program_data_read(self):
        """The role must still read program/cycle data (from group_programs_viewer)."""
        self.assertTrue(self.user.has_group("spp_programs.group_programs_viewer"))
