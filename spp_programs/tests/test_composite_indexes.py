# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase


class TestCompositeIndexes(TransactionCase):
    """Test that composite indexes exist for frequent query patterns."""

    def test_entitlement_cycle_partner_index_exists(self):
        """Composite index on spp_entitlement(cycle_id, partner_id) must exist.

        The prepare_entitlements duplicate check searches entitlements by
        (cycle_id, partner_id). Without this index, each batch does a
        sequential scan.
        """
        self.env.cr.execute(
            """
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'spp_entitlement'
              AND indexdef LIKE '%%cycle_id%%'
              AND indexdef LIKE '%%partner_id%%'
            """
        )
        self.assertTrue(
            self.env.cr.fetchone(),
            "Composite index on (cycle_id, partner_id) must exist on spp_entitlement",
        )

    def test_entitlement_cycle_state_index_exists(self):
        """Composite index on spp_entitlement(cycle_id, state) must exist.

        Cycle computed fields (total_amount, show_approve_button,
        entitlements_count) filter entitlements by cycle_id and state.
        """
        self.env.cr.execute(
            """
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'spp_entitlement'
              AND indexdef LIKE '%%cycle_id%%'
              AND indexdef LIKE '%%state%%'
            """
        )
        self.assertTrue(
            self.env.cr.fetchone(),
            "Composite index on (cycle_id, state) must exist on spp_entitlement",
        )

    def test_program_membership_program_state_index_exists(self):
        """Composite index on spp_program_membership(program_id, state) must exist.

        get_beneficiaries() and count_beneficiaries() filter by
        (program_id, state) on every async batch dispatch.
        """
        self.env.cr.execute(
            """
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'spp_program_membership'
              AND indexdef LIKE '%%program_id%%'
              AND indexdef LIKE '%%state%%'
            """
        )
        self.assertTrue(
            self.env.cr.fetchone(),
            "Composite index on (program_id, state) must exist on spp_program_membership",
        )
