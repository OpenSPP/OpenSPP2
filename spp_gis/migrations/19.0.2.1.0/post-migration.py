# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Recreate geofence tag links parked by the matching pre-migration.

Creates one spp.gis.geofence.tag per distinct legacy vocabulary name and
restores the geofence links, then drops the aux table. See pre-migration.py
for the full story.

All SQL is literal and value-parameterized; identifiers are never composed.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger("odoo.addons.spp_gis.migrations.geofence_tags")


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _table_exists(cr, "spp_gis_geofence_tag_legacy_migration"):
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Tag = env["spp.gis.geofence.tag"]

    cr.execute("SELECT DISTINCT vocab_name FROM spp_gis_geofence_tag_legacy_migration")
    tag_ids_by_name = {}
    for (name,) in cr.fetchall():
        tag = Tag.search([("name", "=", name)], limit=1)
        if not tag:
            tag = Tag.create({"name": name})
        tag_ids_by_name[name] = tag.id

    restored = 0
    cr.execute("SELECT geofence_id, vocab_name FROM spp_gis_geofence_tag_legacy_migration")
    for geofence_id, name in cr.fetchall():
        cr.execute(
            """
            INSERT INTO spp_gis_geofence_tag_rel (geofence_id, tag_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (geofence_id, tag_ids_by_name[name]),
        )
        restored += cr.rowcount

    cr.execute("DROP TABLE spp_gis_geofence_tag_legacy_migration")
    _logger.info(
        "spp_gis geofence tag migration: created %s tags, restored %s links",
        len(tag_ids_by_name),
        restored,
    )
