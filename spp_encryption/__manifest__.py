# pylint: disable=pointless-statement
{
    "name": "OpenSPP Encryption: Base",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "sequence": 1,
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/OpenSPP2",
    "license": "LGPL-3",
    "development_status": "Beta",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "depends": [
        "spp_security",
        "spp_key_management",  # Centralized key storage
    ],
    "external_dependencies": {"python": ["jwcrypto>=1.5.6"]},
    "data": [
        "security/privileges.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "views/encryption_provider.xml",
        "data/default_provider.xml",
    ],
    "assets": {
        "web.assets_backend": [],
        "web.assets_qweb": [],
    },
    "demo": [],
    "images": [],
    "application": False,
    "installable": True,
    "auto_install": False,
    "summary": "Implements advanced cryptographic services for OpenSPP, enabling data encryption, decryption, digital signing, and signature verification for sensitive program information. It securely manages cryptographic keys in JWK format and distributes public keys via JWKS, facilitating secure inter-system verification and data integrity.",
    "post_init_hook": "post_init_hook",
}
