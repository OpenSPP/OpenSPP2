import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migration script to rename g2p_encryption models to spp_encryption.
    This merges the base g2p.encryption.provider model into spp.encryption.provider.
    """
    _logger.info("Starting pre-migration for spp_encryption")

    # Rename the model table
    _logger.info("Renaming model g2p_encryption_provider to spp_encryption_provider")
    cr.execute(
        """
        ALTER TABLE IF EXISTS g2p_encryption_provider
        RENAME TO spp_encryption_provider
        """
    )

    # Update ir_model entries
    _logger.info("Updating ir_model entries")
    cr.execute(
        """
        UPDATE ir_model
        SET model = 'spp.encryption.provider',
            name = 'SPP Encryption Provider'
        WHERE model = 'g2p.encryption.provider'
        """
    )

    # Update ir_model_fields entries
    _logger.info("Updating ir_model_fields entries")
    cr.execute(
        """
        UPDATE ir_model_fields
        SET model = 'spp.encryption.provider'
        WHERE model = 'g2p.encryption.provider'
        """
    )

    # Update ir_model_data entries
    _logger.info("Updating ir_model_data entries for models")
    cr.execute(
        """
        UPDATE ir_model_data
        SET model = 'spp.encryption.provider'
        WHERE model = 'g2p.encryption.provider'
        """
    )

    # Update ir_model_data entries for the model itself
    cr.execute(
        """
        UPDATE ir_model_data
        SET name = 'model_spp_encryption_provider',
            module = 'spp_encryption'
        WHERE model = 'ir.model'
        AND name = 'model_g2p_encryption_provider'
        """
    )

    # Update ir_model_access entries
    _logger.info("Updating ir_model_access entries")
    cr.execute(
        """
        UPDATE ir_model_access
        SET name = REPLACE(name, 'g2p_encryption_provider', 'spp_encryption_provider')
        WHERE name LIKE '%g2p_encryption_provider%'
        """
    )

    # Update ir_ui_view entries
    _logger.info("Updating ir_ui_view entries")
    cr.execute(
        """
        UPDATE ir_ui_view
        SET model = 'spp.encryption.provider'
        WHERE model = 'g2p.encryption.provider'
        """
    )

    # Update ir_act_window entries
    _logger.info("Updating ir_act_window entries")
    cr.execute(
        """
        UPDATE ir_act_window
        SET res_model = 'spp.encryption.provider'
        WHERE res_model = 'g2p.encryption.provider'
        """
    )

    # Update ir_rule entries if any
    _logger.info("Updating ir_rule entries")
    cr.execute(
        """
        UPDATE ir_rule
        SET model_id = (SELECT id FROM ir_model WHERE model = 'spp.encryption.provider')
        WHERE model_id IN (SELECT id FROM ir_model WHERE model = 'g2p.encryption.provider')
        """
    )

    # Update security group module references
    _logger.info("Updating security group module references")
    cr.execute(
        """
        UPDATE ir_model_data
        SET module = 'spp_encryption'
        WHERE module = 'g2p_encryption'
        AND model IN ('res.groups', 'ir.module.category')
        """
    )

    # Update XML ID references in ir_model_data
    _logger.info("Updating XML ID module references")
    cr.execute(
        """
        UPDATE ir_model_data
        SET module = 'spp_encryption'
        WHERE module = 'g2p_encryption'
        """
    )

    _logger.info("Pre-migration for spp_encryption completed successfully")
