# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ChangeRequestService."""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase

from ..schemas.change_request import (
    ChangeRequestCreate,
    ChangeRequestType,
    RegistrantRef,
)
from ..services.change_request_service import ChangeRequestService


class TestChangeRequestService(TransactionCase):
    """Tests for ChangeRequestService."""

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

        # Create test registrant with identifier
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

    def test_find_registrant_by_identifier(self):
        """Test finding registrant by external identifier."""
        service = ChangeRequestService(self.env)
        partner = service.find_registrant_by_identifier(
            "urn:openspp:vocab:id-type",
            "TEST-123",
        )
        self.assertEqual(partner, self.registrant)

    def test_find_registrant_not_found(self):
        """Test finding non-existent registrant."""
        service = ChangeRequestService(self.env)
        partner = service.find_registrant_by_identifier(
            "urn:openspp:vocab:id-type",
            "NONEXISTENT",
        )
        self.assertFalse(partner)

    def test_create_change_request(self):
        """Test creating a change request via service."""
        service = ChangeRequestService(self.env)

        schema = ChangeRequestCreate(
            type="ChangeRequest",
            requestType=ChangeRequestType(code="edit_individual"),
            registrant=RegistrantRef(
                system="urn:openspp:vocab:id-type",
                value="TEST-123",
            ),
            detail={
                "given_name": "Updated Name",
            },
        )

        cr = service.create(schema, source="urn:test:api")

        self.assertTrue(cr.id)
        self.assertTrue(cr.name.startswith("CR/"))
        self.assertEqual(cr.registrant_id, self.registrant)
        self.assertEqual(cr.source_type, "api")
        self.assertEqual(cr.source_reference, "urn:test:api")

        # Check detail was updated
        detail = cr.get_detail()
        self.assertEqual(detail.given_name, "Updated Name")

    def test_create_invalid_type(self):
        """Test creating CR with invalid type code."""
        service = ChangeRequestService(self.env)

        schema = ChangeRequestCreate(
            type="ChangeRequest",
            requestType=ChangeRequestType(code="invalid_type"),
            registrant=RegistrantRef(
                system="urn:openspp:vocab:id-type",
                value="TEST-123",
            ),
        )

        with self.assertRaises(ValidationError):
            service.create(schema, source="urn:test:api")

    def test_create_invalid_registrant(self):
        """Test creating CR with non-existent registrant."""
        service = ChangeRequestService(self.env)

        schema = ChangeRequestCreate(
            type="ChangeRequest",
            requestType=ChangeRequestType(code="edit_individual"),
            registrant=RegistrantRef(
                system="urn:openspp:vocab:id-type",
                value="NONEXISTENT",
            ),
        )

        with self.assertRaises(ValidationError):
            service.create(schema, source="urn:test:api")

    def test_find_by_reference(self):
        """Test finding CR by reference."""
        service = ChangeRequestService(self.env)

        # Create a CR first
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Find it by reference
        found = service.find_by_reference(cr.name)
        self.assertEqual(found, cr)

    def test_to_api_schema(self):
        """Test converting CR to API schema."""
        service = ChangeRequestService(self.env)

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        data = service.to_api_schema(cr)

        self.assertEqual(data["type"], "ChangeRequest")
        self.assertEqual(data["reference"], cr.name)
        self.assertEqual(data["requestType"]["code"], "edit_individual")
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["registrant"]["system"], "urn:openspp:vocab:id-type")
        self.assertEqual(data["registrant"]["value"], "TEST-123")
        self.assertIn("meta", data)
        self.assertIn("versionId", data["meta"])

    def test_search(self):
        """Test searching change requests."""
        service = ChangeRequestService(self.env)

        # Create a few CRs
        self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Search by registrant
        records, total = service.search({"registrant": "urn:openspp:vocab:id-type|TEST-123"})
        self.assertGreaterEqual(total, 2)

        # Search by type
        records, total = service.search({"request_type": "edit_individual"})
        self.assertGreaterEqual(total, 2)

        # Search by status
        records, total = service.search({"status": "draft"})
        self.assertGreaterEqual(total, 2)
