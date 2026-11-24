"""The audit decorator's context flags are for server-side code only.

A plain value in the context, such as one sent by an RPC client, does not
change what is audited.
"""

import json
from unittest.mock import patch

from odoo import Command
from odoo.service.model import call_kw
from odoo.tests.common import new_test_user

from ..tools import AUDIT_DISABLE
from ..tools.decorator import _writes_in_progress
from .test_audit_disable import AuditDisableCommon

PLAIN_DISABLE_FLAGS = [
    {"audit_disable": True},
    {"audit_disable": "audit_disable"},
]
# audit_in_progress is not read by the decorator; a client may still send it
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


class TestNestedWritesAudited(AuditDisableCommon):
    """A write made inside an audited write is audited when it touches other records."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env,
            login="audit_nested_write_user",
            groups="base.group_user,base.group_partner_manager",
        )

    def test_child_updated_through_parent_is_logged(self):
        parent = self.env["res.partner"].create({"name": "Nested Parent", "is_company": True})
        child = self.env["res.partner"].create({"name": "Nested Child", "parent_id": parent.id})
        call_kw(
            self.env["res.partner"].with_user(self.user),
            "write",
            [[parent.id], {"child_ids": [Command.update(child.id, {"name": "Nested Child Changed"})]}],
            {},
        )
        self.assertEqual(child.name, "Nested Child Changed")
        self.assertEqual(len(self._logs(child, "write")), 1)

    def test_parent_and_child_each_logged_once(self):
        parent = self.env["res.partner"].create({"name": "Both Parent", "is_company": True})
        child = self.env["res.partner"].create({"name": "Both Child", "parent_id": parent.id})
        parent.write(
            {"name": "Both Parent Changed", "child_ids": [Command.update(child.id, {"name": "Both Child Changed"})]}
        )
        self.assertEqual(len(self._logs(parent, "write")), 1)
        self.assertEqual(len(self._logs(child, "write")), 1)

    def test_write_in_progress_for_another_record_does_not_skip(self):
        covered = self.env["res.partner"].create({"name": "Covered"})
        other = self.env["res.partner"].create({"name": "Other"})
        in_progress = _writes_in_progress(self.env)
        in_progress.add(("res.partner", covered.id))
        self.addCleanup(in_progress.clear)
        (covered | other).write({"name": "Written Together"})
        self.assertFalse(self._logs(covered, "write"))
        self.assertEqual(len(self._logs(other, "write")), 1)

    def test_nested_write_to_same_record_is_logged_once(self):
        """The original write runs with its records marked, so a nested write to them is not logged again."""
        partner = self.env["res.partner"].create({"name": "Same Record"})
        audit_write = type(partner).write
        real_origin = audit_write.origin
        seen = []

        def spy(records, vals):
            seen.append(set(_writes_in_progress(records.env)))
            if len(seen) == 1:
                # A write to the same record, on an audited field, from inside the original write
                records.write({"name": "Same Record Nested"})
            return real_origin(records, vals)

        with patch.object(audit_write, "origin", spy):
            partner.write({"name": "Same Record Changed"})

        self.assertIn(("res.partner", partner.id), seen[0])
        self.assertEqual(len(self._logs(partner, "write")), 1)
        self.assertFalse(_writes_in_progress(self.env))

    def test_failed_write_leaves_nothing_in_progress(self):
        partner = self.env["res.partner"].create({"name": "Failing Write"})
        audit_write = type(partner).write

        def failing(records, vals):
            raise RuntimeError("write failed")

        with patch.object(audit_write, "origin", failing), self.assertRaises(RuntimeError):
            partner.write({"name": "Never Written"})

        self.assertFalse(_writes_in_progress(self.env))
        partner.write({"name": "Written After Failure"})
        self.assertEqual(len(self._logs(partner, "write")), 1)
