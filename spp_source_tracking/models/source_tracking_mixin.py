# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SourceTrackingMixin(models.AbstractModel):
    """Mixin for tracking data provenance.

    This mixin provides source tracking capabilities for models that need
    to track where data originated and how it was collected.

    Usage:
        class MyModel(models.Model):
            _name = "my.model"
            _inherit = ["my.model", "spp.mixin.source.tracking"]

    Context variables for controlling source tracking:
        - source_system: Override the detected source system
        - source_reference: Reference ID in source system
        - collection_method: Override collection method detection
        - skip_source_tracking: Skip updating last_update fields on write
        - import_file: Automatically detected for bulk imports
    """

    _name = "spp.mixin.source.tracking"
    _description = "Source Tracking Mixin"

    # === CREATION PROVENANCE (immutable after create) ===
    source_system = fields.Char(
        string="Original Source",
        readonly=True,
        copy=False,
        help="System that originally created this record",
    )
    source_reference = fields.Char(
        string="Source Reference",
        readonly=True,
        copy=False,
        help="Original ID or reference in source system",
    )
    collection_method = fields.Selection(
        selection="_selection_collection_method",
        string="Collection Method",
        readonly=True,
        copy=False,
    )
    collection_date = fields.Datetime(
        string="Collection Date",
        readonly=True,
        copy=False,
        help="When data was originally collected (may differ from create_date)",
    )

    # === LAST UPDATE PROVENANCE ===
    last_update_system = fields.Char(
        string="Last Updated By System",
        readonly=True,
        copy=False,
        help="System that made the most recent update",
    )
    last_update_reference = fields.Char(
        string="Last Update Reference",
        readonly=True,
        copy=False,
        help="Reference ID for the update (API request ID, import batch, etc.)",
    )

    @api.model
    def _selection_collection_method(self):
        """Return available collection methods.

        Extensions can override this to add additional methods.
        """
        return [
            ("manual", "Manual Entry"),
            ("import", "Bulk Import"),
            ("api", "API"),
            ("mobile", "Mobile App"),
            ("migration", "Data Migration"),
            ("merge", "Created from Merge"),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        """Set source tracking on create if not provided."""
        for vals in vals_list:
            if not vals.get("source_system"):
                vals["source_system"] = self._get_current_source_system()
            if not vals.get("collection_method"):
                vals["collection_method"] = self._get_current_collection_method()
            if not vals.get("collection_date"):
                vals["collection_date"] = fields.Datetime.now()
            # Set source_reference from context if provided and not already set
            if not vals.get("source_reference") and self.env.context.get("source_reference"):
                vals["source_reference"] = self.env.context["source_reference"]
        return super().create(vals_list)

    def write(self, vals):
        """Track update source, preserve original source fields."""
        # Never overwrite original source fields
        for field in (
            "source_system",
            "source_reference",
            "collection_method",
            "collection_date",
        ):
            vals.pop(field, None)

        # Determine if we need to track update provenance
        should_track = not self.env.context.get("skip_source_tracking")

        # Call parent write first (don't modify vals - Odoo 19 compatibility)
        result = super().write(vals)

        # Update tracking fields separately after parent write completes
        if should_track and self:
            tracking_vals = {
                "last_update_system": self._get_current_source_system(),
                "last_update_reference": self.env.context.get("source_reference"),
            }
            # Use skip_source_tracking to prevent infinite recursion
            super(SourceTrackingMixin, self.with_context(skip_source_tracking=True)).write(tracking_vals)

        return result

    def _get_current_source_system(self):
        """Determine current source from context or request.

        Priority:
        1. Explicit context value (source_system)
        2. X-Source-System HTTP header (for external API calls)
        3. Default to 'odoo-ui' for standard UI interactions
        """
        if self.env.context.get("source_system"):
            return self.env.context["source_system"]

        try:
            from odoo.http import request

            if request and hasattr(request, "httprequest"):
                # Explicit header from external systems takes priority
                header = request.httprequest.headers.get("X-Source-System")
                if header:
                    return header
                # Odoo web client uses JSON-RPC via /web/ or /jsonrpc routes
                # These are UI interactions, not external API calls
                if not self._is_external_api_request(request):
                    return "odoo-ui"
                return "api"
        except (ImportError, RuntimeError):
            pass  # No request context

        return "odoo-ui"

    def _get_current_collection_method(self):
        """Determine collection method from context.

        Priority:
        1. Explicit context value (collection_method)
        2. import_file context (for bulk imports)
        3. External API request (not Odoo web client)
        4. Default to 'manual' for UI interactions
        """
        if self.env.context.get("collection_method"):
            return self.env.context["collection_method"]

        if self.env.context.get("import_file"):
            return "import"

        try:
            from odoo.http import request

            if request and hasattr(request, "httprequest"):
                if self._is_external_api_request(request):
                    return "api"
        except (ImportError, RuntimeError):
            pass

        return "manual"

    @staticmethod
    def _is_external_api_request(request):
        """Check if the current request is from an external API client.

        Odoo's web UI uses JSON-RPC over routes like /web/, /jsonrpc, etc.
        External API clients typically use /api/, /xmlrpc/, or set
        X-Source-System headers.
        """
        path = request.httprequest.path or ""
        # Odoo web client routes - these are UI, not external API
        if path.startswith(("/web/", "/jsonrpc", "/web")):
            return False
        # Explicit external API routes
        if path.startswith(("/api/", "/xmlrpc/", "/jsonrpc/")):
            return True
        # X-Source-System header indicates an external caller
        if request.httprequest.headers.get("X-Source-System"):
            return True
        return False
