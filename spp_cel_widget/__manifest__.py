{
    "name": "OpenSPP CEL Expression Widget",
    "version": "19.0.2.0.0",
    "category": "OpenSPP",
    "summary": "Reusable CEL expression editor with syntax highlighting and autocomplete",
    "author": "OpenSPP",
    "website": "https://github.com/OpenSPP/openspp-modules",
    "license": "LGPL-3",
    "development_status": "Stable",
    "depends": [
        "web",
        "spp_cel_domain",
    ],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        "security/ir.model.access.csv",
        "wizard/cel_widget_demo_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # CodeMirror library
            "spp_cel_widget/static/lib/codemirror/codemirror.bundle.js",
            "spp_cel_widget/static/lib/codemirror/codemirror.css",
            # CEL language support
            "spp_cel_widget/static/src/js/cel_language/syntax.js",
            "spp_cel_widget/static/src/js/cel_language/highlight.js",
            "spp_cel_widget/static/src/js/cel_language/autocomplete.js",
            "spp_cel_widget/static/src/js/cel_language/lint.js",
            # Widget components
            "spp_cel_widget/static/src/js/cel_symbol_service.js",
            "spp_cel_widget/static/src/js/cel_symbol_browser.js",
            "spp_cel_widget/static/src/js/cel_editor.js",
            "spp_cel_widget/static/src/js/cel_editor_field.js",
            # Templates
            "spp_cel_widget/static/src/xml/cel_symbol_browser.xml",
            "spp_cel_widget/static/src/xml/cel_editor.xml",
            "spp_cel_widget/static/src/xml/cel_editor_field.xml",
            # Styles
            "spp_cel_widget/static/src/scss/cel_editor.scss",
        ],
        "web.assets_tests": [
            "spp_cel_widget/static/tests/tours/cel_widget_tour.js",
        ],
    },
    "installable": True,
    "auto_install": True,
    "application": False,
}
