"""An attachment stranded at ``scan_status = pending`` must not stay unscanned forever.

Queueing a malware scan is best-effort: the ``create``/``write`` hooks swallow every
non-database enqueue failure so a dead broker or a misconfigured channel cannot block an
attachment write (see ``test_scan_queue_error_handling``). #464 added a second, benign
source of the same state — nothing is enqueued while the registry loads.

Both leave the attachment written, at the ``scan_status`` default ``pending``, with one
ERROR line in the server log as the only evidence and ``action_rescan`` as the only route
back. For a runtime user upload that is an unscanned file, indistinguishable in the UI from
one still waiting its turn in a deep queue, retained indefinitely.

``_cron_sweep_pending_scans`` closes that. The tests below pin every design call it makes,
in both directions where the rule could silently invert:

* only records older than the age threshold — a fresh upload is legitimately ``pending``
  and must not be double-queued;
* a bounded batch, ordered so successive runs advance instead of re-picking the same rows;
* quarantined records skipped, matching ``action_rescan``;
* scope limited to user content — a ``res_model`` must be set, and system models that store
  their own source-controlled binaries (menu ``web_icon_data``) are excluded;
* a bounded attempt count, so a record that cannot be enqueued is not retried at full rate
  forever, and does not spam ERROR on every tick.
"""

import base64
from unittest.mock import MagicMock, patch

import psycopg2

from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models.ir_attachment import (
    PENDING_SWEEP_BATCH_SIZE_PARAM,
    PENDING_SWEEP_MAX_ATTEMPTS_PARAM,
    PENDING_SWEEP_MIN_AGE_MINUTES_PARAM,
    SWEEP_EXCLUDED_MODELS,
)

LOGGER = "odoo.addons.spp_attachment_av_scan.models.ir_attachment"


def _raise_serialization_failure(*args, **kwargs):
    raise psycopg2.errors.SerializationFailure("could not serialize access due to concurrent update")


def _raise_value_error(*args, **kwargs):
    """A non-database failure, e.g. a misconfigured queue channel."""
    raise ValueError("scan queue is misconfigured")


