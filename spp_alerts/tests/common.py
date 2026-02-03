# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import Command
from odoo.tests.common import TransactionCase


class AlertsTestCommon(TransactionCase):
    """Common test class for spp_alerts tests.

    Provides shared setup for vocabulary codes, test users, and common
    helper methods for creating alerts and alert rules in tests.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get vocabulary codes for alert types
        cls.vocab_code = cls.env["spp.vocabulary.code"]

        cls.alert_type_threshold = cls.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:alerts"),
                ("code", "=", "threshold"),
            ],
            limit=1,
        )

        cls.alert_type_expiry = cls.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:alerts"),
                ("code", "=", "expiry"),
            ],
            limit=1,
        )

        cls.alert_type_deadline = cls.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:alerts"),
                ("code", "=", "deadline"),
            ],
            limit=1,
        )

        cls.alert_type_manual = cls.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:alerts"),
                ("code", "=", "manual"),
            ],
            limit=1,
        )

        cls.alert_type_system = cls.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:alerts"),
                ("code", "=", "system"),
            ],
            limit=1,
        )

        # Create test companies for multi-company testing
        cls.company_main = cls.env.company
        cls.company_secondary = cls.env["res.company"].create(
            {
                "name": "Test Secondary Company",
            }
        )

        # Create test users with different access levels
        # All users need base.group_user for basic Odoo functionality (mail.thread, etc.)
        base_user_group = cls.env.ref("base.group_user")

        cls.user_viewer = cls.env["res.users"].create(
            {
                "name": "Alert Viewer",
                "login": "alert_viewer",
                "email": "viewer@test.com",
                "group_ids": [
                    Command.link(base_user_group.id),
                    Command.link(cls.env.ref("spp_alerts.group_alerts_viewer").id),
                ],
            }
        )

        cls.user_officer = cls.env["res.users"].create(
            {
                "name": "Alert Officer",
                "login": "alert_officer",
                "email": "officer@test.com",
                "group_ids": [
                    Command.link(base_user_group.id),
                    Command.link(cls.env.ref("spp_alerts.group_alerts_officer").id),
                ],
            }
        )

        cls.user_manager = cls.env["res.users"].create(
            {
                "name": "Alert Manager",
                "login": "alert_manager",
                "email": "manager@test.com",
                "group_ids": [
                    Command.link(base_user_group.id),
                    Command.link(cls.env.ref("spp_alerts.group_alerts_manager").id),
                ],
            }
        )

        # Create test model reference for alert rules
        cls.test_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def _create_test_alert(self, **kwargs):
        """Helper method to create a test alert with default values.

        Args:
            **kwargs: Override default field values

        Returns:
            spp.alert: Created alert record
        """
        default_vals = {
            "alert_type_id": self.alert_type_threshold.id,
            "title": "Test Alert",
            "priority": "medium",
            "description": "Test alert description",
        }
        default_vals.update(kwargs)
        return self.env["spp.alert"].create(default_vals)

    def _create_test_alert_rule(self, **kwargs):
        """Helper method to create a test alert rule with default values.

        Args:
            **kwargs: Override default field values

        Returns:
            spp.alert.rule: Created alert rule record
        """
        default_vals = {
            "name": "Test Alert Rule",
            "alert_type_id": self.alert_type_threshold.id,
            "priority": "medium",
        }
        default_vals.update(kwargs)
        return self.env["spp.alert.rule"].create(default_vals)
