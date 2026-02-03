# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AreaImportLanguageWizard(models.TransientModel):
    _name = "spp.area.import.language.wizard"
    _description = "Area Import Language Activation Wizard"

    area_import_id = fields.Many2one(
        "spp.area.import",
        string="Area Import",
        required=True,
        ondelete="cascade",
    )

    # Languages to activate (set when wizard is created)
    # Note: These are inactive languages, so we need active_test=False in context
    language_ids = fields.Many2many(
        "res.lang",
        "spp_area_import_lang_wizard_rel",
        string="Languages to Activate",
        help="Languages found in the import file that are not currently active",
        context={"active_test": False},
    )

    # Display languages as HTML list
    languages_display = fields.Html(
        string="Languages",
        compute="_compute_languages_display",
    )

    @api.depends("language_ids")
    def _compute_languages_display(self):
        for wizard in self:
            if not wizard.language_ids:
                wizard.languages_display = _("<p class='text-muted'>No languages to activate.</p>")
            else:
                lang_list = "".join(
                    [f"<li><strong>{lang.name}</strong> ({lang.code})</li>" for lang in wizard.language_ids]
                )
                wizard.languages_display = f"<ul class='list-unstyled'>{lang_list}</ul>"

    def action_activate_and_continue(self):
        """Activate all languages and continue with the import."""
        self.ensure_one()

        # Activate all languages
        for lang in self.language_ids:
            lang.active = True
            _logger.info(
                "Area Import: User activated language: %s (%s)",
                lang.iso_code or lang.code,
                lang.name,
            )

        # Continue with the import process
        return self.area_import_id._continue_import_after_language_check()

    def action_skip_and_continue(self):
        """Skip language activation and continue with the import (translations will be skipped)."""
        self.ensure_one()
        _logger.info("Area Import: User chose to skip language activation")

        # Continue with the import process without activating languages
        return self.area_import_id._continue_import_after_language_check()

    def action_cancel(self):
        """Cancel the import process."""
        self.ensure_one()
        # Unlock the import record
        self.area_import_id.is_locked = False
        self.area_import_id.locked_reason = None
        return {"type": "ir.actions.act_window_close"}
