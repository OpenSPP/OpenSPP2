from . import models
from . import controllers

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Post-installation hook to perform initial branding setup
    """
    _logger.info("OpenSPP Branding Kit: Running post-installation setup...")

    # No default parameters for app filtering; UI handles Apps filters now

    # Disable Odoo branding elements
    try:
        # Deactivate brand promotion view
        brand_promotion = env.ref("web.brand_promotion_message", raise_if_not_found=False)
        if brand_promotion:
            brand_promotion.active = False
            _logger.info("Disabled Odoo brand promotion message")

        # Disable specific Odoo update notification cron (if present)
        crons_to_disable = [
            "mail.ir_cron_module_update_notification",  # Module update notification
        ]

        for cron_xml_id in crons_to_disable:
            try:
                cron = env.ref(cron_xml_id, raise_if_not_found=False)
                if cron and cron.active:
                    cron.active = False
                    _logger.info("Disabled cron job: %s (%s)", cron.name, cron_xml_id)
            except Exception as e:
                _logger.debug("Could not disable cron %s: %s", cron_xml_id, e)

        # Disable theme store menu if it exists
        # nosemgrep: odoo-sudo-without-context — post-install hook runs as system to configure branding
        theme_menu = env["ir.ui.menu"].sudo().search([("name", "ilike", "Theme Store")], limit=1)
        if theme_menu and theme_menu.active:
            theme_menu.active = False
            _logger.info("Disabled Theme Store menu")

    except Exception as e:
        _logger.warning("Error during branding setup: %s", e)

    # Update company information for all companies
    try:
        # nosemgrep: odoo-sudo-without-context — post-install hook runs as system to configure branding
        Company = env["res.company"].sudo()
        companies = Company.search([])
        for company in companies:
            company.write(
                {
                    "report_header": "OpenSPP Platform",
                    "report_footer": "OpenSPP - Open Source Social Protection Platform",
                    "website": "https://openspp.org",
                }
            )
        _logger.info("Updated branding for %d companies", len(companies))
    except Exception as e:
        _logger.warning("Error updating company data: %s", e)

    _logger.info("OpenSPP Branding Kit: Post-installation setup completed")


def uninstall_hook(env):
    """
    Uninstall hook to clean up configuration parameters
    """
    _logger.info("OpenSPP Branding Kit: Running uninstall cleanup...")

    # Remove all spp.* configuration parameters created by this module
    try:
        # nosemgrep: odoo-sudo-without-context — standard Odoo pattern for system parameter access
        IrConfigParam = env["ir.config_parameter"].sudo()
        params = IrConfigParam.search([("key", "=like", "spp.%")])
        if params:
            param_count = len(params)
            params.unlink()
            _logger.info("Removed %d OpenSPP configuration parameters", param_count)
    except Exception as e:
        _logger.warning("Error removing configuration parameters: %s", e)

    # Optionally re-enable Odoo branding elements
    # This is commented out by default to maintain debranding even after uninstall
    # Uncomment if you want to restore Odoo branding on module removal

    # try:
    #     brand_promotion = env.ref('web.brand_promotion_message', raise_if_not_found=False)
    #     if brand_promotion:
    #         brand_promotion.active = True
    # except Exception as e:
    #     _logger.warning(f"Error during uninstall cleanup: {e}")

    _logger.info("OpenSPP Branding Kit: Uninstall cleanup completed")
