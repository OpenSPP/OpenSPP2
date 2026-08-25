# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Drop the unconditional ID-type constraint this version replaces (OP#1136).

``spp.registry.id`` used to carry ``UNIQUE(partner_id, id_type_id)``. Removing
an ID through a change request keeps the row and marks it Invalid, so that
constraint counted dead rows: once an ID had been removed, that type could never
be used again for the registrant. It is replaced by a partial unique index that
ignores invalid rows, declared on the model as ``models.UniqueIndex``.

The replacement is created by the framework, but the old constraint has to be
dropped here: Odoo only adds and updates the constraints a model declares, and
never removes one that has simply stopped being declared. Left in place it would
keep refusing exactly the Remove-then-Add sequence this version fixes.

Runs pre-migration so the constraint is gone before the ORM reconciles the
table, which is also when the new index is created.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Written as a literal rather than composed: nothing here is dynamic, and a
    # composed SQL string is the pitfall the injection check exists to catch.
    # Odoo names a table constraint "{table}_{attribute with the leading
    # underscore removed}", so `_unique_partner_id_type` became this.
    cr.execute("ALTER TABLE spp_registry_id DROP CONSTRAINT IF EXISTS spp_registry_id_unique_partner_id_type")
    _logger.info("Dropped the unconditional ID-type constraint; live-only uniqueness is now a partial index")
