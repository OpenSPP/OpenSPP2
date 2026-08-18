# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import AttendanceFixtureMixin


@tagged("post_install", "-at_install")
class TestClientCredentials(AttendanceFixtureMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_oauth_keys()

    def _create(self, name="Cred"):
        return self.env["spp.attendance.api.client.credential"].create({"name": name})

    def test_create_stores_hash_and_transient_plaintext(self):
        credential = self._create()
        self.assertTrue(credential.client_id.startswith("c-id-"))
        self.assertTrue(credential.client_secret.startswith("c-secret-"))
        self.assertTrue(credential.client_secret_hash.startswith("$scrypt$"))
        self.assertNotIn(credential.client_secret, credential.client_secret_hash)

    def test_authenticate_success_and_failure(self):
        credential = self._create()
        plaintext = credential.client_secret
        Model = self.env["spp.attendance.api.client.credential"]

        self.assertEqual(Model.authenticate(credential.client_id, plaintext), credential)
        self.assertFalse(Model.authenticate(credential.client_id, "wrong-secret"))
        self.assertFalse(Model.authenticate("no-such-client", plaintext))
        self.assertFalse(Model.authenticate(credential.client_id, ""))

    def test_verify_secret_rejects_malformed_hashes(self):
        Model = self.env["spp.attendance.api.client.credential"]
        self.assertFalse(Model._verify_secret("secret", ""))
        self.assertFalse(Model._verify_secret("secret", "not-a-hash"))
        self.assertFalse(Model._verify_secret("secret", "$md5$abc$def"))
        self.assertFalse(Model._verify_secret("secret", "$scrypt$!!!$!!!"))

    def test_show_credentials_scrubs_plaintext_and_is_once(self):
        credential = self._create()
        plaintext = credential.client_secret

        action = credential.show_credentials()
        wizard = self.env["spp.attendance.show.credential.wizard"].browse(action["res_id"])
        self.assertEqual(wizard.display_client_secret, plaintext)
        self.assertEqual(wizard.display_client_id, credential.client_id)

        # plaintext scrubbed before the dialog even renders
        self.assertFalse(credential.client_secret)
        self.assertTrue(credential.show_button_clicked)

        # authentication still works against the hash
        Model = self.env["spp.attendance.api.client.credential"]
        self.assertEqual(Model.authenticate(credential.client_id, plaintext), credential)

        with self.assertRaises(UserError):
            credential.show_credentials()

    def test_regenerate_rotates_secret_without_storing_plaintext(self):
        credential = self._create()
        old_plaintext = credential.client_secret
        credential.show_credentials()

        action = credential.action_regenerate_secret()
        wizard = self.env["spp.attendance.show.credential.wizard"].browse(action["res_id"])
        new_plaintext = wizard.display_client_secret

        self.assertNotEqual(new_plaintext, old_plaintext)
        self.assertFalse(credential.client_secret, "regeneration must not store plaintext")

        Model = self.env["spp.attendance.api.client.credential"]
        self.assertEqual(Model.authenticate(credential.client_id, new_plaintext), credential)
        self.assertFalse(Model.authenticate(credential.client_id, old_plaintext))

    def test_export_blocked(self):
        credential = self._create()
        with self.assertRaises(UserError):
            credential.export_data(["client_id"])

    def test_generate_access_token_is_verifiable(self):
        from odoo.addons.spp_oauth.tools import verify_and_decode_signature

        token = self.env["spp.attendance.api.client.credential"].generate_access_token()
        payload = verify_and_decode_signature(self.env, token.encode())
        self.assertEqual(payload.get("iss"), "openspp:auth-service")

    def test_migration_hashes_existing_plaintext(self):
        """The 19.0.2.0.0 migration hashes and scrubs legacy plaintext rows."""
        credential = self._create()
        legacy_secret = "c-secret-legacy-plaintext"
        # Simulate a pre-migration row: plaintext present, no hash
        credential.write({"client_secret": legacy_secret, "client_secret_hash": False})

        import importlib.util
        import os

        script = os.path.join(os.path.dirname(__file__), "..", "migrations", "19.0.2.0.0", "post-migration.py")
        spec = importlib.util.spec_from_file_location("spp_attendance_migration_19_0_2_0_0", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "19.0.1.3.1")

        self.assertFalse(credential.client_secret)
        self.assertTrue(credential.client_secret_hash)
        Model = self.env["spp.attendance.api.client.credential"]
        self.assertEqual(Model.authenticate(credential.client_id, legacy_secret), credential)
