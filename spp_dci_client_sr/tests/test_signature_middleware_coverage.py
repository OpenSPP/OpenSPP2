# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Additional coverage for middleware/signature.py.

The existing tests cover most branches. The outer ``except Exception`` catch-all
is triggered when a non-HTTPException escapes the inner code — e.g. when
``verifier.verify()`` raises unexpectedly.
"""

import asyncio
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import HTTPException

from .common import SRClientCommon


@tagged("post_install", "-at_install")
class TestSignatureMiddlewareOuterException(SRClientCommon):
    """Cover the outer except Exception in verify_sr_signature."""

    def setUp(self):
        super().setUp()
        self.create_test_sr_sender()

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    async def _verify(self, envelope_data):
        from odoo.addons.spp_dci_client_sr.middleware.signature import verify_sr_signature

        envelope = DCIEnvelope(**envelope_data)
        return await verify_sr_signature(envelope, self.env)

    def test_outer_exception_returns_500(self):
        """When verifier.verify() raises an unexpected RuntimeError, the outer
        handler catches it and responds with HTTP 500 rather than propagating.

        Code path:
          get_verifier() succeeds (inner try passes)
          verifier.verify() raises RuntimeError
          outer except Exception catches it → HTTP 500
        """
        envelope_data = self.create_signed_envelope(
            sender_id=self.test_sender_id,
            receiver_id="sr.client.openspp",
            action="notify",
        )

        # A verifier whose .verify() raises a non-HTTPException.
        mock_verifier = MagicMock()
        mock_verifier.verify = MagicMock(side_effect=RuntimeError("unexpected verify failure"))

        # Patch DCIVerifier so get_verifier() returns mock_verifier.
        # get_verifier() calls: DCIVerifier(algorithm=..., public_key=...)
        # Patching the class makes the call return mock_verifier.
        mock_dci_verifier_cls = MagicMock(return_value=mock_verifier)
        with patch("odoo.addons.spp_dci.services.signing.DCIVerifier", mock_dci_verifier_cls):
            with self.assertRaises(HTTPException) as ctx:
                self._run(self._verify(envelope_data))

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("verification error", ctx.exception.detail.lower())
