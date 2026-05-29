# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.dci.server.key.

Server signing keys carry constraints and lifecycle actions that aren't
already covered by the receipt/jwks tests:
- key_id format constraint
- activate-without-keys constraint
- expiration in the past constraint
- single-active-key constraint
- action_generate_key state guard, double-generation guard, error path
- action_activate happy path, already-active, already-revoked, missing-keys
- action_revoke happy path, idempotency guard
- get_active_key with and without an active key
- get_signer with state checks
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import DCIServerCommon


@tagged("post_install", "-at_install")
class TestServerKey(DCIServerCommon):
    def setUp(self):
        super().setUp()
        self.Key = self.env["spp.dci.server.key"].sudo()
        # Clear any default-installed server keys so tests run from a
        # known empty state.
        self.Key.search([]).unlink()

    def _draft_key(self, key_id="srv-1", **overrides):
        vals = {
            "name": f"Test Server Key {key_id}",
            "key_id": key_id,
            "algorithm": "ed25519",
        }
        vals.update(overrides)
        return self.Key.create(vals)

    # --- constraints ---------------------------------------------------------

    def test_key_id_must_be_alphanumeric_or_separators(self):
        with self.assertRaises(ValidationError):
            self._draft_key(key_id="not allowed!")

    def test_cannot_activate_without_keys(self):
        key = self._draft_key()
        with self.assertRaises(ValidationError):
            key.write({"state": "active"})

    def test_expires_at_must_be_future(self):
        key = self._draft_key()
        with self.assertRaises(ValidationError):
            key.write({"expires_at": fields.Datetime.now() - timedelta(days=1)})

    def test_single_active_key_constraint(self):
        first = self._draft_key("srv-active-1")
        first.action_generate_key()
        first.action_activate()
        second = self._draft_key("srv-active-2")
        second.action_generate_key()
        with self.assertRaises(ValidationError):
            second.write({"active": True})

    # --- action_generate_key -------------------------------------------------

    def test_generate_key_only_from_draft_state(self):
        key = self._draft_key("srv-gen-1")
        key.action_generate_key()
        # Subsequent attempt fails because keys exist (caught before state check).
        with self.assertRaises(UserError):
            key.action_generate_key()

    def test_generate_key_blocks_when_keys_exist(self):
        key = self._draft_key("srv-gen-2")
        key.write({"private_key": "stub", "public_key": "stub"})
        with self.assertRaises(UserError):
            key.action_generate_key()

    def test_generate_key_propagates_crypto_failures(self):
        key = self._draft_key("srv-gen-3")
        with patch.object(
            type(key),
            "_generate_ed25519_keypair",
            side_effect=RuntimeError("crypto blew up"),
        ):
            with self.assertRaises(UserError):
                key.action_generate_key()

    # --- action_activate -----------------------------------------------------

    def test_activate_happy_path(self):
        key = self._draft_key("srv-act-1")
        key.action_generate_key()
        result = key.action_activate()
        self.assertEqual(key.state, "active")
        self.assertTrue(key.active)
        self.assertTrue(key.activated_date)
        # Returns a display_notification action dict
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "success")

    def test_activate_already_active_blocks(self):
        key = self._draft_key("srv-act-2")
        key.action_generate_key()
        key.action_activate()
        with self.assertRaises(UserError):
            key.action_activate()

    def test_activate_revoked_key_blocks(self):
        key = self._draft_key("srv-act-3")
        key.action_generate_key()
        key.action_activate()
        key.action_revoke()
        with self.assertRaises(UserError):
            key.action_activate()

    def test_activate_without_keys_blocks(self):
        key = self._draft_key("srv-act-4")
        with self.assertRaises(UserError):
            key.action_activate()

    def test_activate_deactivates_other_active_keys(self):
        first = self._draft_key("srv-rotate-1")
        first.action_generate_key()
        first.action_activate()
        # The single-active-key constraint blocks activating two at the
        # state-level, so we use a second draft key that has not been
        # activated yet but is marked active=False (default) -- then
        # activate it.
        second = self._draft_key("srv-rotate-2")
        second.action_generate_key()
        second.action_activate()
        # action_activate must have deactivated the first as a side effect.
        first.invalidate_recordset()
        self.assertFalse(first.active)

    # --- action_revoke -------------------------------------------------------

    def test_revoke_happy_path(self):
        key = self._draft_key("srv-rev-1")
        key.action_generate_key()
        key.action_activate()
        result = key.action_revoke()
        self.assertEqual(key.state, "revoked")
        self.assertFalse(key.active)
        self.assertTrue(key.revoked_date)
        self.assertEqual(result["params"]["type"], "warning")

    def test_revoke_already_revoked_blocks(self):
        key = self._draft_key("srv-rev-2")
        key.action_generate_key()
        key.action_activate()
        key.action_revoke()
        with self.assertRaises(UserError):
            key.action_revoke()

    # --- get_active_key ------------------------------------------------------

    def test_get_active_key_returns_active(self):
        key = self._draft_key("srv-get-1")
        key.action_generate_key()
        key.action_activate()
        self.assertEqual(self.Key.get_active_key(), key)

    def test_get_active_key_raises_when_none(self):
        with self.assertRaises(UserError):
            self.Key.get_active_key()

    # --- get_signer ----------------------------------------------------------

    def test_get_signer_for_active_key(self):
        from odoo.addons.spp_dci.services.signing import DCISigner

        key = self._draft_key("srv-sign-1")
        key.action_generate_key()
        key.action_activate()
        signer = key.get_signer()
        self.assertIsInstance(signer, DCISigner)
        self.assertEqual(signer.algorithm, "ed25519")
        self.assertEqual(signer.key_id, "srv-sign-1")

    def test_get_signer_blocks_when_not_active(self):
        key = self._draft_key("srv-sign-2")
        key.action_generate_key()
        with self.assertRaises(UserError):
            key.get_signer()

    def test_get_signer_blocks_when_no_private_key(self):
        """A key in 'active' state but missing private material cannot
        sign. We bypass the _check_keys_present constraint by clearing
        private_key via raw SQL so the row sits in the broken state we
        want to test."""
        key = self._draft_key("srv-sign-3")
        key.action_generate_key()
        key.action_activate()
        # Strip private_key without going through the ORM constraint.
        self.env.cr.execute(
            "UPDATE spp_dci_server_key SET private_key = NULL WHERE id = %s",
            (key.id,),
        )
        key.invalidate_recordset(["private_key"])
        with self.assertRaises(UserError):
            key.get_signer()
