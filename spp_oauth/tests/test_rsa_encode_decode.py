import uuid

from ..tools.rsa_encode_decode import (
    calculate_signature,
    get_private_key,
    get_public_key,
    verify_and_decode_signature,
)
from .common import Common


class TestRSA(Common):
    def test_get_private_key(self):
        self.set_parameters()

        private_key = get_private_key(self.env)
        self.assertIsNotNone(private_key)

    def test_get_public_key(self):
        self.set_parameters()

        public_key = get_public_key(self.env)
        self.assertIsNotNone(public_key)

    def test_calculate_signature(self):
        self.set_parameters()

        openapi_token = str(uuid.uuid4())

        token = calculate_signature(
            env=self.env,
            header=None,
            payload={
                "database": self.env.cr.dbname,
                "token": openapi_token,
            },
        )
        self.assertIsNotNone(token)

    def test_verify_and_decode_signature(self):
        self.set_parameters()

        openapi_token = str(uuid.uuid4())

        token = calculate_signature(
            env=self.env,
            header=None,
            payload={
                "database": self.env.cr.dbname,
                "token": openapi_token,
            },
        )
        self.assertIsNotNone(token)

        decoded = verify_and_decode_signature(
            env=self.env,
            access_token=token,
        )
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.get("database"), self.env.cr.dbname)
        self.assertEqual(decoded.get("token"), openapi_token)
