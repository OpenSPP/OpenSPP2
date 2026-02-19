# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Common test utilities for Change Request API V2 tests."""

from odoo.tests import TransactionCase

from ..services.change_request_service import ChangeRequestService


class ChangeRequestTestCase(TransactionCase):
    """Base class for Change Request API V2 unit tests.

    Provides shared fixtures: vocabularies, registrants, CR types,
    and a service helper.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.cr_model = cls.env["spp.change.request"]

        # Get or create ID Type vocabulary
        id_type_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not id_type_vocab:
            id_type_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Type",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )

        # Create ID type as vocabulary code
        cls.id_type = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", id_type_vocab.id),
                ("code", "=", "test_national_id"),
            ],
            limit=1,
        )
        if not cls.id_type:
            cls.id_type = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "test_national_id",
                    "display": "Test National ID",
                    "is_local": True,
                    "target_type": "individual",
                }
            )

        # Create test registrant
        cls.registrant = cls.partner_model.create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.registrant.id,
                "id_type_id": cls.id_type.id,
                "value": "TEST-123",
            }
        )

        # Create test group
        cls.group = cls.partner_model.create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.group.id,
                "id_type_id": cls.id_type.id,
                "value": "GROUP-123",
            }
        )

        # Get or create CR type
        cls.cr_type_edit = cls.env.ref(
            "spp_change_request_v2.cr_type_edit_individual",
            raise_if_not_found=False,
        )
        if not cls.cr_type_edit:
            cls.cr_type_edit = cls.env.ref(
                "spp_cr_types_base.cr_type_edit_individual",
                raise_if_not_found=False,
            )
        if not cls.cr_type_edit:
            cls.cr_type_edit = cls.env["spp.change.request.type"].search([("code", "=", "edit_individual")], limit=1)
        if not cls.cr_type_edit:
            cls.cr_type_edit = cls.env["spp.change.request.type"].create(
                {
                    "name": "Edit Individual",
                    "code": "edit_individual",
                    "target_type": "individual",
                    "detail_model": "spp.cr.detail.edit_individual",
                }
            )

        # Gender vocabulary (needed by type schema tests, available to all)
        gender_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:iso:std:iso:5218")], limit=1)
        if not gender_vocab:
            gender_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "Gender (ISO 5218)",
                    "namespace_uri": "urn:iso:std:iso:5218",
                }
            )
        cls.gender_vocab = gender_vocab

        for code, display in [("1", "Male"), ("2", "Female")]:
            existing = cls.env["spp.vocabulary.code"].search(
                [("vocabulary_id", "=", gender_vocab.id), ("code", "=", code)],
                limit=1,
            )
            if not existing:
                cls.env["spp.vocabulary.code"].create(
                    {
                        "vocabulary_id": gender_vocab.id,
                        "code": code,
                        "display": display,
                    }
                )

    @classmethod
    def _get_service(cls):
        """Return a ChangeRequestService instance."""
        return ChangeRequestService(cls.env)
