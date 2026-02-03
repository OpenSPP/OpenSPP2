# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP DRIMS - Sri Lanka Configuration",
    "summary": "Sri Lanka-specific configuration for DRIMS disaster response "
    "inventory management. Includes geographic hierarchy, government agencies, "
    "and approval thresholds per DMC requirements.",
    "category": "OpenSPP/Inventory",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "spp_drims",
        "spp_approval",
        "product_expiry",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Company/locale configuration (must be first)
        "data/company_config.xml",
        # Master data
        "data/area_types.xml",
        # Areas imported via spp.area.import from lka_adminboundaries_tabulardata.xlsx
        "data/hazard_categories.xml",
        "data/vocabulary_codes.xml",
        "data/agencies.xml",
        "data/warehouses.xml",
        "data/ir_sequence.xml",
        # Product catalog
        "data/product_categories.xml",
        "data/products.xml",
        # Users must come before approval_config (referenced by tiers)
        "data/demo_users.xml",
        # Approval workflow configuration
        "data/approval_config.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
