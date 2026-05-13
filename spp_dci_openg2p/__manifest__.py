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
        "spp_dci_client_dr",
    ],
    "external_dependencies": {"python": []},
    "data": [
        "data/openg2p_data_source.xml",
        "data/openg2p_data_provider.xml",
        "data/openg2p_cel_variables.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
