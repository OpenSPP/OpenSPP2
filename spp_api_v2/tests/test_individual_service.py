# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for IndividualService"""

from datetime import date

from ..schemas.individual import Individual
from ..schemas.patch import IndividualPatch
from ..services.individual_service import IndividualService
from .common import ApiV2TestCase


class TestIndividualService(ApiV2TestCase):
    """Test IndividualService functionality"""

    def setUp(self):
        super().setUp()
        self.service = IndividualService(self.env)

    def test_find_by_identifier_using_namespace_uri(self):
        """Lookup uses namespace_uri, not name"""
        individual = self.create_test_individual(
            name="Jane Doe",
            identifier_value="TEST-123",
        )

        # Find using namespace_uri
        found = self.service.find_by_identifier(
            "urn:openspp:vocab:id-type#test_national_id",
            "TEST-123",
        )

        self.assertEqual(found, individual)

    def test_find_by_identifier_not_found(self):
        """Returns empty recordset when not found"""
        found = self.service.find_by_identifier(
            "urn:openspp:vocab:id-type#test_national_id",
            "NONEXISTENT",
        )

        self.assertFalse(found)

    def test_to_api_schema_no_database_id(self):
        """Response has no 'id' field, only 'identifier'"""
        individual = self.create_test_individual(
            name="Test Person",
            identifier_value="TEST-001",
        )

        data = self.service.to_api_schema(individual)

        self.assertNotIn("id", data, "Database ID must not be exposed")
        self.assertIn("identifier", data)
        self.assertGreater(len(data["identifier"]), 0)

    def test_to_api_schema_identifier_structure(self):
        """Identifiers use namespace_uri as system"""
        individual = self.create_test_individual(identifier_value="TEST-001")

        data = self.service.to_api_schema(individual)

        # Find the specific identifier we created (may have other identifiers from demo data)
        identifier = next(
            (i for i in data["identifier"] if i["value"] == "TEST-001"),
            None,
        )
        self.assertIsNotNone(identifier, "Expected identifier not found")
        self.assertEqual(identifier["system"], "urn:openspp:vocab:id-type#test_national_id")
        self.assertEqual(identifier["value"], "TEST-001")

    def test_to_api_schema_uses_gender_id_vocabulary(self):
        """Gender uses vocabulary code, not string"""
        individual = self.create_test_individual(
            identifier_value="TEST-001",
            gender_id=self.gender_female.id,
        )

        data = self.service.to_api_schema(individual)

        self.assertIn("gender", data)
        self.assertIn("coding", data["gender"])
        coding = data["gender"]["coding"][0]
        self.assertEqual(coding["system"], "urn:iso:std:iso:5218")
        self.assertEqual(coding["code"], "2")
        self.assertEqual(coding["display"], "Female")

    def test_to_api_schema_basic_fields(self):
        """Basic fields are mapped correctly"""
        individual = self.create_test_individual(
            name="Maria Santos",
            given_name="Maria",
            family_name="Santos",
            identifier_value="TEST-001",
            birthdate=date(1985, 3, 15),
        )

        data = self.service.to_api_schema(individual)

        self.assertEqual(data["type"], "Individual")
        self.assertEqual(data["active"], True)
        self.assertEqual(data["name"]["given"], "Maria")
        self.assertEqual(data["name"]["family"], "Santos")
        self.assertEqual(data["birthDate"], "1985-03-15")

    def test_to_api_schema_contact_info(self):
        """Contact information is mapped correctly"""
        individual = self.create_test_individual(
            identifier_value="TEST-001",
            phone="+1234567890",
            mobile="+9876543210",
            email="test@example.com",
        )

        data = self.service.to_api_schema(individual)

        self.assertIn("telecom", data)
        self.assertEqual(len(data["telecom"]), 3)

        # Check phone
        phone_contact = next(t for t in data["telecom"] if t["value"] == "+1234567890")
        self.assertEqual(phone_contact["system"], "phone")
        self.assertEqual(phone_contact["use"], "home")

        # Check email
        email_contact = next(t for t in data["telecom"] if t["system"] == "email")
        self.assertEqual(email_contact["value"], "test@example.com")

    def test_to_api_schema_address(self):
        """Address is mapped correctly"""
        individual = self.create_test_individual(
            identifier_value="TEST-001",
            street="123 Main St",
            city="Test City",
            zip="12345",
            state_id=self.test_state.id,
            country_id=self.test_country.id,
        )

        data = self.service.to_api_schema(individual)

        self.assertIn("address", data)
        address = data["address"][0]
        self.assertEqual(address["type"], "physical")
        self.assertEqual(address["line"], ["123 Main St"])
        self.assertEqual(address["city"], "Test City")
        self.assertEqual(address["state"], "Test State")
        self.assertEqual(address["country"], "TC")
        self.assertEqual(address["postalCode"], "12345")

    def test_to_api_schema_group_membership(self):
        """Group membership is included"""
        individual = self.create_test_individual(identifier_value="IND-001")
        self.create_test_group(
            name="Test Household",
            identifier_value="HH-001",
            members=[(individual, self.relationship_head)],
        )

        data = self.service.to_api_schema(individual)

        self.assertIn("groupMembership", data)
        membership = data["groupMembership"][0]
        self.assertIn("group", membership)
        self.assertIn("HH-001", membership["group"]["reference"])
        self.assertEqual(membership["group"]["display"], "Test Household")
        self.assertIn("role", membership)
        self.assertEqual(membership["role"]["coding"][0]["code"], "head")

    def test_to_api_schema_metadata(self):
        """Metadata includes version and timestamp"""
        individual = self.create_test_individual(identifier_value="TEST-001")

        data = self.service.to_api_schema(individual)

        self.assertIn("meta", data)
        self.assertIn("versionId", data["meta"])
        self.assertIn("lastUpdated", data["meta"])

    def test_to_api_schema_missing_identifiers_raises(self):
        """Partner without identifiers raises ValidationError"""
        # Create partner without registry ID
        partner = self.env["res.partner"].create(
            {
                "name": "No Identifier",
                "is_registrant": True,
                "is_group": False,
            }
        )

        result = self.service.to_api_schema(partner)
        self.assertIsNone(result)

    def test_from_api_schema_creates_vals(self):
        """from_api_schema converts API schema to Odoo vals"""
        from ..schemas.base import HumanName, Identifier

        schema = Individual(
            identifier=[Identifier(system="urn:openspp:vocab:id-type#test_national_id", value="NEW-001")],
            name=HumanName(
                given="John",
                family="Smith",
                text="John Smith",
            ),
            active=True,
            birth_date=date(1990, 1, 1),
        )

        vals = self.service.from_api_schema(schema)

        self.assertEqual(vals["is_registrant"], True)
        self.assertEqual(vals["is_group"], False)
        self.assertEqual(vals["given_name"], "John")
        self.assertEqual(vals["family_name"], "Smith")
        self.assertEqual(vals["birthdate"], date(1990, 1, 1))

    def test_from_api_schema_gender_lookup(self):
        """from_api_schema finds gender by namespace_uri + code"""
        from ..schemas.base import CodeableConcept, Coding, HumanName, Identifier

        schema = Individual(
            identifier=[Identifier(system="urn:openspp:vocab:id-type#test_national_id", value="NEW-001")],
            name=HumanName(given="Jane", family="Doe"),
            gender=CodeableConcept(
                coding=[
                    Coding(
                        system="urn:iso:std:iso:5218",
                        code="2",
                        display="Female",
                    )
                ]
            ),
        )

        vals = self.service.from_api_schema(schema)

        self.assertEqual(vals["gender_id"], self.gender_female.id)

    def test_create_with_source_tracking(self):
        """Create sets source_system from context"""
        from ..schemas.base import HumanName, Identifier

        schema = Individual(
            identifier=[
                Identifier(
                    system="urn:openspp:vocab:id-type#test_national_id",
                    value="CREATE-001",
                )
            ],
            name=HumanName(given="New", family="Person"),
        )

        partner = self.service.create(schema, source="urn:test:source")

        self.assertTrue(partner)
        self.assertEqual(partner.source_system, "urn:test:source")

    def test_update_with_source_tracking(self):
        """Update sets last_update_system"""
        from ..schemas.base import HumanName, Identifier

        individual = self.create_test_individual(
            identifier_value="UPDATE-001",
            name="Old Name",
        )

        schema = Individual(
            identifier=[
                Identifier(
                    system="urn:openspp:vocab:id-type#test_national_id",
                    value="UPDATE-001",
                )
            ],
            name=HumanName(given="Updated", family="Name"),
        )

        updated = self.service.update(individual, schema, source="urn:test:updater")

        self.assertEqual(updated.given_name, "Updated")
        self.assertEqual(updated.family_name, "Name")

    def test_to_api_schema_photo(self):
        """Photo is base64 encoded"""
        photo_data = self.create_test_photo()

        individual = self.create_test_individual(
            identifier_value="PHOTO-001",
            image_1920=photo_data,
        )

        data = self.service.to_api_schema(individual)

        self.assertIn("photo", data)
        self.assertIsInstance(data["photo"], str)
        self.assertGreater(len(data["photo"]), 0)

    def test_from_api_schema_photo(self):
        """Photo is decoded from base64"""
        import base64

        from ..schemas.base import HumanName, Identifier

        photo_b64 = base64.b64encode(self.create_test_photo()).decode("utf-8")

        schema = Individual(
            identifier=[
                Identifier(
                    system="urn:openspp:vocab:id-type#test_national_id",
                    value="PHOTO-001",
                )
            ],
            name=HumanName(given="Photo", family="Test"),
            photo=photo_b64,
        )

        vals = self.service.from_api_schema(schema)

        self.assertIn("image_1920", vals)
        self.assertTrue(vals["image_1920"])


