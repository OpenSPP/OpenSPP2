# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Storage backend credentials must not be readable by ordinary internal users.

The model stores S3 access/secret keys and Azure connection strings. Ordinary
`base.group_user` users get model read access (to resolve/use a backend), but
must never be able to read the raw credentials over RPC/`read`/`search_read`.
Only storage administrators (and trusted server-side `sudo()` flows, e.g. the
S3/Azure client builders) may resolve the credential values.
"""

import sys
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

S3_SECRET = "super-secret-s3-key"
S3_ACCESS = "super-access-s3-id"
AZURE_CONN = "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=SECRETKEY==;"
CRED_FIELDS = ("s3_access_key", "s3_secret_key", "azure_connection_string")


@tagged("post_install", "-at_install")
class TestStorageCredentialAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Backend = cls.env["spp.storage.backend"]
        cls.s3_backend = Backend.create(
            {
                "name": "S3 Cred Backend",
                "backend_type": "s3",
                "s3_bucket": "bucket",
                "s3_access_key": S3_ACCESS,
                "s3_secret_key": S3_SECRET,
                "s3_region": "us-east-1",
            }
        )
        cls.azure_backend = Backend.create(
            {
                "name": "Azure Cred Backend",
                "backend_type": "azure",
                "azure_connection_string": AZURE_CONN,
                "azure_container": "container",
            }
        )
        cls.base_user = cls.env["res.users"].create(
            {
                "name": "Plain Internal User",
                "login": "storage_plain_user",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.storage_admin = cls.env["res.users"].create(
            {
                "name": "Storage Admin User",
                "login": "storage_admin_user",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("spp_storage_backend.group_storage_admin").id,
                        ],
                    )
                ],
            }
        )

    def _read_field(self, backend, user, field):
        """Return the field value as seen by `user`, or None if blocked."""
        try:
            return backend.with_user(user).read([field])[0].get(field)
        except AccessError:
            return None

    # --- credentials hidden from ordinary users -----------------------

    def test_base_user_cannot_read_s3_secret(self):
        self.assertNotEqual(
            self._read_field(self.s3_backend, self.base_user, "s3_secret_key"),
            S3_SECRET,
            "base.group_user must not be able to read s3_secret_key",
        )

    def test_base_user_cannot_read_s3_access_key(self):
        self.assertNotEqual(
            self._read_field(self.s3_backend, self.base_user, "s3_access_key"),
            S3_ACCESS,
        )

    def test_base_user_cannot_read_azure_connection_string(self):
        self.assertNotEqual(
            self._read_field(self.azure_backend, self.base_user, "azure_connection_string"),
            AZURE_CONN,
        )

    def test_base_user_search_read_explicit_credentials_denied(self):
        # Explicitly requesting a restricted field over RPC raises AccessError.
        with self.assertRaises(AccessError):
            self.env["spp.storage.backend"].with_user(self.base_user).search_read([], list(CRED_FIELDS))

    def test_base_user_default_read_excludes_credentials(self):
        # Reading the accessible fields must not surface the credentials.
        rows = self.env["spp.storage.backend"].with_user(self.base_user).search_read([])
        self.assertTrue(rows)
        for row in rows:
            for field in CRED_FIELDS:
                self.assertNotIn(field, row, f"{field} leaked via default search_read")

    def test_credential_fields_are_group_restricted(self):
        info = self.env["spp.storage.backend"].fields_get(list(CRED_FIELDS))
        for field in CRED_FIELDS:
            self.assertTrue(
                info[field].get("groups"),
                f"{field} must carry a field-level groups restriction",
            )

    # --- admins and trusted flows can still resolve them --------------

    def test_storage_admin_can_read_credentials(self):
        self.assertEqual(
            self._read_field(self.s3_backend, self.storage_admin, "s3_secret_key"),
            S3_SECRET,
        )
        self.assertEqual(
            self._read_field(self.azure_backend, self.storage_admin, "azure_connection_string"),
            AZURE_CONN,
        )

    def test_s3_client_builder_resolves_credentials_for_non_admin(self):
        """The S3 client is built server-side with the real credentials even
        when the operating user cannot read them (use-without-see via sudo)."""
        fake_boto3 = MagicMock()
        with patch.dict(sys.modules, {"boto3": fake_boto3}):
            self.s3_backend.with_user(self.base_user)._get_s3_client()
        _, kwargs = fake_boto3.client.call_args
        self.assertEqual(kwargs.get("aws_secret_access_key"), S3_SECRET)
        self.assertEqual(kwargs.get("aws_access_key_id"), S3_ACCESS)

    def test_azure_client_builder_resolves_credentials_for_non_admin(self):
        fake_module = MagicMock()
        mods = {"azure": MagicMock(), "azure.storage": MagicMock(), "azure.storage.blob": fake_module}
        with patch.dict(sys.modules, mods):
            self.azure_backend.with_user(self.base_user)._get_azure_client()
        args, _ = fake_module.BlobServiceClient.from_connection_string.call_args
        self.assertEqual(args[0], AZURE_CONN)
