# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Deduplicate data before adding SQL UNIQUE constraints.

    Removes duplicate rows using ROW_NUMBER() OVER (PARTITION BY ...),
    keeping the earliest record (lowest id) for each unique combination.
    """
    if not version:
        return

    _deduplicate_program_memberships(cr)
    _deduplicate_cycle_memberships(cr)
    _deduplicate_entitlement_codes(cr)


def _deduplicate_program_memberships(cr):
    """Remove duplicate (partner_id, program_id) rows from spp_program_membership."""
    cr.execute(
        """
        DELETE FROM spp_program_membership
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY partner_id, program_id
                           ORDER BY id
                       ) AS rn
                FROM spp_program_membership
            ) sub
            WHERE rn > 1
        )
        """
    )
    if cr.rowcount:
        _logger.info("Deduplicated %d duplicate program membership rows", cr.rowcount)


def _deduplicate_cycle_memberships(cr):
    """Remove duplicate (partner_id, cycle_id) rows from spp_cycle_membership."""
    cr.execute(
        """
        DELETE FROM spp_cycle_membership
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY partner_id, cycle_id
                           ORDER BY id
                       ) AS rn
                FROM spp_cycle_membership
            ) sub
            WHERE rn > 1
        )
        """
    )
    if cr.rowcount:
        _logger.info("Deduplicated %d duplicate cycle membership rows", cr.rowcount)


def _deduplicate_entitlement_codes(cr):
    """Remove duplicate code values from spp_entitlement.

    For duplicate codes, regenerates codes for the newer records rather
    than deleting them, since entitlements may have financial significance.
    """
    cr.execute(
        """
        UPDATE spp_entitlement
        SET code = code || '-' || id::text
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY code
                           ORDER BY id
                       ) AS rn
                FROM spp_entitlement
                WHERE code IS NOT NULL
            ) sub
            WHERE rn > 1
        )
        """
    )
    if cr.rowcount:
        _logger.info("Deduplicated %d entitlement rows with duplicate codes", cr.rowcount)
