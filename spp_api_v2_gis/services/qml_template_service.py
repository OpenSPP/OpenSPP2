# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""QML Template Service for QGIS styling.

Generates QML (QGIS Layer Definition) files from templates, injecting
values from GIS report configurations such as color schemes, thresholds,
and opacity settings.
"""

import logging
import os

_logger = logging.getLogger(__name__)


class QMLTemplateService:
    """Service for generating QML style files from templates."""

    TEMPLATE_DIR = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "qml_templates",
    )

    # Map geometry types to template files
    TEMPLATE_MAP = {
        "polygon": "graduated_polygon.qml",
        "point": "point_basic.qml",
        "cluster": "point_cluster.qml",
        "heatmap": "point_basic.qml",  # Fallback to basic point
    }

    def __init__(self, env):
        """Initialize service with Odoo environment.

        Args:
            env: Odoo environment for database access
        """
        self.env = env

    def generate_qml(
        self,
        report_id: int,
        geometry_type: str,
        field_name: str | None = None,
        opacity: float = 0.7,
        admin_level: int | None = None,
    ) -> str:
        """Generate QML XML for a GIS report.

        Args:
            report_id: ID of spp.gis.report record
            geometry_type: Type of geometry (polygon, point, cluster, heatmap)
            field_name: Field name to symbolize (for choropleth)
            opacity: Layer opacity (0.0 to 1.0)
            admin_level: Admin level to adapt thresholds for (optional)

        Returns:
            QML XML string

        Raises:
            ValueError: If report not found or template missing
        """
        # Get report record
        report = self.env["spp.gis.report"].browse(report_id)
        if not report.exists():
            raise ValueError(f"Report with ID {report_id} not found")

        # Load template
        template_name = self.TEMPLATE_MAP.get(geometry_type, "point_basic.qml")
        template_path = os.path.join(self.TEMPLATE_DIR, template_name)

        if not os.path.exists(template_path):
            _logger.warning("QML template not found: %s", template_path)
            raise ValueError(f"QML template not found: {template_name}")

        with open(template_path) as f:
            template = f.read()

        # Generate QML based on geometry type
        if geometry_type == "polygon":
            return self._generate_graduated_polygon(template, report, field_name, opacity, admin_level=admin_level)
        elif geometry_type in ("point", "cluster", "heatmap"):
            return self._generate_point(template, report, opacity)
        else:
            raise ValueError(f"Unsupported geometry type: {geometry_type}")

    def _generate_graduated_polygon(
        self,
        template: str,
        report,
        field_name: str | None,
        opacity: float,
        admin_level: int | None = None,
    ) -> str:
        """Generate graduated polygon (choropleth) QML.

        When admin_level is provided, thresholds are adapted to the
        data range at that level so features show meaningful color
        variation even when global thresholds would compress them
        into a single bucket.

        Args:
            template: Template string
            report: GIS report record
            field_name: Field to symbolize
            opacity: Layer opacity
            admin_level: Admin level to compute per-level thresholds (optional)

        Returns:
            Populated QML string
        """
        # Use configured field or default
        if not field_name:
            field_name = "normalized_value"

        # Get color scheme
        color_scheme = report.color_scheme_id
        if not color_scheme:
            # Fallback to default scheme
            color_scheme = self.env["spp.gis.color.scheme"].get_default_scheme()

        # Get thresholds
        thresholds = report.threshold_ids.sorted("sequence")
        if not thresholds:
            _logger.warning("No thresholds defined for report: %s", report.id)
            # Generate default single-class QML
            return self._generate_default_polygon(template, field_name, opacity)

        # When an admin level is specified, compute per-level thresholds
        # to avoid all features falling into a single global bucket
        if admin_level is not None:
            level_thresholds = self._compute_level_thresholds(report, thresholds, field_name, admin_level)
            if level_thresholds:
                return self._render_graduated_polygon(template, level_thresholds, field_name, opacity)

        # Use global thresholds
        threshold_defs = []
        for threshold in thresholds:
            threshold_defs.append(
                {
                    "lower": threshold.min_value if threshold.min_value is not None else 0,
                    "upper": threshold.max_value if threshold.max_value is not None else 999999,
                    "label": threshold.label or f"Class {len(threshold_defs) + 1}",
                    "color": threshold.color or "#808080",
                }
            )

        return self._render_graduated_polygon(template, threshold_defs, field_name, opacity)

    def _compute_level_thresholds(self, report, global_thresholds, field_name, admin_level):
        """Compute thresholds adapted to a specific admin level's data range.

        Uses equal-interval breaks across the level's actual data range,
        preserving the global threshold colors and labels.

        Args:
            report: GIS report record
            global_thresholds: Report's threshold records
            field_name: Field being symbolized
            admin_level: Admin level to compute thresholds for

        Returns:
            list[dict]: Per-level threshold definitions, or None to fall back to global
        """
        # Query the data range at this admin level
        data = (
            self.env["spp.gis.report.data"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("report_id", "=", report.id),
                    ("area_level", "=", admin_level),
                    (field_name, "!=", False),
                ]
            )
        )

        if not data:
            return None

        values = [getattr(d, field_name) for d in data if getattr(d, field_name) is not None]
        if not values:
            return None

        min_val = min(values)
        max_val = max(values)

        # If all values are the same, no differentiation is possible
        if min_val == max_val:
            return None

        # Check if global thresholds already provide good differentiation
        # by counting how many distinct buckets the level's data falls into
        sorted_thresholds = global_thresholds.sorted("sequence")
        buckets_used = set()
        for val in values:
            for idx, threshold in enumerate(sorted_thresholds):
                lower = threshold.min_value if threshold.min_value is not None else float("-inf")
                upper = threshold.max_value if threshold.max_value is not None else float("inf")
                if lower <= val <= upper:
                    buckets_used.add(idx)
                    break
        # If data uses 2+ buckets, global thresholds work well enough
        if len(buckets_used) >= 2:
            return None

        # Recompute: equal-interval breaks using global colors/labels
        number_of_classes = len(sorted_thresholds)
        interval = (max_val - min_val) / number_of_classes

        # Add small padding to ensure min and max values are included
        padded_min = min_val - (interval * 0.001)
        padded_max = max_val + (interval * 0.001)
        interval = (padded_max - padded_min) / number_of_classes

        level_thresholds = []
        for idx, threshold in enumerate(sorted_thresholds):
            lower = padded_min + (idx * interval)
            upper = padded_min + ((idx + 1) * interval)
            level_thresholds.append(
                {
                    "lower": round(lower, 6),
                    "upper": round(upper, 6),
                    "label": threshold.label or f"Class {idx + 1}",
                    "color": threshold.color or "#808080",
                }
            )

        return level_thresholds

    def _render_graduated_polygon(self, template, threshold_defs, field_name, opacity):
        """Render a graduated polygon QML from threshold definitions.

        Args:
            template: Template string
            threshold_defs: List of threshold dicts with lower, upper, label, color
            field_name: Field to symbolize
            opacity: Layer opacity

        Returns:
            Populated QML string
        """
        ranges_xml = []
        symbols_xml = []

        for idx, threshold in enumerate(threshold_defs):
            lower = threshold["lower"]
            upper = threshold["upper"]
            label = threshold["label"]
            color_hex = threshold["color"]

            color_rgb = self._hex_to_rgb(color_hex)

            ranges_xml.append(
                f'      <range symbol="{idx}" lower="{lower}" upper="{upper}" '
                f'label="{self._escape_xml(label)}" render="true"/>'
            )

            symbols_xml.append(
                f'      <symbol type="fill" name="{idx}" alpha="{opacity}" clip_to_extent="1">\n'
                f'        <layer class="SimpleFill" locked="0" enabled="1">\n'
                f'          <prop k="border_width_map_unit_scale" v="3x:0,0,0,0,0,0"/>\n'
                f'          <prop k="color" v="{color_rgb}"/>\n'
                f'          <prop k="joinstyle" v="bevel"/>\n'
                f'          <prop k="offset" v="0,0"/>\n'
                f'          <prop k="offset_map_unit_scale" v="3x:0,0,0,0,0,0"/>\n'
                f'          <prop k="offset_unit" v="MM"/>\n'
                f'          <prop k="outline_color" v="35,35,35,255"/>\n'
                f'          <prop k="outline_style" v="solid"/>\n'
                f'          <prop k="outline_width" v="0.26"/>\n'
                f'          <prop k="outline_width_unit" v="MM"/>\n'
                f'          <prop k="style" v="solid"/>\n'
                f"        </layer>\n"
                f"      </symbol>"
            )

        qml = template.replace("{{FIELD_NAME}}", field_name)
        qml = qml.replace("{{RANGES}}", "\n".join(ranges_xml))
        qml = qml.replace("{{SYMBOLS}}", "\n".join(symbols_xml))
        qml = qml.replace("{{OPACITY}}", str(opacity))

        return qml

    def _generate_point(
        self,
        template: str,
        report,
        opacity: float,
    ) -> str:
        """Generate point marker QML.

        Args:
            template: Template string
            report: GIS report record
            opacity: Layer opacity

        Returns:
            Populated QML string
        """
        # Get color from color scheme
        color_scheme = report.color_scheme_id
        if not color_scheme:
            color_scheme = self.env["spp.gis.color.scheme"].get_default_scheme()

        # Use first color from scheme
        colors = color_scheme.get_colors_list()
        color_hex = colors[0] if colors else "#3498db"
        color_rgb = self._hex_to_rgb(color_hex)

        # Replace placeholders
        qml = template.replace("{{COLOR}}", color_rgb)
        qml = qml.replace("{{OPACITY}}", str(opacity))

        return qml

    def _generate_default_polygon(
        self,
        template: str,
        field_name: str,
        opacity: float,
    ) -> str:
        """Generate default single-class polygon QML.

        Args:
            template: Template string
            field_name: Field name
            opacity: Layer opacity

        Returns:
            Populated QML string
        """
        # Single default range
        ranges_xml = '      <range symbol="0" lower="0" upper="999999" label="All Values" render="true"/>'

        # Single default symbol (blue)
        symbols_xml = (
            f'      <symbol type="fill" name="0" alpha="{opacity}" clip_to_extent="1">\n'
            f'        <layer class="SimpleFill" locked="0" enabled="1">\n'
            f'          <prop k="color" v="52,152,219,255"/>\n'
            f'          <prop k="outline_color" v="35,35,35,255"/>\n'
            f'          <prop k="outline_style" v="solid"/>\n'
            f'          <prop k="outline_width" v="0.26"/>\n'
            f'          <prop k="outline_width_unit" v="MM"/>\n'
            f'          <prop k="style" v="solid"/>\n'
            f"        </layer>\n"
            f"      </symbol>"
        )

        qml = template.replace("{{FIELD_NAME}}", field_name)
        qml = qml.replace("{{RANGES}}", ranges_xml)
        qml = qml.replace("{{SYMBOLS}}", symbols_xml)
        qml = qml.replace("{{OPACITY}}", str(opacity))

        return qml

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> str:
        """Convert hex color to RGB string for QML.

        Args:
            hex_color: Hex color string (e.g., '#3498db')

        Returns:
            RGB string for QML (e.g., '52,152,219,255')
        """
        hex_color = hex_color.lstrip("#")
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"{r},{g},{b},255"
        except (ValueError, IndexError):
            # Fallback to gray
            return "128,128,128,255"

    @staticmethod
    def _escape_xml(text: str) -> str:
        """Escape special XML characters.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
