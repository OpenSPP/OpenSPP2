{  # pylint: disable=pointless-statement
    "name": "OpenSPP DCI Server — Disability Registry",
    "summary": (
        "Server-side DCI Disability Registry handler — replaces the 501 stub "
        "in spp_dci_server with a real /disability/registry/sync/search endpoint."
    ),
    "version": "19.0.1.0.0",
    "category": "OpenSPP/Integration",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "spp_dci_server",
        "spp_registry",
        "spp_vocabulary",
        # The register service creates spp.disability.assessment records
        # when the SR self-reports disability. That model is defined in
        # spp_disability_registry, which is the actual data store the
        # DR's DCI server reads from (has_disability, severity, etc.).
        "spp_disability_registry",
        # Loaded so the green-theme overrides in static/src/scss/dr_theme.scss
        # apply after spp_base_common/navbar.scss in the assets_backend bundle.
        "spp_base_common",
    ],
    "external_dependencies": {"python": []},
    "data": [
        "security/ir.model.access.csv",
        "data/dr_id_types.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "spp_dci_server_disability/static/src/scss/dr_theme.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
