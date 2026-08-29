import logging

_logger = logging.getLogger(__name__)

_RECORDS = (
    "ir_cron_purge_quarantined_files",
    "ir_cron_cleanup_forensic_downloads",
    "config_param_quarantine_retention_days",
    "config_param_forensic_download_retention_hours",
)


def migrate(cr, version):
    """Protect admin-tuned quarantine crons/params from upgrade resets.

    The records in ``data/quarantine_cron.xml`` are now declared
    ``noupdate="1"``, but that flag is only honored when a record is first
    created. On any database that installed this module before the flag was
    added, the ``ir.model.data`` rows already exist with ``noupdate = False``,
    so every upgrade keeps rewriting them to the shipped defaults. Flip the
    flag on the existing rows; leave the stored values untouched so an admin's
    tuning survives and untouched defaults stay as shipped.
    """
    cr.execute(
        """
        UPDATE ir_model_data
        SET noupdate = TRUE
        WHERE module = 'spp_attachment_av_scan'
          AND name IN %s
        """,
        (_RECORDS,),
    )
    _logger.info(
        "spp_attachment_av_scan: set noupdate on %s quarantine cron/param records",
        cr.rowcount,
    )
