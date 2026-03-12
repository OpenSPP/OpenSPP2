# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json
import logging

from odoo import Command, _, api, fields, models

try:
    from odoo.addons.queue_job.delay import group
except ImportError:
    group = None

try:
    from shapely.geometry import mapping
    from shapely.ops import unary_union
except ImportError:
    mapping = None
    unary_union = None

_logger = logging.getLogger(__name__)


class GeofenceEligibilityManager(models.Model):
    _inherit = "spp.eligibility.manager"

    @api.model
    def _selection_manager_ref_id(self):
        selection = super()._selection_manager_ref_id()
        new_manager = (
            "spp.program.membership.manager.geofence",
            "Geofence Eligibility",
        )
        if new_manager not in selection:
            selection.append(new_manager)
        return selection


class GeofenceMembershipManager(models.Model):
    _name = "spp.program.membership.manager.geofence"
    _inherit = ["spp.program.membership.manager", "spp.manager.source.mixin"]
    _description = "Geofence Eligibility Manager"
    ASYNC_IMPORT_THRESHOLD = 1000
    IMPORT_CHUNK_SIZE = 10000

    include_area_fallback = fields.Boolean(
        default=True,
        string="Include Area Fallback",
        help="When enabled, registrants whose administrative area intersects the geofence "
        "are included even if their coordinates are not set.",
    )
    fallback_area_type_id = fields.Many2one(
        "spp.area.type",
        string="Fallback Area Type",
        help="When set, only areas of this type are considered for the area fallback. "
        "Use this to restrict matching to a specific administrative level (e.g. District) "
        "and avoid overly broad matches from large provinces or regions.",
    )
    program_geofence_ids = fields.Many2many(
        "spp.gis.geofence",
        related="program_id.geofence_ids",
        readonly=True,
        string="Program Geofences",
    )
    preview_count = fields.Integer(
        string="Preview Count",
        readonly=True,
    )
    preview_error = fields.Char(
        string="Preview Error",
        readonly=True,
    )

    def _get_combined_geometry(self):
        """Return the union of all geofence geometries for this manager's program.

        Returns None if there are no geofences or if shapely is unavailable.
        """
        self.ensure_one()
        if unary_union is None:
            _logger.warning("spp_program_geofence: shapely is not available; cannot compute combined geometry")
            return None

        geofences = self.program_id.geofence_ids
        if not geofences:
            return None

        shapes = [gf.geometry for gf in geofences if gf.geometry]
        if not shapes:
            return None

        return unary_union(shapes)

    def _prepare_eligible_domain(self, membership=None):
        """Build the base Odoo search domain for eligible registrants.

        Args:
            membership: Optional recordset of spp.program.membership records.
                When provided, results are restricted to partners in that set.

        Returns:
            list: Odoo domain expression.
        """
        domain = []
        if membership is not None:
            ids = membership.partner_id.ids
            domain += [("id", "in", ids)]

        # Exclude disabled registrants
        domain += [("disabled", "=", False)]

        if self.program_id.target_type == "group":
            domain += [("is_group", "=", True), ("is_registrant", "=", True)]
        elif self.program_id.target_type == "individual":
            domain += [("is_group", "=", False), ("is_registrant", "=", True)]

        return domain

    def _find_eligible_registrants(self, membership=None):
        """Find all registrants that fall within the program's geofences.

        Uses a two-tier approach:
        - Tier 1: registrants whose coordinates fall within the combined geofence geometry.
        - Tier 2 (when include_area_fallback is True): registrants whose administrative
          area intersects the combined geofence geometry and were not already found in tier 1.

        Args:
            membership: Optional recordset restricting the search population.

        Returns:
            res.partner recordset of eligible registrants.
        """
        self.ensure_one()
        geofences = self.program_id.geofence_ids
        if not geofences:
            return self.env["res.partner"].browse()

        combined = self._get_combined_geometry()
        if combined is None:
            return self.env["res.partner"].browse()

        combined_geojson = json.dumps(mapping(combined))
        base_domain = self._prepare_eligible_domain(membership)

        # Tier 1: registrants with coordinates inside the geofence
        tier1_domain = base_domain + [("coordinates", "gis_intersects", combined_geojson)]
        tier1 = self.env["res.partner"].search(tier1_domain)

        # Tier 2: registrants whose area intersects the geofence
        if self.include_area_fallback:
            area_domain = [("geo_polygon", "gis_intersects", combined_geojson)]
            if self.fallback_area_type_id:
                area_domain += [("area_type_id", "=", self.fallback_area_type_id.id)]
            matching_areas = self.env["spp.area"].search(area_domain)
            if matching_areas:
                tier2_domain = base_domain + [
                    ("area_id", "in", matching_areas.ids),
                    ("id", "not in", tier1.ids),
                ]
                tier2 = self.env["res.partner"].search(tier2_domain)
                return tier1 | tier2

        return tier1

    def enroll_eligible_registrants(self, program_memberships):
        self.ensure_one()
        eligible = self._find_eligible_registrants(program_memberships)
        return self.env["spp.program.membership"].search(
            [
                ("partner_id", "in", eligible.ids),
                ("program_id", "=", self.program_id.id),
            ]
        )

    def verify_cycle_eligibility(self, cycle, membership):
        self.ensure_one()
        eligible = self._find_eligible_registrants(membership)
        return self.env["spp.cycle.membership"].search(
            [
                ("partner_id", "in", eligible.ids),
                ("cycle_id", "=", cycle.id),
            ]
        )

    def import_eligible_registrants(self, state="draft"):
        self.ensure_one()
        new_beneficiaries = self._find_eligible_registrants()

        # Exclude already-enrolled beneficiaries
        existing_partner_ids = set(self.program_id.program_membership_ids.partner_id.ids)
        new_beneficiaries = new_beneficiaries.filtered(lambda r: r.id not in existing_partner_ids)

        ben_count = len(new_beneficiaries)
        if ben_count < self.ASYNC_IMPORT_THRESHOLD:
            self._import_registrants(new_beneficiaries, state=state, do_count=True)
        else:
            self._import_registrants_async(new_beneficiaries, state=state)
        return ben_count

    def _import_registrants_async(self, new_beneficiaries, state="draft"):
        self.ensure_one()
        program = self.program_id
        program.message_post(body=f"Import of {len(new_beneficiaries)} beneficiaries started.")
        program.write({"is_locked": True, "locked_reason": "Importing beneficiaries"})

        jobs = []
        for i in range(0, len(new_beneficiaries), self.IMPORT_CHUNK_SIZE):
            jobs.append(
                self.delayable(channel="root_program.eligibility_manager")._import_registrants(
                    new_beneficiaries[i : i + self.IMPORT_CHUNK_SIZE], state
                )
            )
        main_job = group(*jobs)
        main_job.on_done(self.delayable(channel="root_program.eligibility_manager").mark_import_as_done())
        main_job.delay()

    def mark_import_as_done(self):
        self.ensure_one()
        self.program_id._compute_eligible_beneficiary_count()
        self.program_id._compute_beneficiary_count()
        self.program_id.is_locked = False
        self.program_id.locked_reason = None
        self.program_id.message_post(body=_("Import finished."))

    def _import_registrants(self, new_beneficiaries, state="draft", do_count=False):
        _logger.info("spp_program_geofence: Importing %s beneficiaries", len(new_beneficiaries))
        beneficiaries_val = [Command.create({"partner_id": b.id, "state": state}) for b in new_beneficiaries]
        self.program_id.update({"program_membership_ids": beneficiaries_val})

        if do_count:
            self.program_id._compute_eligible_beneficiary_count()
            self.program_id._compute_beneficiary_count()

    def action_preview_eligible(self):
        self.ensure_one()
        try:
            eligible = self._find_eligible_registrants()
            self.preview_count = len(eligible)
            self.preview_error = False
        except Exception:
            _logger.exception("Geofence eligibility preview failed for manager %s", self.id)
            self.preview_count = 0
            self.preview_error = "Preview failed. Check the server logs for details."
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Preview Complete",
                "message": f"{self.preview_count} registrants match the current geofences.",
                "sticky": False,
                "type": "success" if not self.preview_error else "warning",
            },
        }
