# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Park legacy vocabulary-based geofence tag links before the schema swap.

Up to v19.0.2.0.0 (release Biliran), spp.gis.geofence.tag_ids pointed at
spp.vocabulary through spp_gis_geofence_tag_rel. The field now points at the
new spp.gis.geofence.tag model over the SAME rel table. During upgrade the ORM
re-targets the rel table's tag_id foreign key at the new table; legacy rows
referencing vocabulary ids would make that constraint swap fail.

This pre-migration moves legacy rows (with the referenced vocabulary's name)
into an aux table; the matching post-migration recreates them as
spp.gis.geofence.tag links and drops the aux table.

All SQL is literal and value-parameterized; identifiers are never composed.
"""

import logging

_logger = logging.getLogger("odoo.addons.spp_gis.migrations.geofence_tags")

_CREATE_AUX = """
    CREATE TABLE IF NOT EXISTS spp_gis_geofence_tag_legacy_migration (
        geofence_id integer NOT NULL,
        vocab_name varchar NOT NULL
    )
"""

# name is a translated (jsonb) field: prefer en_US, else any value.
_PARK_LEGACY = """
    INSERT INTO spp_gis_geofence_tag_legacy_migration (geofence_id, vocab_name)
    SELECT rel.geofence_id,
           COALESCE(v.name->>'en_US', (SELECT t.value FROM jsonb_each_text(v.name) t LIMIT 1))
    FROM spp_gis_geofence_tag_rel rel
    JOIN spp_vocabulary v ON v.id = rel.tag_id
"""

_DELETE_LEGACY = """
    DELETE FROM spp_gis_geofence_tag_rel rel
    USING spp_vocabulary v
    WHERE v.id = rel.tag_id
"""

# Variants used when the new tag table already exists (migration rerun or
# tests): a row is a valid new-style link if its tag_id exists there; it is
# legacy if it references a vocabulary instead. Checking the new table first
# resolves numeric id collisions in favor of valid links.
_PARK_LEGACY_SKIP_VALID = """
    INSERT INTO spp_gis_geofence_tag_legacy_migration (geofence_id, vocab_name)
    SELECT rel.geofence_id,
           COALESCE(v.name->>'en_US', (SELECT t.value FROM jsonb_each_text(v.name) t LIMIT 1))
    FROM spp_gis_geofence_tag_rel rel
    JOIN spp_vocabulary v ON v.id = rel.tag_id
    WHERE rel.tag_id NOT IN (SELECT id FROM spp_gis_geofence_tag)
"""

_DELETE_LEGACY_SKIP_VALID = """
    DELETE FROM spp_gis_geofence_tag_rel rel
    USING spp_vocabulary v
    WHERE v.id = rel.tag_id
      AND rel.tag_id NOT IN (SELECT id FROM spp_gis_geofence_tag)
"""


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _table_exists(cr, "spp_gis_geofence_tag_rel"):
        return

    if _table_exists(cr, "spp_gis_geofence_tag"):
        park_query = _PARK_LEGACY_SKIP_VALID
        delete_query = _DELETE_LEGACY_SKIP_VALID
    else:
        park_query = _PARK_LEGACY
        delete_query = _DELETE_LEGACY

    cr.execute(_CREATE_AUX)
    cr.execute(park_query)
    parked = cr.rowcount
    cr.execute(delete_query)
    _logger.info(
        "spp_gis geofence tag migration: parked %s legacy vocabulary tag links (%s rows removed)",
        parked,
        cr.rowcount,
    )
