import logging

_logger = logging.getLogger(__name__)

_RECORDS = (
    "ir_cron_purge_quarantined_files",
    "ir_cron_cleanup_forensic_downloads",
    "config_param_quarantine_retention_days",
    "config_param_forensic_download_retention_hours",
)


def migrate(cr, version):
    """Reconcile ``ir_model_data.noupdate`` for the quarantine crons/params.

    ``data/quarantine_cron.xml`` is declared ``noupdate="1"`` now, and on an
    already-installed database that file-level flag is by itself enough to stop
    the reset: ``xml_import._tag_record`` tests ``self.noupdate``, which
    ``_tag_root`` reads off the ``<odoo>`` element rather than off the stored
    row, and returns before ``_load_records`` whenever the mode is not ``init``.
    So this migration is not what fixes the upgrade rewrite, and no pre-migrate
    is needed; the XML-only fix applied to ``scan_sweep_cron.xml`` in #470 is
    correct as it stands.

    What the XML cannot do is correct the stored rows.
    ``_build_update_xmlids_query`` upserts ``ON CONFLICT ... DO UPDATE SET
    (model, res_id, write_date)`` and never writes ``noupdate``, so every
    database that already carries these xml_ids keeps ``noupdate = false`` in
    ``ir_model_data``. That column is the one ``ir.model.data._process_end``
    consults, and the one an admin -- or the regression test for these records
    -- reads to confirm they are protected. Flip it once here, and leave the
    stored values alone: tuned values survive and untouched defaults stay as
    shipped.
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
