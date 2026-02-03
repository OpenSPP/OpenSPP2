"""Tests for Studio Change Request Type functionality."""

import logging

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestStudioCRType(TransactionCase):
    """Test Studio Change Request Type creation and lifecycle."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get required models
        cls.StudioCRType = cls.env["spp.studio.change.request.type"]
        cls.FieldMapping = cls.env["spp.studio.cr.field.mapping"]
        cls.IrFields = cls.env["ir.model.fields"]

        # Get some fields to work with
        cls.field_street = cls.IrFields.search(
            [
                ("model", "=", "res.partner"),
                ("name", "=", "street"),
            ],
            limit=1,
        )
        cls.field_city = cls.IrFields.search(
            [
                ("model", "=", "res.partner"),
                ("name", "=", "city"),
            ],
            limit=1,
        )
        cls.field_phone = cls.IrFields.search(
            [
                ("model", "=", "res.partner"),
                ("name", "=", "phone"),
            ],
            limit=1,
        )
        cls.field_email = cls.IrFields.search(
            [
                ("model", "=", "res.partner"),
                ("name", "=", "email"),
            ],
            limit=1,
        )

        # Get approval group
        cls.approval_group = cls.env.ref("spp_studio.group_studio_manager")

    def test_01_create_cr_type_basic(self):
        """Test creating a basic CR type."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Address Update Request",
                "target_type": "individual",
                "description": "Update address information",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
                "auto_apply": True,
            }
        )

        self.assertEqual(cr_type.state, "draft")
        self.assertTrue(cr_type.technical_name.startswith("x_cr_"))
        self.assertEqual(cr_type.field_count, 0)

    def test_02_create_cr_type_with_mappings(self):
        """Test creating a CR type with field mappings."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Contact Update",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        # Add field mappings
        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
                "label": "New Phone Number",
                "is_required": True,
                "sequence": 10,
            }
        )
        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_email.id,
                "label": "New Email",
                "is_required": False,
                "sequence": 20,
            }
        )

        self.assertEqual(cr_type.field_count, 2)
        self.assertEqual(len(cr_type.field_mapping_ids), 2)

    def test_03_activate_cr_type(self):
        """Test activating a CR type creates the necessary records."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Address Change",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        # Add field mappings
        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_street.id,
                "sequence": 10,
            }
        )
        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_city.id,
                "sequence": 20,
            }
        )

        # Activate
        cr_type.action_activate()

        self.assertEqual(cr_type.state, "active")
        self.assertTrue(cr_type.spp_change_request_type_id)
        self.assertTrue(cr_type.detail_model_id)

        # Check that the CR type was created
        spp_cr_type = cr_type.spp_change_request_type_id
        self.assertEqual(spp_cr_type.name, "Address Change")
        self.assertEqual(spp_cr_type.target_type, "individual")
        self.assertEqual(spp_cr_type.apply_strategy, "field_mapping")

        # Check that mappings were created
        mappings = spp_cr_type.apply_mapping_ids
        self.assertEqual(len(mappings), 2)

    def test_04_cannot_activate_without_fields(self):
        """Test that CR type cannot be activated without field mappings."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Test CR",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        with self.assertRaises(ValidationError):
            cr_type.action_activate()

    def test_05_cannot_edit_core_settings_on_active_cr_type(self):
        """Test that core settings on active CR types cannot be edited."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Phone Update",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
            }
        )

        cr_type.action_activate()

        # Try to edit name - should fail
        with self.assertRaises(UserError):
            cr_type.write({"name": "New Name"})

        # Try to edit target_type - should fail
        with self.assertRaises(UserError):
            cr_type.write({"target_type": "group"})

        # Try to edit requires_approval - should fail
        with self.assertRaises(UserError):
            cr_type.write({"requires_approval": False})

        # State changes should be allowed
        cr_type.action_deactivate()
        self.assertEqual(cr_type.state, "inactive")

    def test_06_deactivate_cr_type(self):
        """Test deactivating a CR type."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Email Update",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_email.id,
            }
        )

        cr_type.action_activate()
        spp_cr_type_id = cr_type.spp_change_request_type_id.id

        # Deactivate
        cr_type.action_deactivate()

        self.assertEqual(cr_type.state, "inactive")
        # The SPP CR type should be deactivated
        spp_cr_type = self.env["spp.change.request.type"].browse(spp_cr_type_id)
        self.assertFalse(spp_cr_type.active)

    def test_07_reactivate_cr_type(self):
        """Test reactivating a deactivated CR type."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Test Reactivate",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
            }
        )

        cr_type.action_activate()
        cr_type.action_deactivate()

        # Reactivate
        cr_type.action_reactivate()

        self.assertEqual(cr_type.state, "active")
        self.assertTrue(cr_type.spp_change_request_type_id.active)

    def test_08_technical_name_generation(self):
        """Test technical name generation is unique."""
        cr_type1 = self.StudioCRType.create(
            {
                "name": "Address Update",
                "target_type": "individual",
            }
        )
        cr_type2 = self.StudioCRType.create(
            {
                "name": "Address Update",
                "target_type": "group",
            }
        )

        self.assertNotEqual(cr_type1.technical_name, cr_type2.technical_name)
        self.assertTrue(cr_type1.technical_name.startswith("x_cr_address_update"))
        self.assertTrue(cr_type2.technical_name.startswith("x_cr_address_update"))

    def test_09_field_mapping_validation(self):
        """Test field mapping validation."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Test Validation",
                "target_type": "individual",
            }
        )

        # Create mapping with regex validation
        mapping = self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
                "validation_type": "regex",
                "validation_rule": r"^\+?[0-9]{10,15}$",
            }
        )

        self.assertEqual(mapping.validation_type, "regex")

        # Test invalid regex
        with self.assertRaises(ValidationError):
            mapping.write(
                {
                    "validation_rule": "[invalid regex(",
                }
            )

    def test_10_cannot_duplicate_field_mapping(self):
        """Test that the same field cannot be mapped twice in one CR type."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Test Duplicate",
                "target_type": "individual",
            }
        )

        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
            }
        )

        # Try to add the same field again
        with self.assertRaises(ValidationError):
            self.FieldMapping.create(
                {
                    "cr_type_id": cr_type.id,
                    "field_id": self.field_phone.id,
                }
            )

    def test_11_wizard_flow(self):
        """Test the wizard flow for creating CR types."""
        Wizard = self.env["spp.studio.cr.type.wizard"]

        # Step 1: Create wizard
        wizard = Wizard.create(
            {
                "name": "Wizard Test CR",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
                "auto_apply": True,
            }
        )

        self.assertEqual(wizard.step, "basic")

        # Step 2: Move to field selection
        wizard.action_next()
        self.assertEqual(wizard.step, "fields")

        # Select fields
        wizard.write(
            {
                "selected_field_ids": [Command.set([self.field_street.id, self.field_city.id])],
            }
        )

        # Step 3: Move to review
        wizard.action_next()
        self.assertEqual(wizard.step, "review")
        self.assertEqual(wizard.preview_field_count, 2)

        # Create the CR type
        result = wizard.action_create_cr_type()

        # Verify the CR type was created
        cr_type_id = result.get("res_id")
        cr_type = self.StudioCRType.browse(cr_type_id)

        self.assertEqual(cr_type.name, "Wizard Test CR")
        self.assertEqual(cr_type.state, "draft")
        self.assertEqual(len(cr_type.field_mapping_ids), 2)

    def test_12_delete_active_cr_type_fails(self):
        """Test that active CR types cannot be deleted."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Test Delete",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
            }
        )

        cr_type.action_activate()

        # Try to delete - should fail
        with self.assertRaises(UserError):
            cr_type.unlink()

        # Deactivate and delete should work
        cr_type.action_deactivate()
        cr_type.unlink()

    def test_13_cr_type_with_both_target(self):
        """Test CR type that targets both individual and group."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Contact Update (Both)",
                "target_type": "both",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
            }
        )

        cr_type.action_activate()

        self.assertEqual(cr_type.spp_change_request_type_id.target_type, "both")

    def test_14_field_mapping_label_default(self):
        """Test that field mapping label defaults to field description."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Test Label",
                "target_type": "individual",
            }
        )

        mapping = self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
            }
        )

        # Label should be empty initially but onchange should set it
        # In tests, onchange doesn't fire automatically, so we can test the compute
        mapping._onchange_field_id()
        self.assertEqual(mapping.label, self.field_phone.field_description)

    def test_15_edit_field_mappings_on_active_type(self):
        """Test that field mappings can be added to active CR types."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Edit Active Mappings",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        # Add initial field mapping
        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
                "sequence": 10,
            }
        )

        # Activate the type
        cr_type.action_activate()
        self.assertEqual(cr_type.state, "active")
        initial_field_count = len(cr_type.field_mapping_ids)

        # Add a new field mapping to active type - this should work
        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_email.id,
                "label": "Email Address",
                "sequence": 20,
            }
        )

        self.assertEqual(len(cr_type.field_mapping_ids), initial_field_count + 1)

        # Verify the new field was added to the detail model
        detail_model = cr_type.detail_model_id
        email_field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", detail_model.id),
                ("name", "=", "x_email"),
            ],
            limit=1,
        )
        self.assertTrue(email_field, "Email field should be added to detail model")

        # Verify mapping was added to spp.change.request.type
        spp_mappings = cr_type.spp_change_request_type_id.apply_mapping_ids
        email_mapping = spp_mappings.filtered(lambda m: m.source_field == "x_email")
        self.assertTrue(email_mapping, "Email mapping should be added to CR type")

    def test_16_modify_field_mapping_on_active_type(self):
        """Test that existing field mappings can be modified on active types."""
        cr_type = self.StudioCRType.create(
            {
                "name": "Modify Active Mapping",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        mapping = self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
                "label": "Phone Number",
                "is_required": False,
                "sequence": 10,
            }
        )

        # Activate the type
        cr_type.action_activate()

        # Modify the mapping
        mapping.write(
            {
                "label": "Contact Phone",
                "is_required": True,
            }
        )

        # Verify changes are reflected
        self.assertEqual(mapping.label, "Contact Phone")
        self.assertTrue(mapping.is_required)

        # The detail model field should also be updated
        detail_model = cr_type.detail_model_id
        phone_field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", detail_model.id),
                ("name", "=", "x_phone"),
            ],
            limit=1,
        )
        self.assertEqual(phone_field.field_description, "Contact Phone")
        # Field should NOT have database-level required constraint
        self.assertFalse(phone_field.required)
        # But it SHOULD be in the CR type's required_field_ids
        spp_cr_type = cr_type.spp_change_request_type_id
        self.assertIn(phone_field, spp_cr_type.required_field_ids)

    def test_17_edit_mode_does_not_affect_existing_requests(self):
        """Test that editing mappings on active type doesn't break existing change requests."""
        # Create and activate a CR type
        cr_type = self.StudioCRType.create(
            {
                "name": "Test Existing Requests",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
                "sequence": 10,
            }
        )

        cr_type.action_activate()

        # Create a test registrant
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create a change request using this type
        spp_cr_type = cr_type.spp_change_request_type_id
        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": spp_cr_type.id,
                "registrant_id": partner.id,
            }
        )

        # Now add a new field mapping
        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_email.id,
                "sequence": 20,
            }
        )

        # The existing CR should still be valid
        self.assertTrue(cr.exists())
        self.assertEqual(cr.request_type_id.id, spp_cr_type.id)

    def test_18_required_fields_validation(self):
        """Test that required fields are properly handled via required_field_ids."""
        # Create CR type with required and optional fields
        cr_type = self.StudioCRType.create(
            {
                "name": "Test Required Fields",
                "target_type": "individual",
                "requires_approval": True,
                "approval_group_id": self.approval_group.id,
            }
        )

        # Add field mappings - phone is required, email is optional
        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_phone.id,
                "label": "Phone Number",
                "is_required": True,
                "sequence": 10,
            }
        )
        self.FieldMapping.create(
            {
                "cr_type_id": cr_type.id,
                "field_id": self.field_email.id,
                "label": "Email Address",
                "is_required": False,
                "sequence": 20,
            }
        )

        # Activate the type
        cr_type.action_activate()
        spp_cr_type = cr_type.spp_change_request_type_id
        detail_model = cr_type.detail_model_id

        # Verify that phone field is in required_field_ids
        phone_field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", detail_model.id),
                ("name", "=", "x_phone"),
            ],
            limit=1,
        )
        email_field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", detail_model.id),
                ("name", "=", "x_email"),
            ],
            limit=1,
        )

        # Phone should be in required_field_ids, email should not
        self.assertIn(phone_field, spp_cr_type.required_field_ids)
        self.assertNotIn(email_field, spp_cr_type.required_field_ids)

        # Neither should have database-level required constraint
        self.assertFalse(phone_field.required)
        self.assertFalse(email_field.required)

        # Create a test registrant and change request
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cr = self.env["spp.change.request"].create(
            {
                "request_type_id": spp_cr_type.id,
                "registrant_id": partner.id,
            }
        )

        # CR should be created successfully (no database constraint)
        self.assertTrue(cr.exists())
        detail = cr.get_detail()
        self.assertTrue(detail)

        # Test validation - detail record with empty required field should fail validation
        is_valid, missing = spp_cr_type.validate_required_fields(detail)
        self.assertFalse(is_valid)
        self.assertIn("Phone Number", missing)

        # Fill in the required field
        detail.write({"x_phone": "+1234567890"})

        # Now validation should pass
        is_valid, missing = spp_cr_type.validate_required_fields(detail)
        self.assertTrue(is_valid)
        self.assertEqual(len(missing), 0)
