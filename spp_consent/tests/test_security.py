# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Test security and access control for consent operations."""

import time
from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestConsentSecurity(TransactionCase):
    """Test security and access control for consent operations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test data (non-user data that can be shared across tests)
        cls.individual = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.controller = cls.env["res.partner"].create(
            {
                "name": "Test Controller",
            }
        )

        cls.recipient = cls.env["res.partner"].create(
            {
                "name": "Test Recipient",
            }
        )

        cls.purpose = cls.env["spp.consent.purpose"].create(
            {
                "name": "Service Delivery",
                "code": "service_delivery",
            }
        )

        cls.personal_data = cls.env["spp.consent.personal.data"].create(
            {
                "name": "Contact Information",
                "code": "contact_info",
            }
        )

        # Create a valid consent for testing
        cls.consent = cls.env["spp.consent"].create(
            {
                "name": "Test Consent",
                "signatory_id": cls.individual.id,
                "controller_id": cls.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "recipient_mode": "specific",
                "recipient_ids": [Command.set([cls.recipient.id])],
                "purpose_ids": [Command.set([cls.purpose.id])],
                "personal_data_ids": [Command.set([cls.personal_data.id])],
            }
        )

    def setUp(self):
        """Create fresh test users for each test method.

        Moving user creation to setUp ensures proper ACL cache state in full CI,
        where setUpClass-created users may have stale cache entries.
        """
        super().setUp()

        # Get required groups
        group_user = self.env.ref("base.group_user")
        group_registry_viewer = self.env.ref("spp_registry.group_registry_viewer")

        # Create user with viewer permissions (has read access)
        # Use unique ID per test to avoid any conflicts
        test_id = int(time.time() * 1000000)
        user_vals = {
            "name": f"Consent Viewer User {test_id}",
            "login": f"consent_viewer_test_{test_id}",
            "group_ids": [(6, 0, [group_user.id, group_registry_viewer.id])],
        }
        # Bypass default roles from base_user_role module if installed
        if "role_line_ids" in self.env["res.users"]._fields:
            user_vals["role_line_ids"] = []
        self.user_viewer = self.env["res.users"].create(user_vals)

        # Invalidate cache to ensure ACL changes are recognized
        self.env.invalidate_all()

    def test_check_consent_requires_read_permission(self):
        """Test that check_consent() enforces read permissions."""
        # Create user with no consent read permissions
        user_vals = {
            "name": "No Access User",
            "login": f"noaccess_{int(time.time() * 1000000)}",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        }
        # Bypass default roles from base_user_role module if installed
        if "role_line_ids" in self.env["res.users"]._fields:
            user_vals["role_line_ids"] = []
        user_no_access = self.env["res.users"].create(user_vals)
        self.env.invalidate_all()

        # Try to call check_consent as user without permission
        with self.assertRaises(AccessError, msg="check_consent should require read permission"):
            self.env["spp.consent"].with_user(user_no_access).check_consent(
                registrant_id=self.individual.id,
                recipient_id=self.recipient.id,
            )

    def test_check_consent_succeeds_with_permission(self):
        """Test that check_consent() works for users with proper permissions."""
        # Use viewer group which has read permission
        result = (
            self.env["spp.consent"]
            .with_user(self.user_viewer)
            .check_consent(
                registrant_id=self.individual.id,
                recipient_id=self.recipient.id,
            )
        )

        # Should work without AccessError
        self.assertIsNotNone(result)
