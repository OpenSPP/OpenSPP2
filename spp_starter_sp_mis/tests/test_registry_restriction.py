# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Registry access-control setting: persistence and enforcement (OP#1142).

Two independent defects are covered here.

1. The setting could not be switched off. Odoo stores a False
   ``config_parameter`` by *deleting* the row, and ``default_get`` then falls
   back to the field default — so ``default=True`` made "off" unrepresentable
   and the form kept springing back to on. Worse, the enforcement side read a
   missing row as False, so the form claimed "restricted" while the registry
   was in fact wide open.

2. The restriction was cosmetic. It hid buttons from the DOM in JavaScript and
   nothing on the server refused the write, so RPC and import went straight
   through — and the list "New" button was never hidden at all, because the
   patch assigned a ``canCreate`` property that Odoo 19's ListController does
   not read (its template gates on ``activeActions.create``).
"""

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

PARAM = "spp_starter.registry_admin_only_crud"


class RegistryRestrictionCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.Partner = cls.env["res.partner"]
        cls.Settings = cls.env["res.config.settings"]

        # Mirrors the Global Registrar role — see
        # spp_base_common/data/global_roles.xml. This is the profile QA used.
        cls.registrar = cls._make_user(
            "op1142_registrar",
            [
                "base.group_user",
                "base.group_partner_manager",
                "spp_registry.group_registry_officer",
            ],
        )
        # A non-admin who *can* delete registrants today, so the unlink test
        # proves this gate bites rather than re-testing spp_registry's own
        # officer deletion block.
        cls.manager = cls._make_user(
            "op1142_manager",
            [
                "base.group_user",
                "base.group_partner_manager",
                "spp_registry.group_registry_officer",
                "spp_registry.group_registry_manager",
            ],
        )
        cls.spp_admin = cls._make_user(
            "op1142_admin",
            [
                "base.group_user",
                "base.group_partner_manager",
                "spp_registry.group_registry_officer",
                "spp_security.group_spp_admin",
            ],
        )

    @classmethod
    def _make_user(cls, login, group_xmlids):
        groups = cls.env["res.groups"]
        for xmlid in group_xmlids:
            groups |= cls.env.ref(xmlid)
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@example.test",
                "group_ids": [(6, 0, groups.ids)],
            }
        )

    @classmethod
    def _restrict(cls, enabled):
        cls.ICP.set_param(PARAM, "True" if enabled else "False")

    def _new_registrant(self):
        return self.Partner.create({"name": "OP1142 Registrant", "is_registrant": True, "is_group": False})


@tagged("post_install", "-at_install")
class TestRegistryRestrictionSetting(RegistryRestrictionCommon):
    """Defect 1 — the toggle must be able to hold "off"."""

    def test_setting_can_be_turned_off(self):
        """Unticking and saving leaves the setting off, not back on."""
        self._restrict(True)

        self.Settings.create({"is_registry_admin_only_crud": False}).execute()

        defaults = self.Settings.default_get(["is_registry_admin_only_crud"])
        self.assertFalse(
            defaults["is_registry_admin_only_crud"],
            "Settings form still reports the restriction as enabled after it was turned off",
        )

    def test_off_is_stored_not_deleted(self):
        """ "Off" is a stored fact, so it cannot be mistaken for "never set"."""
        self._restrict(True)

        self.Settings.create({"is_registry_admin_only_crud": False}).execute()

        self.assertEqual(self.ICP.get_param(PARAM, "MISSING"), "False")

    def test_setting_can_be_turned_back_on(self):
        """The toggle still works in the enabling direction."""
        self._restrict(False)

        self.Settings.create({"is_registry_admin_only_crud": True}).execute()

        self.assertEqual(self.ICP.get_param(PARAM, "MISSING"), "True")
        defaults = self.Settings.default_get(["is_registry_admin_only_crud"])
        self.assertTrue(defaults["is_registry_admin_only_crud"])

    def test_form_and_enforcement_never_disagree(self):
        """What the form shows is what the server enforces, both ways.

        The original defect made these two diverge: the form fell back to
        ``default=True`` while the enforcement read a missing row as False.
        """
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                self.Settings.create({"is_registry_admin_only_crud": enabled}).execute()

                shown = self.Settings.default_get(["is_registry_admin_only_crud"])["is_registry_admin_only_crud"]
                enforced = self.Partner.with_user(self.registrar)._is_registry_crud_restricted()

                self.assertEqual(bool(shown), enabled)
                self.assertEqual(enforced, enabled)


@tagged("post_install", "-at_install")
class TestRegistryRestrictionEnforcement(RegistryRestrictionCommon):
    """Defect 2 — the restriction must be enforced by the server."""

    def test_non_admin_cannot_create_registrant(self):
        self._restrict(True)
        with self.assertRaises(AccessError):
            self.Partner.with_user(self.registrar).create(
                {"name": "Blocked Registrant", "is_registrant": True, "is_group": False}
            )

    def test_non_admin_cannot_create_registrant_group(self):
        self._restrict(True)
        with self.assertRaises(AccessError):
            self.Partner.with_user(self.registrar).create(
                {"name": "Blocked Group", "is_registrant": True, "is_group": True}
            )

    def test_non_admin_cannot_write_registrant(self):
        self._restrict(True)
        registrant = self._new_registrant()
        with self.assertRaises(AccessError):
            registrant.with_user(self.registrar).write({"name": "Renamed"})

    def test_non_admin_cannot_unlink_registrant(self):
        """Even a Registry Manager, who may delete registrants normally."""
        self._restrict(False)
        registrant = self._new_registrant()
        registrant.with_user(self.manager).unlink()  # allowed while unrestricted

        self._restrict(True)
        blocked = self._new_registrant()
        with self.assertRaises(AccessError):
            blocked.with_user(self.manager).unlink()

    def test_plain_contacts_are_not_restricted(self):
        """The setting governs registrants — it must not lock the Contacts app."""
        self._restrict(True)
        contact = self.Partner.with_user(self.registrar).create({"name": "Ordinary Contact"})
        contact.write({"name": "Ordinary Contact Renamed"})
        self.assertEqual(contact.name, "Ordinary Contact Renamed")

    def test_admin_is_exempt(self):
        self._restrict(True)
        registrant = self.Partner.with_user(self.spp_admin).create(
            {"name": "Admin Registrant", "is_registrant": True, "is_group": False}
        )
        registrant.write({"name": "Admin Registrant Renamed"})
        self.assertEqual(registrant.name, "Admin Registrant Renamed")

    def test_non_admin_unaffected_when_setting_is_off(self):
        self._restrict(False)
        registrant = self.Partner.with_user(self.registrar).create(
            {"name": "Allowed Registrant", "is_registrant": True, "is_group": False}
        )
        registrant.write({"name": "Allowed Registrant Renamed"})
        self.assertEqual(registrant.name, "Allowed Registrant Renamed")


@tagged("post_install", "-at_install")
class TestRegistryRestrictionArch(RegistryRestrictionCommon):
    """The "New" button follows server access, so no JavaScript is needed.

    ``ir.ui.view._postprocess_access_rights`` stamps ``create="false"`` onto the
    arch when ``has_access('create')`` is False, which is what actually removes
    the button from the control panel.
    """

    def _create_disabled(self, user, **context):
        """Whether the arch tells the client not to offer New.

        Read off the root node rather than by searching the arch text: fields
        carry their own ``can_create`` attribute, so a substring test matches
        ``can_create="False"`` and reports True for every view.
        """
        arch = self.Partner.with_user(user).with_context(**context).get_view(view_type="list")["arch"]
        return etree.fromstring(arch).get("create") in ("False", "false", "0")

    def test_registry_list_drops_create_for_non_admin(self):
        self._restrict(True)
        self.assertTrue(
            self._create_disabled(self.registrar, default_is_registrant=True),
            "Registry list still offers New to a restricted user",
        )

    def test_registry_list_keeps_create_for_admin(self):
        self._restrict(True)
        self.assertFalse(self._create_disabled(self.spp_admin, default_is_registrant=True))

    def test_registry_list_keeps_create_when_setting_is_off(self):
        self._restrict(False)
        self.assertFalse(self._create_disabled(self.registrar, default_is_registrant=True))

    def test_contacts_list_is_unaffected(self):
        """Outside the registry context the Contacts app keeps its New button."""
        self._restrict(True)
        self.assertFalse(self._create_disabled(self.registrar))
