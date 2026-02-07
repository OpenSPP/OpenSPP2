# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ChangeRequestService."""

from odoo.exceptions import UserError, ValidationError

from ..schemas.change_request import (
    ChangeRequestCreate,
    ChangeRequestType,
    RegistrantRef,
)
from ..services.change_request_service import ChangeRequestService
from .common import ChangeRequestTestCase


class TestChangeRequestService(ChangeRequestTestCase):
    """Tests for ChangeRequestService."""

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

    # ──────────────────────────────────────────────────────────────────────
    # State validation tests
    # ──────────────────────────────────────────────────────────────────────

    def test_reject_non_pending_raises(self):
        """Rejecting a non-pending CR raises UserError."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        with self.assertRaises(UserError):
            service.reject(cr, reason="test rejection")

    def test_approve_non_pending_raises(self):
        """Approving a non-pending CR raises UserError."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        with self.assertRaises(UserError):
            service.approve(cr, comment="looks good")

    # ──────────────────────────────────────────────────────────────────────
    # Detail validation tests
    # ──────────────────────────────────────────────────────────────────────

    def test_update_detail_unknown_field_raises(self):
        """Unknown fields in detail data raise ValidationError."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        with self.assertRaises(ValidationError):
            service.update_detail(cr, {"nonexistent_field_xyz": "value"})

    def test_update_detail_unresolved_vocabulary_raises(self):
        """Unresolved vocabulary code in detail data raises ValidationError."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        with self.assertRaises(ValidationError):
            service.update_detail(
                cr,
                {
                    "gender_id": {
                        "system": "urn:iso:std:iso:5218",
                        "code": "nonexistent_code",
                    },
                },
            )

    def test_update_detail_readonly_field_raises(self):
        """Sending a readonly/computed field in detail data raises ValidationError."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        # Find a computed/readonly field from the schema
        detail = cr.get_detail()
        field_defs = service._build_field_definitions(self.cr_type_edit, detail)
        readonly_fields = [f["name"] for f in field_defs if f["readonly"]]
        if readonly_fields:
            with self.assertRaises(ValidationError):
                service.update_detail(cr, {readonly_fields[0]: "value"})
        else:
            # No readonly fields on this detail model; verify validation
            # still passes for valid fields
            service.update_detail(cr, {"given_name": "Valid Name"})
