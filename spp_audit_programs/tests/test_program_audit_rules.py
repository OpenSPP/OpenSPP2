# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Program/cycle audit rules are created by this companion (OP#1085)."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProgramAuditRules(TransactionCase):
    def test_program_audit_rules_created(self):
        """The Program and Cycle audit rules exist once this module is installed."""
        Rule = self.env["spp.audit.rule"]
        self.assertTrue(Rule.search([("name", "=", "Program Rule")], limit=1))
        self.assertTrue(Rule.search([("name", "=", "Cycle Rule")], limit=1))
