# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import uuid

from psycopg2 import IntegrityError

from odoo import fields
from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestSQLConstraints(TransactionCase):
    """Test that SQL UNIQUE constraints enforce uniqueness at the database level.

    These constraints replace the old Python @api.constrains checks that
    performed per-record search() calls, causing O(N^2) during bulk inserts.
    """

    def setUp(self):
        super().setUp()
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.registrant = self.env["res.partner"].create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
            }
        )
        self.registrant2 = self.env["res.partner"].create(
            {
                "name": "Test Registrant 2",
                "is_registrant": True,
            }
        )
        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

    # -- Program Membership uniqueness --

    def test_program_membership_unique_constraint_exists(self):
        """SQL UNIQUE constraint on (partner_id, program_id) must exist."""
        self.env.cr.execute(
            """
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'spp_program_membership'::regclass
              AND contype = 'u'
              AND conkey @> ARRAY[
                  (SELECT attnum FROM pg_attribute
                   WHERE attrelid = 'spp_program_membership'::regclass
                     AND attname = 'partner_id'),
                  (SELECT attnum FROM pg_attribute
                   WHERE attrelid = 'spp_program_membership'::regclass
                     AND attname = 'program_id')
              ]
            """
        )
        self.assertTrue(
            self.env.cr.fetchone(),
            "UNIQUE constraint on (partner_id, program_id) must exist on spp_program_membership",
        )

    def test_program_membership_duplicate_blocked(self):
        """Inserting a duplicate (partner_id, program_id) must raise IntegrityError."""
        self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": self.program.id,
            }
        )
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    """
                    INSERT INTO spp_program_membership
                        (partner_id, program_id, state,
                         create_uid, write_uid, create_date, write_date)
                    VALUES (%s, %s, 'draft', %s, %s, now(), now())
                    """,
                    (
                        self.registrant.id,
                        self.program.id,
                        self.env.uid,
                        self.env.uid,
                    ),
                )

    def test_program_membership_different_partners_allowed(self):
        """Different partners in the same program must be allowed."""
        self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": self.program.id,
            }
        )
        membership2 = self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant2.id,
                "program_id": self.program.id,
            }
        )
        self.assertTrue(membership2.id)

    def test_program_membership_same_partner_different_programs(self):
        """Same partner in different programs must be allowed."""
        program2 = self.env["spp.program"].create({"name": f"Test Program 2 {uuid.uuid4().hex[:8]}"})
        self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": self.program.id,
            }
        )
        membership2 = self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": program2.id,
            }
        )
        self.assertTrue(membership2.id)

    # -- Cycle Membership uniqueness --

    def test_cycle_membership_unique_constraint_exists(self):
        """SQL UNIQUE constraint on (partner_id, cycle_id) must exist."""
        self.env.cr.execute(
            """
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'spp_cycle_membership'::regclass
              AND contype = 'u'
              AND conkey @> ARRAY[
                  (SELECT attnum FROM pg_attribute
                   WHERE attrelid = 'spp_cycle_membership'::regclass
                     AND attname = 'partner_id'),
                  (SELECT attnum FROM pg_attribute
                   WHERE attrelid = 'spp_cycle_membership'::regclass
                     AND attname = 'cycle_id')
              ]
            """
        )
        self.assertTrue(
            self.env.cr.fetchone(),
            "UNIQUE constraint on (partner_id, cycle_id) must exist on spp_cycle_membership",
        )

    def test_cycle_membership_duplicate_blocked(self):
        """Inserting a duplicate (partner_id, cycle_id) must raise IntegrityError."""
        self.env["spp.cycle.membership"].create(
            {
                "partner_id": self.registrant.id,
                "cycle_id": self.cycle.id,
            }
        )
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    """
                    INSERT INTO spp_cycle_membership
                        (partner_id, cycle_id, state,
                         create_uid, write_uid, create_date, write_date)
                    VALUES (%s, %s, 'draft', %s, %s, now(), now())
                    """,
                    (
                        self.registrant.id,
                        self.cycle.id,
                        self.env.uid,
                        self.env.uid,
                    ),
                )

    def test_cycle_membership_different_partners_allowed(self):
        """Different partners in the same cycle must be allowed."""
        self.env["spp.cycle.membership"].create(
            {
                "partner_id": self.registrant.id,
                "cycle_id": self.cycle.id,
            }
        )
        membership2 = self.env["spp.cycle.membership"].create(
            {
                "partner_id": self.registrant2.id,
                "cycle_id": self.cycle.id,
            }
        )
        self.assertTrue(membership2.id)

    # -- Entitlement code uniqueness --

    def test_entitlement_code_unique_constraint_exists(self):
        """SQL UNIQUE constraint on (code) must exist on spp_entitlement."""
        self.env.cr.execute(
            """
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'spp_entitlement'::regclass
              AND contype = 'u'
              AND conkey @> ARRAY[
                  (SELECT attnum FROM pg_attribute
                   WHERE attrelid = 'spp_entitlement'::regclass
                     AND attname = 'code')
              ]
            """
        )
        self.assertTrue(
            self.env.cr.fetchone(),
            "UNIQUE constraint on (code) must exist on spp_entitlement",
        )

    def test_entitlement_duplicate_code_blocked(self):
        """Inserting a duplicate entitlement code must raise IntegrityError."""
        entitlement = self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant.id,
                "cycle_id": self.cycle.id,
                "initial_amount": 100.0,
            }
        )
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    """
                    INSERT INTO spp_entitlement
                        (code, partner_id, cycle_id, initial_amount,
                         state, create_uid, write_uid,
                         create_date, write_date)
                    VALUES (%s, %s, %s, 100.0, 'draft', %s, %s, now(), now())
                    """,
                    (
                        entitlement.code,
                        self.registrant2.id,
                        self.cycle.id,
                        self.env.uid,
                        self.env.uid,
                    ),
                )

    def test_entitlement_different_codes_allowed(self):
        """Different entitlement codes must be allowed."""
        ent1 = self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant.id,
                "cycle_id": self.cycle.id,
                "initial_amount": 100.0,
            }
        )
        ent2 = self.env["spp.entitlement"].create(
            {
                "partner_id": self.registrant2.id,
                "cycle_id": self.cycle.id,
                "initial_amount": 200.0,
            }
        )
        self.assertNotEqual(ent1.code, ent2.code)
        self.assertTrue(ent2.id)
