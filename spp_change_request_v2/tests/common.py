"""Common test utilities for Change Request V2 tests."""

from odoo.tests import TransactionCase, tagged

# Definitions for CR types needed by strategy tests.
# These mirror what spp_cr_types_base / spp_cr_types_advanced install via XML.
CR_TYPE_DEFS = {
    "add_member": {
        "name": "Add Group Member",
        "target_type": "group",
        "detail_model": "spp.cr.detail.add_member",
        "apply_strategy": "custom",
        "apply_model": "spp.cr.apply.add_member",
    },
    "remove_member": {
        "name": "Remove Group Member",
        "target_type": "group",
        "detail_model": "spp.cr.detail.remove_member",
        "apply_strategy": "custom",
        "apply_model": "spp.cr.apply.remove_member",
    },
    "change_hoh": {
        "name": "Change Head of Household",
        "target_type": "group",
        "detail_model": "spp.cr.detail.change_hoh",
        "apply_strategy": "custom",
        "apply_model": "spp.cr.apply.change_hoh",
    },
    "exit_registrant": {
        "name": "Exit Registrant",
        "target_type": "both",
        "detail_model": "spp.cr.detail.exit_registrant",
        "apply_strategy": "custom",
        "apply_model": "spp.cr.apply.exit_registrant",
    },
    "transfer_member": {
        "name": "Transfer Member",
        "target_type": "group",
        "detail_model": "spp.cr.detail.transfer_member",
        "apply_strategy": "custom",
        "apply_model": "spp.cr.apply.transfer_member",
    },
    "update_id": {
        "name": "Update ID Document",
        "target_type": "both",
        "detail_model": "spp.cr.detail.update_id",
        "apply_strategy": "custom",
        "apply_model": "spp.cr.apply.update_id",
    },
    "create_group": {
        "name": "Create Group",
        "target_type": "group",
        "detail_model": "spp.cr.detail.create_group",
        "apply_strategy": "custom",
        "apply_model": "spp.cr.apply.create_group",
    },
    "split_household": {
        "name": "Split Household",
        "target_type": "group",
        "detail_model": "spp.cr.detail.split_household",
        "apply_strategy": "custom",
        "apply_model": "spp.cr.apply.split_household",
    },
    "merge_registrants": {
        "name": "Merge Registrants",
        "target_type": "both",
        "detail_model": "spp.cr.detail.merge_registrants",
        "apply_strategy": "custom",
        "apply_model": "spp.cr.apply.merge_registrants",
    },
    "edit_individual": {
        "name": "Edit Individual",
        "target_type": "individual",
        "detail_model": "spp.cr.detail.edit_individual",
        "apply_strategy": "field_mapping",
    },
    "edit_group": {
        "name": "Edit Group",
        "target_type": "group",
        "detail_model": "spp.cr.detail.edit_group",
        "apply_strategy": "field_mapping",
    },
}


def get_or_create_cr_type(env, code):
    """Get a CR type by code, creating it if not found (for tests)."""
    cr_type = env["spp.change.request.type"].search([("code", "=", code)], limit=1)
    if not cr_type:
        defs = CR_TYPE_DEFS[code]
        cr_type = env["spp.change.request.type"].create({"code": code, **defs})
    return cr_type


# Vocabulary codes that may not be installed (commented out in default data).
_MEMBERSHIP_TYPE_CODES = {
    "spouse": {"display": "Spouse", "sequence": 3},
    "child": {"display": "Child", "sequence": 2},
    "other": {"display": "Other", "sequence": 10},
}

MEMBERSHIP_TYPE_NS = "urn:openspp:vocab:group-membership-type"


def get_or_create_membership_kind(env, code):
    """Get a membership type vocabulary code, creating it if not found."""
    kind = env["spp.vocabulary.code"].get_code(MEMBERSHIP_TYPE_NS, code)
    if not kind:
        vocab = env["spp.vocabulary"].search(
            [("namespace_uri", "=", MEMBERSHIP_TYPE_NS)], limit=1
        )
        defs = _MEMBERSHIP_TYPE_CODES[code]
        kind = env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": vocab.id,
                "code": code,
                "display": defs["display"],
                "sequence": defs["sequence"],
                "is_local": True,
            }
        )
    return kind


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
