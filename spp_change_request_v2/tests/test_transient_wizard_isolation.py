# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: the Create-Group member wizards must be scoped to their owner.

``spp.cr.detail.create_group.member.wizard`` and its ``.phone`` / ``.bank``
children are ``TransientModel``s carrying proposed-member PII -- given name,
family name, birthdate, birth place, phone numbers and bank account numbers.
Their ACL grants ``group_cr_user`` full read/write/create/unlink and no
``ir.rule`` covers them, so one change-request user can reach another's rows.

The ``TransientModel`` docstring claims users "may only access the records they
created", but that behaviour is not implemented anywhere in Odoo 19:
``ir.rule._compute_domain`` has no transient branch, so a transient model with
no rule resolves to ``Domain.TRUE``. Transience only bounds the exposure
window -- the vacuum keeps rows for ``transient_age_limit`` (1 hour by default)
and never removes rows touched in the last five minutes.
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import CRTestCase, get_or_create_cr_type

_WIZARD = "spp.cr.detail.create_group.member.wizard"


@tagged("post_install", "-at_install")
class TestTransientWizardIsolation(CRTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_group = cls.env.ref("base.group_user")
        cls.user_group = cls.env.ref("spp_change_request_v2.group_cr_user")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.owner = Users.create(
            {
                "name": "Wizard Owner",
                "login": "cr_wizard_owner",
                "email": "cr_wizard_owner@test.com",
                "group_ids": [(4, cls.internal_group.id), (4, cls.user_group.id)],
            }
        )
        cls.other = Users.create(
            {
                "name": "Wizard Other",
                "login": "cr_wizard_other",
                "email": "cr_wizard_other@test.com",
                "group_ids": [(4, cls.internal_group.id), (4, cls.user_group.id)],
            }
        )
        cls.create_group_type = get_or_create_cr_type(cls.env, "create_group")

    def setUp(self):
        super().setUp()
        cr = self.CR.with_user(self.owner).create(
            {
                "request_type_id": self.create_group_type.id,
                "registrant_id": self.test_group.id,
            }
        )
        detail = cr.with_user(self.owner).get_detail()
        self.wizard = (
            self.env[_WIZARD]
            .with_user(self.owner)
            .create(
                {
                    "detail_id": detail.id,
                    "mode": "new",
                    "given_name": "Confidential",
                    "family_name": "Applicant",
                    "birthdate": "1990-01-01",
                    "birth_place": "Undisclosed",
                }
            )
        )
        self.phone = (
            self.env[f"{_WIZARD}.phone"]
            .with_user(self.owner)
            .create({"wizard_id": self.wizard.id, "phone_no": "09180000001"})
        )
        self.bank = (
            self.env[f"{_WIZARD}.bank"]
            .with_user(self.owner)
            .create({"wizard_id": self.wizard.id, "acc_number": "SECRET-ACCT-0001"})
        )

    # ------------------------------------------------------------------
    # Enumeration
    # ------------------------------------------------------------------

    def test_other_user_cannot_search_foreign_wizard(self):
        """A second cr_user must not enumerate another user's wizard rows."""
        found = self.env[_WIZARD].with_user(self.other).search([])
        self.assertNotIn(
            self.wizard.id,
            found.ids,
            "another change-request user enumerated a wizard row they do not own "
            "(no ir.rule scopes the transient wizard to its creator)",
        )

    def test_other_user_cannot_search_foreign_wizard_children(self):
        """Phone and bank child rows must not be enumerable either."""
        phones = self.env[f"{_WIZARD}.phone"].with_user(self.other).search([])
        self.assertNotIn(self.phone.id, phones.ids, "foreign wizard phone row was enumerable")
        banks = self.env[f"{_WIZARD}.bank"].with_user(self.other).search([])
        self.assertNotIn(self.bank.id, banks.ids, "foreign wizard bank row was enumerable")

    # ------------------------------------------------------------------
    # Direct access by id
    # ------------------------------------------------------------------

    def test_other_user_cannot_read_foreign_wizard_pii(self):
        with self.assertRaises(
            AccessError,
            msg="another change-request user read proposed-member PII from a wizard they do not own",
        ):
            self.wizard.with_user(self.other).read(["given_name", "family_name", "birthdate"])

    def test_other_user_cannot_read_foreign_bank_account(self):
        with self.assertRaises(
            AccessError,
            msg="another change-request user read a proposed member's bank account number",
        ):
            self.bank.with_user(self.other).read(["acc_number"])

    # ------------------------------------------------------------------
    # Tampering -- the ACL grants write and unlink to group_cr_user
    # ------------------------------------------------------------------

    def test_other_user_cannot_write_foreign_wizard(self):
        with self.assertRaises(
            AccessError,
            msg="another change-request user overwrote a wizard row they do not own",
        ):
            self.wizard.with_user(self.other).write({"given_name": "Tampered"})

    def test_other_user_cannot_unlink_foreign_wizard(self):
        with self.assertRaises(
            AccessError,
            msg="another change-request user deleted a wizard row they do not own",
        ):
            self.wizard.with_user(self.other).unlink()

    # ------------------------------------------------------------------
    # The owner keeps working
    # ------------------------------------------------------------------

    def test_owner_retains_full_access(self):
        """Scoping must not cage the creator out of their own wizard."""
        self.assertIn(self.wizard.id, self.env[_WIZARD].with_user(self.owner).search([]).ids)
        self.wizard.with_user(self.owner).write({"given_name": "Updated"})
        self.assertEqual(self.wizard.with_user(self.owner).read(["given_name"])[0]["given_name"], "Updated")
