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
        # Find a computed/readonly field by inspecting the detail model directly
        detail = cr.get_detail()
        from odoo.addons.spp_api_v2.services.schema_builder import SKIP_FIELD_TYPES

        from ..services.change_request_service import DETAIL_SKIP_FIELDS

        readonly_fields = []
        for field_name, field in detail._fields.items():
            if field_name.startswith("_") or field_name in DETAIL_SKIP_FIELDS:
                continue
            if not field.store or field.type in SKIP_FIELD_TYPES:
                continue
            if field.readonly or field.compute:
                readonly_fields.append(field_name)

        if readonly_fields:
            with self.assertRaises(ValidationError):
                service.update_detail(cr, {readonly_fields[0]: "value"})
        else:
            # No readonly fields on this detail model; verify validation
            # still passes for valid fields
            service.update_detail(cr, {"given_name": "Valid Name"})

    # ──────────────────────────────────────────────────────────────────────
    # to_api_schema edge cases
    # ──────────────────────────────────────────────────────────────────────

    def test_to_api_schema_empty_recordset(self):
        """to_api_schema returns empty dict for empty recordset."""
        service = ChangeRequestService(self.env)
        empty = self.env["spp.change.request"]
        self.assertEqual(service.to_api_schema(empty), {})

    def test_to_api_schema_registrant_without_identifier(self):
        """to_api_schema falls back to internal identifier when registrant has no reg_ids."""
        service = ChangeRequestService(self.env)

        # Create registrant without external identifier
        partner_no_id = self.partner_model.create(
            {
                "name": "No ID Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": partner_no_id.id,
            }
        )

        data = service.to_api_schema(cr)
        self.assertEqual(data["registrant"]["system"], "urn:openspp:internal")
        self.assertTrue(data["registrant"]["value"].startswith("partner-"))

    def test_to_api_schema_with_description_and_notes(self):
        """to_api_schema includes description and notes when set."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
                "description": "Test description",
                "notes": "Test notes",
            }
        )

        data = service.to_api_schema(cr)
        self.assertEqual(data["description"], "Test description")
        self.assertEqual(data["notes"], "Test notes")

    def test_to_api_schema_with_applicant(self):
        """to_api_schema includes applicant when set."""
        service = ChangeRequestService(self.env)

        # Create an applicant with an external identifier
        applicant = self.partner_model.create(
            {
                "name": "Test Applicant",
                "is_registrant": True,
                "is_group": False,
            }
        )
        self.env["spp.registry.id"].create(
            {
                "partner_id": applicant.id,
                "id_type_id": self.id_type.id,
                "value": "APPLICANT-001",
            }
        )

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
                "applicant_id": applicant.id,
                "applicant_phone": "+1234567890",
            }
        )

        data = service.to_api_schema(cr)
        self.assertIn("applicant", data)
        self.assertEqual(data["applicant"]["value"], "APPLICANT-001")
        self.assertEqual(data["applicantPhone"], "+1234567890")

    def test_to_api_schema_with_detail_data(self):
        """to_api_schema serializes detail data."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        service.update_detail(cr, {"given_name": "Jane", "family_name": "Doe"})

        data = service.to_api_schema(cr)
        self.assertIn("detail", data)
        self.assertEqual(data["detail"]["given_name"], "Jane")
        self.assertEqual(data["detail"]["family_name"], "Doe")

    def test_to_api_schema_meta_source(self):
        """to_api_schema includes source_reference in meta."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
                "source_reference": "urn:test:source",
            }
        )

        data = service.to_api_schema(cr)
        self.assertEqual(data["meta"]["source"], "urn:test:source")
        self.assertIsNotNone(data["meta"]["lastUpdated"])

    # ──────────────────────────────────────────────────────────────────────
    # _serialize_detail tests
    # ──────────────────────────────────────────────────────────────────────

    def test_serialize_detail_vocabulary_field(self):
        """_serialize_detail serializes many2one vocabulary fields."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Set gender via deserialization
        service.update_detail(
            cr,
            {
                "gender_id": {
                    "system": "urn:iso:std:iso:5218",
                    "code": "1",
                },
            },
        )

        detail = cr.get_detail()
        result = service._serialize_detail(detail)

        self.assertIn("gender_id", result)
        self.assertEqual(result["gender_id"]["system"], "urn:iso:std:iso:5218")
        self.assertEqual(result["gender_id"]["code"], "1")
        self.assertIn("display", result["gender_id"])

    def test_serialize_detail_date_field(self):
        """_serialize_detail serializes date fields to ISO format."""
        from datetime import date

        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        service.update_detail(cr, {"birthdate": "1990-01-15"})

        detail = cr.get_detail()
        result = service._serialize_detail(detail)

        self.assertEqual(result["birthdate"], date(1990, 1, 15).isoformat())

    def test_serialize_detail_date_field_none(self):
        """_serialize_detail returns None for empty date fields."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        detail = cr.get_detail()
        result = service._serialize_detail(detail)

        # birthdate not set, should be None
        self.assertIsNone(result.get("birthdate"))

    def test_serialize_detail_char_fields(self):
        """_serialize_detail includes char fields."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        service.update_detail(cr, {"phone": "+639171234567", "email": "test@example.com"})

        detail = cr.get_detail()
        result = service._serialize_detail(detail)

        self.assertEqual(result["phone"], "+639171234567")
        self.assertEqual(result["email"], "test@example.com")

    def test_serialize_detail_excludes_skip_fields(self):
        """_serialize_detail excludes DETAIL_SKIP_FIELDS."""
        from ..services.change_request_service import DETAIL_SKIP_FIELDS

        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        detail = cr.get_detail()
        result = service._serialize_detail(detail)

        for skip_field in DETAIL_SKIP_FIELDS:
            self.assertNotIn(skip_field, result)

    # ──────────────────────────────────────────────────────────────────────
    # _deserialize_detail tests
    # ──────────────────────────────────────────────────────────────────────

    def test_deserialize_detail_vocabulary_code(self):
        """_deserialize_detail resolves vocabulary code references."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        detail = cr.get_detail()

        vals = service._deserialize_detail(
            detail,
            {
                "gender_id": {
                    "system": "urn:iso:std:iso:5218",
                    "code": "2",
                },
            },
        )

        self.assertIn("gender_id", vals)
        # Should be an integer ID
        self.assertIsInstance(vals["gender_id"], int)
        # Verify it resolves to the Female code
        code_rec = self.env["spp.vocabulary.code"].browse(vals["gender_id"])
        self.assertEqual(code_rec.code, "2")

    def test_deserialize_detail_date_string(self):
        """_deserialize_detail parses ISO date strings."""
        from datetime import date

        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        detail = cr.get_detail()

        vals = service._deserialize_detail(detail, {"birthdate": "1985-06-15"})

        self.assertEqual(vals["birthdate"], date(1985, 6, 15))

    def test_deserialize_detail_char_passthrough(self):
        """_deserialize_detail passes char values through."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        detail = cr.get_detail()

        vals = service._deserialize_detail(detail, {"given_name": "Alice"})
        self.assertEqual(vals["given_name"], "Alice")

    def test_deserialize_detail_unknown_field_skipped(self):
        """_deserialize_detail skips fields not in model (caught by validation)."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        detail = cr.get_detail()

        vals = service._deserialize_detail(detail, {"nonexistent_xyz": "value"})
        self.assertNotIn("nonexistent_xyz", vals)

    def test_deserialize_detail_partner_identifier(self):
        """_deserialize_detail resolves partner identifiers via system/value."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        detail = cr.get_detail()

        # Check if this detail model has any many2one partner fields
        # We'll test with a field that points to res.partner, if any exists
        partner_fields = []
        for field_name, field in detail._fields.items():
            if field.type == "many2one" and field.comodel_name == "res.partner":
                if field_name not in ("registrant_id", "create_uid", "write_uid"):
                    partner_fields.append(field_name)

        if partner_fields:
            vals = service._deserialize_detail(
                detail,
                {
                    partner_fields[0]: {
                        "system": "urn:openspp:vocab:id-type",
                        "value": "TEST-123",
                    },
                },
            )
            self.assertIn(partner_fields[0], vals)
            self.assertEqual(vals[partner_fields[0]], self.registrant.id)

    # ──────────────────────────────────────────────────────────────────────
    # get_primary_identifier tests
    # ──────────────────────────────────────────────────────────────────────

    def test_get_primary_identifier_with_reg_ids(self):
        """get_primary_identifier returns identifier dict for partner with reg_ids."""
        service = ChangeRequestService(self.env)
        result = service.get_primary_identifier(self.registrant)

        self.assertIsNotNone(result)
        self.assertEqual(result["system"], "urn:openspp:vocab:id-type")
        self.assertEqual(result["value"], "TEST-123")
        self.assertEqual(result["display"], self.registrant.name)

    def test_get_primary_identifier_without_reg_ids(self):
        """get_primary_identifier returns None for partner without reg_ids."""
        service = ChangeRequestService(self.env)

        partner_no_id = self.partner_model.create(
            {
                "name": "No ID Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )
        result = service.get_primary_identifier(partner_no_id)
        self.assertIsNone(result)

    # ──────────────────────────────────────────────────────────────────────
    # create with optional fields tests
    # ──────────────────────────────────────────────────────────────────────

    def test_create_with_description_and_notes(self):
        """create sets description and notes when provided."""
        service = ChangeRequestService(self.env)

        schema = ChangeRequestCreate(
            type="ChangeRequest",
            requestType=ChangeRequestType(code="edit_individual"),
            registrant=RegistrantRef(
                system="urn:openspp:vocab:id-type",
                value="TEST-123",
            ),
            description="My description",
            notes="Some notes here",
        )

        cr = service.create(schema, source="urn:test:api")
        self.assertEqual(cr.description, "My description")
        self.assertEqual(cr.notes, "Some notes here")

    def test_create_with_applicant(self):
        """create sets applicant when provided."""
        service = ChangeRequestService(self.env)

        # Create an applicant
        applicant = self.partner_model.create(
            {
                "name": "Applicant Person",
                "is_registrant": True,
                "is_group": False,
            }
        )
        self.env["spp.registry.id"].create(
            {
                "partner_id": applicant.id,
                "id_type_id": self.id_type.id,
                "value": "APPLICANT-002",
            }
        )

        schema = ChangeRequestCreate(
            type="ChangeRequest",
            requestType=ChangeRequestType(code="edit_individual"),
            registrant=RegistrantRef(
                system="urn:openspp:vocab:id-type",
                value="TEST-123",
            ),
            applicant=RegistrantRef(
                system="urn:openspp:vocab:id-type",
                value="APPLICANT-002",
            ),
            applicantPhone="+9876543210",
        )

        cr = service.create(schema, source="urn:test:api")
        self.assertEqual(cr.applicant_id, applicant)
        self.assertEqual(cr.applicant_phone, "+9876543210")

    def test_create_with_nonexistent_applicant(self):
        """create proceeds without setting applicant_id if applicant not found."""
        service = ChangeRequestService(self.env)

        schema = ChangeRequestCreate(
            type="ChangeRequest",
            requestType=ChangeRequestType(code="edit_individual"),
            registrant=RegistrantRef(
                system="urn:openspp:vocab:id-type",
                value="TEST-123",
            ),
            applicant=RegistrantRef(
                system="urn:openspp:vocab:id-type",
                value="NONEXISTENT-APPLICANT",
            ),
        )

        cr = service.create(schema, source="urn:test:api")
        # CR should be created but without applicant
        self.assertTrue(cr.id)
        self.assertFalse(cr.applicant_id)

    def test_create_without_detail(self):
        """create works without detail data."""
        service = ChangeRequestService(self.env)

        schema = ChangeRequestCreate(
            type="ChangeRequest",
            requestType=ChangeRequestType(code="edit_individual"),
            registrant=RegistrantRef(
                system="urn:openspp:vocab:id-type",
                value="TEST-123",
            ),
        )

        cr = service.create(schema, source="urn:test:api")
        self.assertTrue(cr.id)
        self.assertTrue(cr.name.startswith("CR/"))

    # ──────────────────────────────────────────────────────────────────────
    # search edge cases
    # ──────────────────────────────────────────────────────────────────────

    def test_search_with_date_filters(self):
        """search filters by created_after and created_before."""
        service = ChangeRequestService(self.env)

        # Create a CR
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Search with date range that includes the CR
        records, total = service.search(
            {
                "created_after": "2020-01-01",
                "created_before": "2099-12-31",
            }
        )
        self.assertGreaterEqual(total, 1)
        self.assertIn(cr.id, records.ids)

        # Search with date range that excludes the CR
        records, total = service.search(
            {
                "created_after": "2099-01-01",
            }
        )
        self.assertEqual(total, 0)

    def test_search_nonexistent_registrant_returns_empty(self):
        """search returns empty when registrant identifier doesn't exist."""
        service = ChangeRequestService(self.env)
        records, total = service.search({"registrant": "urn:test:fake|NONEXISTENT"})
        self.assertEqual(total, 0)
        self.assertEqual(len(records), 0)

    def test_search_without_pipe_in_registrant(self):
        """search ignores registrant filter without pipe separator."""
        service = ChangeRequestService(self.env)

        self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Registrant without pipe — no filter applied
        records, total = service.search({"registrant": "no-pipe-here"})
        # Should return results since no registrant filter is applied
        self.assertGreaterEqual(total, 1)

    # ──────────────────────────────────────────────────────────────────────
    # Additional state validation tests
    # ──────────────────────────────────────────────────────────────────────

    def test_reject_empty_reason_raises(self):
        """Rejecting with empty reason raises ValidationError."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        cr.approval_state = "pending"

        with self.assertRaises(ValidationError):
            service.reject(cr, reason="")

    def test_request_revision_non_pending_raises(self):
        """Requesting revision on non-pending CR raises UserError."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        with self.assertRaises(UserError):
            service.request_revision(cr, notes="needs changes")

    def test_request_revision_empty_notes_raises(self):
        """Requesting revision with empty notes raises ValidationError."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        cr.approval_state = "pending"

        with self.assertRaises(ValidationError):
            service.request_revision(cr, notes="")

    def test_apply_already_applied_raises(self):
        """Applying already-applied CR raises UserError."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        cr.approval_state = "approved"
        cr.is_applied = True

        with self.assertRaises(UserError):
            service.apply(cr)

    # ──────────────────────────────────────────────────────────────────────
    # find_by_reference edge cases
    # ──────────────────────────────────────────────────────────────────────

    def test_find_by_reference_not_found(self):
        """find_by_reference returns empty recordset for unknown reference."""
        service = ChangeRequestService(self.env)
        result = service.find_by_reference("CR/9999/99999")
        self.assertFalse(result)

    # ──────────────────────────────────────────────────────────────────────
    # update_detail edge cases
    # ──────────────────────────────────────────────────────────────────────

    def test_update_detail_with_vocabulary_success(self):
        """update_detail successfully sets vocabulary field via system/code."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        service.update_detail(
            cr,
            {
                "gender_id": {
                    "system": "urn:iso:std:iso:5218",
                    "code": "2",
                },
            },
        )

        detail = cr.get_detail()
        self.assertTrue(detail.gender_id)
        self.assertEqual(detail.gender_id.code, "2")

    def test_update_detail_multiple_fields(self):
        """update_detail handles multiple fields at once."""
        service = ChangeRequestService(self.env)
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        service.update_detail(
            cr,
            {
                "given_name": "Alice",
                "family_name": "Smith",
                "phone": "+1111111111",
                "birthdate": "1992-03-20",
            },
        )

        detail = cr.get_detail()
        self.assertEqual(detail.given_name, "Alice")
        self.assertEqual(detail.family_name, "Smith")
        self.assertEqual(detail.phone, "+1111111111")
        self.assertEqual(detail.birthdate.isoformat(), "1992-03-20")
