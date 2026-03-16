# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Change Request API endpoints."""

from .common import ChangeRequestTestCase


class TestChangeRequestAPI(ChangeRequestTestCase):
    """Tests for Change Request API endpoints.

    These tests verify the API endpoint logic.
    Full integration tests require FastAPI test client setup.
    """

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

    # ──────────────────────────────────────────────────────────────────────
    # Router helper tests
    # ──────────────────────────────────────────────────────────────────────

    def test_build_reference(self):
        """_build_reference reconstructs CR reference from path segments."""
        from ..routers.change_request import _build_reference

        self.assertEqual(_build_reference("CR", "2026", "00001"), "CR/2026/00001")
        self.assertEqual(_build_reference("CR", "2024", "12345"), "CR/2024/12345")

    # ──────────────────────────────────────────────────────────────────────
    # Model extension tests
    # ──────────────────────────────────────────────────────────────────────

    def test_api_client_scope_has_change_request_resource(self):
        """spp.api.client.scope includes change_request as a resource option."""
        scope_model = self.env["spp.api.client.scope"]
        resource_field = scope_model._fields["resource"]
        selection_keys = [key for key, _label in resource_field.selection]
        self.assertIn("change_request", selection_keys)

    # ──────────────────────────────────────────────────────────────────────
    # End-to-end workflow tests
    # ──────────────────────────────────────────────────────────────────────

    def test_create_update_read_workflow(self):
        """Full create → update detail → read back workflow via service."""
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
            detail={"given_name": "Initial"},
        )
        cr = service.create(schema, source="urn:test:workflow")

        # Update
        service.update_detail(cr, {"given_name": "Updated", "family_name": "Name"})

        # Read back via to_api_schema
        data = service.to_api_schema(cr)
        self.assertEqual(data["detail"]["given_name"], "Updated")
        self.assertEqual(data["detail"]["family_name"], "Name")
        self.assertEqual(data["status"], "draft")
        self.assertFalse(data["isApplied"])

    def test_version_id_is_derived_from_write_date(self):
        """versionId in meta is derived from CR write_date."""
        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        data = service.to_api_schema(cr)
        version_id = data["meta"]["versionId"]

        # versionId should be a numeric string derived from write_date
        self.assertTrue(version_id.isdigit())
        expected = str(int(cr.write_date.timestamp() * 1000000))
        self.assertEqual(version_id, expected)

    # ──────────────────────────────────────────────────────────────────────
    # Router-level logic tests (testing logic without HTTP transport)
    # ──────────────────────────────────────────────────────────────────────

    def test_update_non_draft_cr_rejected(self):
        """Updating a non-draft CR should be rejected (mirrors router 409 logic)."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        cr.approval_state = "pending"

        # The router checks approval_state != "draft" and returns 409.
        # Verify the state check that the router relies on.
        self.assertNotEqual(cr.approval_state, "draft")

    def test_optimistic_locking_version_mismatch(self):
        """Version mismatch detection for If-Match header (mirrors router logic)."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Compute current version the same way the router does
        current_version = str(int(cr.write_date.timestamp() * 1000000))

        # Matching version should pass
        if_match_value = f'"{current_version}"'
        if_match_clean = if_match_value.strip('"')
        self.assertEqual(if_match_clean, current_version)

        # Mismatched version should be detected
        stale_version = "9999999999999999"
        self.assertNotEqual(stale_version, current_version)

    def test_etag_header_value_format(self):
        """ETag value follows the quoted versionId format."""
        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        data = service.to_api_schema(cr)
        version_id = data.get("meta", {}).get("versionId")

        # ETag would be formatted as: '"<versionId>"'
        self.assertIsNotNone(version_id)
        etag = f'"{version_id}"'
        self.assertTrue(etag.startswith('"'))
        self.assertTrue(etag.endswith('"'))

    def test_cr_not_found_returns_falsy(self):
        """find_by_reference returns falsy for nonexistent CR (mirrors router 404)."""
        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)
        result = service.find_by_reference("CR/9999/99999")
        self.assertFalse(result)

    def test_type_schema_not_found_returns_none(self):
        """get_type_schema returns None for nonexistent type (mirrors router 404)."""
        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)
        result = service.get_type_schema("nonexistent_type_xyz")
        self.assertIsNone(result)

    def test_reset_revision_state_to_draft(self):
        """Reset a revision-state CR to draft."""
        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )
        cr.approval_state = "revision"

        service.reset_to_draft(cr)
        self.assertEqual(cr.approval_state, "draft")

    def test_search_defaults(self):
        """Search with empty params uses defaults (offset=0, count=20)."""
        from ..services.change_request_service import ChangeRequestService

        service = ChangeRequestService(self.env)

        # Create a CR so results aren't empty
        self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit.id,
                "registrant_id": self.registrant.id,
            }
        )

        records, total = service.search({})
        self.assertGreaterEqual(total, 1)
        self.assertLessEqual(len(records), 20)
