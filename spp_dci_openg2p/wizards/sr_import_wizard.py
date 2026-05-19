"""SR-import wizard: discover and ingest registrants from an OpenG2P SR.

Operator-driven alternative to the seed script — instead of running a
Python file against Odoo shell, the wizard lets a user fire DCI
search-sync requests against the configured OpenG2P SR data source,
preview matched records, pick which ones to import, and (optionally)
auto-enroll them into a program.

Scope: this wizard intentionally captures only the BARE MINIMUM partner
fields (name, given_name, family_name, sex, birthdate) plus a UIN
``spp.registry.id``. The eligibility rules continue to read the rich
attributes (``income_level``, etc.) on demand via the CEL ↔ DCI bridge
— this wizard is NOT a full SR replica.

Discovery semantics: the SPDCI search-sync protocol is lookup-only
(``search_text`` → record). There is no standard "list all registrants"
operation, so this wizard offers two practical discovery modes:

  - ``range``: sweep a contiguous identifier range
                (e.g., ``IND-NSR-0001`` .. ``IND-NSR-0015``).
                Useful against the OpenG2P playground where seeded
                identifiers form a known range.

  - ``list``:  operator pastes/types a list of identifiers
                (one per line). Matches the production-shaped workflow
                where the SR operator hands over a partner list out of
                band.

Both modes invoke the same per-identifier DCI lookup through
``OpenG2PSocialService``.
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SppDciSrImportWizard(models.TransientModel):
    _name = "spp.dci.sr.import.wizard"
    _description = "Import Registrants from External Social Registry (DCI)"

    state = fields.Selection(
        [
            ("configure", "Configure"),
            ("preview", "Preview"),
            ("done", "Done"),
        ],
        default="configure",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Configure step
    # ------------------------------------------------------------------

    data_source_id = fields.Many2one(
        "spp.dci.data.source",
        string="Source Registry",
        required=True,
        domain="[('registry_type', '=', 'ns:org:RegistryType:Social'), ('vendor', '=', 'openg2p'), ('active', '=', True)]",
        default=lambda self: self._default_data_source(),
        help="DCI data source to query. Restricted to active Social Registry "
        "(SR) sources configured with the vendor-specific request semantics "
        "used by this wizard.",
    )

    discovery_mode = fields.Selection(
        [
            ("range", "Identifier range sweep"),
            ("list", "Identifier list"),
        ],
        default="range",
        required=True,
        help=(
            "How to enumerate registrants on the remote SR. "
            "Range = sweep a contiguous numeric suffix (e.g., 0001..0015); "
            "List = explicit identifiers, one per line."
        ),
    )

    # range mode
    range_prefix = fields.Char(
        string="Identifier Prefix",
        default="IND-NSR-",
        help="Prefix for sweep mode. The wizard concatenates this with a zero-padded number in [Start, End].",
    )
    range_start = fields.Integer(string="Start", default=1)
    range_end = fields.Integer(string="End", default=15)
    range_pad = fields.Integer(
        string="Zero-pad Width",
        default=4,
        help="Width to zero-pad the numeric suffix (e.g., 4 → 0001).",
    )

    # list mode
    identifier_list_raw = fields.Text(
        string="Identifiers",
        help="One identifier per line. Lines starting with # are ignored. Blank lines are skipped.",
    )

    # post-import options
    auto_enroll_program_id = fields.Many2one(
        "spp.program",
        string="Auto-enroll into program",
        help="Optional: every imported partner is added as a draft "
        "membership on this program. Eligibility evaluation flips the "
        "membership state on the next Enroll Eligible run.",
    )
    refresh_existing = fields.Boolean(
        string="Refresh existing registrants",
        default=False,
        help=(
            "When set, re-selecting a row whose UIN is already on the SP "
            "overwrites the local partner's name / given_name / family_name "
            "/ sex / birthdate with the latest values from the Social "
            "Registry. Mirror-to-DR follows the same path. When unset "
            "(default), already-on-SP rows are skipped on import even if "
            "manually selected — the safe insert-only contract."
        ),
    )

    # Mirror-to-DR options.
    #
    # When set, every partner created or refreshed on the SP during
    # action_import is also propagated to the configured DR over DCI —
    # using the standard signed envelope (signature + bearer token)
    # that the SP already uses to read has_disability from the same DR.
    # The DR side (spp_dci_server_disability /sync/register endpoint) is
    # idempotent on UIN: pre-existing UINs are 'skipped' or 'updated'
    # depending on refresh_existing.
    mirror_to_dr = fields.Boolean(
        string="Mirror to DR",
        default=False,
        help=(
            "After creating or refreshing a registrant on the SP, also "
            "register them on the configured DR via the DCI "
            "register-individual envelope (same auth and audit path as "
            "the read-side has_disability lookup)."
        ),
    )
    dr_data_source_id = fields.Many2one(
        "spp.dci.data.source",
        string="DR Data Source",
        domain="[('vendor', '=', 'openspp'), ('registry_type', '=', 'ns:org:RegistryType:DR'), ('active', '=', True)]",
        default=lambda self: self._default_dr_data_source(),
        help=(
            "DCI data source for the DR. Defaults to the active OpenSPP-DR "
            "source the bridge uses for has_disability lookups, so mirror "
            "traffic shares the same signed endpoint."
        ),
    )

    # ------------------------------------------------------------------
    # Preview step
    # ------------------------------------------------------------------

    preview_line_ids = fields.One2many(
        "spp.dci.sr.import.wizard.line",
        "wizard_id",
        string="Preview",
    )

    preview_summary = fields.Char(string="Preview Summary", readonly=True)

    # ------------------------------------------------------------------
    # Defaults / helpers
    # ------------------------------------------------------------------

    @api.model
    def _default_dr_data_source(self):
        """Pick the first active OpenSPP-DR DCI source.

        The bridge dispatcher uses the same record to resolve
        has_disability; reusing it here keeps every cross-DR call going
        through one configured endpoint.
        """
        return self.env["spp.dci.data.source"].search(
            [
                ("registry_type", "=", "ns:org:RegistryType:DR"),
                ("vendor", "=", "openspp"),
                ("active", "=", True),
            ],
            limit=1,
            order="id asc",
        )

    @api.model
    def _default_data_source(self):
        """Pick the first active OpenG2P SR source.

        Most demo deployments have one — `openg2p_sr` / `openg2p_dr` (xml
        id kept stable across renames). Operators can change it if they
        have multiple.
        """
        return self.env["spp.dci.data.source"].search(
            [
                ("registry_type", "=", "ns:org:RegistryType:Social"),
                ("vendor", "=", "openg2p"),
                ("active", "=", True),
            ],
            limit=1,
            order="id asc",
        )

    def _collect_identifiers(self):
        """Resolve configure step inputs to a deterministic identifier list."""
        if self.discovery_mode == "range":
            if not (self.range_prefix and self.range_start and self.range_end):
                raise UserError(self.env._("Provide range prefix, start, and end."))
            if self.range_end < self.range_start:
                raise UserError(self.env._("Range end must be ≥ start."))
            return [f"{self.range_prefix}{n:0{self.range_pad}d}" for n in range(self.range_start, self.range_end + 1)]
        if not (self.identifier_list_raw or "").strip():
            raise UserError(self.env._("Provide at least one identifier."))
        identifiers = []
        for line in self.identifier_list_raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            identifiers.append(stripped)
        # De-duplicate while preserving order.
        seen, out = set(), []
        for ident in identifiers:
            if ident not in seen:
                seen.add(ident)
                out.append(ident)
        if not out:
            # Empty after stripping comments / blank lines.
            raise UserError(self.env._("Provide at least one identifier."))
        return out

    def _uin_id_type(self):
        return self.env.ref("spp_dci_openg2p.id_type_uin", raise_if_not_found=False)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_preview(self):
        """Fire DCI lookups for every identifier; populate preview rows.

        Each row carries the resolved record's basic identity (name,
        sex, birthdate) plus an ``already_exists`` flag so the operator
        can see which UINs are already imported.
        """
        self.ensure_one()

        # Lazy import — avoid a hard module-load dependency on the service
        # so this wizard can lint cleanly even when the user runs tests
        # against a stripped install.
        from ..services.openg2p_social_service import OpenG2PSocialService

        identifiers = self._collect_identifiers()
        if not identifiers:
            raise UserError(self.env._("No identifiers to query."))

        if not self.data_source_id:
            raise UserError(self.env._("Select a Source Registry first."))

        service = OpenG2PSocialService(self.env, data_source_code=self.data_source_id.code)

        # Wipe any prior preview lines (operator may iterate)
        self.preview_line_ids.unlink()

        uin_type = self._uin_id_type()
        RegId = self.env["spp.registry.id"]

        lines_vals = []
        n_matched = 0
        n_not_found = 0
        n_already_exists = 0

        for ident in identifiers:
            payload = None
            error = None
            try:
                # Bypass partner-based path; call the client directly so
                # we can use the wizard-provided identifier as search_text.
                from odoo.addons.spp_dci.schemas import QueryType

                response = service.client.search(
                    query_type=QueryType.EXPRESSION,
                    query_value=ident,
                    registry_type="Individual",
                    record_type="Individual",
                    page=1,
                    page_size=1,
                )
                payload = service._extract_first_record(response)
            except Exception as e:
                error = str(e)[:200]
                _logger.warning("SR import: lookup failed for %s: %s", ident, e)

            if error:
                status = "error"
                n_not_found += 1
                line_vals = self._line_vals_empty(ident, status, error)
            elif payload is None:
                status = "not_found"
                n_not_found += 1
                line_vals = self._line_vals_empty(ident, status, "")
            else:
                status = "matched"
                n_matched += 1
                line_vals = self._line_vals_from_payload(ident, payload)

            # Check for existing partner on the SP with this UIN
            if uin_type:
                existing = RegId.search(
                    [("id_type_id", "=", uin_type.id), ("value", "=", ident)],
                    limit=1,
                )
                if existing:
                    line_vals["already_exists"] = True
                    line_vals["existing_partner_id"] = existing.partner_id.id
                    if status == "matched":
                        n_already_exists += 1

            # Default-select all newly matched rows. When refresh_existing
            # is on, also pre-select already-on-SP rows so a re-import
            # against an updated SR is a single click.
            line_vals["selected"] = status == "matched" and (
                not line_vals.get("already_exists") or self.refresh_existing
            )
            lines_vals.append(line_vals)

        self.preview_line_ids.create([dict(vals, wizard_id=self.id) for vals in lines_vals])
        self.state = "preview"
        self.preview_summary = self.env._(
            "%(matched)s matched (%(already)s already on SP), %(not_found)s not found/error, %(total)s total queries.",
            matched=n_matched,
            already=n_already_exists,
            not_found=n_not_found,
            total=len(identifiers),
        )

        return self._reopen()

    def action_import(self):
        """Create res.partner + spp.registry.id rows for selected lines.

        Skips rows where ``already_exists`` is True (UIN already on SP).
        Optionally creates draft program memberships when
        ``auto_enroll_program_id`` is set.
        """
        self.ensure_one()
        if self.state != "preview":
            raise UserError(self.env._("Run Preview first."))

        uin_type = self._uin_id_type()
        if not uin_type:
            raise UserError(self.env._("UIN vocabulary code is missing. Verify spp_dci_openg2p.id_type_uin is loaded."))

        Partner = self.env["res.partner"]
        RegId = self.env["spp.registry.id"]

        n_created = 0
        n_updated = 0
        # Collected once across the SP loop, then sent to the DR in a
        # single signed DCI envelope after the SP write completes.
        dr_items: list[dict] = []
        for line in self.preview_line_ids.filtered(lambda r: r.selected and r.status == "matched"):
            partner_vals = self._partner_vals_from_line(line)

            if line.already_exists:
                if not self.refresh_existing:
                    # Insert-only contract: skip rows already on SP unless
                    # the operator opted into refresh mode.
                    continue
                # Refresh path: overwrite the existing SP partner with the
                # SR's current name/demographic fields. Reg_id is keyed by
                # UIN value and doesn't need to change.
                partner = line.existing_partner_id
                partner.write(partner_vals)
                n_updated += 1
            else:
                partner = Partner.create(partner_vals)
                RegId.create(
                    {
                        "partner_id": partner.id,
                        "id_type_id": uin_type.id,
                        "value": line.uin,
                    }
                )
                n_created += 1

                if self.auto_enroll_program_id:
                    self.env["spp.program.membership"].create(
                        {
                            "partner_id": partner.id,
                            "program_id": self.auto_enroll_program_id.id,
                            "state": "draft",
                        }
                    )

            if self.mirror_to_dr:
                dr_items.append(
                    {
                        "uin": line.uin,
                        "name": partner.name,
                        "given_name": partner.given_name or False,
                        "family_name": partner.family_name or False,
                        "sex": line.sex or False,
                        "birth_date": line.birth_date or False,
                        # Forward the SR self-report flag so the DR can
                        # surface the registrant to the assessor backlog.
                        "is_disabled": bool(line.sr_is_disabled),
                    }
                )

        dr_summary = ""
        if self.mirror_to_dr and dr_items:
            dr_summary = self._fire_dr_register(dr_items)

        self.state = "done"
        sp_msg = self.env._(
            "%(c)s created, %(u)s updated on SP.",
            c=n_created,
            u=n_updated,
        )
        if self.mirror_to_dr:
            self.preview_summary = f"{sp_msg} {dr_summary}".strip()
        else:
            self.preview_summary = sp_msg
        return self._reopen()

    def _fire_dr_register(self, dr_items: list[dict]) -> str:
        """Send the batched mirror payload to the DR over DCI.

        Wraps the call so transport-level failures show up as a single
        summary line instead of rolling back the SP-side imports we just
        committed. Per-item DR-side status is read out of the response
        envelope and summarised (created / updated / skipped / rjct).
        """
        if not self.dr_data_source_id:
            return str(self.env._("DR mirror skipped: no DR data source configured."))

        # Lazy import — keeps the wizard loadable on databases that
        # don't have spp_dci_openspp_dr installed.
        try:
            from odoo.addons.spp_dci_openspp_dr.services.openspp_dr_service import OpenSPPDRService
        except ImportError:
            return str(self.env._("DR mirror skipped: spp_dci_openspp_dr not installed."))

        try:
            service = OpenSPPDRService(self.env, data_source_code=self.dr_data_source_id.code)
            response = service.register_individuals(dr_items, refresh_existing=self.refresh_existing)
        except Exception as e:
            _logger.warning("DR register call failed: %s", e)
            return str(self.env._("DR mirror error: %(e)s", e=str(e)[:200]))

        msg = (response or {}).get("message") or {}
        items = msg.get("register_response") or []
        n_created = sum(1 for r in items if r.get("operation") == "created")
        n_updated = sum(1 for r in items if r.get("operation") == "updated")
        n_skipped = sum(1 for r in items if r.get("operation") == "skipped")
        n_rjct = sum(1 for r in items if r.get("status") == "rjct")
        n_drafts = sum(1 for r in items if r.get("draft_assessment_created"))
        summary = str(
            self.env._(
                "DR: %(c)s created, %(u)s updated, %(s)s skipped, %(r)s rejected.",
                c=n_created,
                u=n_updated,
                s=n_skipped,
                r=n_rjct,
            )
        )
        if n_drafts:
            summary += " " + str(
                self.env._(
                    "%(n)s draft assessment(s) opened for assessor review.",
                    n=n_drafts,
                )
            )
        return summary

    @staticmethod
    def _partner_vals_from_line(line):
        """Build the partner write/create payload from a preview line."""
        partner_vals = {
            "name": f"{line.given_name or ''} {line.surname or ''}".strip() or line.uin,
            "given_name": line.given_name or False,
            "family_name": line.surname or False,
            "is_registrant": True,
            "is_group": False,
        }
        if line.birth_date:
            partner_vals["birthdate"] = line.birth_date
        return partner_vals

    def action_back_to_configure(self):
        self.ensure_one()
        self.preview_line_ids.unlink()
        self.state = "configure"
        self.preview_summary = False
        return self._reopen()

    def _reopen(self):
        """Re-open the wizard on the same record so the next view step shows."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    # ------------------------------------------------------------------
    # Preview-line constructors
    # ------------------------------------------------------------------

    @staticmethod
    def _line_vals_empty(uin, status, error_message):
        return {
            "uin": uin,
            "status": status,
            "error_message": error_message,
            "given_name": "",
            "surname": "",
            "sex": "",
            "birth_date": False,
            "already_exists": False,
            "existing_partner_id": False,
            "sr_is_disabled": False,
        }

    @staticmethod
    def _line_vals_from_payload(uin, payload):
        demo = payload.get("demographic_info") or {}
        name = demo.get("name") or {}
        birth = demo.get("birth_date") or False
        # SR exposes is_disabled as a self-report flag on the registry
        # record. Captured here so the operator sees it in the preview
        # and so the DR-mirror payload can carry it on through.
        sr_is_disabled = bool(payload.get("is_disabled"))
        return {
            "uin": uin,
            "status": "matched",
            "given_name": name.get("given_name") or "",
            "surname": name.get("surname") or "",
            "sex": demo.get("sex") or "",
            "birth_date": birth,
            "already_exists": False,
            "existing_partner_id": False,
            "error_message": "",
            "sr_is_disabled": sr_is_disabled,
        }


