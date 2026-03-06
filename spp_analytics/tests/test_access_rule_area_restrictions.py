# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for area-based access restrictions on aggregation access rules."""

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestAccessRuleAreaRestrictions(TransactionCase):
    """Test area-based access restrictions for explicit scopes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test areas
        cls.area_north = cls.env["spp.area"].create(
            {
                "draft_name": "North District",
                "code": "NORTH-001",
            }
        )
        cls.area_south = cls.env["spp.area"].create(
            {
                "draft_name": "South District",
                "code": "SOUTH-001",
            }
        )
        cls.area_east = cls.env["spp.area"].create(
            {
                "draft_name": "East District",
                "code": "EAST-001",
            }
        )

        # Create test registrants in different areas
        cls.registrant_north_1 = cls.env["res.partner"].create(
            {
                "name": "North Registrant 1",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_north.id,
            }
        )
        cls.registrant_north_2 = cls.env["res.partner"].create(
            {
                "name": "North Registrant 2",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_north.id,
            }
        )
        cls.registrant_south_1 = cls.env["res.partner"].create(
            {
                "name": "South Registrant 1",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_south.id,
            }
        )
        cls.registrant_south_2 = cls.env["res.partner"].create(
            {
                "name": "South Registrant 2",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_south.id,
            }
        )
        cls.registrant_east = cls.env["res.partner"].create(
            {
                "name": "East Registrant",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_east.id,
            }
        )

        # Create test user
        cls.restricted_user = cls.env["res.users"].create(
            {
                "name": "Restricted Area User",
                "login": "restricted_user",
                "email": "restricted@test.com",
            }
        )

        # Create unrestricted user
        cls.unrestricted_user = cls.env["res.users"].create(
            {
                "name": "Unrestricted User",
                "login": "unrestricted_user",
                "email": "unrestricted@test.com",
            }
        )

    def test_access_rule_with_area_restrictions(self):
        """Test that access rules can have area restrictions."""
        rule = self.env["spp.analytics.access.rule"].create(
            {
                "name": "North District Only Rule",
                "user_id": self.restricted_user.id,
                "access_level": "aggregate",
                "allow_inline_scopes": True,
                "allowed_area_ids": [(6, 0, [self.area_north.id])],
            }
        )

        self.assertEqual(len(rule.allowed_area_ids), 1)
        self.assertIn(self.area_north, rule.allowed_area_ids)

    def test_explicit_scope_rejected_when_outside_allowed_areas(self):
        """Test that explicit scopes are rejected when registrants are outside allowed areas."""
        # Create rule restricting to North district only
        rule = self.env["spp.analytics.access.rule"].create(
            {
                "name": "North District Only Rule",
                "user_id": self.restricted_user.id,
                "access_level": "aggregate",
                "allow_inline_scopes": True,
                "allowed_area_ids": [(6, 0, [self.area_north.id])],
            }
        )

        # Try to query registrants from South district (should fail)
        scope = {
            "scope_type": "explicit",
            "explicit_partner_ids": [self.registrant_south_1.id, self.registrant_south_2.id],
        }

        with self.assertRaises(ValidationError) as context:
            rule.check_scope_allowed(scope)

        self.assertIn("outside your allowed areas", str(context.exception))

    def test_explicit_scope_allowed_when_within_allowed_areas(self):
        """Test that explicit scopes are allowed when all registrants are within allowed areas."""
        # Create rule restricting to North district only
        rule = self.env["spp.analytics.access.rule"].create(
            {
                "name": "North District Only Rule",
                "user_id": self.restricted_user.id,
                "access_level": "aggregate",
                "allow_inline_scopes": True,
                "allowed_area_ids": [(6, 0, [self.area_north.id])],
            }
        )

        # Query registrants from North district (should succeed)
        scope = {
            "scope_type": "explicit",
            "explicit_partner_ids": [self.registrant_north_1.id, self.registrant_north_2.id],
        }

        # Should not raise
        self.assertTrue(rule.check_scope_allowed(scope))

    def test_explicit_scope_rejected_when_mixed_areas(self):
        """Test that explicit scopes are rejected when some registrants are outside allowed areas."""
        # Create rule restricting to North district only
        rule = self.env["spp.analytics.access.rule"].create(
            {
                "name": "North District Only Rule",
                "user_id": self.restricted_user.id,
                "access_level": "aggregate",
                "allow_inline_scopes": True,
                "allowed_area_ids": [(6, 0, [self.area_north.id])],
            }
        )

        # Try to query registrants from both North and South (should fail)
        scope = {
            "scope_type": "explicit",
            "explicit_partner_ids": [self.registrant_north_1.id, self.registrant_south_1.id],
        }

        with self.assertRaises(ValidationError) as context:
            rule.check_scope_allowed(scope)

        self.assertIn("outside your allowed areas", str(context.exception))

    def test_explicit_scope_allowed_when_no_area_restrictions(self):
        """Test that explicit scopes are allowed when user has no area restrictions."""
        # Create rule without area restrictions
        rule = self.env["spp.analytics.access.rule"].create(
            {
                "name": "Unrestricted Rule",
                "user_id": self.unrestricted_user.id,
                "access_level": "aggregate",
                "allow_inline_scopes": True,
            }
        )

        # Query registrants from any area (should succeed)
        scope = {
            "scope_type": "explicit",
            "explicit_partner_ids": [
                self.registrant_north_1.id,
                self.registrant_south_1.id,
                self.registrant_east.id,
            ],
        }

        # Should not raise
        self.assertTrue(rule.check_scope_allowed(scope))

    def test_explicit_scope_allowed_with_multiple_allowed_areas(self):
        """Test that explicit scopes work correctly with multiple allowed areas."""
        # Create rule allowing North and South districts
        rule = self.env["spp.analytics.access.rule"].create(
            {
                "name": "North and South Rule",
                "user_id": self.restricted_user.id,
                "access_level": "aggregate",
                "allow_inline_scopes": True,
                "allowed_area_ids": [(6, 0, [self.area_north.id, self.area_south.id])],
            }
        )

        # Query registrants from North and South (should succeed)
        scope = {
            "scope_type": "explicit",
            "explicit_partner_ids": [
                self.registrant_north_1.id,
                self.registrant_south_1.id,
            ],
        }

        # Should not raise
        self.assertTrue(rule.check_scope_allowed(scope))

        # Query registrants including East (should fail)
        scope_with_east = {
            "scope_type": "explicit",
            "explicit_partner_ids": [
                self.registrant_north_1.id,
                self.registrant_east.id,
            ],
        }

        with self.assertRaises(ValidationError):
            rule.check_scope_allowed(scope_with_east)

    def test_area_only_scope_type_rejects_explicit_scopes(self):
        """Test that area_only scope type restriction rejects explicit scopes even within allowed areas."""
        # Create rule with area_only scope type restriction
        rule = self.env["spp.analytics.access.rule"].create(
            {
                "name": "Area Only Rule",
                "user_id": self.restricted_user.id,
                "access_level": "aggregate",
                "allowed_scope_types": "area_only",
                "allow_inline_scopes": True,  # Allow inline scopes, but only area-based ones
                "allowed_area_ids": [(6, 0, [self.area_north.id])],
            }
        )

        # Try to use explicit scope even with allowed area registrants (should fail)
        scope = {
            "scope_type": "explicit",
            "explicit_partner_ids": [self.registrant_north_1.id],
        }

        with self.assertRaises(ValidationError) as context:
            rule.check_scope_allowed(scope)

        self.assertIn("Only area-based scopes are allowed", str(context.exception))

    def test_aggregation_service_enforces_area_restrictions_on_gis_explicit_scopes(self):
        """Test that AggregationService enforces area restrictions on GIS-generated explicit scopes."""
        # Create rule restricting to North district only
        self.env["spp.analytics.access.rule"].create(
            {
                "name": "North District Only Rule",
                "user_id": self.restricted_user.id,
                "access_level": "aggregate",
                "allow_inline_scopes": True,
                "allowed_area_ids": [(6, 0, [self.area_north.id])],
            }
        )

        # Switch to restricted user
        restricted_env = self.env(user=self.restricted_user)
        aggregation_service = restricted_env["spp.analytics.service"]

        # Try to compute aggregation for South registrants (simulating GIS query)
        scope = {
            "scope_type": "explicit",
            "explicit_partner_ids": [self.registrant_south_1.id, self.registrant_south_2.id],
        }

        with self.assertRaises(AccessError) as context:
            aggregation_service.compute_aggregation(scope=scope, statistics=["count"])

        self.assertIn("outside your allowed areas", str(context.exception))

    def test_aggregation_service_allows_area_restricted_explicit_scopes(self):
        """Test that AggregationService allows explicit scopes within allowed areas."""
        # Create rule restricting to North district only
        self.env["spp.analytics.access.rule"].create(
            {
                "name": "North District Only Rule",
                "user_id": self.restricted_user.id,
                "access_level": "aggregate",
                "allow_inline_scopes": True,
                "allowed_area_ids": [(6, 0, [self.area_north.id])],
            }
        )

        # Switch to restricted user
        restricted_env = self.env(user=self.restricted_user)
        aggregation_service = restricted_env["spp.analytics.service"]

        # Compute aggregation for North registrants (should succeed)
        scope = {
            "scope_type": "explicit",
            "explicit_partner_ids": [self.registrant_north_1.id, self.registrant_north_2.id],
        }

        result = aggregation_service.compute_aggregation(scope=scope, statistics=["count"])

        self.assertEqual(result["total_count"], 2)
        self.assertIn("count", result["statistics"])
