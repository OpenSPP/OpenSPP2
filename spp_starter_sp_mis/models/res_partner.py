# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import AccessError

from .res_config_settings import REGISTRY_ADMIN_ONLY_CRUD_PARAM

ADMIN_GROUP = "spp_security.group_spp_admin"

# Operations the setting withholds from non-admins. ``read`` is deliberately
# absent: the whole point is that everyone keeps visibility of the registry.
RESTRICTED_OPERATIONS = ("create", "write", "unlink")


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _is_registry_crud_restricted(self):
        """Whether registry changes are currently withheld from this user."""
        if self.env.user.has_group(ADMIN_GROUP):
            return False
        param = self.env["ir.config_parameter"].sudo().get_param(REGISTRY_ADMIN_ONLY_CRUD_PARAM, "False")
        return param == "True"

    def _make_registry_access_error(self):
        return AccessError(
            _(
                "Registry records are restricted to administrators. Ask an administrator to make "
                "this change, or turn off 'Restrict Registry Edits to Admin Only' in SP-MIS Settings."
            )
        )

    def _check_access(self, operation):
        """Withhold registrant create/write/unlink from non-admins (OP#1142).

        This is the single chokepoint behind ``check_access``, ``has_access``
        and the ORM's own create/write/unlink guards, so one override both
        refuses the change — over RPC and import as much as through the UI —
        and takes New/Edit/Delete off registry views for free, because
        ``ir.ui.view._postprocess_access_rights`` stamps ``create="false"`` onto
        an arch whenever ``has_access('create')`` comes back False. That is what
        actually removes the button; the previous JavaScript patch assigned a
        ``canCreate`` property Odoo 19's ListController never reads.

        Enforcement is scoped to registrants so the setting cannot lock the
        whole Contacts app. On a populated recordset that is a plain filter, and
        it is the check the ORM applies to real writes — including the
        post-create pass — so it holds regardless of how the call arrives.

        The empty recordset is the model-level probe, used by views and by
        ``create()`` before any record exists. There is nothing to filter there,
        so registrant intent is read from the context both registry actions
        carry. Note that ``get_view`` documents its result as depending only on
        access rights and a few context keys, so should that ever stop flowing,
        the button reappears but the refusal above still stands — the failure
        mode is cosmetic, not a loss of enforcement.
        """
        result = super()._check_access(operation)
        if result is not None or operation not in RESTRICTED_OPERATIONS:
            return result
        if not self._is_registry_crud_restricted():
            return None

        if self:
            forbidden = self.browse(self.sudo().filtered("is_registrant").ids)
            if not forbidden:
                return None
        elif self.env.context.get("default_is_registrant"):
            forbidden = self
        else:
            return None

        return forbidden, self._make_registry_access_error