@tagged("post_install", "-at_install")
class TestPendingScanSweep(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env["ir.attachment"]
        cls.partner = cls.env["res.partner"].create({"name": "AV sweep host"})

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _create_pending(self, name, res_model="res.partner", res_id=None, payload=b"probe", **extra):
        """A binary attachment left at ``pending``, as a failed enqueue would leave it.

        ``with_delay`` is stubbed out so creating the fixture does not queue a real job —
        otherwise every fixture would arrive already spoken for.
        """
        vals = {
            "name": name,
            "datas": base64.b64encode(payload),
            "mimetype": "text/plain",
            "res_model": res_model,
            "res_id": res_id if res_id is not None else (self.partner.id if res_model else 0),
        }
        vals.update(extra)
        with patch.object(type(self.Attachment), "with_delay", MagicMock()):
            attachment = self.Attachment.create(vals)
        self.assertEqual(attachment.scan_status, "pending", "fixture must start stranded")
        return attachment

    def _age(self, attachments, minutes):
        """Backdate ``write_date`` past the sweep's age threshold.

        ``write_date`` is maintained by the ORM, so the fixture has to reach around it with
        SQL — the same way the record would have aged in production.
        """
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE ir_attachment SET write_date = %s WHERE id IN %s",
            (fields.Datetime.subtract(fields.Datetime.now(), minutes=minutes), tuple(attachments.ids)),
        )
        attachments.invalidate_recordset(["write_date"])

    def _set_param(self, key, value):
        self.env["ir.config_parameter"].sudo().set_param(key, value)

    def _sweep(self):
        """Run one sweep with ``with_delay`` stubbed; return the mock for assertions."""
        with patch.object(type(self.Attachment), "with_delay", autospec=True) as mock_delay:
            self.Attachment._cron_sweep_pending_scans()
        return mock_delay

    def _swept_ids(self, mock_delay):
        """`autospec` keeps `self` in the call args, so we can see *which* records ran.

        A bare ``MagicMock`` on the class is not a descriptor, so the calling recordset
        never reaches the mock and every assertion here would collapse to "something was
        queued".
        """
        return {call.args[0].id for call in mock_delay.call_args_list}

    # ------------------------------------------------------------------
    # the core behaviour
    # ------------------------------------------------------------------

    def test_a_stranded_pending_attachment_is_re_enqueued(self):
        attachment = self._create_pending("stranded.txt")
        self._age(attachment, minutes=180)

        mock_delay = self._sweep()

        self.assertIn(attachment.id, self._swept_ids(mock_delay))

    def test_a_fresh_pending_attachment_is_not_re_enqueued(self):
        """The hooks just queued it; a deep queue is not a stranded record."""
        attachment = self._create_pending("fresh.txt")

        mock_delay = self._sweep()

        self.assertNotIn(
            attachment.id,
            self._swept_ids(mock_delay),
            "sweeping a fresh upload double-queues everything the hooks just queued",
        )

    def test_the_age_threshold_is_read_from_the_config_parameter(self):
        """Anti-vacuity for the test above: age is the reason, not some other filter."""
        attachment = self._create_pending("threshold.txt")
        self._age(attachment, minutes=30)

        self._set_param(PENDING_SWEEP_MIN_AGE_MINUTES_PARAM, "60")
        self.assertNotIn(attachment.id, self._swept_ids(self._sweep()))

        self._set_param(PENDING_SWEEP_MIN_AGE_MINUTES_PARAM, "10")
        self.assertIn(attachment.id, self._swept_ids(self._sweep()))

    # ------------------------------------------------------------------
    # batching
    # ------------------------------------------------------------------

    def test_the_batch_limit_is_respected_and_successive_runs_advance(self):
        """A first run on an existing database must not enqueue the whole backlog."""
        backlog = self.Attachment.browse()
        for index in range(5):
            backlog |= self._create_pending(f"backlog-{index}.txt")
        self._age(backlog, minutes=180)
        self._set_param(PENDING_SWEEP_BATCH_SIZE_PARAM, "2")

        first = self._swept_ids(self._sweep())
        self.assertEqual(len(first & set(backlog.ids)), 2, "the batch limit must bound one run")

        second = self._swept_ids(self._sweep())
        self.assertFalse(
            first & second,
            "successive runs must advance instead of re-picking the same rows",
        )
        self.assertEqual(len(second & set(backlog.ids)), 2)

    # ------------------------------------------------------------------
    # scope
    # ------------------------------------------------------------------

    def test_a_quarantined_attachment_is_skipped(self):
        """``action_rescan`` refuses a quarantined file; the sweep must do the same."""
        attachment = self._create_pending("quarantined.txt")
        attachment.with_context(skip_av_scan_queue=True).write({"is_quarantined": True})
        self._age(attachment, minutes=180)

        self.assertNotIn(attachment.id, self._swept_ids(self._sweep()))

    def test_an_attachment_without_a_res_model_is_skipped(self):
        """Module data and standalone system files are not user content."""
        attachment = self._create_pending("no-res-model.txt", res_model=False)
        self._age(attachment, minutes=180)

        self.assertNotIn(attachment.id, self._swept_ids(self._sweep()))

    def test_an_attachment_on_an_excluded_system_model_is_skipped(self):
        """Menu ``web_icon_data`` carries ``res_model='ir.ui.menu'``, not a blank one.

        `Binary(attachment=True)` storage sets ``res_model`` to the owning model, so a
        bare "``res_model`` is set" rule would sweep every source-controlled menu icon —
        exactly the records #464 stopped queueing.
        """
        self.assertIn("ir.ui.menu", SWEEP_EXCLUDED_MODELS)
        menu = self.env["ir.ui.menu"].create({"name": "AV sweep probe menu"})
        attachment = self._create_pending(
            "web-icon.png",
            res_model="ir.ui.menu",
            res_id=menu.id,
            res_field="web_icon_data",
        )
        self._age(attachment, minutes=180)

        self.assertNotIn(attachment.id, self._swept_ids(self._sweep()))

    def test_a_user_upload_into_a_binary_field_is_still_swept(self):
        """Anti-vacuity for the rule above: field storage per se is not the exclusion.

        ``res.partner.image_1920`` is field storage too, and it is user content.
        """
        attachment = self._create_pending(
            "user-image.png",
            res_model="res.partner",
            res_field="image_1920",
        )
        self._age(attachment, minutes=180)

        self.assertIn(attachment.id, self._swept_ids(self._sweep()))

    def test_a_forensic_download_copy_is_skipped(self):
        """A temporary admin copy of an already-infected file needs no scan."""
        attachment = self._create_pending("forensic.txt", is_forensic_download=True)
        self._age(attachment, minutes=180)

        self.assertNotIn(attachment.id, self._swept_ids(self._sweep()))

    def test_a_url_attachment_is_skipped(self):
        attachment = self.Attachment.create(
            {
                "name": "link.txt",
                "type": "url",
                "url": "https://example.invalid/file.txt",
                "res_model": "res.partner",
                "res_id": self.partner.id,
            }
        )
        self._age(attachment, minutes=180)

        self.assertNotIn(attachment.id, self._swept_ids(self._sweep()))

    # ------------------------------------------------------------------
    # bounded retries
    # ------------------------------------------------------------------

    def test_a_successful_re_enqueue_still_counts_as_an_attempt(self):
        """A queued job whose worker never runs it must be bounded too, not just a failure."""
        attachment = self._create_pending("counted.txt")
        self._age(attachment, minutes=180)

        self._sweep()

        self.assertEqual(attachment.scan_queue_attempts, 1)

    def test_a_record_at_the_attempt_cap_is_no_longer_picked_up(self):
        attachment = self._create_pending("exhausted.txt")
        self._set_param(PENDING_SWEEP_MAX_ATTEMPTS_PARAM, "3")
        attachment.with_context(skip_av_scan_queue=True).write({"scan_queue_attempts": 3})
        self._age(attachment, minutes=180)

        self.assertNotIn(attachment.id, self._swept_ids(self._sweep()))

    def test_a_record_below_the_attempt_cap_is_still_picked_up(self):
        """Anti-vacuity: the cap must bound retries, not disable the sweep."""
        attachment = self._create_pending("not-exhausted.txt")
        self._set_param(PENDING_SWEEP_MAX_ATTEMPTS_PARAM, "3")
        attachment.with_context(skip_av_scan_queue=True).write({"scan_queue_attempts": 2})
        self._age(attachment, minutes=180)

        self.assertIn(attachment.id, self._swept_ids(self._sweep()))

    def test_changing_the_bytes_re_arms_the_sweep(self):
        """New bytes are a new scan need, so the previous run's budget must not carry over."""
        attachment = self._create_pending("re-armed.txt")
        attachment.with_context(skip_av_scan_queue=True).write({"scan_queue_attempts": 3})

        with patch.object(type(self.Attachment), "with_delay", MagicMock()):
            attachment.write({"datas": base64.b64encode(b"changed")})

        self.assertEqual(attachment.scan_queue_attempts, 0)

    def test_a_manual_rescan_re_arms_the_sweep(self):
        """A human asking for a rescan must get the sweep's help again, not a dead record."""
        attachment = self._create_pending("manual-rescan.txt")
        attachment.with_context(skip_av_scan_queue=True).write({"scan_queue_attempts": 3})

        with patch.object(type(self.Attachment), "with_delay", MagicMock()):
            attachment.action_rescan()

        self.assertEqual(attachment.scan_queue_attempts, 0)

    def test_an_unreadable_attachment_cannot_occupy_a_batch_slot_forever(self):
        """`file_size` says there are bytes, but the filestore file is gone.

        Such a record can never be scanned. If the sweep skipped it without counting an
        attempt, its `write_date` would never move, it would sort to the head of every
        single run under `write_date asc`, and it would eat a batch slot forever.
        """
        attachment = self._create_pending("lost-filestore.txt")
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE ir_attachment SET store_fname = %s WHERE id = %s",
            ("av/sweep-probe-missing-file", attachment.id),
        )
        attachment.invalidate_recordset()
        self._age(attachment, minutes=180)

        # Odoo logs the unreadable filestore read itself, with a traceback. Capture it so
        # the test output stays clean, wherever between the probe and the sweep it lands.
        with self.assertLogs("odoo.addons.base.models.ir_attachment"):
            self.assertGreater(attachment.file_size, 0, "the record must still look like it has bytes")
            self.assertFalse(attachment.datas, "but the bytes must be unreadable")
            with self.assertLogs(LOGGER, "WARNING"):
                mock_delay = self._sweep()

        self.assertNotIn(attachment.id, self._swept_ids(mock_delay), "there is nothing to scan")
        self.assertEqual(attachment.scan_queue_attempts, 1, "but the slot it took must still be counted")

    def test_the_sweep_does_not_retain_binary_payloads_in_the_cache(self):
        """One hourly transaction must not accumulate every payload it inspects.

        Binary fields are not prefetched, but they are not evicted either: whatever the
        readability check reads stays cached for the rest of the run, so a full batch of
        stranded videos would hold every payload in memory simultaneously. The queued job
        re-reads the bytes in its own transaction, so nothing after the check needs them.
        """
        attachment = self._create_pending("cache-evict.txt")
        self._age(attachment, minutes=180)
        raw = self.Attachment._fields["raw"]

        # Anti-vacuity: reading the payload does put it in the cache.
        self.env.invalidate_all()
        self.assertTrue(attachment.datas)
        self.assertTrue(self.env.cache.contains(attachment, raw))

        self.env.invalidate_all()
        self._sweep()

        self.assertFalse(
            self.env.cache.contains(attachment, raw),
            "the readability check must evict the payload it read",
        )

    # ------------------------------------------------------------------
    # error handling — same two-sided contract as the hooks
    # ------------------------------------------------------------------

    def test_a_non_database_failure_does_not_abort_the_run_and_does_not_log_error(self):
        """The whole point is that a broken queue is survivable; it must also stay quiet.

        A record that fails every tick must not spam ERROR forever — the attempt cap
        bounds the retries and the run reports once, at WARNING.
        """
        attachment = self._create_pending("queue-broken.txt")
        self._age(attachment, minutes=180)

        with patch.object(type(self.Attachment), "with_delay", _raise_value_error):
            with self.assertLogs(LOGGER, "WARNING") as logs:
                self.Attachment._cron_sweep_pending_scans()

        self.assertTrue(attachment.exists())
        self.assertEqual(attachment.scan_status, "pending")
        self.assertEqual(attachment.scan_queue_attempts, 1, "a failed attempt must still be counted")
        self.assertFalse(
            [record for record in logs.records if record.levelname == "ERROR"],
            "a failing sweep must not spam ERROR on every tick",
        )

    def test_a_database_error_during_the_sweep_propagates(self):
        """Same contract as the hooks: the transaction is dead, the loop cannot continue."""
        attachment = self._create_pending("sweep-db-error.txt")
        self._age(attachment, minutes=180)

        with patch.object(type(self.Attachment), "with_delay", _raise_serialization_failure):
            with self.assertRaises(psycopg2.errors.SerializationFailure):
                self.Attachment._cron_sweep_pending_scans()

    # ------------------------------------------------------------------
    # wiring
    # ------------------------------------------------------------------

    def test_the_cron_is_registered_and_active(self):
        """The backlog is bounded by the batch limit, so shipping it disabled helps nobody."""
        cron = self.env.ref("spp_attachment_av_scan.ir_cron_sweep_pending_scans")
        self.assertTrue(cron.active)
        self.assertEqual(cron.model_id.model, "ir.attachment")
        self.assertIn("_cron_sweep_pending_scans", cron.code)

    def test_the_cron_and_config_defaults_are_not_reset_by_a_module_upgrade(self):
        """The comments on these records invite the admin to tune them.

        Without ``noupdate`` every module upgrade silently rewrites them: a raised batch
        size, a lowered age threshold, or a deliberately disabled cron all snap back to
        the shipped defaults.
        """
        for name in (
            "ir_cron_sweep_pending_scans",
            "config_param_pending_sweep_min_age_minutes",
            "config_param_pending_sweep_batch_size",
            "config_param_pending_sweep_max_attempts",
            "ir_cron_purge_quarantined_files",
            "ir_cron_cleanup_forensic_downloads",
            "config_param_quarantine_retention_days",
            "config_param_forensic_download_retention_hours",
        ):
            with self.subTest(record=name):
                imd = self.env["ir.model.data"].search([("module", "=", "spp_attachment_av_scan"), ("name", "=", name)])
                self.assertTrue(imd, "the record must exist")
                self.assertTrue(imd.noupdate, "an upgrade must keep admin-tuned values")
