# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from .common import get_or_create_cr_type


@tagged("post_install", "-at_install")
class TestReasonDocumentConstraint(TransactionCase):
    """Test that the (cr_type_id, reason) uniqueness of spp.cr.type.reason.document
    is enforced at the database level (#394).

    The rule was originally declared with the legacy ``_sql_constraints``
    attribute, which Odoo 19 ignores entirely — the constraint was never
    created, so duplicate rules could be saved silently.
    """

    def setUp(self):
        super().setUp()
        self.cr_type = get_or_create_cr_type(self.env, "change_hoh")

    def test_reason_document_unique_constraint_exists(self):
        """SQL UNIQUE constraint on (cr_type_id, reason) must exist."""
        self.env.cr.execute(
            """
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'spp_cr_type_reason_document'::regclass
              AND contype = 'u'
              AND conkey @> ARRAY[
                  (SELECT attnum FROM pg_attribute
                   WHERE attrelid = 'spp_cr_type_reason_document'::regclass
                     AND attname = 'cr_type_id'),
                  (SELECT attnum FROM pg_attribute
                   WHERE attrelid = 'spp_cr_type_reason_document'::regclass
                     AND attname = 'reason')
              ]
            """
        )
        self.assertTrue(
            self.env.cr.fetchone(),
            "UNIQUE constraint on (cr_type_id, reason) must exist on spp_cr_type_reason_document",
        )

    def test_duplicate_reason_rule_blocked(self):
        """Inserting a duplicate (cr_type_id, reason) rule must raise IntegrityError."""
        self.env["spp.cr.type.reason.document"].create(
            {
                "cr_type_id": self.cr_type.id,
                "reason": "deceased",
            }
        )
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    """
                    INSERT INTO spp_cr_type_reason_document
                        (cr_type_id, reason,
                         create_uid, write_uid, create_date, write_date)
                    VALUES (%s, 'deceased', %s, %s, now(), now())
                    """,
                    (
                        self.cr_type.id,
                        self.env.uid,
                        self.env.uid,
                    ),
                )

    def test_different_reasons_allowed(self):
        """Different reasons on the same CR type must be allowed."""
        self.env["spp.cr.type.reason.document"].create(
            {
                "cr_type_id": self.cr_type.id,
                "reason": "deceased",
            }
        )
        rule2 = self.env["spp.cr.type.reason.document"].create(
            {
                "cr_type_id": self.cr_type.id,
                "reason": "incapacitated",
            }
        )
        self.assertTrue(rule2.id)

    def test_same_reason_different_types_allowed(self):
        """The same reason on different CR types must be allowed."""
        other_type = get_or_create_cr_type(self.env, "remove_member")
        self.env["spp.cr.type.reason.document"].create(
            {
                "cr_type_id": self.cr_type.id,
                "reason": "deceased",
            }
        )
        rule2 = self.env["spp.cr.type.reason.document"].create(
            {
                "cr_type_id": other_type.id,
                "reason": "deceased",
            }
        )
        self.assertTrue(rule2.id)

    def test_no_legacy_sql_constraints_attribute(self):
        """The model must not carry the legacy _sql_constraints attribute,
        which Odoo 19 ignores (it only logs a warning at registry load)."""
        model_cls = type(self.env["spp.cr.type.reason.document"])
        self.assertFalse(
            hasattr(model_cls, "_sql_constraints"),
            "spp.cr.type.reason.document must define models.Constraint, not _sql_constraints",
        )
