# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Guardrail for the CEL Expressions view's ace editor configuration.

Odoo 19's ``CodeEditor`` OWL component validates its ``mode`` prop against
a fixed allow-list:

    addons/web/static/src/core/code_editor/code_editor.js
        static MODES = ["javascript", "xml", "qweb", "scss", "python"];

A field declaring ``widget="ace" options="{'mode': '<invalid>'}"`` crashes
the client the moment the editor mounts (the field is only rendered when
its ``use_cel_*`` toggle is enabled). The original view used
``'mode': 'text'`` — not in MODES — which is exactly that crash. This test
parses the view arch and fails if any ace field declares a mode the
component would reject, so the regression can't silently come back.
"""

import ast

from lxml import etree

from odoo.tests import TransactionCase, tagged

# Mirror of CodeEditor.MODES (see module docstring). Kept here as a literal
# because the allow-list lives in JS and isn't importable from Python.
VALID_ACE_MODES = {"javascript", "xml", "qweb", "scss", "python"}


@tagged("post_install", "-at_install")
class TestCelViewAceMode(TransactionCase):
    """The CEL Expressions form must only use ace modes CodeEditor accepts."""

    def test_cel_ace_fields_use_valid_mode(self):
        view = self.env.ref("spp_approval.view_spp_approval_definition_form_cel")
        arch = etree.fromstring(view.arch)

        ace_fields = arch.xpath("//field[@widget='ace']")
        self.assertTrue(
            ace_fields,
            "Expected at least one widget='ace' field in the CEL view — did the view change?",
        )

        for field in ace_fields:
            options = field.get("options")
            self.assertTrue(
                options,
                f"ace field {field.get('name')!r} must declare options with a mode",
            )
            mode = ast.literal_eval(options).get("mode")
            self.assertIn(
                mode,
                VALID_ACE_MODES,
                f"ace field {field.get('name')!r} uses mode {mode!r}, which "
                f"CodeEditor rejects (valid: {sorted(VALID_ACE_MODES)}). "
                "This crashes the client when the field is rendered.",
            )
