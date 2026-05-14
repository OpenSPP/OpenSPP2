"""Currency + decimal formatting on the "What Do They Receive?" overview text.

OP#941 round-2 feedback: the entitlement summary on the program overview
should include the currency symbol next to the amount and render with the
currency's native decimal precision (e.g. 1.00 instead of 1.0 for USD).
Covers both code paths in `program_manager_ui.py`:

- `_manager_detail_entitlement_items` (when the entitlement manager has
  `entitlement_item_ids` — this is what default cash transfer programs hit).
- `_manager_detail_basic_cash` (when the manager is a "Basic Cash" with
  `amount_per_cycle` / `amount_per_individual_in_group`).
"""

from odoo import fields
from odoo.tests import TransactionCase


class TestManagerSummaryFormatting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env["spp.program"].create({"name": "Summary Fmt Program [TEST]"})
        cls.program.create_journal()  # Sets program.journal_id with a currency

        entitlement_model = cls.env["ir.model"].search([("model", "=", "spp.entitlement")], limit=1)
        cls.approval_def = cls.env["spp.approval.definition"].create(
            {
                "name": "Summary Fmt Approval [TEST]",
                "model_id": entitlement_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )

    def _wrap_manager(self, concrete):
        """Attach concrete manager to program via the wrapper + m2m field."""
        wrapper = self.env["spp.program.entitlement.manager"].create(
            {
                "program_id": self.program.id,
                "manager_ref_id": f"{concrete._name},{concrete.id}",
            }
        )
        self.program.write({"entitlement_manager_ids": [fields.Command.link(wrapper.id)]})
        return wrapper

    def test_items_summary_includes_currency_and_two_decimals(self):
        """Items path: 'Amount per beneficiary: <SYM> 1.00 per cycle'."""
        cash = self.env["spp.program.entitlement.manager.cash"].create(
            {
                "name": "Cash With Items [TEST]",
                "program_id": self.program.id,
                "approval_definition_id": self.approval_def.id,
            }
        )
        self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": cash.id,
                "amount": 1.0,
            }
        )
        self._wrap_manager(cash)

        summary = self.program.entitlement_manager_detail or ""
        # Amount must render with 2-decimal precision (1.00, not 1.0)
        self.assertIn("1.00", summary)
        self.assertNotRegex(summary, r"\b1\.0\b(?!\d)")
        # Currency symbol must be present
        currency = self.program.journal_id.currency_id
        sym = currency.symbol or currency.name
        self.assertIn(sym, summary, f"summary missing currency symbol {sym!r}: {summary!r}")
        # Sanity: the per-cycle suffix is still there
        self.assertIn("per cycle", summary)

    def test_basic_cash_summary_two_decimals(self):
        """Basic Cash path: amount_per_cycle renders as e.g. '12.50', not '12.5'."""
        default_cash = self.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Default Cash [TEST]",
                "program_id": self.program.id,
                "amount_per_cycle": 12.5,
            }
        )
        self._wrap_manager(default_cash)

        summary = self.program.entitlement_manager_detail or ""
        self.assertIn("12.50", summary)
        self.assertNotRegex(summary, r"\b12\.5\b(?!\d)")
        currency = self.program.journal_id.currency_id
        sym = currency.symbol or currency.name
        self.assertIn(sym, summary)

    def test_items_summary_includes_thousands_separator(self):
        """Round-3 QA: large amounts must group thousands (1,000,000.00 not 1000000.00)."""
        cash = self.env["spp.program.entitlement.manager.cash"].create(
            {
                "name": "Cash Large Amount [TEST]",
                "program_id": self.program.id,
                "approval_definition_id": self.approval_def.id,
            }
        )
        self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": cash.id,
                "amount": 1_000_000.0,
            }
        )
        self._wrap_manager(cash)

        summary = self.program.entitlement_manager_detail or ""
        # Should include a comma in the grouped amount for en_US locale.
        self.assertIn("1,000,000", summary, f"summary missing thousands separator: {summary!r}")
        # And of course still no bare "1000000" without a separator.
        self.assertNotRegex(summary, r"\b1000000\b")
