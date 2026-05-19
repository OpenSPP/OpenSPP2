# pylint: disable=pointless-statement
{
    "name": "OpenSPP DCI - OpenG2P Preset",
    "summary": ("Pre-configured DCI data source, provider, and CEL variables for OpenG2P deployments"),
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "spp_cel_dci_bridge",
        "spp_vocabulary",
        "spp_registry",
        # The SR-import wizard's mirror-to-DR feature calls the
        # OpenSPP-DR via the DCI register-individual endpoint, using
        # OpenSPPDRService and the spp_dci_openspp_dr data source preset
        # (the source is what supplies vendor='openspp').
        "spp_dci_openspp_dr",
    ],
    "external_dependencies": {"python": []},
    "data": [
        "security/ir.model.access.csv",
        "data/openg2p_id_types.xml",
        "data/openg2p_data_source.xml",
        "data/openg2p_data_provider.xml",
        "data/openg2p_cel_variables.xml",
        "views/sr_import_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
