# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CR roles must read registrant data (a change request is about a registrant)
but must NOT carry the Tier-2 ``group_registry_viewer`` group, which gates the
standalone Registry Search portal menu — an over-broad registrant PII
enumeration surface. Registrant read is preserved via the Tier-3
``group_registry_read`` group (granted through their ``group_cr_*`` chain and
the explicit role link).
"""

from odoo.tests import TransactionCase, tagged

_CR_ROLE_XMLIDS = [
    "spp_change_request_v2.global_role_cr_requestor",
    "spp_change_request_v2.local_role_cr_validator",
    "spp_change_request_v2.global_role_cr_validator_hq",
]


@tagged("post_install", "-at_install")
class TestCRRolesRegistryScope(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrant = cls.env["res.partner"].create(
            {"name": "CR Registrant", "is_registrant": True, "is_group": False}
        )
        cls.reg_id = cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.registrant.id,
                "id_type_id": cls.env.ref("spp_vocabulary.code_id_type_national_id").id,
                "value": "CR-123",
            }
        )
        cls.phone = cls.env["spp.phone.number"].create({"partner_id": cls.registrant.id, "phone_no": "09180000000"})

    def _user_with_role(self, role_xmlid, login):
        user = self.env["res.users"].create({"name": login, "login": login, "email": f"{login}@example.com"})
        self.env["res.users.role.line"].create({"user_id": user.id, "role_id": self.env.ref(role_xmlid).id})
        user.set_groups_from_roles()
        return user

    def test_cr_roles_lack_tier2_registry_viewer(self):
        for xmlid in _CR_ROLE_XMLIDS:
            user = self._user_with_role(xmlid, f"crscope_{xmlid.split('.')[-1]}")
            self.assertFalse(
                user.has_group("spp_registry.group_registry_viewer"),
                f"{xmlid} must not carry the Tier-2 registry viewer group (it gates the registry search portal menu)",
            )

    def test_cr_roles_keep_registrant_read(self):
        for xmlid in _CR_ROLE_XMLIDS:
            user = self._user_with_role(xmlid, f"crread_{xmlid.split('.')[-1]}")
            self.assertTrue(
                user.has_group("spp_registry.group_registry_read"),
                f"{xmlid} must keep Tier-3 registry read",
            )
            # Functional read of the sensitive PII models as the role user.
            self.registrant.with_user(user).read(["name"])
            self.reg_id.with_user(user).read(["value"])
            self.phone.with_user(user).read(["phone_no"])
