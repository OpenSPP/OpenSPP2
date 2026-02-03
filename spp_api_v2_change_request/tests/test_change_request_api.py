# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Change Request API endpoints."""

from odoo.tests import TransactionCase


class TestChangeRequestAPI(TransactionCase):
    """Tests for Change Request API endpoints.

    These tests verify the API endpoint logic.
    Full integration tests require FastAPI test client setup.
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

    def test_router_included(self):
        """Test that CR router is included in API V2."""
        endpoint = self.env["fastapi.endpoint"].search(
            [("app", "=", "api_v2")],
            limit=1,
        )
        if not endpoint:
            self.skipTest("No API V2 endpoint found")

        routers = endpoint._get_fastapi_routers()
        router_prefixes = [r.prefix for r in routers]
        self.assertIn("/ChangeRequest", router_prefixes)

    def test_service_create_and_read_workflow(self):
        """Test create and read workflow through service."""
        from ..schemas.change_request import (
            ChangeRequestCreate,
            ChangeRequestType,
            RegistrantRef,
        )
        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        # Create
        schema = ChangeRequestCreate(
            type="ChangeRequest",
            requestType=ChangeRequestType(code="edit_individual"),
            registrant=RegistrantRef(
                system="urn:openspp:vocab:id-type",
                value="TEST-123",
            ),
            detail={"given_name": "Test Name"},
        )

        cr = service.create(schema, source="urn:test:api")
        self.assertTrue(cr.name.startswith("CR/"))

        # Read
        found = service.find_by_reference(cr.name)
        self.assertEqual(found.id, cr.id)

        # Convert to API schema
        data = service.to_api_schema(found)
        self.assertEqual(data["type"], "ChangeRequest")
        self.assertEqual(data["reference"], cr.name)
        self.assertEqual(data["status"], "draft")

    def test_service_update_workflow(self):
        """Test update workflow through service."""
        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        # Create CR
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Update detail
        service.update_detail(cr, {"given_name": "Updated Name"})

        # Verify
        detail = cr.get_detail()
        self.assertEqual(detail.given_name, "Updated Name")

    def test_service_submit_workflow(self):
        """Test submit workflow through service."""
        from odoo.exceptions import UserError

        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        # Create CR
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Submit should work for draft
        # Note: This may fail if no approval definition is configured
        # In that case, we expect a UserError
        try:
            service.submit(cr)
            self.assertIn(cr.approval_state, ["pending", "approved"])  # Could be auto-approved
        except UserError as e:
            # Expected if no approval workflow configured
            self.assertIn("approval", str(e).lower())

    def test_service_submit_non_draft_fails(self):
        """Test that submitting non-draft CR fails."""
        from odoo.exceptions import UserError

        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        # Create CR and set to pending
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        cr.approval_state = "pending"

        with self.assertRaises(UserError):
            service.submit(cr)

    def test_service_apply_requires_approved(self):
        """Test that apply requires approved status."""
        from odoo.exceptions import UserError

        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        # Create draft CR
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        with self.assertRaises(UserError):
            service.apply(cr)

    def test_service_reset_to_draft(self):
        """Test reset to draft workflow."""

        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        # Create CR and set to rejected
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        cr.approval_state = "rejected"

        # Reset should work
        service.reset_to_draft(cr)
        self.assertEqual(cr.approval_state, "draft")

    def test_service_reset_draft_fails(self):
        """Test that resetting draft CR fails."""
        from odoo.exceptions import UserError

        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        # Create draft CR
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        with self.assertRaises(UserError):
            service.reset_to_draft(cr)

    def test_search_with_pagination(self):
        """Test search with pagination."""
        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        # Create multiple CRs
        for _i in range(5):
            self.cr_model.create(
                {
                    "request_type_id": self.cr_type_edit.id,
                    "registrant_id": self.registrant.id,
                }
            )

        # Search with pagination
        records, total = service.search(
            {
                "_count": 2,
                "_offset": 0,
            }
        )
        self.assertLessEqual(len(records), 2)
        self.assertGreaterEqual(total, 5)

        # Second page
        records2, total2 = service.search(
            {
                "_count": 2,
                "_offset": 2,
            }
        )
        self.assertLessEqual(len(records2), 2)
        self.assertEqual(total, total2)
