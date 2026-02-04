import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migrate g2p_bank → spp_banking

    CRITICAL: This runs BEFORE module code is loaded.

    This migration script handles the namespace change from g2p_bank to spp_banking.
    It updates all database references including models, fields, external IDs, and metadata.
    """
    _logger.info("=" * 80)
    _logger.info("Starting g2p_bank → spp_banking migration")
    _logger.info("=" * 80)

    # Note: g2p_bank module doesn't create custom database tables with g2p_bank prefix
    # It only extends res.partner.bank (res_partner_bank table)
    # Therefore, we don't need to rename any tables

    # Step 1: Update ir.model.data (external IDs) - Critical for Odoo to find records
    _logger.info("Step 1: Updating ir.model.data (external IDs)")
    cr.execute("""
        UPDATE ir_model_data
        SET module = 'spp_banking'
        WHERE module = 'g2p_bank';
    """)
    rows_updated = cr.rowcount
    _logger.info("  → Updated %d external ID records from g2p_bank to spp_banking", rows_updated)

    # Step 2: Update ir.model.data for g2p_bank_rest_api module
    _logger.info("Step 2: Updating ir.model.data for REST API module")
    cr.execute("""
        UPDATE ir_model_data
        SET module = 'spp_banking_rest_api'
        WHERE module = 'g2p_bank_rest_api';
    """)
    rows_updated = cr.rowcount
    _logger.info(
        "  → Updated %d external ID records from g2p_bank_rest_api to spp_banking_rest_api",
        rows_updated,
    )

    # Step 3: Update module dependencies in ir_module_module_dependency
    _logger.info("Step 3: Updating module dependencies")
    cr.execute("""
        UPDATE ir_module_module_dependency
        SET name = 'spp_banking'
        WHERE name = 'g2p_bank';
    """)
    rows_updated = cr.rowcount
    _logger.info("  → Updated %d module dependency records", rows_updated)

    # Step 4: Update module dependencies for REST API
    cr.execute("""
        UPDATE ir_module_module_dependency
        SET name = 'spp_banking_rest_api'
        WHERE name = 'g2p_bank_rest_api';
    """)
    rows_updated = cr.rowcount
    _logger.info("  → Updated %d REST API module dependency records", rows_updated)

    # Step 5: Update module names in ir_module_module if they exist
    _logger.info("Step 4: Updating module names in ir_module_module")
    cr.execute("""
        UPDATE ir_module_module
        SET name = 'spp_banking'
        WHERE name = 'g2p_bank';
    """)
    rows_updated = cr.rowcount
    if rows_updated > 0:
        _logger.info("  → Updated module name: g2p_bank → spp_banking")
    else:
        _logger.info("  → Module g2p_bank not found in ir_module_module (may not be installed)")

    cr.execute("""
        UPDATE ir_module_module
        SET name = 'spp_banking_rest_api'
        WHERE name = 'g2p_bank_rest_api';
    """)
    rows_updated = cr.rowcount
    if rows_updated > 0:
        _logger.info("  → Updated module name: g2p_bank_rest_api → spp_banking_rest_api")
    else:
        _logger.info("  → Module g2p_bank_rest_api not found in ir_module_module (may not be installed)")

    _logger.info("=" * 80)
    _logger.info("Completed g2p_bank → spp_banking migration successfully")
    _logger.info("=" * 80)
