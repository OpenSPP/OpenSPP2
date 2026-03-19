# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Manage Farm Activity Change Request detail and strategy."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from .common import FarmerCRTestMixin


@tagged("post_install", "-at_install")
class TestCRManageFarmActivityAdd(TransactionCase, FarmerCRTestMixin):
    """Tests for add operation of spp.cr.detail.manage_farm_activity."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.CR = cls.env["spp.change.request"]
        cls.Activity = cls.env["spp.farm.activity"]

        cls.test_farm = cls._create_test_farm(name="Test Farm for Activities")
        cls.test_season = cls._create_test_season(name="Test Season 2024")
        cls.species_vocabs = cls._create_species_vocabularies()

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Manage Farm Activity {test_id}",
            code=f"manage_farm_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
        )

    def test_detail_creation(self):
        """Test creating manage farm activity CR detail record."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        self.assertTrue(detail, "Detail record should be created")
        self.assertEqual(detail._name, "spp.cr.detail.manage_farm_activity")
        self.assertEqual(detail.change_request_id, cr)
        self.assertEqual(detail.registrant_id, self.test_farm)
        self.assertEqual(detail.operation, "add")

    def test_species_namespace_computation_crop(self):
        """Test species namespace is computed correctly for crop activity."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.activity_type = "crop"
        detail._compute_species_namespace()

        self.assertEqual(detail.species_namespace, "urn:fao:icc:1.1")

    def test_species_namespace_computation_livestock(self):
        """Test species namespace is computed correctly for livestock activity."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.activity_type = "livestock"
        detail._compute_species_namespace()

        self.assertEqual(detail.species_namespace, "urn:fao:livestock:2020")

    def test_species_namespace_computation_aquaculture(self):
        """Test species namespace is computed correctly for aquaculture activity."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.activity_type = "aquaculture"
        detail._compute_species_namespace()

        self.assertEqual(detail.species_namespace, "urn:fao:asfis:2024")

    def test_onchange_activity_type_clears_species(self):
        """Test that changing activity type clears species selection."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.operation = "add"
        detail.activity_type = "crop"
        detail.species_id = self.species_vocabs["crop"]["rice"]

        detail.activity_type = "livestock"
        detail._onchange_activity_type()

        self.assertFalse(detail.species_id)

    def test_default_season(self):
        """Test that default_get sets most recent active season."""
        DetailModel = self.env["spp.cr.detail.manage_farm_activity"]
        defaults = DetailModel.default_get(["season_id"])

        if defaults.get("season_id"):
            self.assertEqual(defaults["season_id"], self.test_season.id)

    def test_apply_add_creates_crop_activity(self):
        """Test applying add CR creates crop activity."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "activity_type": "crop",
                "species_id": self.species_vocabs["crop"]["rice"].id,
                "quantity": 1000.0,
                "quantity_unit": "kg",
                "area_planted": 2.5,
                "expected_yield": 800.0,
                "season_id": self.test_season.id,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)

        activities = self.Activity.search([("crop_farm_id", "=", self.test_farm.id)])
        self.assertEqual(len(activities), 1)

        activity = activities[0]
        self.assertEqual(activity.activity_type, "crop")
        self.assertEqual(activity.species_id, self.species_vocabs["crop"]["rice"])
        self.assertEqual(activity.quantity, 1000.0)

    def test_apply_add_creates_livestock_activity(self):
        """Test applying add CR creates livestock activity."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "activity_type": "livestock",
                "species_id": self.species_vocabs["livestock"]["cattle"].id,
                "quantity": 15.0,
                "quantity_unit": "head",
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        activities = self.Activity.search([("livestock_farm_id", "=", self.test_farm.id)])
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0].activity_type, "livestock")

    def test_apply_add_requires_group(self):
        """Test that add requires registrant to be a group (farm)."""
        individual = self.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=individual,
        )

        detail = cr.get_detail()
        detail.write({"operation": "add", "activity_type": "crop", "quantity": 100.0})

        cr.approval_state = "approved"
        with self.assertRaises(UserError) as ctx:
            cr.action_apply()

        self.assertIn("must be a group", str(ctx.exception).lower())

    def test_apply_add_requires_activity_type(self):
        """Test that add requires activity_type to be set."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write({"operation": "add", "quantity": 100.0})

        cr.approval_state = "approved"
        with self.assertRaises(UserError) as ctx:
            cr.action_apply()

        self.assertIn("activity type", str(ctx.exception).lower())

    def test_preview_add(self):
        """Test preview for add operation."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "add",
                "activity_type": "crop",
                "species_id": self.species_vocabs["crop"]["maize"].id,
                "season_id": self.test_season.id,
            }
        )

        strategy = self.env["spp.cr.apply.manage_farm_activity"]
        preview = strategy.preview(cr)

        self.assertEqual(preview["_action"], "add_farm_activity")
        self.assertIn("Species", preview)
        self.assertEqual(preview["Farm"], self.test_farm.name)


