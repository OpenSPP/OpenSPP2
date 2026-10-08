"""Guard the form-view "New" button extension in custom_list_create_template.xml.

spp_base_common extends the ``web.FormView`` template so that any module can set
``this.hideFormCreateButton = true`` on its FormController patch to hide the
control-panel "New" button. Stock Odoo renders that button with
``t-if="canCreate"``, and ``canCreate`` is the single switch behind every way a
form can be opened without create: ``{'create': False}`` in the action context,
``create="0"`` on the form arch, and a missing create ACL. Replacing the
condition instead of extending it rendered a live "New" button in all three
cases (#582). The fourth input to ``canCreate``, the ``preventCreate`` prop, is
only passed by form dialogs, which do not render the control panel at all.

The web client applies template inheritance in the browser, which the test image
cannot run. Odoo ships the same xpath/position engine server-side in
``odoo.tools.template_inheritance``, so this test applies the extension to the
real stock template and checks the resulting condition.
"""

import copy

from lxml import etree

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase
from odoo.tools.misc import file_open
from odoo.tools.template_inheritance import apply_inheritance_specs

STOCK_FORM_TEMPLATES = "web/static/src/views/form/form_controller.xml"
EXTENSION_TEMPLATES = "spp_base_common/static/src/xml/custom_list_create_template.xml"
# Relative to the template element: an absolute "//" xpath on an lxml element
# searches the whole document, i.e. every template in the file.
CREATE_BUTTON_XPATH = ".//button[hasclass('o_form_button_create')]"


def _load_templates(path):
    with file_open(path, "rb") as template_file:
        return etree.fromstring(template_file.read())


class TestFormCreateButtonTemplate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stock = _load_templates(STOCK_FORM_TEMPLATES)
        cls.extension = _load_templates(EXTENSION_TEMPLATES)

    def _apply_extension(self, template_name):
        """Return the stock template after every spec that inherits it is applied.

        The template is detached from its file first so that the spec's own
        "//" xpath is scoped to this one template, as the web client scopes it.
        """
        (source,) = self.stock.xpath(f"./t[@t-name='{template_name}']")
        source = copy.deepcopy(source)
        specs = [
            spec
            for inherit in self.extension.xpath(f"./t[@t-inherit='{template_name}']")
            for spec in inherit
            if isinstance(spec.tag, str)
        ]
        return apply_inheritance_specs(source, specs)

    def test_control_panel_new_button_keeps_can_create(self):
        form_view = self._apply_extension("web.FormView")
        (button,) = form_view.xpath(CREATE_BUTTON_XPATH)
        condition = button.get("t-if")

        # Exact match: the condition is a one-line expression under our control,
        # and a token check would accept "canCreate or !hideFormCreateButton",
        # which reintroduces the bug.
        self.assertEqual(
            condition,
            "canCreate and !hideFormCreateButton",
            "the form New button must keep Odoo's canCreate guard "
            '(action context, create="0", ACL, preventCreate) and the '
            "hideFormCreateButton opt-out must still hide the button",
        )

    def test_extension_is_shipped_in_the_backend_bundle(self):
        """The template only takes effect if the manifest still lists it in web.assets_backend."""
        manifest = get_manifest("spp_base_common")
        self.assertIn(EXTENSION_TEMPLATES, manifest["assets"]["web.assets_backend"])

    def test_dialog_new_button_is_not_touched(self):
        """The extension targets web.FormView only; dialog footers keep stock markup."""
        self.assertFalse(self.extension.xpath("./t[@t-inherit='web.FormView.Buttons']"))
        (source,) = self.stock.xpath("./t[@t-name='web.FormView.Buttons']")
        (button,) = source.xpath(CREATE_BUTTON_XPATH)
        self.assertRegex(button.get("t-if"), r"\bcanCreate\b")
