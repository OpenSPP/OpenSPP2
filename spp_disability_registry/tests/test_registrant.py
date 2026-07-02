from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRegistrantDisability(TransactionCase):
    """Test cases for registrant disability extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test user with appropriate groups
        cls.user_assessor = cls.env["res.users"].create(
            {
                "name": "Test Assessor",
                "login": "test_registrant_assessor",
                "email": "registrant_assessor@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("spp_disability_registry.group_disability_assessor").id),
                ],
            }
        )

        cls.user_validator = cls.env["res.users"].create(
            {
                "name": "Test Validator",
                "login": "test_registrant_validator",
                "email": "registrant_validator@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("spp_disability_registry.group_disability_validator").id),
                ],
            }
        )

        # Create test registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Registrant for Disability",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=40),
            }
        )

        # Create a household group
        cls.household = cls.env["res.partner"].create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create household members
        cls.member1 = cls.env["res.partner"].create(
            {
                "name": "Household Member 1",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=45),
            }
        )

        cls.member2 = cls.env["res.partner"].create(
            {
                "name": "Household Member 2",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=42),
            }
        )

        # Get head membership type
        cls.head_type = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-membership-type"), ("code", "=", "head")],
            limit=1,
        )

        # Add members to household
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household.id,
                "individual": cls.member1.id,
                "membership_type_ids": [Command.link(cls.head_type.id)] if cls.head_type else [],
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household.id,
                "individual": cls.member2.id,
            }
        )

        # Get severity vocabulary codes
        cls.severity_mild = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:02"),
                ("code", "=", "mild"),
            ],
            limit=1,
        )
        cls.severity_severe = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:02"),
                ("code", "=", "severe"),
            ],
            limit=1,
        )

        # Get device type
        cls.device_wheelchair = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:04"),
                ("code", "=", "wheelchair"),
            ],
            limit=1,
        )

    # === Current Disability Assessment Tests ===

    def test_no_disability_without_assessment(self):
        """Test registrant has no disability without assessment."""
        self.assertFalse(self.registrant.has_disability)
        self.assertFalse(self.registrant.current_disability_assessment_id)

    def test_no_disability_with_draft_assessment(self):
        """Test registrant has no disability with only draft assessment."""
        self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.registrant.id,
                "assessment_date": date.today(),
                "wg_seeing": "a_lot",
                "severity_level_id": self.severity_mild.id if self.severity_mild else False,
            }
        )
        # Recompute
        self.registrant.invalidate_recordset()
        self.assertFalse(self.registrant.has_disability)

    def test_disability_with_approved_assessment(self):
        """Test registrant has disability after approved assessment."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.registrant.id,
                "assessment_date": date.today(),
                "wg_seeing": "a_lot",
                "severity_level_id": self.severity_severe.id if self.severity_severe else False,
                "review_category": "mip",
            }
        )
        # Manually set approval state (normally done via workflow)
        assessment.write({"approval_state": "approved"})

        # Recompute
        self.registrant.invalidate_recordset()
        self.assertTrue(self.registrant.has_disability)
        self.assertEqual(self.registrant.current_disability_assessment_id, assessment)
        if self.severity_severe:
            self.assertEqual(self.registrant.disability_severity_id, self.severity_severe)
        self.assertEqual(self.registrant.disability_review_category, "mip")

    def test_latest_approved_assessment_used(self):
        """Test that the latest approved assessment is used."""
        # Create older assessment
        old_assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.registrant.id,
                "assessment_date": date.today() - relativedelta(months=6),
                "wg_seeing": "a_lot",
                "severity_level_id": self.severity_mild.id if self.severity_mild else False,
            }
        )
        old_assessment.write({"approval_state": "approved"})

        # Create newer assessment
        new_assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.registrant.id,
                "assessment_date": date.today(),
                "wg_seeing": "cannot",
                "severity_level_id": self.severity_severe.id if self.severity_severe else False,
            }
        )
        new_assessment.write({"approval_state": "approved"})

        # Recompute
        self.registrant.invalidate_recordset()
        self.assertEqual(self.registrant.current_disability_assessment_id, new_assessment)
        if self.severity_severe:
            self.assertEqual(self.registrant.disability_severity_id, self.severity_severe)

    # === Assessment Count Tests ===

    def test_assessment_count(self):
        """Test assessment count computation."""
        self.assertEqual(self.registrant.disability_assessment_count, 0)

        # Create assessments
        self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.registrant.id,
                "assessment_date": date.today() - relativedelta(months=3),
            }
        )
        self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.registrant.id,
                "assessment_date": date.today(),
            }
        )

        self.registrant.invalidate_recordset()
        self.assertEqual(self.registrant.disability_assessment_count, 2)

    # === Assistive Device Tests ===

    def test_assistive_device_count(self):
        """Test assistive device count computation."""
        self.assertEqual(self.registrant.assistive_device_count, 0)

        # Create device
        if self.device_wheelchair:
            self.env["spp.assistive.device"].create(
                {
                    "registrant_id": self.registrant.id,
                    "device_type_id": self.device_wheelchair.id,
                    "status": "provided",
                }
            )

            self.registrant.invalidate_recordset()
            self.assertEqual(self.registrant.assistive_device_count, 1)

    def test_unmet_device_need_detection(self):
        """Test unmet device need is detected."""
        if not self.device_wheelchair:
            self.skipTest("No device type vocabulary available")

        self.assertFalse(self.registrant.has_unmet_device_need)

        # Create device with needed status
        self.env["spp.assistive.device"].create(
            {
                "registrant_id": self.registrant.id,
                "device_type_id": self.device_wheelchair.id,
                "status": "needed",
            }
        )

        self.registrant.invalidate_recordset()
        self.assertTrue(self.registrant.has_unmet_device_need)

    def test_no_unmet_need_when_provided(self):
        """Test no unmet need when device is provided."""
        if not self.device_wheelchair:
            self.skipTest("No device type vocabulary available")

        # Create device with provided status
        self.env["spp.assistive.device"].create(
            {
                "registrant_id": self.registrant.id,
                "device_type_id": self.device_wheelchair.id,
                "status": "provided",
            }
        )

        self.registrant.invalidate_recordset()
        self.assertFalse(self.registrant.has_unmet_device_need)

    # === Action Tests ===

    def test_action_view_assessments(self):
        """Test action to view assessments returns correct action."""
        action = self.registrant.action_view_disability_assessments()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.disability.assessment")
        self.assertIn(("registrant_id", "=", self.registrant.id), action["domain"])

    def test_action_view_devices(self):
        """Test action to view devices returns correct action."""
        action = self.registrant.action_view_assistive_devices()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.assistive.device")
        self.assertIn(("registrant_id", "=", self.registrant.id), action["domain"])

    def test_action_create_assessment(self):
        """Test action to create assessment returns correct action."""
        action = self.registrant.action_create_disability_assessment()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.disability.assessment")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["context"]["default_registrant_id"], self.registrant.id)

    # === Household Disability Tests ===

    def test_household_member_disability_independent(self):
        """Test that each member's disability status is independent."""
        # Create approved assessment for member1
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.member1.id,
                "assessment_date": date.today(),
                "wg_walking": "cannot",
                "severity_level_id": self.severity_severe.id if self.severity_severe else False,
            }
        )
        assessment.write({"approval_state": "approved"})

        # Recompute
        self.member1.invalidate_recordset()
        self.member2.invalidate_recordset()

        # Member1 should have disability
        self.assertTrue(self.member1.has_disability)

        # Member2 should not have disability
        self.assertFalse(self.member2.has_disability)


