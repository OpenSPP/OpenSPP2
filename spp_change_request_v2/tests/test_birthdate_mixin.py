# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The shared birthdate guard on change request detail models.

``spp.cr.birthdate.mixin`` mirrors the registry's
``_check_birthdate_not_future`` so a future date of birth is refused while
the change request is being filled in, rather than at apply time — where it
would roll back the whole approval and report an error the approver cannot
trace back to a field.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .common import get_or_create_cr_type


@tagged("post_install", "-at_install")
class TestBirthdateMixin(TransactionCase):
    """spp_change_request_v2/models/birthdate_mixin.py"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.CR = cls.env["spp.change.request"]
        cls.individual = cls.Partner.create({"name": "Mixin Subject", "is_registrant": True, "is_group": False})
        cls.group = cls.Partner.create({"name": "Mixin Household", "is_registrant": True, "is_group": True})

    def setUp(self):
        super().setUp()
        # Mirror the constraint, which compares against the user's today.
        self.today = fields.Date.context_today(self.individual)
        self.future = self.today + timedelta(days=1)

    def _detail(self, code, registrant):
        cr = self.CR.create(
            {
                "request_type_id": get_or_create_cr_type(self.env, code).id,
                "registrant_id": registrant.id,
            }
        )
        return cr.get_detail()

    def test_edit_individual_future_birthdate_rejected(self):
        """The guard fires at data entry, not at apply time."""
        detail = self._detail("edit_individual", self.individual)
        with self.assertRaisesRegex(ValidationError, "Date of birth cannot be in the future"):
            detail.write({"birthdate": self.future})

    def test_edit_individual_today_allowed(self):
        """birthdate == today is the boundary that must pass."""
        detail = self._detail("edit_individual", self.individual)
        detail.write({"birthdate": self.today})
        self.assertEqual(detail.birthdate, self.today)

    def test_add_member_future_birthdate_rejected(self):
        detail = self._detail("add_member", self.group)
        with self.assertRaisesRegex(ValidationError, "Date of birth cannot be in the future"):
            detail.write({"birthdate": self.future})

    def test_create_group_new_member_future_birthdate_rejected(self):
        """The sub-model reached through the wizard is guarded too."""
        detail = self._detail("create_group", self.group)
        with self.assertRaisesRegex(ValidationError, "Date of birth cannot be in the future"):
            detail.write(
                {
                    "member_new_ids": [
                        (
                            0,
                            0,
                            {
                                "given_name": "Ada",
                                "family_name": "Lovelace",
                                "birthdate": self.future,
                            },
                        )
                    ]
                }
            )
