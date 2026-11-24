"""The audit decorator's context flags are for server-side code only.

A plain value in the context, such as one sent by an RPC client, does not
change what is audited.
"""

import json

from odoo.service.model import call_kw
from odoo.tests.common import new_test_user

from ..tools import AUDIT_DISABLE
from .test_audit_disable import AuditDisableCommon

PLAIN_DISABLE_FLAGS = [
    {"audit_disable": True},
    {"audit_disable": "audit_disable"},
]
# audit_in_progress is only read on write
PLAIN_FLAGS = PLAIN_DISABLE_FLAGS + [
    {"audit_in_progress": True},
    {"audit_in_progress": "audit_in_progress"},
]


class TestPlainContextFlagsStillAudited(AuditDisableCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env,
            login="audit_context_flags_user",
            groups="base.group_user,base.group_partner_manager",
        )

    def _partner_model(self):
        return self.env["res.partner"].with_user(self.user)

    def test_rpc_create_is_logged(self):
        for flags in PLAIN_DISABLE_FLAGS:
            with self.subTest(context=flags):
                partner_id = call_kw(self._partner_model(), "create", [{"name": "Flag Create"}], {"context": flags})
                self.assertTrue(self._logs(self.env["res.partner"].browse(partner_id), "create"))

    def test_rpc_write_is_logged(self):
        for flags in PLAIN_FLAGS:
            with self.subTest(context=flags):
                partner = self.env["res.partner"].create({"name": "Flag Write"})
                call_kw(
                    self._partner_model(), "write", [[partner.id], {"name": "Flag Write Changed"}], {"context": flags}
                )
                self.assertEqual(len(self._logs(partner, "write")), 1)

    def test_rpc_unlink_is_logged(self):
        for flags in PLAIN_DISABLE_FLAGS:
            with self.subTest(context=flags):
                partner = self.env["res.partner"].create({"name": "Flag Unlink"})
                call_kw(self._partner_model(), "unlink", [[partner.id]], {"context": flags})
                self.assertFalse(partner.exists())
                self.assertTrue(self._logs(partner, "unlink"))

    def test_server_side_plain_value_is_logged(self):
        for flags in PLAIN_FLAGS:
            with self.subTest(context=flags):
                partner = self.env["res.partner"].create({"name": "Flag Server"})
                partner.with_context(**flags).write({"name": "Flag Server Changed"})
                self.assertEqual(len(self._logs(partner, "write")), 1)

    def test_server_side_plain_value_create_is_logged(self):
        for flags in PLAIN_DISABLE_FLAGS:
            with self.subTest(context=flags):
                partner = self.env["res.partner"].with_context(**flags).create({"name": "Flag Server Create"})
                self.assertTrue(self._logs(partner, "create"))


class TestContextMarker(AuditDisableCommon):
    def test_marker_does_not_equal_its_text(self):
        self.assertNotEqual(AUDIT_DISABLE, "audit_disable")
        self.assertNotEqual("audit_disable", AUDIT_DISABLE)
        self.assertNotEqual({"audit_disable": "audit_disable"}, {"audit_disable": AUDIT_DISABLE})

    def test_marker_serialises(self):
        self.assertEqual(json.dumps({"audit_disable": AUDIT_DISABLE}), '{"audit_disable": "audit_disable"}')

    def test_plain_text_after_marker_is_logged(self):
        """A context holding the marker's text does not reuse the marker's environment."""
        partner = self.env["res.partner"].create({"name": "Marker Then Text"})
        partner.with_context(audit_disable=AUDIT_DISABLE).write({"name": "Marker Write"})
        self.assertFalse(self._logs(partner, "write"))
        partner.with_context(audit_disable="audit_disable").write({"name": "Text Write"})
        self.assertEqual(len(self._logs(partner, "write")), 1)

    def test_marker_after_plain_text_still_disables(self):
        """A context holding the marker does not reuse the environment of one holding its text."""
        partner = self.env["res.partner"].create({"name": "Text Then Marker"})
        partner.with_context(audit_disable="audit_disable").write({"name": "Text Write"})
        self.assertEqual(len(self._logs(partner, "write")), 1)
        partner.with_context(audit_disable=AUDIT_DISABLE).write({"name": "Marker Write"})
        self.assertEqual(len(self._logs(partner, "write")), 1)
