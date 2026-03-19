# pylint: disable-next=pointless-statement
{
    "name": "OpenSPP Studio - Events",
    "version": "19.0.2.0.0",
    "category": "OpenSPP/Configuration",
    "summary": "No-code event type designer for data collection",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Production/Stable",
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
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
