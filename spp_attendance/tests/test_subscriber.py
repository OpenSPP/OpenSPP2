# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from psycopg2.errors import UniqueViolation

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestSubscriber(TransactionCase):
    def _create(self, identifier="PID-S1", **extra):
        vals = {
            "person_identifier": identifier,
            "family_name": "Santos",
            "given_name": "Ana",
        }
        vals.update(extra)
        return self.env["spp.attendance.subscriber"].create(vals)

    def test_create_builds_partner(self):
        subscriber = self._create()
        self.assertTrue(subscriber.partner_id)
        self.assertEqual(subscriber.partner_id.name, "Santos, Ana")
        self.assertEqual(subscriber.partner_name, "Santos, Ana")
        # inverse pushes the identifier onto the partner
        self.assertEqual(subscriber.partner_id.identifier, "PID-S1")
        # gender must remain unset unless provided (no fabricated default)
        self.assertFalse(subscriber.partner_id.gender_char)

    def test_partner_name_includes_addl_name(self):
        subscriber = self._create(identifier="PID-S2", addl_name="Reyes")
        self.assertEqual(subscriber.partner_name, "Santos, Ana Reyes")

    def test_create_links_existing_partner(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Santos, Ana",
                "family_name": "Santos",
                "given_name": "Ana",
            }
        )
        subscriber = self._create(identifier="PID-S3")
        self.assertEqual(subscriber.partner_id, partner)

    def test_person_identifier_unique(self):
        self._create(identifier="PID-DUP")
        with self.assertRaises((ValidationError, UniqueViolation)), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._create(identifier="PID-DUP", family_name="Other", given_name="Person")
                self.env.flush_all()

    def test_get_attendance_list_filters(self):
        subscriber = self._create(identifier="PID-S4")
        att_type = self.env["spp.attendance.type"].create({"name": "Session"})
        self.env["spp.attendance.list"].create(
            [
                {
                    "subscriber_id": subscriber.id,
                    "attendance_date": "2026-08-01",
                    "attendance_time": "08:00:00",
                    "attendance_type_id": att_type.id,
                    "submitted_by": "seed",
                },
                {
                    "subscriber_id": subscriber.id,
                    "attendance_date": "2026-08-05",
                    "attendance_time": "08:00:00",
                    "attendance_category": "absent",
                    "submitted_by": "seed",
                },
            ]
        )

        total, record = subscriber.get_attendance_list()
        self.assertEqual(total, 2)
        self.assertEqual(record["person_id"], "PID-S4")
        self.assertEqual(record["number_of_days_present"], 1)

        total, _record = subscriber.get_attendance_list(attendance_type_id=att_type.id)
        self.assertEqual(total, 1)

        total, _record = subscriber.get_attendance_list(from_date="2026-08-02", to_date="2026-08-31")
        self.assertEqual(total, 1)

    def test_subscriber_info_uses_external_identifier(self):
        subscriber = self._create(identifier="PID-S5")
        info = subscriber.get_attendance_subscriber_info()
        self.assertEqual(info["id"], "PID-S5", "public id must be the person identifier, not the DB id")
        self.assertEqual(info["person_id"], "PID-S5")
        self.assertEqual(info["name"], "Santos, Ana")
