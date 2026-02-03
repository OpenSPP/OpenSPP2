# pylint: disable=pointless-statement
{
    "name": "CEL Domain Query Builder",
    "summary": "Write simple CEL-like expressions to filter records (OpenSPP/OpenG2P friendly)",
    "version": "19.0.2.0.0",
    "license": "LGPL-3",
    "development_status": "Stable",
    "author": "OpenSPP Community",
    "website": "https://docs.openspp.org",
    "category": "Tools",
    "depends": [
        "base",
        "spp_base_common",
        "spp_security",
        "spp_registry",  # Required for member aggregation tests (income field, group membership)
        # NOTE: spp_programs is NOT a dependency - profiles that reference
        # spp.program.membership and spp.entitlement are loaded dynamically
        # and will only work when spp_programs is also installed.
        # NOTE: spp_indicators is NO LONGER a dependency - this module now provides
        # the unified variable/value storage system (spp.data.value, spp.data.provider)
    ],
    "data": [
        "security/privileges.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "data/cron.xml",
        "data/filter_templates.xml",
        "data/formula_templates.xml",
        "views/data_provider_views.xml",
        "views/data_value_views.xml",
        "views/menus.xml",
        "wizard/cel_rule_wizard_views.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "post_init_hook": "post_init_hook",
}
