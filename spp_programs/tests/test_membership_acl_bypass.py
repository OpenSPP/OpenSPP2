# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security scan finding: "Public raw membership bulk insert bypasses ACLs".

``bulk_create_memberships`` is a public ``@api.model`` method (no leading
underscore), so it is reachable through the web/external RPC layer by any
authenticated user. Its ``skip_duplicates=True`` path runs a raw
``INSERT ... ON CONFLICT`` and its ORM path (program memberships) runs through
``sudo()`` — both bypassing the ORM's ACL checks.

The fix gates ``bulk_create_memberships`` with an explicit
``self.check_access("create")``. These tests assert the secured behaviour:

* a low-privileged user (no create rights) is denied — both via the ORM and
  via the bulk helper;
* a user that *does* have create rights can still use the helper.
"""

import uuid

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMembershipAclBypass(TransactionCase):
    def setUp(self):
        super().setUp()
        # Data created as the test admin.
        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})
        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        self.partner = self.env["res.partner"].create({"name": "Beneficiary", "is_registrant": True})

        # A plain internal user with NO spp_programs access groups: it holds
        # none of the ir.model.access rights on spp.cycle.membership /
        # spp.program.membership, so create() must be denied for it.
        self.low_priv_user = self.env["res.users"].create(
            {
                "name": "Low Priv User",
                "login": f"lowpriv_{uuid.uuid4().hex[:8]}",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        # A user that legitimately may create memberships (officer group grants
        # create on both membership models).
        self.officer_user = self.env["res.users"].create(
            {
                "name": "Officer User",
                "login": f"officer_{uuid.uuid4().hex[:8]}",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("spp_programs.group_programs_officer").id,
                        ],
                    )
                ],
            }
        )

    def test_orm_create_is_denied_for_low_priv_user(self):
        """Control: the low-priv user cannot create a cycle membership via the ORM."""
        with self.assertRaises(AccessError):
            self.env["spp.cycle.membership"].with_user(self.low_priv_user).create(
                {"partner_id": self.partner.id, "cycle_id": self.cycle.id, "state": "enrolled"}
            )

    def test_raw_bulk_insert_enforces_acl(self):
        """The skip_duplicates raw-SQL path must NOT let a low-priv user create rows.

        Before the fix the raw INSERT bypassed ACLs entirely; now
        bulk_create_memberships gates on check_access("create").
        """
        before = self.env["spp.cycle.membership"].sudo().search_count([("cycle_id", "=", self.cycle.id)])

        with self.assertRaises(AccessError):
            self.env["spp.cycle.membership"].with_user(self.low_priv_user).bulk_create_memberships(
                [{"partner_id": self.partner.id, "cycle_id": self.cycle.id, "state": "enrolled"}],
                skip_duplicates=True,
            )

        after = self.env["spp.cycle.membership"].sudo().search_count([("cycle_id", "=", self.cycle.id)])
        self.assertEqual(after, before, "raw bulk insert created a row despite the user lacking create rights")

    def test_program_membership_bulk_enforces_acl(self):
        """The program-membership ORM path (which uses sudo()) must also be gated."""
        before = self.env["spp.program.membership"].sudo().search_count([("program_id", "=", self.program.id)])

        with self.assertRaises(AccessError):
            self.env["spp.program.membership"].with_user(self.low_priv_user).bulk_create_memberships(
                [{"partner_id": self.partner.id, "program_id": self.program.id, "state": "enrolled"}],
            )

        after = self.env["spp.program.membership"].sudo().search_count([("program_id", "=", self.program.id)])
        self.assertEqual(after, before, "bulk helper created a row despite the user lacking create rights")

    def test_privileged_user_can_still_bulk_create(self):
        """A user with create rights can still use the bulk helper (no regression)."""
        count = (
            self.env["spp.cycle.membership"]
            .with_user(self.officer_user)
            .bulk_create_memberships(
                [{"partner_id": self.partner.id, "cycle_id": self.cycle.id, "state": "enrolled"}],
                skip_duplicates=True,
            )
        )
        self.assertEqual(count, 1, "officer with create rights should be able to bulk-create memberships")
