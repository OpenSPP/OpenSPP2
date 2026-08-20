# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Stop re-locking the registry on every upgrade (OP#1142).

``config_registry_admin_only_crud`` is now declared ``noupdate="1"`` so an
administrator's choice survives module upgrades. That declaration only governs
xml_ids created from now on: ``_build_update_xmlids_query`` upserts with
``ON CONFLICT … DO UPDATE SET (model, res_id, write_date)`` and never touches
the stored ``noupdate`` flag of an existing row. So every database that already
carries this xml_id keeps ``noupdate = false``, and each upgrade re-applies
``value = True`` — silently re-locking a registry that was deliberately opened,
which is the bug this module set out to fix.

The flag has to be flipped in the row itself, once.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        UPDATE ir_model_data
           SET noupdate = true
         WHERE module = 'spp_starter_sp_mis'
           AND name = 'config_registry_admin_only_crud'
           AND noupdate IS NOT TRUE
        """
    )
    if cr.rowcount:
        _logger.info("Marked config_registry_admin_only_crud noupdate; the setting now survives upgrades")
