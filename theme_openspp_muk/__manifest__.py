# pylint: disable=pointless-statement
{
    "name": "OpenSPP Theme",
    "author": "OpenSPP.org",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "category": "OpenSPP",
    "version": "19.0.2.0.0",
    "depends": [
        "base",
        "web",
        "muk_web_theme",
    ],
    "license": "LGPL-3",
    "development_status": "Stable",
    "maintainers": ["jeremi", "gonzalesedwin1123"],
    "data": [],
    "assets": {
        "web._assets_primary_variables": [
            "theme_openspp_muk/static/src/scss/colors.scss",
            "theme_openspp_muk/static/src/scss/colors_light.scss",
        ],
        "web.assets_web_dark": ["theme_openspp_muk/static/src/scss/colors_dark.scss"],
        "web.assets_backend": ["theme_openspp_muk/static/src/scss/navbar.scss"],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}
