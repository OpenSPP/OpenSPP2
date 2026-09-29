"""Tests that the module's JavaScript imports resolve in the bundles that load them.

Odoo's module loader logs a console error for every import that no loaded file
defines, and the browser test runner fails any tour on a console error. The
test image has no Chrome, so tours never run in CI; these tests check import
resolution statically, using Odoo's own transpiler to read each file's
dependencies.

Limitation: a module defined only in a lazy-loaded bundle is not in the
defined set, so an import of one would be reported as unresolved.
"""

import ast
import re

from odoo.tests import tagged
from odoo.tests.common import BaseCase, TransactionCase
from odoo.tools.js_transpiler import (
    ODOO_MODULE_RE,
    is_odoo_module,
    transpile_javascript,
    url_to_module_path,
)
from odoo.tools.misc import file_open

from odoo.addons.base.models.assetsbundle import WebAsset

# web.webclient_bootstrap loads web.assets_web, then web.assets_tests in test mode.
BACKEND_TEST_BUNDLES = ("web.assets_web", "web.assets_tests")

TOUR_FILE = "/spp_cel_widget/static/tests/tours/cel_widget_tour.js"

ODOO_DEFINE_RE = re.compile(r"""odoo\.define\(\s*(['"])(?P<name>.+?)\1,\s*(?P<deps>\[.*?\])""", re.DOTALL)


def transpiled_dependencies(transpiled_content):
    """Return the module names a transpiled JS module imports, read from its odoo.define call."""
    match = ODOO_DEFINE_RE.search(transpiled_content)
    return ast.literal_eval(match["deps"])


def module_dependencies(url, content):
    """Return the module names a JS file imports, as Odoo's transpiler resolves them."""
    return transpiled_dependencies(transpile_javascript(url, content))


def defined_module_names(url, content):
    """Return the module names a JS file defines when it is loaded."""
    names = set()
    if is_odoo_module(url, content):
        names.add(url_to_module_path(url))
        header = ODOO_MODULE_RE.match(content)
        if header and header["alias"]:
            names.add(header["alias"])
    else:
        # Files that call odoo.define by hand, e.g. the "@odoo/owl" wrapper in web/static/lib.
        # A transpiled module never does, so its comments and strings are not scanned.
        names.update(match["name"] for match in ODOO_DEFINE_RE.finditer(content))
    return names


class TestAssetImportHelpers(BaseCase):
    """Unit tests for the helpers, so the bundle test cannot pass by matching nothing."""

    def test_module_dependencies_resolves_named_bare_and_relative_imports(self):
        content = (
            'import {registry} from "@web/core/registry";\n'
            'import "@web_tour/tour_utils";\n'
            'import {helper} from "./sibling";\n'
        )
        self.assertCountEqual(
            module_dependencies("/spp_cel_widget/static/src/js/example.js", content),
            ["@web/core/registry", "@web_tour/tour_utils", "@spp_cel_widget/js/sibling"],
        )

    def test_module_dependencies_reads_the_tour_file_web_tour_import(self):
        with file_open(TOUR_FILE.lstrip("/")) as tour_file:
            dependencies = module_dependencies(TOUR_FILE, tour_file.read())
        # Odoo 19's path; the pre-19 "@web_tour/tour_service/tour_utils" must fail here.
        self.assertIn(
            "@web_tour/tour_utils",
            dependencies,
            f"Expected the Odoo 19 @web_tour/tour_utils import in {TOUR_FILE}, got {dependencies}",
        )

    def test_defined_module_names_uses_the_path_and_alias(self):
        content = "/** @odoo-module alias=spp_cel_widget.Example **/\nexport const x = 1;\n"
        self.assertEqual(
            defined_module_names("/spp_cel_widget/static/src/js/example.js", content),
            {"@spp_cel_widget/js/example", "spp_cel_widget.Example"},
        )

    def test_defined_module_names_reads_a_hand_written_define(self):
        content = 'odoo.define("@odoo/owl", [], function () {\n    return owl;\n});\n'
        self.assertEqual(
            defined_module_names("/web/static/lib/owl/odoo_module.js", content),
            {"@odoo/owl"},
        )

    def test_defined_module_names_ignores_define_text_in_a_transpiled_module(self):
        # A transpiled module never contains a hand-written define, so a match in its
        # comments or strings is not a module; counting it could hide a missing import.
        content = (
            "/** @odoo-module **/\n"
            '/** Example: odoo.define("@example/not_a_module", [], function () {}); */\n'
            "export const x = 1;\n"
        )
        self.assertEqual(
            defined_module_names("/spp_cel_widget/static/src/js/example.js", content),
            {"@spp_cel_widget/js/example"},
        )

    def test_defined_module_names_reads_a_multi_line_hand_written_define(self):
        # Mirrors spreadsheet/static/src/o_spreadsheet/odoo_module.js.
        content = (
            "// @odoo-module ignore\n\n"
            'odoo.define(\n    "@odoo/o-spreadsheet",\n'
            '    ["@web/core/l10n/translation", "@spreadsheet/o_spreadsheet/o_spreadsheet"],\n'
            "    function (require) {\n        return {};\n    }\n);\n"
        )
        self.assertEqual(
            defined_module_names("/spreadsheet/static/src/o_spreadsheet/odoo_module.js", content),
            {"@odoo/o-spreadsheet"},
        )


@tagged("post_install", "-at_install")
class TestCelWidgetAssetImports(TransactionCase):
    """Integration test: every import in this module's JS resolves on the backend test page."""

    def _backend_test_page_scripts(self):
        """Return ``{url: JavascriptAsset}`` for the scripts the backend test page loads.

        Odoo's own bundle objects decide what is transpiled and serve the transpiled
        content, and they also read ``ir.asset`` entries stored as attachments.
        """
        scripts = {}
        for bundle in BACKEND_TEST_BUNDLES:
            for asset in self.env["ir.qweb"]._get_asset_bundle(bundle, css=False).javascripts:
                scripts.setdefault(asset.url, asset)
        return scripts

    def test_imports_resolve_on_the_backend_test_page(self):
        scripts = self._backend_test_page_scripts()
        # The source as written: the @odoo-module header (with its alias) and any
        # hand-written odoo.define live there, not in the transpiled output.
        # JavascriptAsset reads it through this same base-class property.
        defined = set().union(
            *(defined_module_names(url, WebAsset.content.fget(asset)) for url, asset in scripts.items())
        )
        own_modules = {
            url: asset for url, asset in scripts.items() if url.startswith("/spp_cel_widget/") and asset.is_transpiled
        }
        self.assertIn(TOUR_FILE, own_modules)

        unresolved = {}
        for url, asset in own_modules.items():
            missing = sorted(set(transpiled_dependencies(asset.content)) - defined)
            if missing:
                unresolved[url] = missing
        self.assertFalse(
            unresolved,
            f"Imports that no file on the backend test page defines (the module loader "
            f"logs a console error for each, failing every tour): {unresolved}",
        )
