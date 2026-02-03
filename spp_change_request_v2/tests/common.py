"""Common test utilities for Change Request V2 tests."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class CRTestCase(TransactionCase):
    """Base test case for Change Request related tests.

    Provides common setup for creating registrants and CR types.
    """

    @classmethod
    def setUpClass(cls):
        """Set up common test data."""
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.CRType = cls.env["spp.change.request.type"]
        cls.CR = cls.env["spp.change.request"]

        # Create a test individual registrant
        cls.test_individual = cls.Partner.create(
            {
                "name": "Test Individual",
                "given_name": "Test",
                "family_name": "Individual",
                "phone": "1234567890",
                "email": "test@example.com",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create a test group registrant
        cls.test_group = cls.Partner.create(
            {
                "name": "Test Group",
                "phone": "9876543210",
                "email": "group@example.com",
                "is_registrant": True,
                "is_group": True,
            }
        )

    def create_cr(self, cr_type_code, registrant=None):
        """Helper to create a CR of a given type.

        Args:
            cr_type_code: Code of the CR type to use
            registrant: Registrant to use (defaults to test_individual)

        Returns:
            Created change request record
        """
        cr_type = self.CRType.search([("code", "=", cr_type_code)], limit=1)
        if not cr_type:
            self.fail(f"CR type with code '{cr_type_code}' not found")

        if registrant is None:
            registrant = self.test_individual

        return self.CR.create(
            {
                "request_type_id": cr_type.id,
                "registrant_id": registrant.id,
            }
        )
