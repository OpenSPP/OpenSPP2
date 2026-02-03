# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Common test utilities and base classes for API V2 tests"""

import base64
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone

if sys.version_info >= (3, 11):  # noqa: UP036
    from datetime import UTC
else:
    UTC = timezone.utc  # noqa: UP017

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from ..middleware.rate_limit import get_rate_limiter


class ApiV2TestCase(TransactionCase):
    """Base class for API V2 unit tests (non-HTTP)"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Clear rate limiter state to ensure test isolation
        get_rate_limiter().clear()

        # Set up JWT secret for tests
        cls.env["ir.config_parameter"].sudo().set_param(
            "spp_api_v2.jwt_secret",
            "test-secret-key-for-testing-only-do-not-use-in-production",
        )

        # Create test country and state (use search_or_create to avoid duplicates)
        cls.test_country = cls.env["res.country"].search([("code", "=", "TC")], limit=1)
        if not cls.test_country:
            cls.test_country = cls.env["res.country"].create(
                {
                    "name": "Test Country",
                    "code": "TC",
                }
            )
        cls.test_state = cls.env["res.country.state"].search(
            [("code", "=", "TS"), ("country_id", "=", cls.test_country.id)], limit=1
        )
        if not cls.test_state:
            cls.test_state = cls.env["res.country.state"].create(
                {
                    "name": "Test State",
                    "code": "TS",
                    "country_id": cls.test_country.id,
                }
            )

        # ID types are vocabulary codes from the ID Type vocabulary (urn:openspp:vocab:id-type)
        # The registry ID uses spp.vocabulary.code for id_type_id, not spp.id.type
        # NOTE: namespace_uri on vocabulary codes is a related field from the vocabulary
        id_type_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not id_type_vocab:
            id_type_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Type",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )

        # Get or create test ID type codes within the ID Type vocabulary
        cls.id_type_national = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", id_type_vocab.id), ("code", "=", "test_national_id")],
            limit=1,
        )
        if not cls.id_type_national:
            cls.id_type_national = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "test_national_id",
                    "display": "Test National ID",
                    "is_local": True,
                    "target_type": "individual",
                }
            )
        cls.id_type_passport = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", id_type_vocab.id), ("code", "=", "test_passport")],
            limit=1,
        )
        if not cls.id_type_passport:
            cls.id_type_passport = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "test_passport",
                    "display": "Test Passport",
                    "is_local": True,
                    "target_type": "individual",
                }
            )
        cls.id_type_household = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", id_type_vocab.id), ("code", "=", "test_household_id")],
            limit=1,
        )
        if not cls.id_type_household:
            cls.id_type_household = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "test_household_id",
                    "display": "Test Household ID",
                    "is_local": True,
                    "target_type": "group",
                }
            )

        # Computed URIs for use in test assertions and JSON payloads
        # These match the uri computed field: {vocabulary.namespace_uri}#{code}
        cls.NATIONAL_ID_URI = "urn:openspp:vocab:id-type#test_national_id"
        cls.HOUSEHOLD_ID_URI = "urn:openspp:vocab:id-type#test_household_id"
        cls.PASSPORT_ID_URI = "urn:openspp:vocab:id-type#test_passport"
        # URL-safe versions (# encoded as %23) for use in HTTP URL paths
        cls.NATIONAL_ID_URI_URL = "urn:openspp:vocab:id-type%23test_national_id"
        cls.HOUSEHOLD_ID_URI_URL = "urn:openspp:vocab:id-type%23test_household_id"

        # Create test gender vocabulary codes (use search_or_create to avoid duplicates)
        cls.gender_vocabulary = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:iso:std:iso:5218")], limit=1
        )
        if not cls.gender_vocabulary:
            cls.gender_vocabulary = cls.env["spp.vocabulary"].create(
                {
                    "name": "Gender",
                    "namespace_uri": "urn:iso:std:iso:5218",
                }
            )
        cls.gender_male = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.gender_vocabulary.id),
                ("code", "=", "1"),
            ],
            limit=1,
        )
        if not cls.gender_male:
            cls.gender_male = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.gender_vocabulary.id,
                    "code": "1",
                    "display": "Male",
                    "namespace_uri": "urn:iso:std:iso:5218",
                }
            )
        cls.gender_female = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.gender_vocabulary.id),
                ("code", "=", "2"),
            ],
            limit=1,
        )
        if not cls.gender_female:
            cls.gender_female = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.gender_vocabulary.id,
                    "code": "2",
                    "display": "Female",
                    "namespace_uri": "urn:iso:std:iso:5218",
                }
            )

        # Create test relationship vocabulary (use search_or_create to avoid duplicates)
        cls.relationship_vocabulary = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:group-membership-type")], limit=1
        )
        if not cls.relationship_vocabulary:
            cls.relationship_vocabulary = cls.env["spp.vocabulary"].create(
                {
                    "name": "Group Membership Type",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                }
            )
        cls.relationship_head = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.relationship_vocabulary.id),
                ("code", "=", "head"),
            ],
            limit=1,
        )
        if not cls.relationship_head:
            cls.relationship_head = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.relationship_vocabulary.id,
                    "code": "head",
                    "display": "Head of Household",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                }
            )

        # Create test-specific relationship vocabulary (for API tests using urn:test:relationship)
        cls.test_relationship_vocabulary = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:test:relationship")], limit=1
        )
        if not cls.test_relationship_vocabulary:
            cls.test_relationship_vocabulary = cls.env["spp.vocabulary"].create(
                {
                    "name": "Test Relationship Types",
                    "namespace_uri": "urn:test:relationship",
                }
            )
        cls.test_relationship_head = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.test_relationship_vocabulary.id),
                ("code", "=", "head"),
            ],
            limit=1,
        )
        if not cls.test_relationship_head:
            cls.test_relationship_head = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.test_relationship_vocabulary.id,
                    "code": "head",
                    "display": "Head of Household",
                }
            )
        cls.test_relationship_spouse = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.test_relationship_vocabulary.id),
                ("code", "=", "spouse"),
            ],
            limit=1,
        )
        if not cls.test_relationship_spouse:
            cls.test_relationship_spouse = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.test_relationship_vocabulary.id,
                    "code": "spouse",
                    "display": "Spouse",
                }
            )

    @classmethod
    def create_test_individual(
        cls,
        name="Test Person",
        given_name="Test",
        family_name="Person",
        identifier_value="TEST-001",
        gender_id=None,
        birthdate=None,
        **kwargs,
    ):
        """
        Create an individual with identifier for testing.

        Args:
            name: Full name
            given_name: Given/first name
            family_name: Family/last name
            identifier_value: Identifier value (uses national ID type)
            gender_id: Gender code ID (optional)
            birthdate: Birth date (optional)
            **kwargs: Additional partner fields

        Returns:
            res.partner record
        """
        vals = {
            "name": name,
            "given_name": given_name,
            "family_name": family_name,
            "is_registrant": True,
            "is_group": False,
        }

        # If image_1920 provided as raw bytes, encode to base64 string for Binary field
        if "image_1920" in vals or "image_1920" in kwargs:
            img = kwargs.pop("image_1920", vals.pop("image_1920", None))
            if isinstance(img, bytes | bytearray):
                kwargs["image_1920"] = base64.b64encode(img).decode("ascii")
            else:
                kwargs["image_1920"] = img

        if gender_id:
            vals["gender_id"] = gender_id
        if birthdate:
            vals["birthdate"] = birthdate

        vals.update(kwargs)

        partner = cls.env["res.partner"].create(vals)

        # Create registry ID
        cls.env["spp.registry.id"].create(
            {
                "partner_id": partner.id,
                "id_type_id": cls.id_type_national.id,
                "value": identifier_value,
                "status": "valid",
            }
        )

        return partner

    @classmethod
    def create_test_group(
        cls,
        name="Test Household",
        identifier_value="HH-001",
        members=None,
        id_type=None,
        **kwargs,
    ):
        """
        Create a group/household with identifier.

        Args:
            name: Group name
            identifier_value: Identifier value
            members: List of (partner, role) tuples
            id_type: ID type to use (defaults to household ID type)
            **kwargs: Additional partner fields

        Returns:
            res.partner record
        """
        vals = {
            "name": name,
            "is_registrant": True,
            "is_group": True,
        }
        vals.update(kwargs)

        group = cls.env["res.partner"].create(vals)

        # Create registry ID (use household ID type by default)
        if id_type is None:
            id_type = cls.id_type_household
        cls.env["spp.registry.id"].create(
            {
                "partner_id": group.id,
                "id_type_id": id_type.id,
                "value": identifier_value,
                "status": "valid",
            }
        )

        # Add members if specified
        if members:
            for member_partner, role_code in members:
                # Create group membership
                membership_vals = {
                    "group": group.id,
                    "individual": member_partner.id,
                }
                # Add membership type if role specified
                if role_code:
                    # Use vocabulary code directly as membership type
                    membership_vals["membership_type_ids"] = [Command.set([role_code.id])]

                cls.env["spp.group.membership"].create(membership_vals)

        return group

    def create_api_client(
        self,
        name="Test Client",
        scopes=None,
        require_consent=True,
        legal_basis="consent",
        organization_type="government",
        **kwargs,
    ):
        """
        Create API client with scopes.

        Args:
            name: Client name
            scopes: List of {"resource": "individual", "action": "read"} dicts
            require_consent: Whether consent is required
            legal_basis: Legal basis for data processing
            organization_type: Organization type code (e.g., "ngo", "government")
            **kwargs: Additional client fields (can include organization_type_id directly)

        Returns:
            spp.api.client record
        """
        partner = self.env["res.partner"].create({"name": f"{name} Organization"})

        # Lookup organization type by code if not provided as organization_type_id
        if "organization_type_id" not in kwargs:
            org_type = self.env.ref(
                f"spp_consent.org_type_{organization_type}",
                raise_if_not_found=False,
            )
            if not org_type:
                org_type = self.env["spp.consent.org.type"].search([("code", "=", organization_type)], limit=1)
            if not org_type:
                raise ValueError(
                    f"Organization type '{organization_type}' not found. "
                    f"Available types: government, ngo, ingo, un, private, research, other"
                )
            kwargs["organization_type_id"] = org_type.id

        vals = {
            "name": name,
            "partner_id": partner.id,
            "is_require_consent": require_consent,
            "legal_basis": legal_basis,
        }
        vals.update(kwargs)

        client = self.env["spp.api.client"].create(vals)

        # Create scopes
        if scopes:
            for scope_def in scopes:
                self.env["spp.api.client.scope"].create(
                    {
                        "client_id": client.id,
                        "resource": scope_def.get("resource", "individual"),
                        "action": scope_def.get("action", "read"),
                    }
                )

        return client

    def create_consent(
        self,
        registrant,
        grantee_partner,
        resource_type="individual",
        field_access="all",
        purpose="service_delivery",
        expiry_days=365,
        **kwargs,
    ):
        """
        Create consent for testing.

        Args:
            registrant: res.partner (individual or group)
            grantee_partner: res.partner (organization that gets access)
            resource_type: Type of resource (individual, group, all)
            field_access: Field access level (all, basic, custom)
            purpose: Purpose of data access
            expiry_days: Days until expiry (default 365)
            **kwargs: Additional consent fields

        Returns:
            spp.consent record
        """
        today = date.today()
        expiry = today + timedelta(days=expiry_days)

        vals = {
            "name": f"Test Consent - {registrant.name}",
            # Use correct DPV-aligned fields:
            # - recipient_ids (Many2many) instead of grantee_id
            # - status="given" instead of api_status="active"
            "recipient_ids": [Command.set([grantee_partner.id])],
            "recipient_mode": "specific",
            "status": "given",
            "effective_date": today,
            "expiry": expiry,
        }

        # Set registrant based on type
        if registrant.is_group:
            vals["group_id"] = registrant.id
        else:
            vals["signatory_id"] = registrant.id

        vals.update(kwargs)

        consent = self.env["spp.consent"].create(vals)

        # Create consent scope
        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": resource_type,
                "field_access": field_access,
                "purpose": purpose,
            }
        )

        return consent

    def generate_jwt_token(self, api_client):
        """
        Generate JWT token for API client (for testing API endpoints).

        Args:
            api_client: spp.api.client record

        Returns:
            JWT token string
        """

        import jwt

        secret = self.env["ir.config_parameter"].sudo().get_param("spp_api_v2.jwt_secret")

        now = datetime.now(tz=UTC)
        payload = {
            "iss": "openspp-api-v2",
            "sub": api_client.client_id,
            "aud": "openspp",
            "exp": now + timedelta(hours=1),
            "iat": now,
            "client_id": api_client.client_id,
            "partner_id": api_client.partner_id.id,
            "scopes": [f"{s.resource}:{s.action}" for s in api_client.scope_ids],
        }

        return jwt.encode(payload, secret, algorithm="HS256")

    def create_test_photo(self):
        """
        Create a small test photo (1x1 transparent PNG).

        Returns:
            Raw PNG bytes (caller can base64-encode if needed)
        """

        # Valid 1x1 transparent PNG base64 (already properly padded)
        b64_str = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        try:
            return base64.b64decode(b64_str, validate=True)
        except Exception:
            # Fallback: create minimal PNG manually
            return bytes(
                [
                    0x89,
                    0x50,
                    0x4E,
                    0x47,
                    0x0D,
                    0x0A,
                    0x1A,
                    0x0A,  # PNG signature
                    0x00,
                    0x00,
                    0x00,
                    0x0D,  # IHDR chunk length
                    0x49,
                    0x48,
                    0x44,
                    0x52,  # IHDR
                    0x00,
                    0x00,
                    0x00,
                    0x01,  # width = 1
                    0x00,
                    0x00,
                    0x00,
                    0x01,  # height = 1
                    0x08,
                    0x06,
                    0x00,
                    0x00,
                    0x00,  # bit depth, color type, compression, filter, interlace
                    0x1F,
                    0x15,
                    0xC4,
                    0x89,  # CRC
                    0x00,
                    0x00,
                    0x00,
                    0x00,  # IDAT chunk length
                    0x49,
                    0x44,
                    0x41,
                    0x54,  # IDAT
                    0x08,
                    0xD7,
                    0x63,
                    0xF8,  # CRC
                    0x00,
                    0x00,
                    0x00,
                    0x00,  # IEND chunk length
                    0x49,
                    0x45,
                    0x4E,
                    0x44,  # IEND
                    0xAE,
                    0x42,
                    0x60,
                    0x82,  # CRC
                ]
            )

    def create_test_program(
        self,
        name="Test Program",
        target_type="individual",
        state="active",
        **kwargs,
    ):
        """
        Create a program for testing.

        Args:
            name: Program name
            target_type: Target type (individual/group)
            state: Program state (draft/active/ended)
            **kwargs: Additional program fields

        Returns:
            spp.program record
        """
        vals = {
            "name": name,
            "target_type": target_type,
            "state": state,
        }
        vals.update(kwargs)

        program = self.env["spp.program"].create(vals)

        # Create program identifier if spp.program.id exists
        if "spp.program.id" in self.env:
            self.env["spp.program.id"].create(
                {
                    "program_id": program.id,
                    "namespace_uri": "urn:openspp:program",
                    "value": name.lower().replace(" ", "-"),
                }
            )

        return program

    def create_test_membership(
        self,
        partner,
        program,
        state="enrolled",
        enrollment_date=None,
        **kwargs,
    ):
        """
        Create a program membership for testing.

        Args:
            partner: res.partner record (beneficiary)
            program: spp.program record
            state: Enrollment state
            enrollment_date: Date of enrollment
            **kwargs: Additional membership fields

        Returns:
            spp.program.membership record
        """
        if enrollment_date is None:
            enrollment_date = date.today()

        vals = {
            "partner_id": partner.id,
            "program_id": program.id,
            "state": state,
            "enrollment_date": enrollment_date,
        }
        vals.update(kwargs)

        return self.env["spp.program.membership"].create(vals)


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "ApiV2HttpTestCase skipped")
class ApiV2HttpTestCase(HttpCase):
    """Base class for API V2 HTTP endpoint tests.

    Inherits from HttpCase to properly handle HTTP requests.
    Sets up FastAPI endpoint registry synchronization.

    Use this class instead of mixing ApiV2TestCase with HttpCase.
    """

    def url_open(self, url, *args, **kwargs):
        """Override url_open to flush pending ORM writes before HTTP request.

        HTTP handlers use a separate ORM cache via TestCursor. Data created
        in test setUp() must be flushed to the database savepoint before
        the HTTP handler can see it.
        """
        self.env.cr.flush()
        self.env.invalidate_all()
        return super().url_open(url, *args, **kwargs)

    def url_patch(self, url, data=None, headers=None):
        """Send a PATCH request to the given URL.

        Use this instead of url_open for PATCH endpoints.
        Opener extends requests.Session, so use .patch() method.
        """
        full_url = self.base_url() + url
        return self.opener.patch(full_url, data=data, headers=headers)

    def url_put(self, url, data=None, headers=None):
        """Send a PUT request to the given URL.

        Use this instead of url_open for PUT endpoints.
        Opener extends requests.Session, so use .put() method.
        """
        full_url = self.base_url() + url
        return self.opener.put(full_url, data=data, headers=headers)

    def url_delete(self, url, headers=None):
        """Send a DELETE request to the given URL.

        Use this instead of url_open for DELETE endpoints.
        Opener extends requests.Session, so use .delete() method.
        """
        full_url = self.base_url() + url
        return self.opener.delete(full_url, headers=headers)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Clear rate limiter state to ensure test isolation
        get_rate_limiter().clear()

        # Set up JWT secret for tests
        cls.env["ir.config_parameter"].sudo().set_param(
            "spp_api_v2.jwt_secret",
            "test-secret-key-for-testing-only-do-not-use-in-production",
        )

        # Sync FastAPI endpoint registry - required for HTTP tests
        cls.fastapi_endpoint = cls.env.ref(
            "spp_api_v2.fastapi_endpoint_api_v2",
            raise_if_not_found=False,
        )
        if cls.fastapi_endpoint:
            cls.fastapi_endpoint._handle_registry_sync()

        # ID types are vocabulary codes from the ID Type vocabulary (urn:openspp:vocab:id-type)
        # The registry ID uses spp.vocabulary.code for id_type_id, not spp.id.type
        id_type_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not id_type_vocab:
            id_type_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Type",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )

        cls.id_type_national = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", id_type_vocab.id), ("code", "=", "test_national_id")],
            limit=1,
        )
        if not cls.id_type_national:
            cls.id_type_national = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "test_national_id",
                    "display": "Test National ID",
                    "is_local": True,
                    "target_type": "individual",
                }
            )

        cls.id_type_household = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", id_type_vocab.id), ("code", "=", "test_household_id")],
            limit=1,
        )
        if not cls.id_type_household:
            cls.id_type_household = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "test_household_id",
                    "display": "Test Household ID",
                    "is_local": True,
                    "target_type": "group",
                }
            )

        # Computed URIs for use in test assertions and JSON payloads
        cls.NATIONAL_ID_URI = "urn:openspp:vocab:id-type#test_national_id"
        cls.HOUSEHOLD_ID_URI = "urn:openspp:vocab:id-type#test_household_id"
        cls.PASSPORT_ID_URI = "urn:openspp:vocab:id-type#test_passport"
        # URL-safe versions (# encoded as %23) for use in HTTP URL paths
        cls.NATIONAL_ID_URI_URL = "urn:openspp:vocab:id-type%23test_national_id"
        cls.HOUSEHOLD_ID_URI_URL = "urn:openspp:vocab:id-type%23test_household_id"

        # Create test gender vocabulary codes
        cls.gender_vocabulary = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:iso:std:iso:5218")], limit=1
        )
        if not cls.gender_vocabulary:
            cls.gender_vocabulary = cls.env["spp.vocabulary"].create(
                {
                    "name": "Gender",
                    "namespace_uri": "urn:iso:std:iso:5218",
                }
            )
        cls.gender_male = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.gender_vocabulary.id),
                ("code", "=", "1"),
            ],
            limit=1,
        )
        if not cls.gender_male:
            cls.gender_male = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.gender_vocabulary.id,
                    "code": "1",
                    "display": "Male",
                    "namespace_uri": "urn:iso:std:iso:5218",
                }
            )
        cls.gender_female = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.gender_vocabulary.id),
                ("code", "=", "2"),
            ],
            limit=1,
        )
        if not cls.gender_female:
            cls.gender_female = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.gender_vocabulary.id,
                    "code": "2",
                    "display": "Female",
                    "namespace_uri": "urn:iso:std:iso:5218",
                }
            )

        # Create test relationship vocabulary (use search_or_create to avoid duplicates)
        cls.relationship_vocabulary = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:group-membership-type")], limit=1
        )
        if not cls.relationship_vocabulary:
            cls.relationship_vocabulary = cls.env["spp.vocabulary"].create(
                {
                    "name": "Group Membership Type",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                }
            )
        cls.relationship_head = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.relationship_vocabulary.id),
                ("code", "=", "head"),
            ],
            limit=1,
        )
        if not cls.relationship_head:
            cls.relationship_head = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.relationship_vocabulary.id,
                    "code": "head",
                    "display": "Head of Household",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                }
            )

        # Create test-specific relationship vocabulary (for API tests using urn:test:relationship)
        cls.test_relationship_vocabulary = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:test:relationship")], limit=1
        )
        if not cls.test_relationship_vocabulary:
            cls.test_relationship_vocabulary = cls.env["spp.vocabulary"].create(
                {
                    "name": "Test Relationship Types",
                    "namespace_uri": "urn:test:relationship",
                }
            )
        cls.test_relationship_head = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.test_relationship_vocabulary.id),
                ("code", "=", "head"),
            ],
            limit=1,
        )
        if not cls.test_relationship_head:
            cls.test_relationship_head = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.test_relationship_vocabulary.id,
                    "code": "head",
                    "display": "Head of Household",
                }
            )
        cls.test_relationship_spouse = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", cls.test_relationship_vocabulary.id),
                ("code", "=", "spouse"),
            ],
            limit=1,
        )
        if not cls.test_relationship_spouse:
            cls.test_relationship_spouse = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.test_relationship_vocabulary.id,
                    "code": "spouse",
                    "display": "Spouse",
                }
            )

    @classmethod
    def create_test_individual(
        cls,
        name="Test Person",
        given_name="Test",
        family_name="Person",
        identifier_value="TEST-001",
        gender_id=None,
        birthdate=None,
        **kwargs,
    ):
        """Create an individual with identifier for testing."""
        vals = {
            "name": name,
            "given_name": given_name,
            "family_name": family_name,
            "is_registrant": True,
            "is_group": False,
        }

        if gender_id:
            vals["gender_id"] = gender_id
        if birthdate:
            vals["birthdate"] = birthdate

        vals.update(kwargs)
        partner = cls.env["res.partner"].create(vals)

        # Create registry ID
        cls.env["spp.registry.id"].create(
            {
                "partner_id": partner.id,
                "id_type_id": cls.id_type_national.id,
                "value": identifier_value,
                "status": "valid",
            }
        )

        # Flush to ensure data is visible to HTTP handlers
        cls.env.cr.flush()

        return partner

    @classmethod
    def create_test_group(
        cls,
        name="Test Household",
        identifier_value="HH-001",
        members=None,
        id_type=None,
        **kwargs,
    ):
        """Create a group/household with identifier.

        Args:
            name: Group name
            identifier_value: Identifier value
            members: List of (partner, role) tuples
            id_type: ID type to use (defaults to household ID type)
            **kwargs: Additional partner fields

        Returns:
            res.partner record
        """
        vals = {
            "name": name,
            "is_registrant": True,
            "is_group": True,
        }
        vals.update(kwargs)

        group = cls.env["res.partner"].create(vals)

        # Create registry ID (use household ID type by default)
        if id_type is None:
            id_type = cls.id_type_household
        cls.env["spp.registry.id"].create(
            {
                "partner_id": group.id,
                "id_type_id": id_type.id,
                "value": identifier_value,
                "status": "valid",
            }
        )

        # Add members if specified
        if members:
            for member_partner, role_code in members:
                # Create group membership
                membership_vals = {
                    "group": group.id,
                    "individual": member_partner.id,
                }
                # Add membership type if role specified
                if role_code:
                    # Use vocabulary code directly as membership type
                    membership_vals["membership_type_ids"] = [Command.set([role_code.id])]

                cls.env["spp.group.membership"].create(membership_vals)

        # Flush to ensure data is visible to HTTP handlers
        cls.env.cr.flush()

        return group

    def create_api_client(
        self,
        name="Test Client",
        scopes=None,
        require_consent=True,
        legal_basis="consent",
        organization_type="government",
        **kwargs,
    ):
        """Create API client with scopes."""
        partner = self.env["res.partner"].create({"name": f"{name} Organization"})

        # Lookup organization type by code if not provided as organization_type_id
        if "organization_type_id" not in kwargs:
            org_type = self.env.ref(
                f"spp_consent.org_type_{organization_type}",
                raise_if_not_found=False,
            )
            if not org_type:
                org_type = self.env["spp.consent.org.type"].search([("code", "=", organization_type)], limit=1)
            if not org_type:
                raise ValueError(
                    f"Organization type '{organization_type}' not found. "
                    f"Available types: government, ngo, ingo, un, private, research, other"
                )
            kwargs["organization_type_id"] = org_type.id

        vals = {
            "name": name,
            "partner_id": partner.id,
            "is_require_consent": require_consent,
            "legal_basis": legal_basis,
        }
        vals.update(kwargs)

        client = self.env["spp.api.client"].create(vals)

        # Create scopes
        if scopes:
            for scope_def in scopes:
                self.env["spp.api.client.scope"].create(
                    {
                        "client_id": client.id,
                        "resource": scope_def.get("resource", "individual"),
                        "action": scope_def.get("action", "read"),
                    }
                )

        return client

    def create_consent(
        self,
        registrant,
        grantee_partner,
        resource_type="individual",
        field_access="all",
        purpose="service_delivery",
        expiry_days=365,
        **kwargs,
    ):
        """Create consent for testing."""
        today = date.today()
        expiry = today + timedelta(days=expiry_days)

        vals = {
            "name": f"Test Consent - {registrant.name}",
            "recipient_ids": [Command.set([grantee_partner.id])],
            "recipient_mode": "specific",
            "status": "given",
            "effective_date": today,
            "expiry": expiry,
        }

        if registrant.is_group:
            vals["group_id"] = registrant.id
        else:
            vals["signatory_id"] = registrant.id

        vals.update(kwargs)
        consent = self.env["spp.consent"].create(vals)

        # Create consent scope
        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": resource_type,
                "field_access": field_access,
                "purpose": purpose,
            }
        )

        # Flush to ensure consent is visible to HTTP handlers
        self.env.cr.flush()

        return consent

    def generate_jwt_token(self, api_client):
        """Generate JWT token for API client."""

        import jwt

        secret = self.env["ir.config_parameter"].sudo().get_param("spp_api_v2.jwt_secret")

        now = datetime.now(tz=UTC)
        payload = {
            "iss": "openspp-api-v2",
            "sub": api_client.client_id,
            "aud": "openspp",
            "exp": now + timedelta(hours=1),
            "iat": now,
            "client_id": api_client.client_id,
            "partner_id": api_client.partner_id.id,
            "scopes": [f"{s.resource}:{s.action}" for s in api_client.scope_ids],
        }

        return jwt.encode(payload, secret, algorithm="HS256")

    def create_test_program(
        self,
        name="Test Program",
        target_type="individual",
        state="active",
        **kwargs,
    ):
        """Create a program for testing."""
        vals = {
            "name": name,
            "target_type": target_type,
            "state": state,
        }
        vals.update(kwargs)

        program = self.env["spp.program"].create(vals)

        # Create program identifier if spp.program.id exists
        if "spp.program.id" in self.env:
            self.env["spp.program.id"].create(
                {
                    "program_id": program.id,
                    "namespace_uri": "urn:openspp:program",
                    "value": name.lower().replace(" ", "-"),
                }
            )

        return program

    def create_test_membership(
        self,
        partner,
        program,
        state="enrolled",
        enrollment_date=None,
        **kwargs,
    ):
        """Create a program membership for testing."""
        if enrollment_date is None:
            enrollment_date = date.today()

        vals = {
            "partner_id": partner.id,
            "program_id": program.id,
            "state": state,
            "enrollment_date": enrollment_date,
        }
        vals.update(kwargs)

        return self.env["spp.program.membership"].create(vals)
