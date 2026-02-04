import json
import logging

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import Response, request

_logger = logging.getLogger(__name__)


class GISReportController(http.Controller):
    """GeoJSON API endpoints for GIS reports.

    All endpoints use report CODE (not database ID) as the external identifier,
    following OpenSPP API design principles.
    """

    def _json_response(self, data, status=200):
        """Create a JSON response.

        Args:
            data: Dictionary to serialize as JSON
            status: HTTP status code

        Returns:
            Response: HTTP response with JSON content
        """
        return Response(
            json.dumps(data, default=str),
            status=status,
            content_type="application/json",
        )

    def _get_report_by_code(self, report_code):
        """Look up report by code and check access.

        Args:
            report_code: The report's unique code

        Returns:
            spp.gis.report record

        Raises:
            MissingError: If report not found
            AccessError: If user lacks access
        """
        report = request.env["spp.gis.report"].search([("code", "=", report_code)], limit=1)
        if not report:
            raise MissingError(_("Report not found: %s", report_code))

        # Access control is handled by Odoo's record rules
        # Additional group-based filtering can be implemented via ir.rule if needed

        return report

    def _resolve_area_codes(self, area_codes):
        """Convert area codes to IDs.

        Args:
            area_codes: Comma-separated area codes or list

        Returns:
            list: Area IDs
        """
        if not area_codes:
            return None

        if isinstance(area_codes, str):
            codes = [c.strip() for c in area_codes.split(",")]
        else:
            codes = area_codes

        areas = request.env["spp.area"].search([("code", "in", codes)])
        return areas.ids if areas else None

    @http.route(
        "/api/v2/GISReport",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def list_reports(self):
        """List available GIS reports for current user.

        Returns:
            Response: JSON list of reports with basic metadata (using codes, not IDs)
        """
        try:
            # Get all active reports - Odoo's record rules handle access filtering
            # Reports with access_group_ids are filtered separately if needed
            reports = request.env["spp.gis.report"].search(
                [
                    ("active", "=", True),
                ]
            )

            # Get available admin levels for each report
            report_list = []
            for report in reports:
                admin_levels = report.data_ids.mapped("area_level") if report.data_ids else []

                report_list.append(
                    {
                        "code": report.code,
                        "name": report.name,
                        "category": report.category_id.name if report.category_id else None,
                        "last_refresh": (report.last_refresh.isoformat() if report.last_refresh else None),
                        "admin_levels_available": sorted(set(admin_levels)),
                        "has_disaggregation": any(
                            [
                                report.disaggregate_by_gender,
                                report.disaggregate_by_age,
                                report.disaggregate_by_disability,
                                report.disaggregate_by_tag_ids,
                            ]
                        ),
                    }
                )

            return self._json_response({"reports": report_list})

        except AccessError as e:
            _logger.warning("Access denied listing GIS reports: %s", str(e))
            return self._json_response(
                {"error": _("Access denied"), "code": "ACCESS_ERROR"},
                status=403,
            )
        except Exception as e:
            _logger.error(
                "Error listing GIS reports: %s",
                str(e),
                exc_info=True,
            )
            return self._json_response(
                {"error": _("Failed to list reports"), "code": "LIST_ERROR"},
                status=500,
            )

    @http.route(
        "/api/v2/GISReport/<string:report_code>/geojson",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def get_geojson(
        self,
        report_code,
        admin_level=None,
        area_codes=None,
        parent_area_code=None,
        include_geometry="true",
        include_disaggregation="false",
        format="full",
        **kwargs,
    ):
        """Get report data as GeoJSON.

        Args:
            report_code: Code of the report (NOT database ID)
            admin_level: Filter to specific admin level
            area_codes: Comma-separated area codes (NOT IDs)
            parent_area_code: Only include children of this area (by code)
            include_geometry: Include polygon geometry (default: "true")
            include_disaggregation: Include disaggregation data (default: "false")
            format: 'full' (with metadata) or 'simple' (features only)

        Returns:
            Response: GeoJSON FeatureCollection (RFC 7946 compliant, EPSG:4326)
        """
        try:
            report = self._get_report_by_code(report_code)

            # Convert string parameters to proper types
            include_geometry_bool = str(include_geometry).lower() in (
                "true",
                "1",
                "yes",
            )
            include_disaggregation_bool = str(include_disaggregation).lower() in (
                "true",
                "1",
                "yes",
            )
            admin_level_int = int(admin_level) if admin_level else None

            # Resolve area codes to IDs for internal use
            area_ids = self._resolve_area_codes(area_codes)

            # Resolve parent area code
            parent_area_id = None
            if parent_area_code:
                parent_area = request.env["spp.area"].search([("code", "=", parent_area_code)], limit=1)
                parent_area_id = parent_area.id if parent_area else None

            geojson = report._to_geojson(
                admin_level=admin_level_int,
                area_ids=area_ids,
                parent_area_id=parent_area_id,
                include_geometry=include_geometry_bool,
                include_disaggregation=include_disaggregation_bool,
            )

            # Return simple format if requested (features only)
            if format == "simple":
                return self._json_response(
                    {
                        "type": "FeatureCollection",
                        "features": geojson.get("features", []),
                    }
                )

            return self._json_response(geojson)

        except MissingError as e:
            return self._json_response(
                {"error": str(e), "code": "NOT_FOUND"},
                status=404,
            )
        except AccessError as e:
            _logger.warning("Access denied to report %s: %s", report_code, str(e))
            return self._json_response(
                {"error": _("Access denied"), "code": "ACCESS_ERROR"},
                status=403,
            )
        except Exception as e:
            _logger.error(
                "Error generating GeoJSON for report %s: %s",
                report_code,
                str(e),
                exc_info=True,
            )
            return self._json_response(
                {"error": _("Failed to generate GeoJSON"), "code": "GEOJSON_ERROR"},
                status=500,
            )

    @http.route(
        "/api/v2/GISReport/<string:report_code>/summary",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def get_summary(self, report_code, admin_level=None, parent_area_code=None):
        """Get summary statistics for a report.

        Args:
            report_code: Code of the report (NOT database ID)
            admin_level: Level to summarize
            parent_area_code: Scope to children of this area (by code)

        Returns:
            Response: Summary statistics as JSON
        """
        try:
            report = self._get_report_by_code(report_code)

            # Convert admin_level to int if provided
            admin_level_int = int(admin_level) if admin_level else None

            # Resolve parent area code
            parent_area_id = None
            if parent_area_code:
                parent_area = request.env["spp.area"].search([("code", "=", parent_area_code)], limit=1)
                parent_area_id = parent_area.id if parent_area else None

            summary = report._get_summary(
                admin_level=admin_level_int,
                parent_area_id=parent_area_id,
            )

            return self._json_response(summary)

        except MissingError as e:
            return self._json_response(
                {"error": str(e), "code": "NOT_FOUND"},
                status=404,
            )
        except AccessError as e:
            _logger.warning("Access denied to report %s: %s", report_code, str(e))
            return self._json_response(
                {"error": _("Access denied"), "code": "ACCESS_ERROR"},
                status=403,
            )
        except Exception as e:
            _logger.error(
                "Error generating summary for report %s: %s",
                report_code,
                str(e),
                exc_info=True,
            )
            return self._json_response(
                {"error": _("Failed to generate summary"), "code": "SUMMARY_ERROR"},
                status=500,
            )

    @http.route(
        "/api/v2/GISReport/<string:report_code>/refresh",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def trigger_refresh(self, report_code):
        """Manually trigger report data refresh.

        Args:
            report_code: Code of the report (NOT database ID)

        Returns:
            Response: Status of refresh operation as JSON
        """
        try:
            report = self._get_report_by_code(report_code)

            # Trigger refresh (uses queue_job in implementation)
            report.action_refresh()

            return self._json_response(
                {
                    "status": "queued",
                    "report_code": report.code,
                    "timestamp": fields.Datetime.now().isoformat(),
                    "message": _("Report refresh has been queued for processing"),
                }
            )

        except MissingError as e:
            return self._json_response(
                {"error": str(e), "code": "NOT_FOUND"},
                status=404,
            )
        except AccessError as e:
            _logger.warning("Access denied to report %s: %s", report_code, str(e))
            return self._json_response(
                {"error": _("Access denied"), "code": "ACCESS_ERROR"},
                status=403,
            )
        except Exception as e:
            _logger.error(
                "Error triggering refresh for report %s: %s",
                report_code,
                str(e),
                exc_info=True,
            )
            return self._json_response(
                {"error": _("Failed to trigger refresh"), "code": "REFRESH_ERROR"},
                status=500,
            )