@tagged("post_install", "-at_install")
class TestAssistiveDevice(TransactionCase):
    """Test cases for assistive device functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Registrant for Devices",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=50),
            }
        )

        # Get device types
        cls.device_wheelchair = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:04"),
                ("code", "=", "wheelchair"),
            ],
            limit=1,
        )

        cls.device_hearing_aid = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:04"),
                ("code", "=", "hearing_aid"),
            ],
            limit=1,
        )

    def test_device_creation(self):
        """Test creating an assistive device record."""
        if not self.device_wheelchair:
            self.skipTest("No device type vocabulary available")

        device = self.env["spp.assistive.device"].create(
            {
                "registrant_id": self.registrant.id,
                "device_type_id": self.device_wheelchair.id,
                "status": "needed",
            }
        )
        self.assertTrue(device.id)
        self.assertEqual(device.status, "needed")

    def test_device_status_transitions(self):
        """Test device status can transition through workflow."""
        if not self.device_wheelchair:
            self.skipTest("No device type vocabulary available")

        device = self.env["spp.assistive.device"].create(
            {
                "registrant_id": self.registrant.id,
                "device_type_id": self.device_wheelchair.id,
                "status": "needed",
            }
        )

        # Transition to requested
        device.write({"status": "requested"})
        self.assertEqual(device.status, "requested")

        # Transition to provided
        device.write({"status": "provided", "provision_date": date.today()})
        self.assertEqual(device.status, "provided")
        self.assertEqual(device.provision_date, date.today())

    def test_device_name_computed(self):
        """Test device name is computed from type and registrant."""
        if not self.device_wheelchair:
            self.skipTest("No device type vocabulary available")

        device = self.env["spp.assistive.device"].create(
            {
                "registrant_id": self.registrant.id,
                "device_type_id": self.device_wheelchair.id,
                "status": "needed",
            }
        )
        self.assertIn(self.device_wheelchair.display, device.name)
        self.assertIn(self.registrant.name, device.name)

    def test_multiple_devices_per_registrant(self):
        """Test registrant can have multiple devices."""
        if not self.device_wheelchair or not self.device_hearing_aid:
            self.skipTest("Required device types not available")

        self.env["spp.assistive.device"].create(
            {
                "registrant_id": self.registrant.id,
                "device_type_id": self.device_wheelchair.id,
                "status": "provided",
            }
        )

        self.env["spp.assistive.device"].create(
            {
                "registrant_id": self.registrant.id,
                "device_type_id": self.device_hearing_aid.id,
                "status": "needed",
            }
        )

        self.registrant.invalidate_recordset()
        self.assertEqual(self.registrant.assistive_device_count, 2)
        self.assertTrue(self.registrant.has_unmet_device_need)

    def test_device_onchange_status_clears_provision_date(self):
        """Test that provision_date is cleared when status changes from provided."""
        if not self.device_wheelchair:
            self.skipTest("No device type vocabulary available")

        device = self.env["spp.assistive.device"].create(
            {
                "registrant_id": self.registrant.id,
                "device_type_id": self.device_wheelchair.id,
                "status": "provided",
                "provision_date": date.today(),
            }
        )
        self.assertEqual(device.provision_date, date.today())

        # Change status to needed triggers onchange
        device.status = "needed"
        device._onchange_status()
        self.assertFalse(device.provision_date)

    def test_device_action_view_registrant(self):
        """Test action to view registrant from device."""
        if not self.device_wheelchair:
            self.skipTest("No device type vocabulary available")

        device = self.env["spp.assistive.device"].create(
            {
                "registrant_id": self.registrant.id,
                "device_type_id": self.device_wheelchair.id,
                "status": "needed",
            }
        )
        action = device.action_view_registrant()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["res_id"], self.registrant.id)
