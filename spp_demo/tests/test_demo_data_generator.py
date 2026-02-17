# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import datetime
import logging

from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestDemoDataGenerator(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set context to avoid job queue delay
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                test_queue_job_no_delay=True,
            )
        )

        # Create test country with faker locale
        cls.test_country = cls.env["res.country"].create(
            {
                "name": "Test Country Generator",
                "code": "T1",
                "faker_locale": "en_US",
                "is_faker_locale_available": True,
                "lat_min": -10.0,
                "lat_max": 10.0,
                "lon_min": -10.0,
                "lon_max": 10.0,
            }
        )

        # Get group type from vocabulary
        cls.group_type = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-type", "household")

        # Create test ID type
        cls.id_type = cls.env["spp.id.type"].create(
            {
                "name": "Test ID Type",
                "id_validation": r"^[A-Z]{2}\d{6}$",
            }
        )

        # Create test bank
        cls.test_bank = cls.env["res.bank"].create(
            {
                "name": "Test Bank",
            }
        )

        # Gender is now handled via spp.vocabulary.code with ISO 5218 namespace
        # The generator's get_gender_id method handles this automatically

    def test_01_default_methods(self):
        """Test all default value methods"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Generator Defaults",
                "locale_origin": self.test_country.id,
            }
        )

        # Test default methods return integers
        self.assertIsInstance(generator._default_number_of_groups(), int)
        self.assertIsInstance(generator._default_members_range_from(), int)
        self.assertIsInstance(generator._default_members_range_to(), int)
        self.assertIsInstance(generator._default_batch_size(), int)
        self.assertIsInstance(generator._default_queue_job_minimum_size(), int)
        self.assertIsNotNone(generator._default_locale_origin())

    def test_02_compute_use_job_queue(self):
        """Test job queue computation based on number of groups"""
        # Small batch - should not use job queue
        small_generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Small Generator",
                "number_of_groups": 10,
                "locale_origin": self.test_country.id,
                "queue_job_minimum_size": 500,
            }
        )
        self.assertFalse(small_generator.use_job_queue)

        # Large batch - should use job queue
        large_generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Large Generator",
                "number_of_groups": 600,
                "locale_origin": self.test_country.id,
                "queue_job_minimum_size": 500,
            }
        )
        self.assertTrue(large_generator.use_job_queue)

    def test_03_generate_demo_data_validation_error(self):
        """Test validation when members range is invalid"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Invalid Range Generator",
                "number_of_groups": 1,
                "members_range_from": 10,
                "members_range_to": 5,
                "locale_origin": self.test_country.id,
            }
        )

        with self.assertRaises(ValidationError):
            generator.generate_demo_data()

    def test_04_generate_groups(self):
        """Test group generation"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Group Generator",
                "number_of_groups": 1,
                "locale_origin": self.test_country.id,
                "group_type_id": self.group_type.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        group = generator.generate_groups(fake)

        self.assertTrue(group.is_group)
        self.assertTrue(group.is_registrant)
        self.assertEqual(group.demo_data_group_generator_id, generator)
        self.assertEqual(group.group_type_id.id, self.group_type.id)

    def test_05_generate_individuals(self):
        """Test individual generation"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Individual Generator",
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        individual = generator.generate_individuals(fake)

        self.assertFalse(individual.is_group)
        self.assertTrue(individual.is_registrant)
        self.assertEqual(individual.demo_data_individual_generator_id, generator)
        self.assertIsNotNone(individual.gender_id)
        self.assertIsNotNone(individual.birthdate)

    def test_06_get_group_vals(self):
        """Test group values generation"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Group Vals",
                "locale_origin": self.test_country.id,
                "group_type_id": self.group_type.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        group_vals = generator.get_group_vals(fake)

        self.assertTrue(group_vals["is_group"])
        self.assertTrue(group_vals["is_registrant"])
        self.assertEqual(group_vals["demo_data_group_generator_id"], generator.id)
        self.assertIsNotNone(group_vals["name"])
        self.assertIsNotNone(group_vals["address"])

    def test_07_get_individual_vals(self):
        """Test individual values generation"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Individual Vals",
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        individual_vals = generator.get_individual_vals(fake)

        self.assertFalse(individual_vals["is_group"])
        self.assertTrue(individual_vals["is_registrant"])
        self.assertEqual(individual_vals["demo_data_individual_generator_id"], generator.id)
        self.assertIsNotNone(individual_vals["name"])
        self.assertIsNotNone(individual_vals["gender_id"])
        self.assertIsNotNone(individual_vals["birthdate"])

    def test_08_get_group_membership_vals(self):
        """Test group membership values generation"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Membership Vals",
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        group = generator.generate_groups(fake)
        individual = generator.generate_individuals(fake)

        membership_vals = generator.get_group_membership_vals(fake, group, individual)

        self.assertEqual(membership_vals["group"], group.id)
        self.assertEqual(membership_vals["individual"], individual.id)
        self.assertIsNotNone(membership_vals["start_date"])

    def test_09_get_gender_id(self):
        """Test gender ID retrieval and creation"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Gender",
                "locale_origin": self.test_country.id,
            }
        )

        # Test existing gender
        male_id = generator.get_gender_id("Male")
        male = self.env["spp.vocabulary.code"].browse(male_id)
        self.assertTrue(male)
        self.assertEqual(male.namespace_uri, "urn:iso:std:iso:5218")

        # Test new gender creation (falls back to vocab code lookup or creation)
        new_gender_id = generator.get_gender_id("Other")
        self.assertIsNotNone(new_gender_id)
        new_gender = self.env["spp.vocabulary.code"].browse(new_gender_id)
        self.assertTrue(new_gender)

    def test_10_get_random_date(self):
        """Test random date generation"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Random Date",
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        date_from = datetime.date.today() - relativedelta(years=10)
        date_to = datetime.date.today()

        random_date = generator.get_random_date(fake, date_from, date_to)

        self.assertGreaterEqual(random_date, date_from)
        self.assertLessEqual(random_date, date_to)

    def test_11_get_id_type(self):
        """Test ID type retrieval"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test ID Type",
                "locale_origin": self.test_country.id,
            }
        )

        # Create ID type configuration
        self.env["spp.demo.data.id.types"].create(
            {
                "id_type_id": self.id_type.id,
                "target_type": "individual",
                "demo_data_generator_id": generator.id,
            }
        )

        id_type_id, id_validation = generator.get_id_type("individual")
        self.assertIsNotNone(id_type_id)
        self.assertIsNotNone(id_validation)

    def test_12_generate_id_from_regex(self):
        """Test ID generation from regex patterns"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Regex ID",
                "locale_origin": self.test_country.id,
            }
        )

        # Test simple pattern
        pattern1 = r"^[A-Z]{2}\d{6}$"
        generated_id1 = generator.generate_id_from_regex(pattern1)
        self.assertIsNotNone(generated_id1)
        self.assertEqual(len(generated_id1), 8)

        # Test digit pattern
        pattern2 = r"^\d{10}$"
        generated_id2 = generator.generate_id_from_regex(pattern2)
        self.assertIsNotNone(generated_id2)
        self.assertEqual(len(generated_id2), 10)
        self.assertTrue(generated_id2.isdigit())

        # Test None pattern
        generated_id3 = generator.generate_id_from_regex(None)
        self.assertIsNone(generated_id3)

    def test_13_create_ids(self):
        """Test ID creation for registrants"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Create IDs",
                "locale_origin": self.test_country.id,
                "percentage_with_ids": 100,
            }
        )

        # Create ID type configuration
        self.env["spp.demo.data.id.types"].create(
            {
                "id_type_id": self.id_type.id,
                "target_type": "individual",
                "demo_data_generator_id": generator.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        individual = generator.generate_individuals(fake)

        # Check that ID was created
        self.assertTrue(individual.reg_ids)
        self.assertEqual(len(individual.reg_ids), 1)

    def test_14_get_bank_type(self):
        """Test bank type retrieval"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Bank Type",
                "locale_origin": self.test_country.id,
            }
        )

        # Create bank type configuration
        self.env["spp.demo.data.bank.types"].create(
            {
                "bank_id": self.test_bank.id,
                "target_type": "individual",
                "demo_data_generator_id": generator.id,
            }
        )

        bank_type_id = generator.get_bank_type("individual")
        self.assertIsNotNone(bank_type_id)

    def test_15_create_bank_accounts(self):
        """Test bank account creation for registrants"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Create Bank Accounts",
                "locale_origin": self.test_country.id,
                "percentage_with_bank_account": 100,
            }
        )

        # Create bank type configuration
        self.env["spp.demo.data.bank.types"].create(
            {
                "bank_id": self.test_bank.id,
                "target_type": "individual",
                "demo_data_generator_id": generator.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        individual = generator.generate_individuals(fake)

        # Check that bank account was created
        self.assertTrue(individual.bank_ids)

    def test_16_generate_phone_number(self):
        """Test phone number generation"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Phone Number",
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        phone_number = generator.generate_phone_number(fake)

        self.assertIsNotNone(phone_number)

    def test_17_create_phone_numbers(self):
        """Test phone number creation for registrants"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Create Phone Numbers",
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        individual = generator.generate_individuals(fake)

        # Check that phone numbers were created
        self.assertTrue(individual.phone_number_ids)
        self.assertGreaterEqual(len(individual.phone_number_ids), 1)
        self.assertLessEqual(len(individual.phone_number_ids), 5)

    def test_18_create_gps_coordinates(self):
        """Test GPS coordinates creation for registrants"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test GPS Coordinates",
                "locale_origin": self.test_country.id,
                "percentage_with_gps": 100,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        individual = generator.generate_individuals(fake)

        # Check that GPS coordinates were set
        self.assertIsNotNone(individual.gps_coordinates)
        self.assertIn(",", individual.gps_coordinates)

    def test_19_head_member_getter(self):
        """Test head member identification"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Head Member",
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        group = generator.generate_groups(fake)
        individual = generator.generate_individuals(fake)

        # Create head membership
        head_membership_type = self.env["spp.vocabulary.code"].get_code(
            "urn:openspp:vocab:group-membership-type", "head"
        )
        membership = self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": individual.id,
                "membership_type_ids": [Command.link(head_membership_type.id)],
            }
        )

        head_membership = generator.head_member_getter(group)
        self.assertEqual(head_membership, membership)

    def test_20_generate_demo_data_small_batch(self):
        """Test complete demo data generation with small batch"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Small Batch Test",
                "number_of_groups": 2,
                "members_range_from": 2,
                "members_range_to": 3,
                "locale_origin": self.test_country.id,
                "percentage_with_ids": 0,
                "percentage_with_bank_account": 0,
                "percentage_with_gps": 0,
            }
        )

        generator.generate_demo_data()

        # Check that data generation completed
        self.assertEqual(generator.state, "completed")
        self.assertFalse(generator.is_locked)

        # Check that groups were created
        self.assertEqual(len(generator.generated_group_ids), 2)

        # Check that individuals were created
        self.assertGreaterEqual(len(generator.generated_individual_ids), 4)

    def test_21_refresh_page(self):
        """Test refresh page action"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Test Refresh",
                "locale_origin": self.test_country.id,
            }
        )

        result = generator.refresh_page()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "reload")

    def test_22_generate_demo_data_with_head_member(self):
        """Test that groups always get a head member assigned"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Head Member Test",
                "number_of_groups": 1,
                "members_range_from": 3,
                "members_range_to": 3,
                "locale_origin": self.test_country.id,
                "percentage_with_ids": 0,
                "percentage_with_bank_account": 0,
                "percentage_with_gps": 0,
            }
        )

        generator.generate_demo_data()

        # Check that the group has a head member
        group = generator.generated_group_ids[0]
        head_membership = generator.head_member_getter(group)
        self.assertTrue(head_membership)

    def test_23_spp_demo_data_id_types_model(self):
        """Test SPPDemoDataIDTypes model"""
        id_type_record = self.env["spp.demo.data.id.types"].create(
            {
                "id_type_id": self.id_type.id,
                "target_type": "individual",
            }
        )

        self.assertEqual(id_type_record.id_type_id, self.id_type)
        self.assertEqual(id_type_record.target_type, "individual")

    def test_24_spp_demo_data_bank_types_model(self):
        """Test SPPDemoDataBankTypes model"""
        bank_type_record = self.env["spp.demo.data.bank.types"].create(
            {
                "bank_id": self.test_bank.id,
                "target_type": "group",
            }
        )

        self.assertEqual(bank_type_record.bank_id, self.test_bank)
        self.assertEqual(bank_type_record.target_type, "group")

    def test_25_edge_case_no_group_types(self):
        """Test group generation when no specific group type is set"""
        # Create a generator without specific group type
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "No Group Type Test",
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        group_vals = generator.get_group_vals(fake)

        # Should have some group type assigned from available types
        if self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-type")]
        ):
            self.assertIn("group_type_id", group_vals)

    def test_26_edge_case_zero_percentage_ids(self):
        """Test with 0% percentage for IDs"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Zero ID Percentage",
                "locale_origin": self.test_country.id,
                "percentage_with_ids": 0,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        individual = generator.generate_individuals(fake)

        # Should not have IDs created
        self.assertFalse(individual.reg_ids)

    def test_27_edge_case_regex_generation_complex(self):
        """Test complex regex patterns"""
        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Complex Regex Test",
                "locale_origin": self.test_country.id,
            }
        )

        # Test character class with quantifier
        pattern1 = r"[A-Z]{3}-\d{4}"
        result1 = generator.generate_id_from_regex(pattern1)
        self.assertIsNotNone(result1)

        # Test word character pattern
        pattern2 = r"\w{5}"
        result2 = generator.generate_id_from_regex(pattern2)
        self.assertIsNotNone(result2)
        self.assertEqual(len(result2), 5)

    def test_28_group_gets_area_id(self):
        """Test that groups are assigned an area_id when areas exist."""
        # Create area hierarchy
        area_type_region = self.env["spp.area.type"].create({"name": "Test Region"})
        area_type_barangay = self.env["spp.area.type"].create(
            {"name": "Test Barangay", "parent_id": area_type_region.id}
        )

        region = self.env["spp.area"].create(
            {
                "draft_name": "Test Region",
                "code": "TEST-REG",
                "area_type_id": area_type_region.id,
            }
        )
        self.env["spp.area"].create(
            {
                "draft_name": "Test Barangay",
                "code": "TEST-BRG",
                "area_type_id": area_type_barangay.id,
                "parent_id": region.id,
            }
        )

        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Area Assignment Test",
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        group_vals = generator.get_group_vals(fake)

        # Group should have area_id assigned
        self.assertIn("area_id", group_vals)
        self.assertTrue(group_vals["area_id"])

    def test_29_group_prefers_leaf_areas(self):
        """Test that groups are assigned to leaf-level areas (not regions)."""
        # Create a hierarchy: region -> province -> barangay
        area_type_region = self.env["spp.area.type"].create({"name": "Test Region L"})
        area_type_province = self.env["spp.area.type"].create(
            {"name": "Test Province L", "parent_id": area_type_region.id}
        )
        area_type_leaf = self.env["spp.area.type"].create({"name": "Test Leaf L", "parent_id": area_type_province.id})

        region = self.env["spp.area"].create(
            {
                "draft_name": "Region Parent",
                "code": "TEST-RP",
                "area_type_id": area_type_region.id,
            }
        )
        province = self.env["spp.area"].create(
            {
                "draft_name": "Province Mid",
                "code": "TEST-PM",
                "area_type_id": area_type_province.id,
                "parent_id": region.id,
            }
        )
        leaf1 = self.env["spp.area"].create(
            {
                "draft_name": "Leaf One",
                "code": "TEST-L1",
                "area_type_id": area_type_leaf.id,
                "parent_id": province.id,
            }
        )
        leaf2 = self.env["spp.area"].create(
            {
                "draft_name": "Leaf Two",
                "code": "TEST-L2",
                "area_type_id": area_type_leaf.id,
                "parent_id": province.id,
            }
        )

        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Leaf Area Test",
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")

        # Generate multiple groups and verify they all get leaf areas
        leaf_ids = {leaf1.id, leaf2.id}
        for _ in range(10):
            group_vals = generator.get_group_vals(fake)
            self.assertIn(
                group_vals["area_id"],
                leaf_ids,
                "Group should be assigned to a leaf-level area, not a parent area",
            )

    def test_30_members_inherit_group_area(self):
        """Test that individual members inherit their group's area_id."""
        area_type = self.env["spp.area.type"].create({"name": "Test Area MIA"})
        self.env["spp.area"].create(
            {
                "draft_name": "Member Inherit Area",
                "code": "TEST-MIA",
                "area_type_id": area_type.id,
            }
        )

        generator = self.env["spp.demo.data.generator"].create(
            {
                "name": "Member Inherit Test",
                "number_of_groups": 1,
                "members_range_from": 3,
                "members_range_to": 3,
                "locale_origin": self.test_country.id,
            }
        )

        from faker import Faker

        fake = Faker("en_US")
        generator._generate_demo_data(fake)

        # Find the created group
        group = self.env["res.partner"].search([("demo_data_group_generator_id", "=", generator.id)], limit=1)
        self.assertTrue(group.area_id, "Group should have an area_id")

        # All members should share the group's area
        members = self.env["res.partner"].search([("demo_data_individual_generator_id", "=", generator.id)])
        self.assertTrue(len(members) >= 3)
        for member in members:
            self.assertEqual(
                member.area_id,
                group.area_id,
                f"Member '{member.name}' should inherit group's area_id",
            )