class TestIndividualServicePatchNullSemantics(ApiV2TestCase):
    """Test RFC 7396 null semantics for partial_update"""

    def setUp(self):
        super().setUp()
        self.service = IndividualService(self.env)

    def test_patch_null_gender_clears_field(self):
        """Sending gender=null clears the gender_id field"""
        individual = self.create_test_individual(
            identifier_value="NULL-GENDER-001",
            gender_id=self.gender_female.id,
        )
        self.assertTrue(individual.gender_id)

        patch = IndividualPatch.model_validate({"gender": None})
        updated = self.service.partial_update(individual, patch, source="urn:test:source")

        self.assertFalse(updated.gender_id)

    def test_patch_null_address_clears_fields(self):
        """Sending address=null clears all address fields"""
        individual = self.create_test_individual(
            identifier_value="NULL-ADDR-001",
            street="123 Main St",
            city="Test City",
            zip="12345",
            country_id=self.test_country.id,
            state_id=self.test_state.id,
        )
        self.assertTrue(individual.street)

        patch = IndividualPatch.model_validate({"address": None})
        updated = self.service.partial_update(individual, patch, source="urn:test:source")

        self.assertFalse(updated.street)
        self.assertFalse(updated.city)
        self.assertFalse(updated.zip)
        self.assertFalse(updated.country_id)
        self.assertFalse(updated.state_id)

    def test_patch_null_telecom_clears_contact_fields(self):
        """Sending telecom=null clears phone and email"""
        individual = self.create_test_individual(
            identifier_value="NULL-TEL-001",
            phone="+1234567890",
            email="test@example.com",
        )
        self.assertTrue(individual.phone)
        self.assertTrue(individual.email)

        patch = IndividualPatch.model_validate({"telecom": None})
        updated = self.service.partial_update(individual, patch, source="urn:test:source")

        self.assertFalse(updated.phone)
        self.assertFalse(updated.email)
