# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP Farmer Registry: Change Request Types",
    "summary": "Farmer-specific change request types for farm details and activities",
    "category": "OpenSPP",
    "version": "19.0.1.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123", "emjay0921"],
    "depends": [
        "spp_change_request_v2",
        "spp_farmer_registry",
        "spp_land_record",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/change_request_type_views.xml",
        "views/cr_farm_details_views.xml",
        "views/cr_farm_activity_views.xml",
        "views/cr_land_parcel_views.xml",
        "views/cr_farm_asset_views.xml",
        "data/cr_types.xml",
        "data/approval_definitions.xml",
    ],
    "assets": {},
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "description": """
OpenSPP Farmer Registry: Change Request Types
==============================================

Provides farmer-specific change request types for managing farm data changes
through the approval workflow.

CR Types Included
-----------------
- **Update Farm Details**: Modify farm type, size, land tenure, and acreage breakdown
- **Add Farm Activity**: Add new crop, livestock, or aquaculture activity
- **Update Farm Activity**: Modify existing farm activities

All CR types use the field_mapping strategy and can be customized via Studio.
    """,
}
