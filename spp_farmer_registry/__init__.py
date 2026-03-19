# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from . import controllers
from . import models


def pre_init_hook(env):
    """Create spp.farm.details records for existing partners before NOT NULL constraint.

    The _inherits delegation to spp.farm.details requires farm_details_id to be
    NOT NULL on res_partner. Existing partner rows created before this module
    was installed will have NULL, causing the constraint to fail. This hook
    backfills those rows.
    """
    cr = env.cr
    # Check if farm_details_id column already exists on res_partner
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'res_partner' AND column_name = 'farm_details_id'
        """
    )
    if not cr.fetchone():
        return  # Column doesn't exist yet, ORM will create it with proper defaults

    # Backfill: create spp.farm.details for partners missing one
    cr.execute(
        """
        WITH new_details AS (
            INSERT INTO spp_farm_details (create_uid, create_date, write_uid, write_date)
            SELECT 1, now() at time zone 'UTC', 1, now() at time zone 'UTC'
            FROM res_partner WHERE farm_details_id IS NULL
            RETURNING id
        ),
        numbered AS (
            SELECT id, ROW_NUMBER() OVER () AS rn FROM new_details
        ),
        partners AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS rn
            FROM res_partner WHERE farm_details_id IS NULL
        )
        UPDATE res_partner SET farm_details_id = numbered.id
        FROM numbered JOIN partners ON numbered.rn = partners.rn
        WHERE res_partner.id = partners.id
        """
    )
