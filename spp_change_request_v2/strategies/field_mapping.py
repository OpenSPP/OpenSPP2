import logging
from datetime import date, datetime
from types import SimpleNamespace

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class SPPCRStrategyFieldMapping(models.AbstractModel):
    """Apply strategy: copy fields from detail to registrant."""

    _name = "spp.cr.strategy.field_mapping"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply Strategy: Field Mapping"

    def _effective_mappings(self, change_request):
        """Return the mappings that may be applied for this change request.

        For dynamic-approval CR types the approval workflow is routed and
        approved based on a single selected field, so ONLY that field's mapping
        may be written to the registrant — regardless of any other mapped detail
        fields that were also changed. This keeps the applied change in lockstep
        with what was actually approved. Fail closed: if no field is selected, or
        the selection maps to no configured field, nothing is applied.

        A mapping matches on ``routing_field`` where set, else on
        ``source_field``. The selectable values come from the detail model's
        ``_get_field_to_modify_selection()`` and need not be physical source
        fields: one selectable value may be applied through several mappings --
        a name offered as a single choice but stored as separate components,
        say. Matching on ``source_field`` alone could not express that, and
        matched nothing, so such a request applied nothing at all.
        """
        cr_type = change_request.request_type_id
        mappings = cr_type.apply_mapping_ids
        if not cr_type.use_dynamic_approval:
            return mappings
        selected = change_request.selected_field_name
        if not selected:
            return mappings.browse()
        return mappings.filtered(lambda m: (m.routing_field or m.source_field) == selected)

    def current_target_value(self, mapping, registrant):
        """The registrant's current value for ``mapping``, as apply compares it."""
        value = getattr(registrant, mapping.target_field, None)
        return value.id if hasattr(value, "id") else value

    def proposed_target_value(self, mapping, detail, registrant):
        """The value ``mapping`` would write, transform included.

        Shared with conflict and duplicate detection so the two cannot disagree
        about what counts as a change. Detection previously compared through
        ``_normalize_field_value``, which lowercases and strips strings, while
        apply compares raw and ignores no transform -- so a case- or
        whitespace-only edit was invisible to detection yet still written, and a
        transform could turn a differing value into an identical one (or the
        reverse) with only apply aware of it.
        """
        value = getattr(detail, mapping.source_field, None)
        if hasattr(value, "id"):
            value = value.id
        # The transform is admin-authored configuration. Read it as superuser so
        # detection -- which runs as the requester, not under sudo -- can see it:
        # ``transform_expression`` is gated by ``groups="base.group_system"``, so a
        # plain read by a change-request user would raise AccessError and, worse,
        # a silent skip would put detection and apply back out of step.
        config = mapping.sudo()  # nosemgrep: odoo-sudo-without-context
        if config.transform == "expression" and config.transform_expression:
            value = self._eval_expression(config.transform_expression, value, detail, registrant)
        return value

    def mapping_changes_value(self, mapping, detail, registrant):
        """Whether ``mapping`` would write a different value than is stored.

        A transform that cannot be evaluated fails closed on the apply path
        (``_eval_expression`` raises ``UserError``). Detection must not crash on
        that and must not silently drop the mapping: treat an unevaluable
        transform as a change so the field stays visible to conflict and
        duplicate detection. ``_run_conflict_checks`` on create is not
        try-guarded, so a propagating error here would break creation.
        """
        try:
            proposed = self.proposed_target_value(mapping, detail, registrant)
        except UserError:
            return True
        return proposed != self.current_target_value(mapping, registrant)

    def apply(self, change_request):
        """Apply field mappings from detail to registrant."""
        registrant = change_request.registrant_id
        detail = change_request.get_detail()

        if not detail:
            raise UserError(_("No detail record found."))

        # Fail loudly rather than apply nothing. ``_effective_mappings`` fails
        # closed, so an empty result means the change cannot be carried out at
        # all -- the routed field lost its mapping, or the type has none
        # configured. Returning success here would stamp the request applied,
        # with an audit event and a log line, having written nothing: operators
        # would see a green, applied request whose change was silently dropped.
        # An empty ``values`` below is different and stays allowed: the mappings
        # exist, the registrant simply already holds the proposed values.
        mappings = self._effective_mappings(change_request)
        if not mappings:
            selected = change_request.selected_field_name
            if selected:
                raise UserError(
                    _(
                        "The field this change request was routed on (%(field)s) no longer has a "
                        "mapping on its request type, so applying it would change nothing while "
                        "recording it as applied. Correct the request type's field mappings, or "
                        "reset the request to draft to re-route it.",
                        field=selected,
                    )
                )
            raise UserError(
                _(
                    "This change request type has no field mapping to apply, so applying it "
                    "would change nothing while recording it as applied. Configure the request "
                    "type's field mappings before applying."
                )
            )

        values = {}
        for mapping in mappings:
            source_value = self.proposed_target_value(mapping, detail, registrant)
            current_value = self.current_target_value(mapping, registrant)

            # Skip if value hasn't changed
            if source_value == current_value:
                continue

            # Empty values are applied too (rather than skipped): a user may be
            # intentionally clearing a field.
            values[mapping.target_field] = source_value

        if values:
            _logger.info(
                "Applying field mapping for CR %s: %s",
                change_request.name,
                list(values.keys()),
            )
            registrant.write(values)

            # Only regenerate name if name-related fields were updated
            name_related_fields = {"family_name", "given_name", "addl_name"}
            if name_related_fields & set(values.keys()):
                registrant.name_change()
        else:
            _logger.info(
                "Field mapping for CR %s wrote nothing: the registrant already holds the proposed values.",
                change_request.name,
            )

        return True

    def _expression_record_view(self, record):
        """Attribute-readable snapshot of ``record`` with no ORM handle attached.

        ``safe_eval`` permits arbitrary non-dunder attribute access, so a live
        recordset in the evaluation context exposes ``record.env`` /
        ``record.sudo()`` / ``record._cr`` -- the full ORM (as superuser on the
        apply path, which runs under sudo) and the database cursor. Keeping
        ``env`` out of the context means nothing while a recordset is in it.

        The snapshot carries stored scalar fields only, so ``registrant.family_name``
        keeps working while method calls and relation traversal do not, and its
        ``__dict__`` is blocked by the dunder-name check. Many2one values are
        reduced to their id, matching how ``proposed_target_value`` normalises.

        Group-gated fields are excluded on both paths: detection builds the
        snapshot as the requester, where reading a gated field (e.g.
        ``res.partner.signup_type``) raises AccessError before the expression
        runs, and apply -- which runs under sudo, where the read would succeed
        -- must build the identical snapshot or the two disagree about what a
        mapping writes. Binary fields are excluded so image payloads are not
        hauled into every evaluation, and Reference fields because their value
        is itself a live recordset -- the handle this snapshot exists to keep
        out.
        """
        if not record:
            return None
        values = {}
        for name, field in record._fields.items():
            if not field.store or field.groups or field.type in ("one2many", "many2many", "binary", "reference"):
                continue
            value = record[name]
            values[name] = value.id if field.type == "many2one" else value
        return SimpleNamespace(**values)

    def _eval_expression(self, expr, value, detail, registrant):
        """Safely evaluate a field-mapping transform expression.

        Security contract: the context exposes ``value`` and attribute-readable
        snapshots of ``detail`` and ``registrant`` -- never live recordsets, so
        no ``env``, ``sudo()`` or cursor is reachable from an expression. It
        fails closed: an expression that cannot be evaluated raises rather than
        writing the untransformed, requester-controlled ``value`` through.
        """
        try:
            return safe_eval(  # nosemgrep: odoo-unsafe-safe-eval
                expr,
                {
                    "value": value,
                    "detail": self._expression_record_view(detail),
                    "registrant": self._expression_record_view(registrant),
                    "datetime": datetime,
                    "date": date,
                },
                mode="eval",
            )
        except Exception as error:
            # Fail closed: refuse to write the raw value. ``value`` is
            # requester-controlled, so falling back would let a requester force
            # the untransformed value onto the registrant by feeding input the
            # transform cannot handle. Log the expression and error *type* at
            # ERROR -- never the wrapped error text, which embeds the field
            # value (PII) -- and the full traceback only at DEBUG. The UserError
            # message omits the underlying error for the same reason: it is
            # persisted to ``apply_error`` on the change request.
            _logger.error(
                "Field mapping transform expression failed (%s), refusing to write the raw value: %s",
                type(error).__name__,
                expr,
            )
            _logger.debug("Transform expression failure detail", exc_info=True)
            raise UserError(
                _(
                    "A configured field-mapping transform expression could not be evaluated, "
                    "so the change was not applied. Ask an administrator to review the "
                    "request type's transform expression; the failure detail is in the server log."
                )
            ) from None

    def _is_value_empty(self, value, record=None, field_name=None):
        """Check if a value should be considered empty and skipped.

        Returns True if the value is:
        - None
        - False (for non-Boolean fields; Odoo uses False to represent empty fields)
        - Empty string (after stripping whitespace)
        - Empty collection (list, tuple, set)
        - Numeric 0 is considered a valid value and returns False

        Note: In Odoo's ORM, False is commonly used to represent "no value"
        for Char, Text, Many2one, and other field types. However, for Boolean
        fields, False is a legitimate value.

        Args:
            value: The value to check
            record: Optional recordset to determine field type
            field_name: Optional field name to check field type

        Returns:
            bool: True if value should be skipped, False otherwise
        """
        # None is always considered empty
        if value is None:
            return True

        # Check if False is a valid value for Boolean fields
        if value is False:
            # If we have field information, check if it's a Boolean field
            if record and field_name and field_name in record._fields:
                field = record._fields[field_name]
                # For Boolean fields, False is a valid value
                if field.type == "boolean":
                    return False
            # For non-Boolean fields, False means empty
            return True

        # Numeric 0 is a legitimate value, not empty
        if value == 0 and isinstance(value, int | float):
            return False

        # Empty string (including whitespace-only strings)
        if isinstance(value, str) and not value.strip():
            return True

        # Empty collections (list, tuple, set)
        if isinstance(value, list | tuple | set) and len(value) == 0:
            return True

        return False

    def preview(self, change_request):
        """Preview what changes will be applied."""
        registrant = change_request.registrant_id
        detail = change_request.get_detail()

        if not detail:
            return {}

        changes = {}
        # Mirror apply(): a dynamic-approval CR previews only the selected field,
        # so the approver sees exactly what will be written.
        for mapping in self._effective_mappings(change_request):
            source_raw = getattr(detail, mapping.source_field, None)
            current_raw = getattr(registrant, mapping.target_field, None)

            # Get display-friendly values for relational fields
            source_display = source_raw.display_name if hasattr(source_raw, "display_name") else source_raw
            current_display = current_raw.display_name if hasattr(current_raw, "display_name") else current_raw

            # Normalize for comparison (use IDs for recordsets)
            source_cmp = source_raw.id if hasattr(source_raw, "id") else source_raw
            current_cmp = current_raw.id if hasattr(current_raw, "id") else current_raw

            # Only show fields that actually changed
            if source_cmp != current_cmp:
                # Use field description as label if available
                field_label = mapping.target_field
                if mapping.target_field in registrant._fields:
                    field_label = registrant._fields[mapping.target_field].string or field_label

                changes[field_label] = {
                    "old": current_display,
                    "new": source_display,
                }

        return changes
