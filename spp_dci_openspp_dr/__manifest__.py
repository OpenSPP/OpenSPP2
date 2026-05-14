{  # pylint: disable=pointless-statement
    "name": "OpenSPP DCI — OpenSPP-DR Preset",
    "summary": (
        "Pre-configured DCI data source, provider, and CEL variable binding "
        "for an OpenSPP-DR (Disability Registry) instance."
    ),
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
        "spp_vocabulary",
    ],
    "external_dependencies": {"python": []},
    "data": [
        "security/ir.model.access.csv",
        "data/openspp_dr_id_types.xml",
        "data/openspp_dr_data_source.xml",
        "data/openspp_dr_data_provider.xml",
        "data/openspp_dr_cel_variable.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
