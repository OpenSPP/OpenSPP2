import logging

import psycopg2

from odoo import models

_logger = logging.getLogger(__name__)


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    # Map module technical names to menu xml_ids and icon paths
    ICON_MAP = {
        "project_todo": {
            "menu_xml_id": "project_todo.menu_todo_todos",
            "icon": "spp_base_common,static/description/icon-To-do-White-line.png",
        },
        "mail": {
            "menu_xml_id": "mail.menu_root_discuss",
            "icon": "spp_base_common,static/description/icon-Discuss-White-line.png",
        },
        "job_worker": {
            "menu_xml_id": "job_worker.menu_queue_job_root",
            "icon": "spp_base_common,static/description/icon-Job-Queue-White-line.png",
        },
        "spreadsheet_dashboard": {
            "menu_xml_id": "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
            "icon": "spp_base_common,static/description/icon-Dashboards-White-line.png",
        },
        "project": {
            "menu_xml_id": "project.menu_main_pm",
            "icon": "spp_base_common,static/description/icon-Project-White-line.png",
        },
        "mass_mailing": {
            "menu_xml_id": "mass_mailing.mass_mailing_menu_root",
            "icon": "spp_base_common,static/description/icon-Email-Marketing-White-line.png",
        },
        "survey": {
            "menu_xml_id": "survey.menu_surveys",
            "icon": "spp_base_common,static/description/icon-Surveys-White-line.png",
        },
        "hr": {
            "menu_xml_id": "hr.menu_hr_root",
            "icon": "spp_base_common,static/description/icon-Employees-White-line.png",
        },
        "calendar": {
            "menu_xml_id": "calendar.mail_menu_calendar",
            "icon": "spp_base_common,static/description/OpenSPP-Icons-Menu-Calendar.png",
        },
        "contacts": {
            "menu_xml_id": "contacts.menu_contacts",
            "icon": "spp_base_common,static/description/OpenSPP-Icons-Menu-Contacts.png",
        },
        "account": {
            "menu_xml_id": "account.menu_finance",
            "icon": "spp_base_common,static/description/OpenSPP-Icons-Menu-Invoicing.png",
        },
        "event": {
            "menu_xml_id": "event.event_main_menu",
            "icon": "spp_base_common,static/description/OpenSPP-Icons-Menu-Events.png",
        },
        "stock": {
            "menu_xml_id": "stock.menu_stock_root",
            "icon": "spp_base_common,static/description/OpenSPP-Icons-Menu-Inventory.png",
        },
        "utm": {
            "menu_xml_id": "utm.menu_link_tracker_root",
            "icon": "spp_base_common,static/description/OpenSPP-Icons-Menu-Link-Tracker.png",
        },
        "fastapi": {
            "menu_xml_id": "fastapi.menu_fastapi_root",
            "icon": "spp_base_common,static/description/icon-fast-api.png",
        },
    }

    def update_menu_icons(self):
        """Point the root menus of known third-party apps at OpenSPP icons.

        Purely cosmetic and best-effort: a database error while decorating
        must never abort the module operation that triggered it, so the
        whole pass runs in its own savepoint and is skipped on failure.

        The caller's pending ORM writes are flushed first so that only the
        decoration itself is covered by the guard; a failure in the caller's
        own writes stays the caller's error. Retryable errors (serialization
        failures, deadlocks) are deliberately swallowed too: retrying the
        module operation would rebuild the registry for a cosmetic write.
        """
        self.env.cr.flush()
        try:
            with self.env.cr.savepoint():
                self._write_menu_icons()
        except psycopg2.Error:
            _logger.warning(
                "Skipping the OpenSPP app menu icon update because the database reported an error; "
                "the menus keep their current icons and the module operation continues",
                exc_info=True,
            )

    def _write_menu_icons(self):
        for module in self.search([]):
            icon_info = self.ICON_MAP.get(module.name)
            if not icon_info:
                continue
            menu = self.env.ref(icon_info["menu_xml_id"], raise_if_not_found=False)
            if menu:
                menu.write({"web_icon": icon_info["icon"]})

    def next(self):
        # Call your icon update logic first
        self.update_menu_icons()
        # Then call the original Odoo logic
        return super().next()