class SppDciSrImportWizardLine(models.TransientModel):
    _name = "spp.dci.sr.import.wizard.line"
    _description = "Preview row for the SR-import wizard"
    _order = "uin"

    wizard_id = fields.Many2one(
        "spp.dci.sr.import.wizard",
        required=True,
        ondelete="cascade",
    )

    uin = fields.Char(string="UIN", required=True)
    status = fields.Selection(
        [
            ("matched", "Matched"),
            ("not_found", "Not Found"),
            ("error", "Error"),
        ],
        required=True,
    )

    given_name = fields.Char(string="Given Name")
    surname = fields.Char(string="Surname")
    sex = fields.Char(string="Sex")
    birth_date = fields.Date(string="Birth Date")

    already_exists = fields.Boolean(
        string="Already on SP",
        help="True when a partner with this UIN already exists on the SP. Such rows are skipped on import.",
    )
    existing_partner_id = fields.Many2one(
        "res.partner",
        string="Existing Partner",
        help="The partner record this UIN already points at on the SP.",
    )

    selected = fields.Boolean(
        string="Import?",
        default=False,
        help="When checked AND status='matched' AND not already_exists, the row is imported on the next Import step.",
    )

    error_message = fields.Char(string="Error", help="Truncated error text for status='error' rows.")

    sr_is_disabled = fields.Boolean(
        string="SR self-reports disability",
        help=(
            "True when the registrant's Social Registry record carries "
            "is_disabled=true. Used by the DR mirror: when set, the DR's "
            "register endpoint creates a draft disability assessment for "
            "assessor review (only if no assessment exists yet)."
        ),
    )
