# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Refreshable mixin: reload the current record without changing the route."""

from odoo import models


class RefreshableMixin(models.AbstractModel):
    """Mixin for records that need a "Refresh" button on a banner.

    Adds `action_refresh_record`, intended as the target of a `<button>` on
    forms whose state changes asynchronously (e.g. while a long-running
    background job runs). Returning `None` from the button handler triggers
    Odoo's standard post-button reload path (`view_button_hook.js` →
    `model.load()`), which re-reads the current record while preserving the
    breadcrumb stack and the dialog (popup) context.

    Avoid the temptation to return `{"type": "ir.actions.client", "tag":
    "reload"}` here: that client tag does a full browser reload via
    `router.pushState({reload: true})` (see
    `addons/web/static/src/webclient/actions/client_actions.js`), which
    destroys breadcrumbs and closes any open dialog the form lives in. See
    OP#950 for the original report.
    """

    _name = "spp.refreshable.mixin"
    _description = "Refreshable Mixin"

    def action_refresh_record(self):
        return None
