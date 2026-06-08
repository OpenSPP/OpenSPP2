# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Normalize spp.dci.sr.sender.algorithm values to lowercase.

Earlier versions stored 'Ed25519' / 'RSA-SHA256' / 'ES256'. These do not match
the lowercase identifiers expected by DCIVerifier or by the other DCI sender
models, so signature verification always failed. ES256 is dropped because the
verifier does not implement it; affected rows are reset to the default
('ed25519') and a warning is logged so operators can re-key them.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE spp_dci_sr_sender
        SET algorithm = 'ed25519'
        WHERE algorithm = 'Ed25519'
        """
    )
    cr.execute(
        """
        UPDATE spp_dci_sr_sender
        SET algorithm = 'rs256'
        WHERE algorithm = 'RSA-SHA256'
        """
    )

    cr.execute(
        """
        SELECT id, name, sender_id FROM spp_dci_sr_sender
        WHERE algorithm = 'ES256'
        """
    )
    es256_rows = cr.fetchall()
    if es256_rows:
        for row_id, name, sender_id in es256_rows:
            _logger.warning(
                "spp.dci.sr.sender id=%s (name=%r, sender_id=%r) used ES256, "
                "which is not supported. Reset to 'ed25519'; re-key this "
                "sender to restore signature verification.",
                row_id,
                name,
                sender_id,
            )
        cr.execute(
            """
            UPDATE spp_dci_sr_sender
            SET algorithm = 'ed25519'
            WHERE algorithm = 'ES256'
            """
        )
