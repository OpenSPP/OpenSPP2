# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The shipped CR roles must not grant privileges above their own tier.

A role that links a group far above its stated tier is invisible in the group
definitions — the hierarchy looks correct — yet it silently hands every holder
the higher tier's rights, and it defeats any authorisation check written as
``has_group(<higher group>)``. The CR Requestor role linked
``group_cr_manager``, which implies ``group_cr_validator`` and through it
``spp_approval.group_approval_approver``.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCRRoleTiers(TransactionCase):
    def _role(self, xmlid):
        return self.env.ref(f"spp_change_request_v2.{xmlid}")

    def _granted(self, role):
        """Every group a holder of this role ends up with (transitive closure)."""
        groups = role.implied_ids
        return groups | groups.all_implied_ids

    def test_requestor_role_does_not_grant_manager(self):
        """A requestor creates and submits; it must not be able to approve or delete."""
        granted = self._granted(self._role("global_role_cr_requestor"))

        manager = self.env.ref("spp_change_request_v2.group_cr_manager")
        self.assertNotIn(
            manager,
            granted,
            "CR Requestor must not grant the change-request manager group: it carries "
            "approval rights and model-wide unlink, and it defeats manager-gated "
            "authorisation checks.",
        )

        approver = self.env.ref("spp_approval.group_approval_approver", raise_if_not_found=False)
        if approver:
            self.assertNotIn(
                approver,
                granted,
                "CR Requestor must not grant approval-approver rights — a requestor "
                "could otherwise approve change requests, including their own.",
            )

    def test_requestor_role_still_grants_its_own_tier(self):
        """The de-escalation must not leave requestors unable to do their job."""
        granted = self._granted(self._role("global_role_cr_requestor"))
        self.assertIn(
            self.env.ref("spp_change_request_v2.group_cr_user"),
            granted,
            "CR Requestor must still grant the change-request user group.",
        )

    def test_validator_roles_do_not_grant_manager(self):
        """Validators approve; only managers administer. Pins the same class for them."""
        manager = self.env.ref("spp_change_request_v2.group_cr_manager")
        for xmlid in ("local_role_cr_validator", "global_role_cr_validator_hq"):
            with self.subTest(role=xmlid):
                self.assertNotIn(
                    manager,
                    self._granted(self._role(xmlid)),
                    f"{xmlid} must not grant the change-request manager group.",
                )
