# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared fixtures for spp_primero tests."""

from odoo import Command
from odoo.tests.common import TransactionCase

PROTECTION_CONCERN_NS = "urn:openspp:vocab:protection-concern"
PROTECTION_RISK_NS = "urn:openspp:vocab:protection-risk-level"
ID_TYPE_NS = "urn:openspp:vocab:id-type"

WEBHOOK_URL = "http://host.docker.internal:4000/i/00000000-0000-4000-8000-000000000000"
WEBHOOK_API_KEY = "test-api-key"


class PrimeroTestCase(TransactionCase):
    """A child with a birth-certificate ID, a household, and two users."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.Code = cls.env["spp.vocabulary.code"]

        cls.id_type_birth_certificate = cls.Code.search(
            [("vocabulary_id.namespace_uri", "=", ID_TYPE_NS), ("code", "=", "birth_certificate")],
            limit=1,
        )
        if not cls.id_type_birth_certificate:
            raise AssertionError("spp_vocabulary must seed the birth_certificate ID type")

        cls.child = cls.Partner.create(
            {
                "name": "Sofia Santos",
                "given_name": "Sofia",
                "family_name": "Santos",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.child_reg_id = cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.child.id,
                "id_type_id": cls.id_type_birth_certificate.id,
                "value": "BC-1234-5678901",
            }
        )
        cls.household = cls.Partner.create(
            {
                "name": "Santos Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cls.officer = cls._make_user("primero_officer", ["spp_registry.group_registry_officer"])
        cls.viewer = cls._make_user("primero_viewer", ["spp_registry.group_registry_viewer"])

        cls.env["ir.config_parameter"].sudo().set_param("spp_primero.webhook_url", WEBHOOK_URL)
        cls.env["ir.config_parameter"].sudo().set_param("spp_primero.webhook_api_key", WEBHOOK_API_KEY)

    @classmethod
    def _make_user(cls, login, group_xmlids):
        """An internal user with the given groups (every real user is an internal user)."""
        groups = cls.env.ref("base.group_user")
        for xmlid in group_xmlids:
            groups |= cls.env.ref(xmlid)
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@example.test",
                "group_ids": [Command.set(groups.ids)],
            }
        )

    @classmethod
    def _concern_code(cls, code):
        return cls.Code.search(
            [("vocabulary_id.namespace_uri", "=", PROTECTION_CONCERN_NS), ("code", "=", code)],
            limit=1,
        )

    @classmethod
    def _risk_code(cls, code):
        return cls.Code.search(
            [("vocabulary_id.namespace_uri", "=", PROTECTION_RISK_NS), ("code", "=", code)],
            limit=1,
        )

    def _set_param(self, key, value):
        self.env["ir.config_parameter"].sudo().set_param(key, value)
