import logging
from datetime import timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SPPCRConflictMixin(models.AbstractModel):
    """Mixin providing conflict and duplicate detection for change requests.

    This mixin is designed to be inherited by spp.change.request to add
    conflict detection and duplicate prevention capabilities.
    """

    _name = "spp.cr.conflict.mixin"
    _description = "Change Request Conflict Detection Mixin"

    # ══════════════════════════════════════════════════════════════════════════
    # CONFLICT STATUS FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    conflict_status = fields.Selection(
        [
            ("none", "No Conflicts"),
            ("warning", "Warning"),
            ("blocked", "Blocked"),
            ("overridden", "Overridden"),
        ],
        default="none",
        readonly=True,
        tracking=True,
        help=(
            "None: No conflicts detected. "
            "Warning: Potential conflicts exist but submission allowed. "
            "Blocked: Hard conflict exists, submission blocked. "
            "Overridden: Conflict was overridden by authorized user."
        ),
    )

    conflicting_cr_ids = fields.Many2many(
        "spp.change.request",
        "spp_cr_conflict_rel",
        "cr_id",
        "conflicting_cr_id",
        string="Conflicting CRs",
        readonly=True,
    )

    conflict_count = fields.Integer(
        compute="_compute_conflict_count",
        string="Conflict Count",
    )

    conflict_detection_date = fields.Datetime(
        readonly=True,
        help="When conflict check was last performed",
    )

    conflict_messages = fields.Text(
        readonly=True,
        help="Messages from conflict detection",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # CONFLICT OVERRIDE FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    conflict_override_user_id = fields.Many2one(
        "res.users",
        readonly=True,
        string="Override By",
        tracking=True,
    )

    conflict_override_reason = fields.Text(
        readonly=True,
        string="Override Reason",
        tracking=True,
    )

    conflict_override_date = fields.Datetime(
        readonly=True,
        tracking=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # DUPLICATE STATUS FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    duplicate_status = fields.Selection(
        [
            ("none", "No Duplicates"),
            ("potential", "Potential Duplicate"),
            ("confirmed", "Confirmed Duplicate"),
            ("merged", "Merged"),
        ],
        default="none",
        readonly=True,
        tracking=True,
    )

    potential_duplicate_ids = fields.Many2many(
        "spp.change.request",
        "spp_cr_duplicate_rel",
        "cr_id",
        "duplicate_cr_id",
        string="Potential Duplicates",
        readonly=True,
    )

    duplicate_count = fields.Integer(
        compute="_compute_duplicate_count",
        string="Duplicate Count",
    )

    duplicate_similarity_score = fields.Float(
        readonly=True,
        help="Highest similarity percentage with potential duplicates",
    )

    merged_into_cr_id = fields.Many2one(
        "spp.change.request",
        readonly=True,
        string="Merged Into",
        ondelete="set null",
    )

    merged_from_cr_ids = fields.One2many(
        "spp.change.request",
        "merged_into_cr_id",
        string="Merged From",
        readonly=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends("conflicting_cr_ids")
    def _compute_conflict_count(self):
        for rec in self:
            rec.conflict_count = len(rec.conflicting_cr_ids)

    @api.depends("potential_duplicate_ids")
    def _compute_duplicate_count(self):
        for rec in self:
            rec.duplicate_count = len(rec.potential_duplicate_ids)

    # ══════════════════════════════════════════════════════════════════════════
    # CONFLICT DETECTION
    # ══════════════════════════════════════════════════════════════════════════

    def _detect_conflicts(self):
        """Run conflict detection for this change request.

        Returns a dict with:
            - has_blocking_conflict: bool
            - has_warning: bool
            - conflicting_crs: recordset of conflicting CRs
            - messages: list of conflict message strings
            - status: 'none', 'warning', or 'blocked'
        """
        self.ensure_one()

        cr_type = self.request_type_id
        if not cr_type or not cr_type.enable_conflict_detection:
            return {
                "has_blocking_conflict": False,
                "has_warning": False,
                "conflicting_crs": self.env["spp.change.request"],
                "messages": [],
                "status": "none",
            }

        rules = cr_type.conflict_rule_ids.filtered("active")
        if not rules:
            return {
                "has_blocking_conflict": False,
                "has_warning": False,
                "conflicting_crs": self.env["spp.change.request"],
                "messages": [],
                "status": "none",
            }

        all_conflicting_crs = self.env["spp.change.request"]
        messages = []
        has_blocking = False
        has_warning = False

        for rule in rules:
            domain = self._build_conflict_domain(rule)
            matches = self.env["spp.change.request"].search(domain)

            # For field-level scope, filter by actual field values
            if rule.scope == "field" and matches:
                matches = self._filter_by_field_conflicts(matches, rule)

            # For custom scope, call hook method
            if rule.scope == "custom" and matches:
                matches = self._check_custom_conflicts(matches, rule)

            if matches:
                all_conflicting_crs |= matches
                messages.append(rule.get_conflict_message(matches))

                if rule.action == "block":
                    has_blocking = True
                elif rule.action == "warn":
                    has_warning = True

        status = "none"
        if has_blocking:
            status = "blocked"
        elif has_warning:
            status = "warning"

        return {
            "has_blocking_conflict": has_blocking,
            "has_warning": has_warning,
            "conflicting_crs": all_conflicting_crs,
            "messages": messages,
            "status": status,
        }

    def _build_conflict_domain(self, rule):
        """Build search domain for conflict detection based on rule configuration."""
        self.ensure_one()

        domain = [
            ("id", "!=", self.id),
            ("is_applied", "=", False),
        ]

        # Scope filtering
        if rule.scope in ("registrant", "field"):
            domain.append(("registrant_id", "=", self.registrant_id.id))

        elif rule.scope == "group":
            # Get all members of the registrant's group(s)
            member_ids = self._get_group_member_ids()
            domain.append(("registrant_id", "in", member_ids))

        # Type filtering
        if rule.check_same_type_only:
            domain.append(("request_type_id", "=", self.request_type_id.id))
        elif rule.conflict_type_ids:
            domain.append(("request_type_id", "in", rule.conflict_type_ids.ids))

        # State filtering
        states = rule.get_conflict_states_list()
        domain.append(("approval_state", "in", states))

        # Time window
        if rule.time_window_hours > 0:
            cutoff = fields.Datetime.now() - timedelta(hours=rule.time_window_hours)
            domain.append(("create_date", ">=", cutoff))

        return domain

    def _get_group_member_ids(self):
        """Get IDs of all members in the registrant's group(s).

        Override this method for custom group membership logic.
        """
        self.ensure_one()
        registrant = self.registrant_id

        if not registrant:
            return []

        member_ids = [registrant.id]

        # If registrant is a group, include all individuals in it
        if registrant.is_group:
            if hasattr(registrant, "group_membership_ids"):
                member_ids.extend(
                    registrant.group_membership_ids.filtered(lambda m: not m.ended_date).mapped("individual_id.id")
                )

        # If registrant is an individual, find their groups and group members
        else:
            if hasattr(registrant, "individual_membership_ids"):
                for membership in registrant.individual_membership_ids.filtered(lambda m: not m.ended_date):
                    group = membership.group_id
                    member_ids.append(group.id)
                    member_ids.extend(
                        group.group_membership_ids.filtered(lambda m: not m.ended_date).mapped("individual_id.id")
                    )

        return list(set(member_ids))

    def _proposed_changed_fields(self):
        """Return the detail (source) fields a dynamic-approval CR actually
        proposes to change.

        These are the mapped fields whose detail value differs from the
        registrant's current value — exactly the set the ``field_mapping`` apply
        strategy will write. This is derived server-side from the actual data,
        NOT from a declared label: both ``selected_field_name`` (only
        view-readonly) and the detail's ``field_to_modify`` (freely writable and
        validated only to be a real field name, not tied to what apply changes)
        are attacker-controlled. A user could otherwise clear a field-scoped
        conflict/duplicate by labelling a different, unchanged field while still
        changing a scoped field. Scoping to the real diff makes those labels
        irrelevant to the security decision.

        Returns a set of detail field names for dynamic-approval CR types that
        use the ``field_mapping`` apply strategy, or ``None`` otherwise — for
        non-dynamic types, and for dynamic types whose strategy writes outside
        the mappings, the full configured field set must always be considered
        (their details are not registrant-prefilled snapshots, and an empty
        derived set would silently disable detection).
        """
        self.ensure_one()
        cr_type = self.request_type_id
        if not cr_type.use_dynamic_approval:
            return None
        # The derivation reads the configured field mappings, so it is only
        # meaningful for the field_mapping apply strategy. A custom-strategy
        # type writes fields the mappings do not describe, so deriving from an
        # empty apply_mapping_ids would yield an empty set — which disables
        # both field-scoped conflict detection and duplicate detection. Fall
        # back to the full configured field set (None) instead of failing open.
        if cr_type.apply_strategy != "field_mapping" or not cr_type.apply_mapping_ids:
            return None
        detail = self.get_detail()
        registrant = self.registrant_id
        if not detail or not registrant:
            return set()
        changed = set()
        for mapping in self.request_type_id.apply_mapping_ids:
            source_field = mapping.source_field
            target_field = mapping.target_field
            if source_field not in detail._fields or target_field not in registrant._fields:
                continue
            detail_value = self._normalize_field_value(getattr(detail, source_field, None))
            registrant_value = self._normalize_field_value(getattr(registrant, target_field, None))
            if detail_value != registrant_value:
                changed.add(source_field)
        return changed

    def _effective_conflict_fields(self, conflict_fields):
        """Return the subset of ``conflict_fields`` this CR actually proposes to
        change (the security-relevant scope). Full set for non-dynamic types."""
        self.ensure_one()
        conflict_fields = set(conflict_fields)
        proposed = self._proposed_changed_fields()
        if proposed is None:
            return conflict_fields
        return proposed & conflict_fields

    def _filter_by_field_conflicts(self, candidates, rule):
        """Filter candidate CRs by checking if they modify the same fields.

        For dynamic-approval CRs, the proposed changes are the conflict fields
        whose value actually differs from the registrant (derived server-side),
        not a user-writable label. Prefilled/unchanged fields are ignored.
        """
        self.ensure_one()

        conflict_fields = rule.get_conflict_fields_list()
        if not conflict_fields:
            return candidates

        my_detail = self.get_detail()
        if not my_detail:
            return self.env["spp.change.request"]

        my_effective_fields = self._effective_conflict_fields(conflict_fields)
        if not my_effective_fields:
            # This CR changes none of the rule's fields — nothing to conflict on.
            return self.env["spp.change.request"]

        matching = self.env["spp.change.request"]

        for candidate in candidates:
            candidate_detail = candidate.get_detail()
            if not candidate_detail:
                continue

            candidate_effective = candidate._effective_conflict_fields(conflict_fields)

            # Overlap = fields BOTH CRs actually propose to change.
            fields_to_check = my_effective_fields & candidate_effective

            for field_name in fields_to_check:
                if field_name not in my_detail._fields:
                    continue
                if field_name not in candidate_detail._fields:
                    continue

                my_value = getattr(my_detail, field_name, None)
                candidate_value = getattr(candidate_detail, field_name, None)

                # Both have values for this field = potential conflict
                if my_value and candidate_value:
                    matching |= candidate
                    break

        return matching

    def _check_custom_conflicts(self, candidates, rule):
        """Hook for custom conflict detection logic.

        Override this method in CR type-specific models to add
        custom conflict detection rules.

        Args:
            candidates: Initial set of potentially conflicting CRs
            rule: The conflict rule being evaluated

        Returns:
            Filtered recordset of conflicting CRs
        """
        return candidates

    # ══════════════════════════════════════════════════════════════════════════
    # DUPLICATE DETECTION
    # ══════════════════════════════════════════════════════════════════════════

    def _detect_duplicates(self):
        """Run duplicate detection for this change request.

        Returns a dict with:
            - has_duplicates: bool
            - duplicates: list of dicts with 'cr' and 'similarity' keys
            - max_similarity: float (0-100)
            - status: 'none' or 'potential'
        """
        self.ensure_one()

        cr_type = self.request_type_id
        if not cr_type or not cr_type.enable_duplicate_detection:
            return {
                "has_duplicates": False,
                "duplicates": [],
                "max_similarity": 0.0,
                "status": "none",
            }

        config = cr_type.duplicate_detection_config_id
        if not config or not config.active:
            return {
                "has_duplicates": False,
                "duplicates": [],
                "max_similarity": 0.0,
                "status": "none",
            }

        # Build search domain
        domain = [
            ("id", "!=", self.id),
            ("registrant_id", "=", self.registrant_id.id),
            ("request_type_id", "=", self.request_type_id.id),
            ("approval_state", "in", ["draft", "pending", "approved"]),
            ("is_applied", "=", False),
        ]

        if config.time_window_hours > 0:
            cutoff = fields.Datetime.now() - timedelta(hours=config.time_window_hours)
            domain.append(("create_date", ">=", cutoff))

        candidates = self.env["spp.change.request"].search(domain)

        duplicates = []
        for candidate in candidates:
            similarity = self._calculate_similarity(candidate, config)
            if similarity >= config.similarity_threshold:
                duplicates.append(
                    {
                        "cr": candidate,
                        "similarity": similarity,
                    }
                )

        max_similarity = max((d["similarity"] for d in duplicates), default=0.0)

        return {
            "has_duplicates": bool(duplicates),
            "duplicates": duplicates,
            "max_similarity": max_similarity,
            "status": "potential" if duplicates else "none",
        }

    def _calculate_similarity(self, other_cr, config):
        """Calculate similarity percentage between this CR and another.

        For dynamic-approval CRs, only the selected field (derived server-side
        from the detail's validated ``field_to_modify``) is compared. Prefilled
        fields are ignored to prevent inflated similarity scores.

        Args:
            other_cr: Another spp.change.request record
            config: spp.cr.duplicate.config record

        Returns:
            Float between 0 and 100
        """
        self.ensure_one()

        my_detail = self.get_detail()
        other_detail = other_cr.get_detail()

        if not my_detail or not other_detail:
            return 0.0

        # Dynamic approval: compare only the fields actually changed (derived
        # server-side from the detail-vs-registrant diff, not a writable label).
        my_changed = self._proposed_changed_fields()
        other_changed = other_cr._proposed_changed_fields()
        if my_changed is not None and other_changed is not None:
            # Score the fields BOTH requests actually propose to change.
            #
            # Requiring the two change sets to be *equal* made detection
            # trivially evadable: apply writes only the routed field for a
            # dynamic-approval type, so a requester could add a throwaway edit
            # to another mapped field, make the sets unequal, drop similarity to
            # zero and still have their real change applied unaltered. Scoring
            # the intersection ignores such padding, and scoring it
            # proportionally (the same 1.0 exact / 0.8 fuzzy scale the static
            # path uses) avoids collapsing a mostly identical request to zero
            # the moment one shared field differs.
            #
            # Deliberately not derived from ``selected_field_name`` or
            # ``field_to_modify``: both are requester-writable, which is the
            # bypass the diff-derived change set exists to close.
            shared = my_changed & other_changed
            if not shared:
                return 0.0
            comparable = [f for f in shared if f in my_detail._fields and f in other_detail._fields]
            if not comparable:
                return 0.0
            matching_score = 0.0
            for field_name in comparable:
                my_value = self._normalize_field_value(getattr(my_detail, field_name, None))
                other_value = self._normalize_field_value(getattr(other_detail, field_name, None))
                if my_value == other_value:
                    matching_score += 1.0
                elif self._are_similar(my_value, other_value):
                    matching_score += 0.8
            return (matching_score / len(comparable)) * 100.0

        # Static CRs (or mixed): original logic
        check_fields = config.get_check_fields_list()

        # If no specific fields configured, compare all stored fields
        if not check_fields:
            check_fields = [
                f
                for f in my_detail._fields
                if f
                not in (
                    "id",
                    "create_date",
                    "write_date",
                    "create_uid",
                    "write_uid",
                    "change_request_id",
                    "registrant_id",
                    "approval_state",
                    "is_applied",
                )
                and my_detail._fields[f].store
            ]

        if not check_fields:
            return 0.0

        total_fields = len(check_fields)
        matching_score = 0.0

        for field_name in check_fields:
            if field_name not in my_detail._fields:
                continue
            if field_name not in other_detail._fields:
                continue

            my_value = getattr(my_detail, field_name, None)
            other_value = getattr(other_detail, field_name, None)

            # Normalize for comparison
            my_value = self._normalize_field_value(my_value)
            other_value = self._normalize_field_value(other_value)

            if my_value == other_value:
                matching_score += 1.0
            elif self._are_similar(my_value, other_value):
                matching_score += 0.8  # Partial match for fuzzy similarity

        return (matching_score / total_fields) * 100.0 if total_fields > 0 else 0.0

    def _normalize_field_value(self, value):
        """Normalize a field value for comparison."""
        if value is False:
            return None
        # Check for recordsets first (before accessing .id which requires singleton)
        if hasattr(value, "ids"):
            # For recordsets, return sorted tuple of IDs
            return tuple(sorted(value.ids))
        if isinstance(value, str):
            return value.strip().lower()
        return value

    def _are_similar(self, value1, value2):
        """Check if two values are similar (fuzzy match).

        Override this method for custom similarity logic.
        """
        if value1 is None or value2 is None:
            return False

        # For strings, check if one contains the other
        if isinstance(value1, str) and isinstance(value2, str):
            return value1 in value2 or value2 in value1

        return False

    # ══════════════════════════════════════════════════════════════════════════
    # CONFLICT OVERRIDE
    # ══════════════════════════════════════════════════════════════════════════

    def action_override_conflict(self, reason):
        """Override a blocking conflict with justification.

        Requires the 'override_cr_conflicts' permission.
        """
        self.ensure_one()

        if not self.env.user.has_group("spp_change_request_v2.group_cr_conflict_approver"):
            raise UserError(_("You do not have permission to override conflicts."))

        if self.conflict_status not in ("blocked", "warning"):
            raise UserError(_("No conflict to override."))

        if not reason or len(reason.strip()) < 10:
            raise ValidationError(_("Override justification is required (minimum 10 characters)."))

        self.write(
            {
                "conflict_status": "overridden",
                "conflict_override_user_id": self.env.user.id,
                "conflict_override_reason": reason.strip(),
                "conflict_override_date": fields.Datetime.now(),
            }
        )

        # Create audit event
        self._create_conflict_audit_event("conflict_overridden", reason)

        return True

    def _create_conflict_audit_event(self, action, details=None):
        """Create an audit event for conflict-related actions."""
        self.ensure_one()

        if "spp.event.data" not in self.env:
            return

        event_type = self.env.ref(
            "spp_change_request_v2.event_type_cr_conflict",
            raise_if_not_found=False,
        )
        if not event_type:
            return

        data = {
            "change_request_id": self.id,
            "change_request_name": self.name,
            "action": action,
            "conflict_status": self.conflict_status,
            "conflicting_cr_ids": self.conflicting_cr_ids.ids,
            "user_id": self.env.user.id,
            "user_name": self.env.user.name,
        }
        if details:
            data["details"] = details

        self.env["spp.event.data"].sudo().create(  # nosemgrep: odoo-sudo-without-context
            {
                "event_type_id": event_type.id,
                "partner_id": self.registrant_id.id,
                "collection_date": fields.Date.today(),
                "state": "active",
                "data_json": data,
            }
        )

    # ══════════════════════════════════════════════════════════════════════════
    # WORKFLOW INTEGRATION
    # ══════════════════════════════════════════════════════════════════════════

    def _run_conflict_checks(self):
        """Run all conflict and duplicate checks, update fields accordingly.

        Call this method during CR creation or before submission.

        Returns:
            dict with 'can_proceed', 'needs_override', and 'messages' keys
        """
        self.ensure_one()

        conflict_result = self._detect_conflicts()
        duplicate_result = self._detect_duplicates()

        # Determine new conflict status, preserving "overridden" if still valid
        new_conflict_status = conflict_result["status"]
        if self.conflict_status == "overridden" and conflict_result["status"] in (
            "blocked",
            "warning",
        ):
            # Preserve overridden status if conflicts still exist but were already overridden
            new_conflict_status = "overridden"

        # Update conflict fields
        update_vals = {
            "conflict_status": new_conflict_status,
            "conflicting_cr_ids": [Command.set(conflict_result["conflicting_crs"].ids)],
            "conflict_detection_date": fields.Datetime.now(),
            "conflict_messages": "\n".join(conflict_result["messages"]) or False,
        }

        # Update duplicate fields
        update_vals.update(
            {
                "duplicate_status": duplicate_result["status"],
                "potential_duplicate_ids": [Command.set([d["cr"].id for d in duplicate_result["duplicates"]])],
                "duplicate_similarity_score": duplicate_result["max_similarity"],
            }
        )

        self.write(update_vals)

        # Create audit events if conflicts/duplicates found
        if conflict_result["conflicting_crs"]:
            self._create_conflict_audit_event(
                "conflicts_detected",
                "\n".join(conflict_result["messages"]),
            )

        # Determine if user can proceed
        # If conflict was already overridden, user can proceed despite blocking conflicts
        can_proceed = not conflict_result["has_blocking_conflict"] or self.conflict_status == "overridden"
        needs_override = conflict_result["has_blocking_conflict"] and self.conflict_status != "overridden"

        all_messages = conflict_result["messages"][:]
        if duplicate_result["has_duplicates"]:
            all_messages.append(
                _("Potential duplicate(s) detected with %.1f%% similarity.") % duplicate_result["max_similarity"]
            )

        return {
            "can_proceed": can_proceed,
            "needs_override": needs_override,
            "messages": all_messages,
            "conflict_result": conflict_result,
            "duplicate_result": duplicate_result,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # VIEW ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def action_view_conflicts(self):
        """Open a list view of conflicting CRs."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Conflicting Change Requests"),
            "res_model": "spp.change.request",
            "view_mode": "list,form",
            "domain": [("id", "in", self.conflicting_cr_ids.ids)],
            "target": "current",
        }

    def action_view_duplicates(self):
        """Open a list view of potential duplicate CRs."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Potential Duplicates"),
            "res_model": "spp.change.request",
            "view_mode": "list,form",
            "domain": [("id", "in", self.potential_duplicate_ids.ids)],
            "target": "current",
        }

    def action_open_conflict_wizard(self):
        """Open the conflict resolution wizard."""
        self.ensure_one()
        wizard = self.env["spp.cr.conflict.wizard"].create(
            {
                "change_request_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Resolve Conflict"),
            "res_model": "spp.cr.conflict.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_recheck_conflicts(self):
        """Manually re-run conflict detection."""
        self.ensure_one()
        result = self._run_conflict_checks()
        if result["messages"]:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Conflict Check Complete"),
                    "message": "\n".join(result["messages"]),
                    "type": "warning" if not result["can_proceed"] else "info",
                    "sticky": not result["can_proceed"],
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Conflict Check Complete"),
                "message": _("No conflicts detected."),
                "type": "success",
            },
        }
