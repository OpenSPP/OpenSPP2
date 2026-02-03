"""Tests for Studio Event Type."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestStudioEventType(TransactionCase):
    """Test cases for spp.studio.event.type model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.StudioEventType = cls.env["spp.studio.event.type"]
        cls.StudioEventField = cls.env["spp.studio.event.field"]
        cls.EventType = cls.env["spp.event.type"]

    def test_create_event_type(self):
        """Test creating a basic event type."""
        event_type = self.StudioEventType.create(
            {
                "name": "Test Event Type",
                "target_type": "individual",
                "description": "Test description",
            }
        )
        self.assertTrue(event_type.exists())
        self.assertEqual(event_type.state, "draft")
        self.assertTrue(event_type.technical_name.startswith("x_evt_"))
        self.assertIn("test_event_type", event_type.technical_name)

    def test_technical_name_generation(self):
        """Test technical name is auto-generated from name."""
        event_type = self.StudioEventType.create(
            {
                "name": "Health Screening Event!",
                "target_type": "individual",
            }
        )
        self.assertEqual(event_type.technical_name, "x_evt_health_screening_event")

    def test_technical_name_uniqueness(self):
        """Test technical names are unique."""
        event_type1 = self.StudioEventType.create(
            {
                "name": "Unique Event",
                "target_type": "individual",
            }
        )
        event_type2 = self.StudioEventType.create(
            {
                "name": "Unique Event",
                "target_type": "individual",
            }
        )
        self.assertNotEqual(event_type1.technical_name, event_type2.technical_name)

    def test_create_event_type_with_fields(self):
        """Test creating event type with fields."""
        event_type = self.StudioEventType.create(
            {
                "name": "Health Screening",
                "target_type": "individual",
            }
        )

        # Add fields
        field1 = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Blood Pressure",
                "field_type": "text",
                "is_required": True,
            }
        )
        field2 = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Weight",
                "field_type": "decimal",
                "is_required": False,
            }
        )

        self.assertEqual(event_type.data_field_count, 2)
        self.assertEqual(field1.technical_name, "blood_pressure")
        self.assertEqual(field2.technical_name, "weight")

    def test_selection_field_requires_options(self):
        """Test selection fields require options."""
        event_type = self.StudioEventType.create(
            {
                "name": "Test Event",
                "target_type": "individual",
            }
        )

        with self.assertRaises(ValidationError):
            self.StudioEventField.create(
                {
                    "event_type_id": event_type.id,
                    "label": "Status",
                    "field_type": "selection",
                    # Missing selection_options
                }
            )

    def test_selection_field_with_options(self):
        """Test creating selection field with options."""
        event_type = self.StudioEventType.create(
            {
                "name": "Test Event",
                "target_type": "individual",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Status",
                "field_type": "selection",
                "selection_options": "good|Good\nfair|Fair\npoor|Poor",
            }
        )

        options = field._parse_selection_options()
        self.assertEqual(len(options), 3)
        self.assertEqual(options[0], ("good", "Good"))
        self.assertEqual(options[1], ("fair", "Fair"))
        self.assertEqual(options[2], ("poor", "Poor"))

    def test_cannot_activate_without_fields(self):
        """Test that event types cannot be activated without fields."""
        event_type = self.StudioEventType.create(
            {
                "name": "Empty Event",
                "target_type": "individual",
            }
        )

        with self.assertRaises(UserError):
            event_type.action_activate()

    def test_activate_event_type(self):
        """Test activating an event type creates spp.event.type."""
        event_type = self.StudioEventType.create(
            {
                "name": "Activation Test",
                "target_type": "individual",
            }
        )

        # Add a field
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        # Activate
        event_type.action_activate()

        self.assertEqual(event_type.state, "active")
        self.assertTrue(event_type.spp_event_type_id)
        self.assertEqual(event_type.spp_event_type_id.name, "Activation Test")
        self.assertEqual(event_type.spp_event_type_id.code, event_type.technical_name)

    def test_cannot_modify_active_event_type(self):
        """Test that active event types cannot be modified."""
        event_type = self.StudioEventType.create(
            {
                "name": "Locked Event",
                "target_type": "individual",
            }
        )

        # Add field and activate
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )
        event_type.action_activate()

        # Try to modify - should fail
        with self.assertRaises(UserError):
            event_type.write({"name": "New Name"})

    def test_cannot_modify_fields_when_active(self):
        """Test that fields cannot be modified when event type is active."""
        event_type = self.StudioEventType.create(
            {
                "name": "Locked Fields Event",
                "target_type": "individual",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        # Activate
        event_type.action_activate()

        # Try to modify field - should fail
        with self.assertRaises(UserError):
            field.write({"label": "New Label"})

    def test_cannot_delete_fields_when_active(self):
        """Test that fields cannot be deleted when event type is active."""
        event_type = self.StudioEventType.create(
            {
                "name": "Delete Fields Event",
                "target_type": "individual",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        # Activate
        event_type.action_activate()

        # Try to delete field - should fail
        with self.assertRaises(UserError):
            field.unlink()

    def test_deactivate_event_type(self):
        """Test deactivating an event type."""
        event_type = self.StudioEventType.create(
            {
                "name": "Deactivate Test",
                "target_type": "individual",
            }
        )

        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        # Activate first
        event_type.action_activate()
        self.assertEqual(event_type.state, "active")

        # Deactivate
        result = event_type.action_deactivate()
        if result is True or result is None:
            self.assertEqual(event_type.state, "inactive")
        else:
            # If wizard returned, call _do_deactivate directly
            event_type._do_deactivate()
            self.assertEqual(event_type.state, "inactive")

        # Check that linked event type is also deactivated
        self.assertFalse(event_type.spp_event_type_id.active)

    def test_lifecycle_draft_to_active_to_inactive(self):
        """Test full lifecycle from draft to active to inactive."""
        event_type = self.StudioEventType.create(
            {
                "name": "Lifecycle Test",
                "target_type": "individual",
            }
        )

        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        # Draft state
        self.assertEqual(event_type.state, "draft")
        self.assertFalse(event_type.activated_by_id)

        # Activate
        event_type.action_activate()
        self.assertEqual(event_type.state, "active")
        self.assertTrue(event_type.activated_by_id)
        self.assertTrue(event_type.activated_date)

        # Deactivate
        result = event_type.action_deactivate()
        if result is not True and result is not None:
            event_type._do_deactivate()

        self.assertEqual(event_type.state, "inactive")
        self.assertTrue(event_type.deactivated_by_id)
        self.assertTrue(event_type.deactivated_date)

    def test_cannot_delete_active_event_type(self):
        """Test that active event types cannot be deleted."""
        event_type = self.StudioEventType.create(
            {
                "name": "No Delete",
                "target_type": "individual",
            }
        )

        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        event_type.action_activate()

        with self.assertRaises(UserError):
            event_type.unlink()

    def test_can_delete_draft_event_type(self):
        """Test that draft event types can be deleted."""
        event_type = self.StudioEventType.create(
            {
                "name": "Can Delete",
                "target_type": "individual",
            }
        )

        event_type_id = event_type.id
        event_type.unlink()
        self.assertFalse(self.StudioEventType.browse(event_type_id).exists())

    def test_all_field_types(self):
        """Test creating fields of all types."""
        event_type = self.StudioEventType.create(
            {
                "name": "All Types Event",
                "target_type": "individual",
            }
        )

        field_types = [
            ("text", {}),
            ("long_text", {}),
            ("integer", {}),
            ("decimal", {}),
            ("date", {}),
            ("datetime", {}),
            ("boolean", {}),
            ("selection", {"selection_options": "a|A\nb|B"}),
        ]

        for idx, (ftype, extra_vals) in enumerate(field_types):
            vals = {
                "event_type_id": event_type.id,
                "label": f"Test {ftype} {idx}",
                "field_type": ftype,
            }
            vals.update(extra_vals)
            field = self.StudioEventField.create(vals)
            self.assertEqual(field.field_type, ftype)

    def test_target_type_options(self):
        """Test all target type options."""
        for target_type in ["individual", "group", "both"]:
            event_type = self.StudioEventType.create(
                {
                    "name": f"Target {target_type}",
                    "target_type": target_type,
                }
            )
            self.assertEqual(event_type.target_type, target_type)

    def test_event_type_with_approval(self):
        """Test creating event type with approval requirement."""
        # Create an approval definition first
        approval_group = self.env["res.groups"].create({"name": "Test Approval Group"})
        approval_definition = self.env["spp.approval.definition"].create(
            {
                "name": "Event Approval",
                "model_id": self.env.ref("spp_event_data.model_spp_event_data").id,
                "approval_type": "group",
                "approval_group_id": approval_group.id,
            }
        )

        event_type = self.StudioEventType.create(
            {
                "name": "Approval Event",
                "target_type": "individual",
                "requires_approval": True,
                "approval_definition_id": approval_definition.id,
            }
        )

        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        event_type.action_activate()

        self.assertTrue(event_type.spp_event_type_id.is_requires_approval)
        self.assertEqual(
            event_type.spp_event_type_id.approval_definition_id,
            approval_definition,
        )

    def test_event_type_with_kobo_integration(self):
        """Test creating event type with Kobo form ID."""
        event_type = self.StudioEventType.create(
            {
                "name": "Kobo Event",
                "target_type": "individual",
                "kobo_form_id": "test_form_123",
            }
        )

        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        event_type.action_activate()

        self.assertEqual(event_type.spp_event_type_id.external_form_id, "test_form_123")
        self.assertEqual(event_type.spp_event_type_id.source_type, "kobo")

    # ══════════════════════════════════════════════════════════════════════════
    # NEW FIELD TYPES TESTS
    # ══════════════════════════════════════════════════════════════════════════

    def test_multi_select_field_requires_options(self):
        """Test multi_select fields require options like selection fields."""
        event_type = self.StudioEventType.create(
            {
                "name": "Multi Select Test",
                "target_type": "individual",
            }
        )

        with self.assertRaises(ValidationError):
            self.StudioEventField.create(
                {
                    "event_type_id": event_type.id,
                    "label": "Multi Choice",
                    "field_type": "multi_select",
                    # Missing selection_options
                }
            )

    def test_multi_select_field_with_options(self):
        """Test creating multi_select field with options."""
        event_type = self.StudioEventType.create(
            {
                "name": "Multi Select Test",
                "target_type": "individual",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Services",
                "field_type": "multi_select",
                "selection_options": "health|Health\neducation|Education\nhousing|Housing",
            }
        )

        options = field._parse_selection_options()
        self.assertEqual(len(options), 3)
        self.assertEqual(options[0], ("health", "Health"))

    def test_link_field_requires_model(self):
        """Test link field requires link_model_id."""
        event_type = self.StudioEventType.create(
            {
                "name": "Link Test",
                "target_type": "individual",
            }
        )

        with self.assertRaises(ValidationError):
            self.StudioEventField.create(
                {
                    "event_type_id": event_type.id,
                    "label": "Related Partner",
                    "field_type": "link",
                    # Missing link_model_id
                }
            )

    def test_link_field_with_model(self):
        """Test creating link field with model reference."""
        event_type = self.StudioEventType.create(
            {
                "name": "Link Test",
                "target_type": "individual",
            }
        )

        partner_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Related Partner",
                "field_type": "link",
                "link_model_id": partner_model.id,
                "link_domain": "[('is_registrant', '=', True)]",
            }
        )

        self.assertEqual(field.link_model_id, partner_model)
        self.assertEqual(field.link_domain, "[('is_registrant', '=', True)]")

    # ══════════════════════════════════════════════════════════════════════════
    # VALIDATION RULES TESTS
    # ══════════════════════════════════════════════════════════════════════════

    def test_range_validation_min_max(self):
        """Test range validation with min/max values."""
        event_type = self.StudioEventType.create(
            {
                "name": "Range Validation Test",
                "target_type": "individual",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Age",
                "field_type": "integer",
                "validation_type": "range",
                "validation_min": 0,
                "validation_max": 150,
                "validation_error_message": "Age must be between 0 and 150",
            }
        )

        # Test valid value
        is_valid, error = field.validate_value(50)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        # Test value below minimum
        is_valid, error = field.validate_value(-5)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

        # Test value above maximum
        is_valid, error = field.validate_value(200)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_regex_validation(self):
        """Test regex pattern validation."""
        event_type = self.StudioEventType.create(
            {
                "name": "Regex Validation Test",
                "target_type": "individual",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "National ID",
                "field_type": "text",
                "validation_type": "regex",
                "validation_regex": "^[A-Z]{2}[0-9]{6}$",
                "validation_error_message": "Must be 2 letters followed by 6 digits",
            }
        )

        # Test valid value
        is_valid, error = field.validate_value("AB123456")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        # Test invalid value
        is_valid, error = field.validate_value("invalid")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_invalid_regex_pattern_rejected(self):
        """Test that invalid regex patterns are rejected."""
        event_type = self.StudioEventType.create(
            {
                "name": "Invalid Regex Test",
                "target_type": "individual",
            }
        )

        with self.assertRaises(ValidationError):
            self.StudioEventField.create(
                {
                    "event_type_id": event_type.id,
                    "label": "Bad Pattern",
                    "field_type": "text",
                    "validation_type": "regex",
                    "validation_regex": "[invalid(regex",  # Invalid regex
                }
            )

    def test_selection_validation(self):
        """Test that selection field validates against options."""
        event_type = self.StudioEventType.create(
            {
                "name": "Selection Validation Test",
                "target_type": "individual",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Status",
                "field_type": "selection",
                "selection_options": "active|Active\ninactive|Inactive",
            }
        )

        # Test valid value
        is_valid, error = field.validate_value("active")
        self.assertTrue(is_valid)

        # Test invalid value
        is_valid, error = field.validate_value("unknown")
        self.assertFalse(is_valid)

    def test_multi_select_validation(self):
        """Test that multi_select validates list values."""
        event_type = self.StudioEventType.create(
            {
                "name": "Multi Select Validation Test",
                "target_type": "individual",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Services",
                "field_type": "multi_select",
                "selection_options": "a|A\nb|B\nc|C",
            }
        )

        # Test valid list
        is_valid, error = field.validate_value(["a", "b"])
        self.assertTrue(is_valid)

        # Test list with invalid value
        is_valid, error = field.validate_value(["a", "invalid"])
        self.assertFalse(is_valid)

    def test_empty_value_skips_validation(self):
        """Test that empty values skip validation (required check is separate)."""
        event_type = self.StudioEventType.create(
            {
                "name": "Empty Value Test",
                "target_type": "individual",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Score",
                "field_type": "integer",
                "validation_type": "range",
                "validation_min": 0,
                "validation_max": 100,
            }
        )

        # Empty values should pass validation
        is_valid, error = field.validate_value(None)
        self.assertTrue(is_valid)

        is_valid, error = field.validate_value("")
        self.assertTrue(is_valid)

    # ══════════════════════════════════════════════════════════════════════════
    # CONDITIONAL VISIBILITY TESTS
    # ══════════════════════════════════════════════════════════════════════════

    def test_conditional_visibility_requires_field(self):
        """Test that conditional visibility requires a field reference."""
        event_type = self.StudioEventType.create(
            {
                "name": "Visibility Test",
                "target_type": "individual",
            }
        )

        with self.assertRaises(ValidationError):
            self.StudioEventField.create(
                {
                    "event_type_id": event_type.id,
                    "label": "Conditional Field",
                    "field_type": "text",
                    "visibility_condition": "conditional",
                    # Missing visibility_field_id
                }
            )

    def test_cannot_self_reference_visibility(self):
        """Test that a field cannot reference itself for visibility."""
        event_type = self.StudioEventType.create(
            {
                "name": "Self Reference Test",
                "target_type": "individual",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        with self.assertRaises(ValidationError):
            field.write(
                {
                    "visibility_condition": "conditional",
                    "visibility_field_id": field.id,  # Self reference
                }
            )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIVATION WITH NEW FEATURES TESTS
    # ══════════════════════════════════════════════════════════════════════════

    def test_activate_with_link_field(self):
        """Test activation creates correct event field for link type."""
        event_type = self.StudioEventType.create(
            {
                "name": "Link Activation Test",
                "target_type": "individual",
            }
        )

        partner_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Related Person",
                "field_type": "link",
                "link_model_id": partner_model.id,
            }
        )

        event_type.action_activate()

        # Check the created spp.event.field
        event_field = self.env["spp.event.field"].search(
            [
                ("event_type_id", "=", event_type.spp_event_type_id.id),
                ("name", "=", "related_person"),
            ]
        )
        self.assertTrue(event_field)
        self.assertEqual(event_field.field_type, "many2one")
        self.assertEqual(event_field.relation_model, "res.partner")

    def test_activate_with_multi_select_field(self):
        """Test activation creates correct event field for multi_select type."""
        event_type = self.StudioEventType.create(
            {
                "name": "Multi Select Activation Test",
                "target_type": "individual",
            }
        )

        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Services Used",
                "field_type": "multi_select",
                "selection_options": "health|Health\neducation|Education",
            }
        )

        event_type.action_activate()

        # Check the created spp.event.field (stored as selection type)
        event_field = self.env["spp.event.field"].search(
            [
                ("event_type_id", "=", event_type.spp_event_type_id.id),
                ("name", "=", "services_used"),
            ]
        )
        self.assertTrue(event_field)
        self.assertEqual(event_field.field_type, "selection")


