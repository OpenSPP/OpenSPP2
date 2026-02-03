# pylint: disable-next=pointless-statement
{
    "name": "OpenSPP Studio - Events",
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Configuration",
    "summary": "No-code event type designer for data collection",
    "description": """
OpenSPP Studio - Event Types
=============================

Provides a user-friendly interface for creating custom event types without code.
Event types define data collection forms that can be recorded against individuals/groups.

Features:
- Visual event type builder wizard (3 steps)
- Define custom fields for events (text, number, date, selection, etc.)
- Target type configuration (individual, group, or both)
- Draft/Active lifecycle for safe editing
- Integration with spp.event.data infrastructure
- Optional Kobo form integration
- Configurable approval workflows

Use Cases:
- Health screenings
- Household visits
- Surveys and assessments
- Field inspections
- Data collection campaigns
    """,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "depends": [
        "spp_studio",
        "spp_event_data",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Views
        "views/studio_event_type_views.xml",
        "views/studio_event_template_views.xml",
        "views/menus.xml",
        # Wizards
        "wizard/event_type_wizard_views.xml",
        "wizard/event_data_entry_wizard_views.xml",
        # Data
        "data/event_field_templates.xml",
    ],
    "installable": True,
    "auto_install": True,
}
