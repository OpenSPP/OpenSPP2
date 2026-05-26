# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared fixtures for spp_registry tests."""

from odoo.tests import TransactionCase


class RegistryCommon(TransactionCase):
    """Base class with the registrants, groups and vocab codes used across
    the security-priority test suites.

    The head vocabulary code is loaded by spp_vocabulary at module install
    time (see vocabulary_group_membership_type.xml); we look it up rather
    than recreate it so the test exercises the same row production uses.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.Membership = cls.env["spp.group.membership"]
        cls.VocabCode = cls.env["spp.vocabulary.code"]

        cls.head_code = cls.VocabCode.sudo().get_code("urn:openspp:vocab:group-membership-type", "head")

        cls.group = cls.Partner.create({"name": "Test Household", "is_registrant": True, "is_group": True})
        cls.individual_a = cls.Partner.create({"name": "Alice", "is_registrant": True, "is_group": False})
        cls.individual_b = cls.Partner.create({"name": "Bob", "is_registrant": True, "is_group": False})

    @classmethod
    def _make_user(cls, login, group_xmlids):
        """Create an internal user with the given res.groups xmlids."""
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
