# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Response Signing Service.

Signs outbound DCI responses, callbacks, and notifications using the server's
active signing key.
"""

import logging

_logger = logging.getLogger(__name__)


class DCIResponseSigner:
    """Signs DCI server responses using active server key.

    This service loads the active server signing key and signs outbound
    envelopes (responses, callbacks, notifications) using the DCISigner
    from spp_dci.
    """

    def __init__(self, env):
        """Initialize response signer.

        Args:
            env: Odoo environment
        """
        self.env = env

    def sign_envelope(self, header: dict, message: dict) -> str:
        """Sign a DCI envelope with the active server key.

        Args:
            header: DCI message header dict
            message: DCI message body dict

        Returns:
            str: Signature header string

        Raises:
            UserError: If no active key is found or signing fails
        """
        # Get active server key
        ServerKey = self.env["spp.dci.server.key"]
        active_key = ServerKey.get_active_key()

        # Get signer instance from key
        signer = active_key.get_signer()

        # Sign the envelope
        signature = signer.sign(header, message)

        _logger.debug(
            "Signed envelope with key_id=%s for action=%s",
            active_key.key_id,
            header.get("action"),
        )

        return signature
