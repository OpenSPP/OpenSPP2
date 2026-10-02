"""Tests for the registrant search in the Change Request creation wizard.

The wizard renders its search results server-side as HTML and the browser
widget only wires up selection and paging. These tests pin down the markup
that keyboard users and assistive technology depend on (focusable rows with
a role and a name, a real button pager, status text for a live region) and
the bridge fields the widget writes.
"""

from lxml import html as lxml_html

from odoo.tests import tagged

from .test_change_request import TestChangeRequestBase

PREFIX = "A11Y Searchable"


@tagged("post_install", "-at_install", "cr_ux")
class TestCreateWizardSearch(TestChangeRequestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.individuals = cls.partner_model.create(
            [{"name": f"{PREFIX} {index:02d}", "is_registrant": True, "is_group": False} for index in range(1, 13)]
        )
        cls.search_group = cls.partner_model.create(
            {"name": f"{PREFIX} Group", "is_registrant": True, "is_group": True}
        )
        cls.wizard_model = cls.env["spp.cr.create.wizard"]

    def _wizard(self):
        return self.wizard_model.create({"request_type_id": self.cr_type_edit_individual.id})

    def _render(self, wizard, text, page=0):
        wizard.search_text = text
        wizard._onchange_search_text()
        if page:
            wizard._search_page = page
            wizard._onchange_search_page()
        return lxml_html.fragment_fromstring(str(wizard.search_results_html), create_parent="div")

    @staticmethod
    def _rows(doc):
        return doc.xpath('.//tr[contains(@class, "o_cr_search_result")]')

    @staticmethod
    def _status_text(doc):
        nodes = doc.xpath('.//*[contains(@class, "o_cr_search_status")]')
        return nodes[0].text_content().strip() if nodes else None

    def test_rows_are_focusable_options(self):
        """Rows are options of a listbox, one of them in the Tab order, each with an accessible name."""
        doc = self._render(self._wizard(), PREFIX)

        listbox = doc.xpath('.//tbody[@role="listbox"]')
        self.assertEqual(len(listbox), 1)
        self.assertTrue(listbox[0].get("aria-label"))

        rows = self._rows(doc)
        self.assertEqual(len(rows), 10)
        self.assertEqual([row.get("role") for row in rows], ["option"] * 10)
        self.assertEqual([row.get("tabindex") for row in rows], ["0"] + ["-1"] * 9)
        for row in rows:
            self.assertEqual(row.get("aria-label"), f"{row.get('data-partner-name')}, Individual")

    def test_type_icon_is_hidden_from_assistive_tech(self):
        """Decorative type icons are not announced."""
        doc = self._render(self._wizard(), PREFIX)
        icons = doc.xpath('.//i[contains(@class, "fa")]')
        self.assertEqual(len(icons), 10)
        for icon in icons:
            self.assertEqual(icon.get("aria-hidden"), "true")

    def test_pager_renders_buttons_with_disabled_edges(self):
        """Previous/Next are real buttons; the edge of the range is disabled rather than merely styled."""
        wizard = self._wizard()

        doc = self._render(wizard, PREFIX)
        prev = doc.xpath('.//button[contains(@class, "o_cr_page_prev")]')[0]
        nxt = doc.xpath('.//button[contains(@class, "o_cr_page_next")]')[0]
        self.assertEqual((prev.get("type"), nxt.get("type")), ("button", "button"))
        self.assertIsNotNone(prev.get("disabled"))
        self.assertIsNone(nxt.get("disabled"))
        self.assertEqual((prev.get("data-page"), nxt.get("data-page")), ("-1", "1"))

        doc = self._render(wizard, PREFIX, page=1)
        prev = doc.xpath('.//button[contains(@class, "o_cr_page_prev")]')[0]
        nxt = doc.xpath('.//button[contains(@class, "o_cr_page_next")]')[0]
        self.assertIsNone(prev.get("disabled"))
        self.assertIsNotNone(nxt.get("disabled"))
        self.assertEqual((prev.get("data-page"), nxt.get("data-page")), ("0", "2"))

    def test_status_text_is_marked_for_live_region(self):
        """The range summary and the empty-result message carry the status marker the widget mirrors."""
        wizard = self._wizard()
        self.assertEqual(self._status_text(self._render(wizard, PREFIX)), "1-10 of 12")
        self.assertEqual(self._status_text(self._render(wizard, PREFIX, page=1)), "11-12 of 12")
        self.assertEqual(self._status_text(self._render(wizard, f"{PREFIX} nothing matches")), "No registrants found.")

    def test_aria_label_escapes_name(self):
        """A name containing markup is escaped in the accessible name as it is in the cell."""
        self.partner_model.create({"name": f"{PREFIX} <b>bold</b>", "is_registrant": True, "is_group": False})
        wizard = self._wizard()
        wizard.search_text = f"{PREFIX} <b>"
        wizard._onchange_search_text()
        raw = str(wizard.search_results_html)

        self.assertIn(f'aria-label="{PREFIX} &lt;b&gt;bold&lt;/b&gt;, Individual"', raw)
        self.assertNotIn("<b>bold</b>", raw)

    def test_selected_partner_bridge_sets_registrant(self):
        """The integer the widget writes on Enter/click becomes the registrant."""
        wizard = self._wizard()
        chosen = self.individuals[3]
        wizard._selected_partner_id = chosen.id
        wizard._onchange_selected_partner()
        self.assertEqual(wizard.registrant_id, chosen)

    def test_page_change_rerenders_and_clamps(self):
        """Paging shows the remaining rows, never the group, and an out-of-range page falls back to the last one."""
        wizard = self._wizard()
        first_page = {row.get("data-partner-name") for row in self._rows(self._render(wizard, PREFIX))}
        second_page = {row.get("data-partner-name") for row in self._rows(self._render(wizard, PREFIX, page=1))}

        self.assertEqual(len(first_page), 10)
        self.assertEqual(len(second_page), 2)
        self.assertEqual(first_page | second_page, set(self.individuals.mapped("name")))
        self.assertNotIn(self.search_group.name, first_page | second_page)

        doc = self._render(wizard, PREFIX, page=99)
        self.assertEqual(len(self._rows(doc)), 2)
        self.assertEqual(self._status_text(doc), "11-12 of 12")