@tagged("post_install", "-at_install")
class TestCRManageFarmActivityUpdate(TransactionCase, FarmerCRTestMixin):
    """Tests for update operation of spp.cr.detail.manage_farm_activity."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.CR = cls.env["spp.change.request"]
        cls.Activity = cls.env["spp.farm.activity"]

        cls.test_farm = cls._create_test_farm(name="Test Farm for Update")
        cls.species_vocabs = cls._create_species_vocabularies()

        cls.existing_activity = cls._create_test_activity(
            farm=cls.test_farm,
            activity_type="crop",
            species_id=cls.species_vocabs["crop"]["rice"].id,
            quantity=100.0,
            quantity_unit="kg",
            area_planted=1.0,
            expected_yield=80.0,
        )

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Manage Farm Activity {test_id}",
            code=f"manage_farm_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
        )

    def test_onchange_activity_prefill(self):
        """Test that onchange pre-fills current values from activity."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.operation = "update"
        detail.activity_id = self.existing_activity
        detail._onchange_activity_id()

        self.assertEqual(detail.activity_type, "crop")
        self.assertEqual(detail.species_id, self.species_vocabs["crop"]["rice"])
        self.assertEqual(detail.quantity, 100.0)

    def test_apply_update_activity(self):
        """Test applying update CR updates existing activity."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "activity_id": self.existing_activity.id,
                "species_id": self.species_vocabs["crop"]["maize"].id,
                "quantity": 200.0,
                "area_planted": 2.0,
                "expected_yield": 150.0,
                "actual_yield": 140.0,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)
        self.assertEqual(self.existing_activity.species_id, self.species_vocabs["crop"]["maize"])
        self.assertEqual(self.existing_activity.quantity, 200.0)

    def test_apply_update_requires_activity_id(self):
        """Test that update requires activity_id to be set."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write({"operation": "update", "quantity": 150.0})

        cr.approval_state = "approved"
        with self.assertRaises(UserError) as ctx:
            cr.action_apply()

        self.assertIn("activity", str(ctx.exception).lower())

    def test_preview_update(self):
        """Test preview for update operation."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "update",
                "activity_id": self.existing_activity.id,
                "quantity": 250.0,
                "expected_yield": 200.0,
            }
        )

        strategy = self.env["spp.cr.apply.manage_farm_activity"]
        preview = strategy.preview(cr)

        self.assertEqual(preview["_action"], "update_farm_activity")
        self.assertIn("Quantity", preview)
        self.assertEqual(preview["Quantity"]["old"], 100.0)
        self.assertEqual(preview["Quantity"]["new"], 250.0)


@tagged("post_install", "-at_install")
class TestCRManageFarmActivityRemove(TransactionCase, FarmerCRTestMixin):
    """Tests for remove operation of spp.cr.detail.manage_farm_activity."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.CR = cls.env["spp.change.request"]
        cls.Activity = cls.env["spp.farm.activity"]

        cls.test_farm = cls._create_test_farm(name="Test Farm for Remove")
        cls.species_vocabs = cls._create_species_vocabularies()

        cls.existing_activity = cls._create_test_activity(
            farm=cls.test_farm,
            activity_type="livestock",
            species_id=cls.species_vocabs["livestock"]["cattle"].id,
            quantity=20.0,
        )

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Manage Farm Activity {test_id}",
            code=f"manage_farm_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
        )

    def test_apply_remove_activity(self):
        """Test applying remove CR deletes existing activity."""
        activity_id = self.existing_activity.id

        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "remove",
                "activity_id": self.existing_activity.id,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)
        self.assertFalse(self.Activity.search([("id", "=", activity_id)]))

    def test_apply_remove_requires_activity_id(self):
        """Test that remove requires activity_id to be set."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write({"operation": "remove"})

        cr.approval_state = "approved"
        with self.assertRaises(UserError) as ctx:
            cr.action_apply()

        self.assertIn("activity", str(ctx.exception).lower())

    def test_preview_remove(self):
        """Test preview for remove operation."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write(
            {
                "operation": "remove",
                "activity_id": self.existing_activity.id,
            }
        )

        strategy = self.env["spp.cr.apply.manage_farm_activity"]
        preview = strategy.preview(cr)

        self.assertEqual(preview["_action"], "remove_farm_activity")
        self.assertIn("Activity", preview)


