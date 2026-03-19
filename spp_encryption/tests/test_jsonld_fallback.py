# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from pyld import jsonld

from odoo.tests.common import TransactionCase


class JSONLDFallbackTest(TransactionCase):
    def setUp(self):
        super().setUp()
        self.provider = self.env.ref("spp_encryption.encryption_provider_default")
        if not self.provider.type:
            self.provider.write({"type": "jwcrypto"})
        if not self.provider.jwcrypto_key:
            self.provider.generate_and_store_jwcrypto_key()

    def _raise_remote_context(self, *args, **kwargs):  # pragma: no cover - helper
        raise jsonld.JsonLdError("loading remote context failed")

    def test_jsonld_fallback_allowed(self):
        self.env["ir.config_parameter"].sudo().set_param("spp.vc.allow_jsonld_fallback", True)
        credential = {
            "@context": ["https://w3id.org/security/v2"],
            "type": ["VerifiableCredential"],
            "issuer": "did:web:test",
        }
        with patch("pyld.jsonld.normalize", side_effect=self._raise_remote_context):
            result = self.provider._sign_credential_ld_proof_default(credential)
        self.assertIn("proof", result)

    def test_jsonld_fallback_disallowed(self):
        self.env["ir.config_parameter"].sudo().set_param("spp.vc.allow_jsonld_fallback", False)
        credential = {
            "@context": ["https://w3id.org/security/v2"],
            "type": ["VerifiableCredential"],
            "issuer": "did:web:test",
        }
        with patch("pyld.jsonld.normalize", side_effect=self._raise_remote_context):
            with self.assertRaises(jsonld.JsonLdError):
                self.provider._sign_credential_ld_proof_default(credential)

    def test_jsonld_local_cache_without_fallback(self):
        """When remote fails but local context exists, normalization should still work with fallback disabled."""
        self.env["ir.config_parameter"].sudo().set_param("spp.vc.allow_jsonld_fallback", False)
        credential = {
            "@context": ["https://w3id.org/security/v2"],
            "type": ["VerifiableCredential"],
            "issuer": "did:web:test",
        }

        calls = [
            jsonld.JsonLdError("loading remote context failed"),
            # second call uses the real normalize
        ]

        def side_effect(*args, **kwargs):
            if calls:
                exc = calls.pop(0)
                if isinstance(exc, Exception):
                    raise exc
            return jsonld.normalize(*args, **kwargs)

        with patch("pyld.jsonld.normalize", side_effect=side_effect):
            result = self.provider._sign_credential_ld_proof_default(credential)
        self.assertIn("proof", result)
