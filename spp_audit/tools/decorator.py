# (C) 2021 Smile (<https://www.smile.eu>)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import copy
import logging

from markupsafe import Markup

from odoo import api

_logger = logging.getLogger(__name__)


class _ContextMarker(str):
    """Context value that the audit decorator recognises by identity.

    A context can be supplied by an RPC client, so a plain value such as
    ``True`` proves nothing about who set it. A marker is an object that only
    server-side Python code can put in the context: a value that arrives over
    RPC is never the same object. It is a ``str`` so that a context holding it
    can still be serialised.

    Equality is identity too. Odoo reuses an environment whose context
    compares equal, so a marker that equalled its own text would let a context
    holding that plain text stand in for one holding the marker.
    """

    __slots__ = ()

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    __hash__ = str.__hash__

    def __reduce__(self):
        # copy, deepcopy and pickle give back the module-level marker itself
        return "AUDIT_DISABLE"


# Trusted server-side flows pass this as the ``audit_disable`` context value
# to skip audit logging: ``records.with_context(audit_disable=AUDIT_DISABLE)``.
AUDIT_DISABLE = _ContextMarker("audit_disable")


# Key in the cursor's cache for the records whose write is being audited.
_WRITE_IN_PROGRESS = "spp_audit_write_in_progress"


def _writes_in_progress(env):
    """Return the ``(model name, record id)`` pairs whose write is being audited.

    The set lives on the cursor, not in the context, so a caller cannot supply
    it and it is shared by every environment of the transaction. A write
    nested inside an audited write is skipped for those records only: the
    enclosing write already logs their change, and writes to any other record
    are still audited.

    Odoo clears the cursor's cache on commit, rollback and savepoint rollback.
    If that happens during a write, a later nested write to the same records
    is logged again: the guard fails towards more logging, never less.
    """
    return env.cr.cache.setdefault(_WRITE_IN_PROGRESS, set())


def _stringify_markup(values):
    """Convert Markup field values to plain str in read() result dicts."""
    for rec_values in values or []:
        for key, value in rec_values.items():
            if isinstance(value, Markup):
                rec_values[key] = str(value)


def audit_decorator(method):
    """
    The audit_decorator function is a Python decorator that adds auditing functionality to create, write, and
    unlink methods of a class.

    :param method: The `method` parameter is a string that specifies the type of operation being
    performed. It can have one of the following values: "create", "write", or "unlink"
    :return: The audit_decorator function returns one of three functions: audit_create, audit_write, or
    audit_unlink, depending on the value of the method parameter.
    """

    @api.model_create_multi
    def audit_create(self, vals_list):
        # audit_disable: trusted machine flows (e.g. replication of records
        # already audited at their source) opt out of audit logging and its
        # full-record snapshot reads.
        if self.env.context.get("audit_disable") is AUDIT_DISABLE:
            return audit_create.origin(self, vals_list)
        result = audit_create.origin(self, vals_list)
        records = result
        rules = self.get_audit_rules("create")
        if not rules:
            # No matching rule: skip the snapshot read — reading every field
            # evaluates every non-stored compute on the new records.
            return result

        # Use sudo() to avoid access errors when reading computed fields
        new_values = (
            records.sudo()  # nosemgrep: odoo-sudo-without-context
            .with_context(allowed_company_ids=[])
            .read(  # nosemgrep: odoo-sudo-without-context
                load="_classic_write"
            )
        )
        if new_values:
            _stringify_markup(new_values)
            rules.log("create", new_values=new_values)
        return result

    def audit_write(self, vals):
        # audit_disable: trusted machine flows opt out entirely (see audit_create)
        if self.env.context.get("audit_disable") is AUDIT_DISABLE:
            return audit_write.origin(self, vals)
        # Records already being audited by an enclosing audit_write are left to it
        in_progress = _writes_in_progress(self.env)
        records = self
        if in_progress:
            records = self.filtered(lambda record: (record._name, record.id) not in in_progress)
        rules = self.get_audit_rules("write") if records else None
        if not rules:
            # Nothing left to audit, or no matching rule: skip the snapshot
            # reads, which evaluate every non-stored compute on the records.
            return audit_write.origin(self, vals)

        # Use sudo() to take a full snapshot of record values for auditing,
        # regardless of user field-level access; audit rules control exposure.
        old_values = (
            records.sudo()  # nosemgrep: odoo-sudo-without-context
            .with_context(allowed_company_ids=[])
            .read(load="_classic_write")
        )
        old_values_copy = copy.deepcopy(old_values)

        auditing = {(records._name, record_id) for record_id in records.ids}
        in_progress |= auditing
        try:
            result = audit_write.origin(self, vals)
        finally:
            in_progress -= auditing

        new_values = (
            records.sudo()  # nosemgrep: odoo-sudo-without-context
            .with_context(allowed_company_ids=[])
            .read(load="_classic_write")
        )

        if new_values and old_values_copy:
            _stringify_markup(new_values)
            _stringify_markup(old_values_copy)
            rules.log("write", old_values_copy, new_values)
        return result

    def audit_unlink(self):
        # audit_disable: trusted machine flows opt out entirely (see audit_create)
        if self.env.context.get("audit_disable") is AUDIT_DISABLE:
            return audit_unlink.origin(self)
        rules = self.get_audit_rules("unlink")
        if not rules:
            return audit_unlink.origin(self)
        # Use sudo() to avoid access errors when reading computed fields
        old_values = (
            self.sudo()  # nosemgrep: odoo-sudo-without-context
            .with_context(allowed_company_ids=[])
            .read(load="_classic_write")
        )

        if old_values:
            _stringify_markup(old_values)
            rules.log("unlink", old_values)
        return audit_unlink.origin(self)

    methods = {
        "create": audit_create,
        "write": audit_write,
        "unlink": audit_unlink,
    }

    return methods[method]
