"""A binary attachment written while the registry is still loading must not queue a scan.

The scan-queue hooks re-raise database errors (see ``test_scan_queue_error_handling``) so a
runtime request can retry a serialization conflict through ``odoo.service.model.retrying``.
That contract is right inside a request, where the retry wrapper exists. It is a trap during
registry construction, which has no such wrapper: a re-raised ``could not serialize access due
to concurrent update`` from a peer instance on a shared database aborts the whole registry
load and the server never boots.

Registry load writes binary attachments routinely. Module data may declare ``ir.attachment``
records outright, and every ``ir.ui.menu`` carrying a ``web_icon`` recomputes ``web_icon_data``
(a ``Binary(attachment=True)`` field) whenever its XML is loaded, which lands as an
``ir.attachment`` create or write. Enqueueing there inserts a ``queue.job`` row, and that
insert flushes the deferred ``ir_attachment`` UPDATE inside the re-raising hook.

The guard: while ``env.registry.ready`` is False, ``create`` and ``write`` enqueue nothing.
``write`` still resets the scan status, so bytes that changed during load do not keep a stale
``clean`` verdict — they go back to ``pending`` and wait for a rescan. Runtime uploads are
untouched. Every side is asserted here so the guard cannot regress in either direction.
"""

import base64
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScanQueueRegistryReady(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env["ir.attachment"]

    def _binary_vals(self, name, payload=b"probe"):
        return {
            "name": name,
            "datas": base64.b64encode(payload),
            "mimetype": "text/plain",
        }

    def test_create_does_not_queue_a_scan_while_the_registry_loads(self):
        """A system asset created during load enqueues nothing, and stays unscanned."""
        with patch.object(self.env.registry, "ready", False):
            with patch.object(type(self.Attachment), "with_delay", MagicMock()) as mock_delay:
                attachment = self.Attachment.create(self._binary_vals("boot-create.txt"))

        mock_delay.assert_not_called()
        self.assertTrue(attachment.exists(), "the attachment must still be created")
        self.assertEqual(
            attachment.scan_status,
            "pending",
            "an unscanned attachment must not look scanned",
        )

    def test_write_does_not_queue_a_scan_while_the_registry_loads(self):
        """The `web_icon_data` refresh is a write(), which is the exact incident site."""
        attachment = self.Attachment.create(self._binary_vals("boot-write.txt"))
        attachment.scan_status = "clean"

        with patch.object(self.env.registry, "ready", False):
            with patch.object(type(self.Attachment), "with_delay", MagicMock()) as mock_delay:
                attachment.write({"datas": base64.b64encode(b"changed-during-load")})

        mock_delay.assert_not_called()
        self.assertEqual(
            attachment.scan_status,
            "pending",
            "changed bytes must not keep the previous scan's clean verdict",
        )

    def test_runtime_create_still_queues_a_scan(self):
        """Anti-vacuity: the guard must suppress only during load, never at runtime."""
        self.assertTrue(self.env.registry.ready, "registry is ready in a normal test run")

        with patch.object(type(self.Attachment), "with_delay", MagicMock()) as mock_delay:
            self.Attachment.create(self._binary_vals("runtime-create.txt"))

        mock_delay.assert_called()

    def test_runtime_write_still_queues_a_scan(self):
        attachment = self.Attachment.create(self._binary_vals("runtime-write.txt"))

        with patch.object(type(self.Attachment), "with_delay", MagicMock()) as mock_delay:
            attachment.write({"datas": base64.b64encode(b"changed-at-runtime")})

        mock_delay.assert_called()
