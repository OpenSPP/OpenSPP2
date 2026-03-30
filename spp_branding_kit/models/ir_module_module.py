from odoo import api, models


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    @api.model
    def get_paid_apps_count(self):
        """Get count of paid apps in the system"""
        return self.search_count(["|", ("license", "=like", "OEEL%"), ("license", "=like", "OPL%")])

    # No overrides of install/upgrade/uninstall buttons are needed once
    # _search is left untouched; UI filtering is handled via web_* APIs.
