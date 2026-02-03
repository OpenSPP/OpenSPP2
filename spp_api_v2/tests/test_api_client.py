# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for API Client model"""

from .common import ApiV2TestCase


class TestApiClient(ApiV2TestCase):
    """Test API Client model functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Get default organization type for tests that create clients directly
        cls.default_org_type = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.default_org_type:
            cls.default_org_type = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

    def test_client_creation_generates_credentials(self):
        """Client ID and secret are auto-generated on create"""
        partner = self.env["res.partner"].create({"name": "Test Organization"})
        client = self.env["spp.api.client"].create(
            {
                "name": "Auto-Generated Client",
                "partner_id": partner.id,
                "organization_type_id": self.default_org_type.id,
            }
        )

        self.assertTrue(client.client_id, "Client ID should be auto-generated")
        self.assertTrue(client.client_secret, "Client secret should be auto-generated")
        self.assertTrue(
            client.client_id.startswith("client_"),
            "Client ID should start with 'client_'",
        )
        self.assertGreater(len(client.client_secret), 20, "Client secret should be long enough")

    def test_client_id_uniqueness(self):
        """Client IDs are automatically unique (auto-generated)"""
        partner = self.env["res.partner"].create({"name": "Test Organization"})

        # Create multiple clients and verify their IDs are unique
        clients = []
        for i in range(5):
            client = self.env["spp.api.client"].create(
                {
                    "name": f"Client {i}",
                    "partner_id": partner.id,
                    "organization_type_id": self.default_org_type.id,
                }
            )
            clients.append(client)

        # Verify all client_ids are unique
        client_ids = [c.client_id for c in clients]
        self.assertEqual(len(client_ids), len(set(client_ids)), "All client_ids should be unique")

    def test_client_authentication_success(self):
        """Valid credentials authenticate successfully"""
        client = self.create_api_client(name="Auth Test Client")

        # Authenticate with correct credentials
        authenticated = self.env["spp.api.client"].authenticate(client.client_id, client.client_secret)

        self.assertEqual(authenticated, client, "Should return client record on successful auth")
        self.assertGreater(
            authenticated.request_count,
            0,
            "Request count should be incremented",
        )
        self.assertTrue(authenticated.last_used_date, "Last used date should be set")

    def test_client_authentication_failure_wrong_secret(self):
        """Invalid secret is rejected"""
        client = self.create_api_client(name="Auth Fail Test")

        # Try to authenticate with wrong secret
        authenticated = self.env["spp.api.client"].authenticate(client.client_id, "wrong-secret")

        self.assertFalse(authenticated, "Should return empty recordset on auth failure")

    def test_client_authentication_failure_wrong_id(self):
        """Unknown client_id is rejected"""
        authenticated = self.env["spp.api.client"].authenticate("unknown_client_id", "any-secret")

        self.assertFalse(authenticated, "Should return empty recordset for unknown client")

    def test_client_inactive_cannot_authenticate(self):
        """Inactive clients cannot authenticate"""
        client = self.create_api_client(name="Inactive Client")
        client.active = False

        # Try to authenticate inactive client
        authenticated = self.env["spp.api.client"].authenticate(client.client_id, client.client_secret)

        self.assertFalse(authenticated, "Should not authenticate inactive client")

    def test_regenerate_secret(self):
        """Secret can be regenerated"""
        client = self.create_api_client(name="Regenerate Test")
        old_secret = client.client_secret

        # Regenerate secret
        client.action_regenerate_secret()

        self.assertNotEqual(
            client.client_secret,
            old_secret,
            "Secret should be changed",
        )
        self.assertGreater(len(client.client_secret), 20, "New secret should be long enough")

    def test_has_scope_positive(self):
        """has_scope returns True for granted scopes"""
        client = self.create_api_client(
            name="Scope Test",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "group", "action": "search"},
            ],
        )

        self.assertTrue(
            client.has_scope("individual", "read"),
            "Should have individual:read scope",
        )
        self.assertTrue(
            client.has_scope("group", "search"),
            "Should have group:search scope",
        )

    def test_has_scope_negative(self):
        """has_scope returns False for non-granted scopes"""
        client = self.create_api_client(
            name="Scope Test",
            scopes=[
                {"resource": "individual", "action": "read"},
            ],
        )

        self.assertFalse(
            client.has_scope("individual", "create"),
            "Should not have individual:create scope",
        )
        self.assertFalse(
            client.has_scope("group", "read"),
            "Should not have group:read scope",
        )

    def test_has_scope_all_action(self):
        """Scope with action='all' grants all actions"""
        client = self.create_api_client(
            name="All Actions Test",
            scopes=[
                {"resource": "individual", "action": "all"},
            ],
        )

        self.assertTrue(
            client.has_scope("individual", "read"),
            "action='all' should grant read",
        )
        self.assertTrue(
            client.has_scope("individual", "create"),
            "action='all' should grant create",
        )
        self.assertTrue(
            client.has_scope("individual", "update"),
            "action='all' should grant update",
        )

    def test_get_allowed_fields_all(self):
        """get_allowed_fields returns None when no filter specified"""
        client = self.create_api_client(
            name="All Fields Test",
            scopes=[
                {"resource": "individual", "action": "read"},
            ],
        )

        allowed = client.get_allowed_fields("individual")
        self.assertIsNone(allowed, "Should return None for unrestricted access")

    def test_scope_count_computed(self):
        """scope_count is computed correctly"""
        client = self.create_api_client(
            name="Scope Count Test",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "individual", "action": "search"},
                {"resource": "group", "action": "read"},
            ],
        )

        self.assertEqual(client.scope_count, 3, "Should count all scopes")

    def test_legal_basis_defaults_to_consent(self):
        """Legal basis defaults to 'consent'"""
        client = self.create_api_client(name="Default Legal Basis")

        self.assertEqual(
            client.legal_basis,
            "consent",
            "Legal basis should default to 'consent'",
        )
        self.assertTrue(client.is_require_consent, "Should require consent by default")

    def test_has_scope_string_empty_returns_false(self):
        """has_scope_string('') returns False for empty input"""
        client = self.create_api_client(
            name="Empty Scope Test",
            scopes=[{"resource": "individual", "action": "read"}],
        )

        self.assertFalse(
            client.has_scope_string(""),
            "Empty scope string should return False",
        )
        self.assertFalse(
            client.has_scope_string(None),
            "None scope string should return False",
        )

    def test_has_scope_string_valid(self):
        """has_scope_string works for valid scope strings"""
        client = self.create_api_client(
            name="Scope String Test",
            scopes=[{"resource": "individual", "action": "read"}],
        )

        self.assertTrue(
            client.has_scope_string("individual:read"),
            "Should match exact scope",
        )
        self.assertTrue(
            client.has_scope_string("individual:*"),
            "Wildcard action should match",
        )
        self.assertTrue(
            client.has_scope_string("individual"),
            "Resource-only should match any action",
        )
        self.assertFalse(
            client.has_scope_string("group:read"),
            "Should not match different resource",
        )

    def test_scope_model_has_no_program_ids_field(self):
        """spp.api.client.scope should not have program_ids field (removed as unenforced)"""
        scope_fields = self.env["spp.api.client.scope"]._fields
        self.assertNotIn(
            "program_ids",
            scope_fields,
            "program_ids field should not exist on spp.api.client.scope "
            "(it was removed because it was never enforced in has_scope)",
        )

    def test_legal_obligation_client(self):
        """Client with legal_obligation basis can be created"""
        client = self.create_api_client(
            name="Legal Obligation Client",
            legal_basis="legal_obligation",
            legal_basis_reference="Test Law 123/2024",
        )

        self.assertEqual(client.legal_basis, "legal_obligation")
        self.assertEqual(client.legal_basis_reference, "Test Law 123/2024")
