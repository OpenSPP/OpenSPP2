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

# web.webclient_bootstrap loads web.assets_web, then web.assets_tests in test mode.
BACKEND_TEST_BUNDLES = ("web.assets_web", "web.assets_tests")

TOUR_FILE = "/spp_cel_widget/static/tests/tours/cel_widget_tour.js"

ODOO_DEFINE_RE = re.compile(r"""odoo\.define\((['"])(?P<name>.+?)\1,\s*(?P<deps>\[.*?\])""")


def module_dependencies(url, content):
    """Return the module names a JS file imports, as Odoo's transpiler resolves them."""
    match = ODOO_DEFINE_RE.search(transpile_javascript(url, content))
    return ast.literal_eval(match["deps"])


def defined_module_names(url, content):
    """Return the module names a JS file defines when it is loaded."""
    names = set()
    if is_odoo_module(url, content):
        names.add(url_to_module_path(url))
        header = ODOO_MODULE_RE.match(content)
        if header and header["alias"]:
            names.add(header["alias"])
    # Files that call odoo.define by hand, e.g. the "@odoo/owl" wrapper in web/static/lib.
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
        self.assertTrue(
            any(name.startswith("@web_tour/") for name in dependencies),
            f"Expected a @web_tour/ import in {TOUR_FILE}, got {dependencies}",
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


@tagged("post_install", "-at_install")
class TestCelWidgetAssetImports(TransactionCase):
    """Integration test: every import in this module's JS resolves on the backend test page."""

    def _backend_test_page_scripts(self):
        scripts = {}
        for bundle in BACKEND_TEST_BUNDLES:
            for path, full_path, _bundle, _last_modified in self.env["ir.asset"]._get_asset_paths(bundle, {}):
                if path.endswith(".js") and path not in scripts:
                    with file_open(full_path) as script:
                        scripts[path] = script.read()
        return scripts

    def test_imports_resolve_on_the_backend_test_page(self):
        scripts = self._backend_test_page_scripts()
        defined = set().union(*(defined_module_names(url, content) for url, content in scripts.items()))
        own_modules = {
            url: content
            for url, content in scripts.items()
            if url.startswith("/spp_cel_widget/") and is_odoo_module(url, content)
        }
        self.assertIn(TOUR_FILE, own_modules)

        unresolved = {}
        for url, content in own_modules.items():
            missing = sorted(set(module_dependencies(url, content)) - defined)
            if missing:
                unresolved[url] = missing
        self.assertFalse(
            unresolved,
            f"Imports that no file on the backend test page defines (the module loader "
            f"logs a console error for each, failing every tour): {unresolved}",
        )