@tagged("post_install", "-at_install")
class TestCRManageFarmActivityOperationLocking(TransactionCase, FarmerCRTestMixin):
    """Tests for operation locking behavior."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.test_farm = cls._create_test_farm()
        cls.species_vocabs = cls._create_species_vocabularies()

        test_id = cls._get_unique_test_id()
        cls.cr_type = cls._create_cr_type(
            name=f"Manage Farm Activity {test_id}",
            code=f"manage_farm_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
        )

    def test_operation_locked_on_next_documents(self):
        """Test operation is locked when proceeding to documents stage."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write({"operation": "add", "activity_type": "crop"})

        self.assertFalse(detail.is_operation_locked)
        detail.action_next_documents()
        self.assertTrue(detail.is_operation_locked)

    def test_onchange_operation_clears_fields(self):
        """Test that changing operation clears all fields."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.operation = "add"
        detail.activity_type = "crop"
        detail.species_id = self.species_vocabs["crop"]["rice"]
        detail.quantity = 100.0

        detail.operation = "update"
        detail._onchange_operation()

        self.assertFalse(detail.activity_type)
        self.assertFalse(detail.species_id)
        self.assertEqual(detail.quantity, 0)

    def test_operation_locked_on_skip_to_review(self):
        """Test operation is locked when skipping to review stage."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write({"operation": "add", "activity_type": "crop"})

        self.assertFalse(detail.is_operation_locked)
        # action_skip_to_review may raise due to missing proposed changes,
        # but the lock should still be written before the super() call
        try:
            detail.action_skip_to_review()
        except (UserError, Exception):
            pass
        self.assertTrue(detail.is_operation_locked)

    def test_operation_display_computed(self):
        """Test operation_display is computed from operation selection."""
        cr = self._create_change_request(
            cr_type=self.cr_type,
            registrant=self.test_farm,
        )

        detail = cr.get_detail()
        detail.write({"operation": "add"})
        detail._compute_operation_display()
        self.assertEqual(detail.operation_display, "Add Activity")

        detail.write({"operation": "update"})
        detail._compute_operation_display()
        self.assertEqual(detail.operation_display, "Edit Activity")

        detail.write({"operation": "remove"})
        detail._compute_operation_display()
        self.assertEqual(detail.operation_display, "Remove Activity")


