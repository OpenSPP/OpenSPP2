# (C) 2021 Smile (<https://www.smile.eu>)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import copy
import logging

from markupsafe import Markup

from odoo import api

_logger = logging.getLogger(__name__)


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
        if self.env.context.get("audit_disable"):
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
        if self.env.context.get("audit_disable"):
            return audit_write.origin(self, vals)
        # Prevent recursive audit logging from computed field updates
        if self.env.context.get("audit_in_progress"):
            return audit_write.origin(self, vals)

        rules = self.get_audit_rules("write")
        old_values_copy = None
        if rules:
            # Use sudo() to take a full snapshot of record values for auditing,
            # regardless of user field-level access; audit rules control exposure.
            old_values = (
                self.sudo()  # nosemgrep: odoo-sudo-without-context
                .with_context(allowed_company_ids=[])
                .read(load="_classic_write")
            )
            old_values_copy = copy.deepcopy(old_values)

        # Set flag to prevent recursive auditing
        result = audit_write.origin(self.with_context(audit_in_progress=True), vals)

        if not rules:
            # No matching rule: skip the post-write snapshot read too — it
            # previously ran unconditionally, evaluating every non-stored
            # compute on every write of an audited model.
            return result

        new_values = (
            self.sudo()  # nosemgrep: odoo-sudo-without-context
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
        if self.env.context.get("audit_disable"):
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
