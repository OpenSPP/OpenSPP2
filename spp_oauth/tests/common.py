from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from odoo.tests import TransactionCase


class Common(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("spp_oauth.oauth_priv_key", None)
        cls.env["ir.config_parameter"].sudo().set_param("spp_oauth.oauth_pub_key", None)

    def set_parameters(self):
        # Generate test RSA keys
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()

        self.env["ir.config_parameter"].sudo().set_param(
            "spp_oauth.oauth_priv_key",
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("utf-8"),
        )

        self.env["ir.config_parameter"].sudo().set_param(
            "spp_oauth.oauth_pub_key",
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8"),
        )
