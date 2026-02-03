# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP CEL Vocabulary Integration",
    "summary": "Vocabulary-aware CEL functions for robust eligibility rules",
    "version": "19.0.2.0.0",
    "category": "OpenSPP",
    "author": "OpenSPP.org",
    "website": "https://docs.openspp.org",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "spp_cel_domain",
        "spp_vocabulary",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/concept_groups.xml",
    ],
    "installable": True,
    "auto_install": True,
    "post_init_hook": "post_init_hook",
}