class TestEventTypeWizard(TransactionCase):
    """Test cases for event type builder wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Wizard = cls.env["spp.studio.event.type.wizard"]
        cls.StudioEventType = cls.env["spp.studio.event.type"]

    def test_wizard_step_basic_to_fields(self):
        """Test wizard progression from basic to fields step."""
        wizard = self.Wizard.create(
            {
                "name": "Wizard Test",
                "target_type": "individual",
                "description": "Test description",
            }
        )

        self.assertEqual(wizard.step, "basic")

        # Move to fields step
        wizard.action_next()
        self.assertEqual(wizard.step, "fields")

    def test_wizard_requires_fields(self):
        """Test wizard requires at least one field."""
        wizard = self.Wizard.create(
            {
                "name": "No Fields Test",
                "target_type": "individual",
            }
        )

        # Move to fields step
        wizard.action_next()
        self.assertEqual(wizard.step, "fields")

        # Try to move to review without fields - should fail
        with self.assertRaises(ValidationError):
            wizard.action_next()

    def test_wizard_complete_flow(self):
        """Test complete wizard flow."""
        wizard = self.Wizard.create(
            {
                "name": "Complete Wizard Test",
                "target_type": "individual",
                "description": "Full wizard test",
            }
        )

        # Add fields
        self.env["spp.studio.event.type.wizard.field"].create(
            {
                "wizard_id": wizard.id,
                "label": "Test Field 1",
                "field_type": "text",
                "is_required": True,
            }
        )
        self.env["spp.studio.event.type.wizard.field"].create(
            {
                "wizard_id": wizard.id,
                "label": "Test Field 2",
                "field_type": "integer",
                "is_required": False,
            }
        )

        # Progress through wizard
        wizard.action_next()  # basic -> fields
        self.assertEqual(wizard.step, "fields")
        self.assertEqual(wizard.field_count, 2)

        wizard.action_next()  # fields -> review
        self.assertEqual(wizard.step, "review")

        # Create event type
        result = wizard.action_create_event_type()
        event_type = self.StudioEventType.browse(result["res_id"])

        self.assertTrue(event_type.exists())
        self.assertEqual(event_type.name, "Complete Wizard Test")
        self.assertEqual(event_type.data_field_count, 2)
        self.assertEqual(event_type.state, "draft")

    def test_wizard_previous_navigation(self):
        """Test wizard backward navigation."""
        wizard = self.Wizard.create(
            {
                "name": "Navigation Test",
                "target_type": "individual",
            }
        )

        # Add a field
        self.env["spp.studio.event.type.wizard.field"].create(
            {
                "wizard_id": wizard.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        # Go forward
        wizard.action_next()  # basic -> fields
        wizard.action_next()  # fields -> review
        self.assertEqual(wizard.step, "review")

        # Go backward
        wizard.action_previous()  # review -> fields
        self.assertEqual(wizard.step, "fields")

        wizard.action_previous()  # fields -> basic
        self.assertEqual(wizard.step, "basic")

    def test_wizard_field_validation(self):
        """Test wizard validates selection field options."""
        wizard = self.Wizard.create(
            {
                "name": "Validation Test",
                "target_type": "individual",
            }
        )

        # Add selection field without options
        field = self.env["spp.studio.event.type.wizard.field"].create(
            {
                "wizard_id": wizard.id,
                "label": "Status",
                "field_type": "selection",
                # Missing selection_options
            }
        )

        wizard.action_next()  # basic -> fields

        # Try to move to review - should fail validation
        with self.assertRaises(ValidationError):
            wizard.action_next()

        # Add options
        field.write({"selection_options": "good|Good\nbad|Bad"})

        # Now it should work
        wizard.action_next()
        self.assertEqual(wizard.step, "review")


class TestEventDataEntryWizard(TransactionCase):
    """Tests for the event data entry wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.StudioEventType = cls.env["spp.studio.event.type"]
        cls.EntryWizard = cls.env["spp.event.data.entry.wizard"]
        cls.EventData = cls.env["spp.event.data"]

        # Create a registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
            }
        )

        # Create and activate an event type
        cls.event_type = cls.StudioEventType.create(
            {
                "name": "Test Entry Event",
                "target_type": "individual",
            }
        )

        # Add fields
        cls.env["spp.studio.event.field"].create(
            [
                {
                    "event_type_id": cls.event_type.id,
                    "label": "Name",
                    "field_type": "text",
                    "is_required": True,
                    "sequence": 10,
                },
                {
                    "event_type_id": cls.event_type.id,
                    "label": "Age",
                    "field_type": "integer",
                    "is_required": True,
                    "validation_type": "range",
                    "validation_min": 0,
                    "validation_max": 150,
                    "sequence": 20,
                },
                {
                    "event_type_id": cls.event_type.id,
                    "label": "Notes",
                    "field_type": "long_text",
                    "is_required": False,
                    "sequence": 30,
                },
            ]
        )

        # Activate the event type
        cls.event_type.action_activate()

    def test_entry_wizard_creates_event(self):
        """Test that the entry wizard creates an event data record."""
        # Get field definitions
        name_field = self.event_type.data_fields.filtered(lambda f: f.label == "Name")
        age_field = self.event_type.data_fields.filtered(lambda f: f.label == "Age")
        notes_field = self.event_type.data_fields.filtered(lambda f: f.label == "Notes")

        # Create wizard with field values pre-populated
        from odoo import Command

        wizard = self.EntryWizard.create(
            {
                "studio_event_type_id": self.event_type.id,
                "partner_id": self.registrant.id,
                "field_value_ids": [
                    Command.create(
                        {
                            "field_def_id": name_field.id,
                            "value_text": "John Doe",
                            "sequence": 10,
                        }
                    ),
                    Command.create(
                        {
                            "field_def_id": age_field.id,
                            "value_integer": 30,
                            "sequence": 20,
                        }
                    ),
                    Command.create(
                        {
                            "field_def_id": notes_field.id,
                            "value_long_text": "Some notes",
                            "sequence": 30,
                        }
                    ),
                ],
            }
        )

        # Create the event
        result = wizard.action_create_event()

        # Verify the event was created
        self.assertEqual(result["res_model"], "spp.event.data")
        event = self.EventData.browse(result["res_id"])
        self.assertEqual(event.partner_id, self.registrant)
        self.assertEqual(event.event_type_id, self.event_type.spp_event_type_id)
        self.assertEqual(event.data_json["name"], "John Doe")
        self.assertEqual(event.data_json["age"], 30)
        self.assertEqual(event.data_json["notes"], "Some notes")

    def test_entry_wizard_validates_required_fields(self):
        """Test that required field validation works."""
        # Get field definitions - create field values but leave required ones empty
        name_field = self.event_type.data_fields.filtered(lambda f: f.label == "Name")

        from odoo import Command

        wizard = self.EntryWizard.create(
            {
                "studio_event_type_id": self.event_type.id,
                "partner_id": self.registrant.id,
                "field_value_ids": [
                    Command.create(
                        {
                            "field_def_id": name_field.id,
                            "sequence": 10,
                            # value_text intentionally empty - required field
                        }
                    ),
                ],
            }
        )

        # Trying to create should fail because required fields are empty
        with self.assertRaises(ValidationError):
            wizard.action_create_event()

    def test_entry_wizard_validates_range(self):
        """Test that range validation works."""
        # Get field definitions
        name_field = self.event_type.data_fields.filtered(lambda f: f.label == "Name")
        age_field = self.event_type.data_fields.filtered(lambda f: f.label == "Age")

        from odoo import Command

        wizard = self.EntryWizard.create(
            {
                "studio_event_type_id": self.event_type.id,
                "partner_id": self.registrant.id,
                "field_value_ids": [
                    Command.create(
                        {
                            "field_def_id": name_field.id,
                            "value_text": "John Doe",
                            "sequence": 10,
                        }
                    ),
                    Command.create(
                        {
                            "field_def_id": age_field.id,
                            "value_integer": 200,  # Invalid - over max (150)
                            "sequence": 20,
                        }
                    ),
                ],
            }
        )

        # Should fail validation due to age out of range
        with self.assertRaises(ValidationError):
            wizard.action_create_event()

    def test_entry_wizard_inactive_event_type_blocked(self):
        """Test that inactive event types cannot be used for data entry."""
        # Create an inactive event type
        inactive_event_type = self.StudioEventType.create(
            {
                "name": "Inactive Event",
                "target_type": "individual",
            }
        )
        self.env["spp.studio.event.field"].create(
            {
                "event_type_id": inactive_event_type.id,
                "label": "Field",
                "field_type": "text",
            }
        )

        # Activate and then deactivate
        inactive_event_type.action_activate()
        inactive_event_type.action_deactivate()

        # Try to open entry wizard
        with self.assertRaises(UserError):
            inactive_event_type.action_enter_event_data()

    def test_entry_wizard_draft_event_type_blocked(self):
        """Test that draft event types cannot be used for data entry."""
        # Create a draft event type
        draft_event_type = self.StudioEventType.create(
            {
                "name": "Draft Event",
                "target_type": "individual",
            }
        )

        # Try to open entry wizard
        with self.assertRaises(UserError):
            draft_event_type.action_enter_event_data()

    def test_action_enter_event_data_returns_wizard_action(self):
        """Test that action_enter_event_data returns correct action."""
        result = self.event_type.action_enter_event_data()

        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.event.data.entry.wizard")
        self.assertEqual(result["target"], "new")
        self.assertEqual(
            result["context"]["default_studio_event_type_id"],
            self.event_type.id,
        )


