{  # pylint: disable=pointless-statement
    "name": "OpenSPP DCI Core",
    "summary": "Core DCI (Digital Convergence Initiative) API components",
    "category": "OpenSPP/Integration",
    "version": "19.0.2.0.2",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Alpha",
    "depends": [
        "base",
        "spp_registry",
        # Not referenced by data files, but the security tests pin design
        # decisions against spp_security.group_spp_admin - keep the
        # dependency explicit rather than transitive via spp_registry.
        "spp_security",
    ],
    "external_dependencies": {
        "python": [
            "pydantic",
            "cryptography",
        ],
    },
    "data": [
        "security/dci_groups.xml",
        "security/ir.model.access.csv",
        "data/identifier_type_data.xml",
    ],
    "installable": True,
    "application": False,
    "maintainers": ["jeremi", "gonzalesedwin1123"],
}