@tagged("post_install", "-at_install")
class TestCRManageFarmActivityOperationConstraints(TransactionCase, FarmerCRTestMixin):
    """Tests for _check_operation_allowed constraint."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.test_farm = cls._create_test_farm(name="Constraint Test Farm")

    def test_check_operation_update_disallowed(self):
        """Test that update operation raises ValidationError when disallowed."""
        test_id = self._get_unique_test_id()
        cr_type = self._create_cr_type(
            name=f"No Update Activity {test_id}",
            code=f"no_update_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
            allow_activity_update=False,
        )

        cr = self._create_change_request(
            cr_type=cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()

        with self.assertRaises(ValidationError):
            detail.write({"operation": "update"})

    def test_check_operation_remove_disallowed(self):
        """Test that remove operation raises ValidationError when disallowed."""
        test_id = self._get_unique_test_id()
        cr_type = self._create_cr_type(
            name=f"No Remove Activity {test_id}",
            code=f"no_remove_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
            allow_activity_remove=False,
        )

        cr = self._create_change_request(
            cr_type=cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()

        with self.assertRaises(ValidationError):
            detail.write({"operation": "remove"})

    def test_check_operation_add_always_allowed(self):
        """Test that add operation is always allowed regardless of config."""
        test_id = self._get_unique_test_id()
        cr_type = self._create_cr_type(
            name=f"Add Only Activity {test_id}",
            code=f"add_only_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
            allow_activity_add=False,
            allow_activity_update=False,
            allow_activity_remove=False,
        )

        cr = self._create_change_request(
            cr_type=cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()

        # Add operation has no constraint check, should not raise
        detail.write({"operation": "add"})
        self.assertEqual(detail.operation, "add")

    def test_check_operation_update_allowed_when_enabled(self):
        """Test that update operation succeeds when allowed."""
        test_id = self._get_unique_test_id()
        cr_type = self._create_cr_type(
            name=f"All Allowed Activity {test_id}",
            code=f"all_allowed_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
            allow_activity_update=True,
            allow_activity_remove=True,
        )

        cr = self._create_change_request(
            cr_type=cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write({"operation": "update"})
        self.assertEqual(detail.operation, "update")

    def test_check_operation_remove_allowed_when_enabled(self):
        """Test that remove operation succeeds when allowed."""
        test_id = self._get_unique_test_id()
        cr_type = self._create_cr_type(
            name=f"Remove Allowed Activity {test_id}",
            code=f"remove_allowed_activity_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
            allow_activity_remove=True,
        )

        cr = self._create_change_request(
            cr_type=cr_type,
            registrant=self.test_farm,
        )
        detail = cr.get_detail()
        detail.write({"operation": "remove"})
        self.assertEqual(detail.operation, "remove")


@tagged("post_install", "-at_install")
class TestCRManageFarmActivityRelatedFields(TransactionCase, FarmerCRTestMixin):
    """Tests for related fields from CR type configuration."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.test_farm = cls._create_test_farm(name="Related Fields Farm")

    def test_related_allow_activity_add(self):
        """Test allow_activity_add is correctly related from CR type."""
        test_id = self._get_unique_test_id()
        cr_type = self._create_cr_type(
            name=f"Related Add {test_id}",
            code=f"related_add_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
            allow_activity_add=True,
        )

        cr = self._create_change_request(cr_type=cr_type, registrant=self.test_farm)
        detail = cr.get_detail()
        self.assertTrue(detail.allow_activity_add)

        # Change at CR type level
        cr_type.write({"allow_activity_add": False})
        self.assertFalse(detail.allow_activity_add)

    def test_related_allow_activity_update(self):
        """Test allow_activity_update is correctly related from CR type."""
        test_id = self._get_unique_test_id()
        cr_type = self._create_cr_type(
            name=f"Related Update {test_id}",
            code=f"related_update_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
            allow_activity_update=False,
        )

        cr = self._create_change_request(cr_type=cr_type, registrant=self.test_farm)
        detail = cr.get_detail()
        self.assertFalse(detail.allow_activity_update)

        cr_type.write({"allow_activity_update": True})
        self.assertTrue(detail.allow_activity_update)

    def test_related_allow_activity_remove(self):
        """Test allow_activity_remove is correctly related from CR type."""
        test_id = self._get_unique_test_id()
        cr_type = self._create_cr_type(
            name=f"Related Remove {test_id}",
            code=f"related_remove_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
            allow_activity_remove=False,
        )

        cr = self._create_change_request(cr_type=cr_type, registrant=self.test_farm)
        detail = cr.get_detail()
        self.assertFalse(detail.allow_activity_remove)

        cr_type.write({"allow_activity_remove": True})
        self.assertTrue(detail.allow_activity_remove)

    def test_species_namespace_empty_for_no_type(self):
        """Test species_namespace is empty when activity_type is not set."""
        test_id = self._get_unique_test_id()
        cr_type = self._create_cr_type(
            name=f"Namespace Empty {test_id}",
            code=f"namespace_empty_{test_id}",
            detail_model="spp.cr.detail.manage_farm_activity",
            apply_model="spp.cr.apply.manage_farm_activity",
        )

        cr = self._create_change_request(cr_type=cr_type, registrant=self.test_farm)
        detail = cr.get_detail()
        # activity_type is not set
        detail._compute_species_namespace()
        self.assertEqual(detail.species_namespace, "")