class TestStudioEventFieldGroup(TransactionCase):
    """Test cases for spp.studio.event.field.group model and tabbed layouts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.StudioEventType = cls.env["spp.studio.event.type"]
        cls.StudioEventField = cls.env["spp.studio.event.field"]
        cls.StudioEventFieldGroup = cls.env["spp.studio.event.field.group"]

    def test_create_field_group(self):
        """Test creating a field group."""
        event_type = self.StudioEventType.create(
            {
                "name": "Group Test Event",
                "target_type": "individual",
            }
        )

        group = self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "Personal Info",
                "sequence": 10,
            }
        )

        self.assertTrue(group.exists())
        self.assertEqual(group.name, "Personal Info")
        self.assertEqual(group.field_count, 0)

    def test_field_group_with_fields(self):
        """Test assigning fields to a group."""
        event_type = self.StudioEventType.create(
            {
                "name": "Fields in Group Test",
                "target_type": "individual",
            }
        )

        group = self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "Medical Info",
                "sequence": 10,
            }
        )

        # Create fields assigned to the group
        field1 = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Blood Type",
                "field_type": "selection",
                "selection_options": "A|A\nB|B\nAB|AB\nO|O",
                "field_group_id": group.id,
            }
        )
        field2 = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Weight",
                "field_type": "decimal",
                "field_group_id": group.id,
            }
        )

        self.assertEqual(group.field_count, 2)
        self.assertIn(field1, group.field_ids)
        self.assertIn(field2, group.field_ids)

    def test_event_type_field_group_count(self):
        """Test field_group_count computed field on event type."""
        event_type = self.StudioEventType.create(
            {
                "name": "Group Count Test",
                "target_type": "individual",
            }
        )

        self.assertEqual(event_type.field_group_count, 0)

        self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "Group 1",
            }
        )
        self.assertEqual(event_type.field_group_count, 1)

        self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "Group 2",
            }
        )
        self.assertEqual(event_type.field_group_count, 2)

    def test_cannot_modify_group_when_active(self):
        """Test that field groups cannot be modified when event type is active."""
        event_type = self.StudioEventType.create(
            {
                "name": "Active Group Test",
                "target_type": "individual",
            }
        )

        group = self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "Test Group",
            }
        )

        # Add a field to the event type (not in group)
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        # Activate the event type
        event_type.action_activate()

        # Try to modify group - should fail
        with self.assertRaises(UserError):
            group.write({"name": "New Name"})

    def test_cannot_delete_group_when_active(self):
        """Test that field groups cannot be deleted when event type is active."""
        event_type = self.StudioEventType.create(
            {
                "name": "Delete Group Test",
                "target_type": "individual",
            }
        )

        group = self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "Test Group",
            }
        )

        # Add a field
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
            }
        )

        # Activate
        event_type.action_activate()

        # Try to delete group - should fail
        with self.assertRaises(UserError):
            group.unlink()

    def test_wizard_view_with_groups(self):
        """Test that generated wizard view has tabs for field groups."""
        event_type = self.StudioEventType.create(
            {
                "name": "Tabbed Wizard Test",
                "target_type": "individual",
            }
        )

        # Create groups
        personal_group = self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "Personal Info",
                "sequence": 10,
            }
        )
        medical_group = self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "Medical Data",
                "sequence": 20,
            }
        )

        # Create fields in groups
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Full Name",
                "field_type": "text",
                "field_group_id": personal_group.id,
            }
        )
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Date of Birth",
                "field_type": "date",
                "field_group_id": personal_group.id,
            }
        )
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Blood Pressure",
                "field_type": "text",
                "field_group_id": medical_group.id,
            }
        )

        # Activate to generate wizard view
        event_type.action_activate()

        # Check that wizard view was created
        self.assertTrue(event_type.wizard_view_id)

        # Check that view arch contains tabs for each group
        view_arch = event_type.wizard_view_id.arch
        self.assertIn('string="Personal Info"', view_arch)
        self.assertIn('string="Medical Data"', view_arch)

    def test_wizard_view_with_ungrouped_fields(self):
        """Test that ungrouped fields appear in General tab."""
        event_type = self.StudioEventType.create(
            {
                "name": "Ungrouped Fields Test",
                "target_type": "individual",
            }
        )

        # Create a group
        group = self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "Specific Group",
                "sequence": 10,
            }
        )

        # Create a field in the group
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Grouped Field",
                "field_type": "text",
                "field_group_id": group.id,
            }
        )

        # Create a field without a group
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Ungrouped Field",
                "field_type": "text",
                # No field_group_id
            }
        )

        # Activate
        event_type.action_activate()

        # Check view arch has both General and Specific Group tabs
        view_arch = event_type.wizard_view_id.arch
        self.assertIn('string="General"', view_arch)
        self.assertIn('string="Specific Group"', view_arch)

    def test_wizard_view_without_groups(self):
        """Test wizard view layout when no groups defined."""
        event_type = self.StudioEventType.create(
            {
                "name": "No Groups Test",
                "target_type": "individual",
            }
        )

        # Create fields without groups
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Field 1",
                "field_type": "text",
            }
        )
        self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Field 2",
                "field_type": "integer",
            }
        )

        # Activate
        event_type.action_activate()

        # Check view uses single "Event Data" tab (old behavior)
        view_arch = event_type.wizard_view_id.arch
        self.assertIn('string="Event Data"', view_arch)

    def test_group_field_deletion_sets_null(self):
        """Test that deleting a group sets field_group_id to null on fields."""
        event_type = self.StudioEventType.create(
            {
                "name": "Group Deletion Test",
                "target_type": "individual",
            }
        )

        group = self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "To Be Deleted",
            }
        )

        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Test Field",
                "field_type": "text",
                "field_group_id": group.id,
            }
        )

        self.assertEqual(field.field_group_id, group)

        # Delete the group
        group.unlink()

        # Field should still exist but without group
        self.assertTrue(field.exists())
        self.assertFalse(field.field_group_id)

    def test_reactivation_regenerates_wizard_view(self):
        """Test that reactivation regenerates wizard view with updated groups."""
        event_type = self.StudioEventType.create(
            {
                "name": "Reactivation Test",
                "target_type": "individual",
            }
        )

        # Create initial field without group
        field = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Initial Field",
                "field_type": "text",
            }
        )

        # Activate - no groups, should have "Event Data" tab
        event_type.action_activate()
        self.assertTrue(event_type.wizard_view_id)
        initial_view_id = event_type.wizard_view_id.id
        initial_view_arch = event_type.wizard_view_id.arch
        self.assertIn('string="Event Data"', initial_view_arch)
        self.assertNotIn('string="New Group"', initial_view_arch)

        # Deactivate
        event_type.action_deactivate()

        # Set to draft to allow editing
        event_type.action_set_draft()

        # Now add a group and assign field to it
        group = self.StudioEventFieldGroup.create(
            {
                "event_type_id": event_type.id,
                "name": "New Group",
                "sequence": 10,
            }
        )
        field.write({"field_group_id": group.id})

        # Reactivate
        event_type.action_activate()

        # Wizard view should be regenerated with new group
        self.assertTrue(event_type.wizard_view_id)
        # View ID should be different (new view created)
        self.assertNotEqual(event_type.wizard_view_id.id, initial_view_id)
        # New view should have the group tab
        new_view_arch = event_type.wizard_view_id.arch
        self.assertIn('string="New Group"', new_view_arch)

    def test_reactivation_updates_field_order(self):
        """Test that reactivation reflects changed field order."""
        event_type = self.StudioEventType.create(
            {
                "name": "Field Order Test",
                "target_type": "individual",
            }
        )

        # Create fields
        field1 = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "First Field",
                "field_type": "text",
                "sequence": 10,
            }
        )
        field2 = self.StudioEventField.create(
            {
                "event_type_id": event_type.id,
                "label": "Second Field",
                "field_type": "text",
                "sequence": 20,
            }
        )

        # Activate
        event_type.action_activate()
        initial_arch = event_type.wizard_view_id.arch
        # First field should appear before second in arch
        first_pos = initial_arch.find("x_evt_first_field")
        second_pos = initial_arch.find("x_evt_second_field")
        self.assertLess(first_pos, second_pos)

        # Deactivate and set to draft
        event_type.action_deactivate()
        event_type.action_set_draft()

        # Swap sequences
        field1.write({"sequence": 30})  # Move first to after second
        field2.write({"sequence": 10})

        # Reactivate
        event_type.action_activate()

        # Check order is now swapped
        new_arch = event_type.wizard_view_id.arch
        new_first_pos = new_arch.find("x_evt_first_field")
        new_second_pos = new_arch.find("x_evt_second_field")
        self.assertGreater(new_first_pos, new_second_pos)  # Now first appears after second
