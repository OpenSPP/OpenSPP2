"""Placement zones for custom field positioning in registry forms."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StudioPlacementZone(models.Model):
    """Defines available placement zones in registry forms.

    Placement zones are pre-defined locations where users can add custom
    fields. Each zone corresponds to a named element in the registry form
    views that can be targeted via XPath.
    """

    _name = "spp.studio.placement.zone"
    _description = "Field Placement Zone"
    _order = "target_type, tab_sequence, sequence"

    name = fields.Char(
        string="Zone Name",
        required=True,
        translate=True,
        help="Display name shown to users (e.g., 'Demographics Section')",
    )
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Technical identifier (e.g., 'demographics_section')",
    )
    description = fields.Text(
        string="Description",
        translate=True,
        help="Explanation of what kind of fields belong in this zone",
    )

    target_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group"),
            ("both", "Both"),
        ],
        string="Target Registry",
        required=True,
        default="both",
        help="Which registry type this zone applies to",
    )

    tab_name = fields.Char(
        string="Tab Name",
        required=True,
        help="Name of the tab containing this zone (e.g., 'Profile', 'Identity')",
    )
    tab_sequence = fields.Integer(
        string="Tab Sequence",
        default=10,
        help="Order of the tab in the form",
    )

    xpath_expression = fields.Char(
        string="XPath Expression",
        required=True,
        help="XPath to locate the zone in the view (e.g., //group[@name='demographics_section'])",
    )
    xpath_position = fields.Selection(
        [
            ("inside", "Inside (append)"),
            ("before", "Before"),
            ("after", "After"),
        ],
        string="Position",
        default="inside",
        help="Where to insert new fields relative to the XPath target",
    )

    view_id = fields.Many2one(
        "ir.ui.view",
        string="Target View",
        help="The form view this zone belongs to (auto-detected if not set)",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of zones within a tab",
    )
    active = fields.Boolean(
        default=True,
    )

    # Visual context for users
    form_preview_hint = fields.Text(
        string="Form Location",
        compute="_compute_form_preview_hint",
        help="Visual description of where this zone appears in the form",
    )
    icon = fields.Selection(
        [
            ("fa-user", "Person"),
            ("fa-users", "Group"),
            ("fa-id-card", "Identity"),
            ("fa-address-book", "Contact"),
            ("fa-money", "Financial"),
            ("fa-calendar", "Events/Participation"),
            ("fa-link", "Relationships"),
            ("fa-folder", "General"),
        ],
        string="Icon",
        default="fa-folder",
        help="Icon to represent this zone visually",
    )

    # Statistics
    field_count = fields.Integer(
        string="Fields",
        compute="_compute_field_count",
    )

    @api.depends("tab_name", "xpath_position", "description", "target_type")
    def _compute_form_preview_hint(self):
        """Generate a user-friendly description of where this zone appears."""
        registry_names = {"individual": "Individual", "group": "Group", "both": "Both"}
        position_text = {
            "inside": "within",
            "before": "before",
            "after": "after",
        }
        for zone in self:
            registry = registry_names.get(zone.target_type, "")
            position = position_text.get(zone.xpath_position, "in")
            zone.form_preview_hint = _(
                "📍 %(registry)s Registry Form\n"
                "   └─ %(tab)s tab\n"
                "      └─ %(position)s the %(name)s section\n\n"
                "%(description)s",
                registry=registry,
                tab=zone.tab_name,
                position=position.title(),
                name=zone.name.replace(f"{registry} - ", ""),
                description=zone.description or "",
            )

    @api.constrains("code")
    def _check_code_unique(self):
        """Ensure zone code is unique."""
        for zone in self:
            if self.search_count([("code", "=", zone.code), ("id", "!=", zone.id)]):
                raise ValidationError(_("Zone code must be unique!"))

    @api.depends("code")
    def _compute_field_count(self):
        """Count fields placed in this zone."""
        StudioField = self.env.get("spp.studio.field")
        for zone in self:
            if StudioField:
                zone.field_count = StudioField.search_count([("placement_zone_id", "=", zone.id)])
            else:
                zone.field_count = 0

    def name_get(self):
        """Return name with tab prefix for clarity."""
        result = []
        for zone in self:
            name = f"{zone.tab_name} > {zone.name}"
            result.append((zone.id, name))
        return result

    @api.model
    def get_zones_for_target(self, target_type):
        """Get available zones for a specific target type.

        Args:
            target_type: 'individual' or 'group'

        Returns:
            Recordset of applicable zones
        """
        domain = [
            "|",
            ("target_type", "=", target_type),
            ("target_type", "=", "both"),
        ]
        return self.search(domain, order="tab_sequence, sequence")

    @api.model
    def get_zone_by_code(self, code):
        """Get a zone by its code.

        Args:
            code: Zone code string

        Returns:
            Zone record or empty recordset
        """
        return self.search([("code", "=", code)], limit=1)
