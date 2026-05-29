# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Common test utilities for DCI Server Social module."""

import logging
from datetime import date, timedelta

from odoo.tests import TransactionCase

_logger = logging.getLogger(__name__)


class DCISocialServerCommon(TransactionCase):
    """Base test class with shared utilities for DCI Social Server tests."""

    @classmethod
    def setUpClass(cls):
        """Set up test data shared across all test methods."""
        super().setUpClass()

        # Models
        cls.Partner = cls.env["res.partner"]
        cls.RegID = cls.env["spp.registry.id"]
        cls.GroupMembership = cls.env["spp.group.membership"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]
        cls.SenderRegistry = cls.env["spp.dci.sender.registry"]

        # Create test ID type for identifiers
        cls.test_id_type = cls.env["spp.id.type"].create(
            {
                "name": "National ID",
                "namespace_uri": "urn:gov:example:id:national-id",
            }
        )

        # Create test vocabulary codes if they don't exist
        cls._create_test_vocabularies()

        # Create test individuals
        cls.individual_1 = cls._create_test_individual(
            {
                "family_name": "Doe",
                "given_name": "John",
                "birthdate": date.today() - timedelta(days=365 * 30),  # 30 years old
                "gender": "male",
                "phone": "+1234567890",
                "email": "john.doe@example.com",
                "street": "123 Main St",
                "city": "Test City",
            },
            identifier_value="NAT-001",
        )

        cls.individual_2 = cls._create_test_individual(
            {
                "family_name": "Doe",
                "given_name": "Jane",
                "birthdate": date.today() - timedelta(days=365 * 28),  # 28 years old
                "gender": "female",
                "phone": "+1234567891",
                "email": "jane.doe@example.com",
                "street": "123 Main St",
                "city": "Test City",
            },
            identifier_value="NAT-002",
        )

        cls.individual_3 = cls._create_test_individual(
            {
                "family_name": "Smith",
                "given_name": "Bob",
                "birthdate": date.today() - timedelta(days=365 * 35),  # 35 years old
                "gender": "male",
                "phone": "+1234567892",
                "email": "bob.smith@example.com",
                "street": "456 Oak Ave",
                "city": "Another City",
            },
            identifier_value="NAT-003",
        )

        # Create test group (household)
        cls.group_1 = cls._create_test_group(
            {
                "name": "Doe Household",
                "street": "123 Main St",
                "city": "Test City",
            },
            identifier_value="HH-001",
            members=[cls.individual_1, cls.individual_2],
        )

        # Create test sender for consent checks
        cls.test_sender = cls._create_test_sender()

    @classmethod
    def _create_test_vocabularies(cls):
        """Get or create test vocabulary codes.

        For system vocabularies like Gender (ISO 5218), the codes should already exist
        from module data. For non-system vocabularies, we create them with is_local=True.
        """
        Vocabulary = cls.env["spp.vocabulary"]

        # Gender vocabulary (ISO 5218) - codes should already exist from spp_vocabulary
        gender_namespace = "urn:iso:std:iso:5218"
        gender_vocab = Vocabulary.search([("namespace_uri", "=", gender_namespace)], limit=1)
        if not gender_vocab:
            # Create vocabulary if it doesn't exist (shouldn't happen in production)
            gender_vocab = Vocabulary.create(
                {
                    "name": "Gender (ISO 5218)",
                    "namespace_uri": gender_namespace,
                }
            )
        # Search for existing codes - they should be loaded from module data
        for code, display in [("male", "Male"), ("female", "Female"), ("other", "Other")]:
            existing = cls.VocabularyCode.search(
                [("vocabulary_id", "=", gender_vocab.id), ("code", "=", code)],
                limit=1,
            )
            if not existing:
                # Create as local extension if not found
                cls.VocabularyCode.create(
                    {
                        "vocabulary_id": gender_vocab.id,
                        "code": code,
                        "display": display,
                        "is_local": True,  # Required for system vocabularies
                    }
                )

        # Group membership type vocabulary
        membership_namespace = "urn:openspp:vocab:group-membership-type"
        membership_vocab = Vocabulary.search([("namespace_uri", "=", membership_namespace)], limit=1)
        if not membership_vocab:
            membership_vocab = Vocabulary.create(
                {
                    "name": "Group Membership Type",
                    "namespace_uri": membership_namespace,
                }
            )
        for code, display in [("head", "Head"), ("member", "Member"), ("spouse", "Spouse")]:
            existing = cls.VocabularyCode.search(
                [("vocabulary_id", "=", membership_vocab.id), ("code", "=", code)],
                limit=1,
            )
            if not existing:
                cls.VocabularyCode.create(
                    {
                        "vocabulary_id": membership_vocab.id,
                        "code": code,
                        "display": display,
                        "is_local": True,  # Mark as local extension
                    }
                )

    @classmethod
    def _create_test_individual(cls, values, identifier_value=None):
        """Create a test individual registrant.

        Args:
            values: Dict of field values
            identifier_value: Optional identifier value

        Returns:
            res.partner: Created individual record
        """
        # Map string gender to vocabulary code
        gender = values.pop("gender", None)
        if gender:
            gender_code = cls.VocabularyCode.search(
                [("namespace_uri", "=", "urn:iso:std:iso:5218"), ("code", "=", gender)], limit=1
            )
            if gender_code:
                values["gender_id"] = gender_code.id

        # Compute name from given_name and family_name if not provided
        given_name = values.get("given_name", "")
        family_name = values.get("family_name", "")
        if "name" not in values and (given_name or family_name):
            values["name"] = f"{given_name} {family_name}".strip()

        # Ensure required fields
        defaults = {
            "is_registrant": True,
            "is_group": False,
        }
        defaults.update(values)

        # Create individual
        individual = cls.Partner.create(defaults)

        # Create identifier if provided
        if identifier_value:
            cls.RegID.create(
                {
                    "partner_id": individual.id,
                    "id_type_id": cls.test_id_type.id,
                    "value": identifier_value,
                }
            )

        return individual

    @classmethod
    def _create_test_group(cls, values, identifier_value=None, members=None):
        """Create a test group registrant.

        Args:
            values: Dict of field values
            identifier_value: Optional identifier value
            members: List of partner records to add as members

        Returns:
            res.partner: Created group record
        """
        # Ensure required fields
        defaults = {
            "is_registrant": True,
            "is_group": True,
        }
        defaults.update(values)

        # Create group
        group = cls.Partner.create(defaults)

        # Create identifier if provided
        if identifier_value:
            cls.RegID.create(
                {
                    "partner_id": group.id,
                    "id_type_id": cls.test_id_type.id,
                    "value": identifier_value,
                }
            )

        # Add members if provided
        if members:
            for i, member in enumerate(members):
                membership_type = cls.VocabularyCode.search(
                    [
                        ("namespace_uri", "=", "urn:openspp:vocab:group-membership-type"),
                        ("code", "=", "head" if i == 0 else "member"),
                    ],
                    limit=1,
                )
                cls.GroupMembership.create(
                    {
                        "group": group.id,
                        "individual": member.id,
                        "membership_type_ids": [(6, 0, [membership_type.id])] if membership_type else [],
                    }
                )

        return group

    @classmethod
    def _create_test_sender(cls, sender_id=None):
        """Create a test DCI sender registry entry.

        Args:
            sender_id: Sender ID (defaults to "crvs.test.gov")

        Returns:
            spp.dci.sender.registry: Created sender record
        """
        # Import here to avoid circular dependencies
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        # Create test keypair
        test_private_key = Ed25519PrivateKey.generate()
        test_public_key_pem = (
            test_private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )

        # Create test partner for sender registry (required by spp.api.client)
        test_partner = cls.env["res.partner"].create(
            {
                "name": f"Test Sender Org {sender_id or 'crvs.test.gov'}",
                "is_company": True,
            }
        )

        # Lookup organization type (required by spp.api.client)
        org_type_government = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not org_type_government:
            org_type_government = cls.env["spp.consent.org.type"].search(
                [("code", "=", "government")], limit=1
            )

        return cls.SenderRegistry.create(
            {
                "name": f"Test Sender {sender_id or 'crvs.test.gov'}",
                "sender_id": sender_id or "crvs.test.gov",
                "public_key": test_public_key_pem,
                "algorithm": "ed25519",
                "active": True,
                "partner_id": test_partner.id,
                "organization_type_id": org_type_government.id,
            }
        )
