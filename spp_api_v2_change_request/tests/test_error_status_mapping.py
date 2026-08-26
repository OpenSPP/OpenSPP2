# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""An authorization failure must surface as 403, not 409.

``AccessError`` subclasses ``UserError`` in Odoo, so the state-transition
endpoints -- which caught ``UserError`` and returned ``409 Conflict`` -- reported
permission failures as conflicts. That is wrong twice over: the client is told to
resolve a conflict it cannot see, and a client that retries on 409 (reasonable
for a genuine conflict, which may clear) loops on a permission error that never
will.

This became reachable on ``$apply`` once applying a change request began
requiring the change-request manager role: the endpoint's own scope check
already returns 403, so the two authorization failures on one endpoint reported
different statuses.
"""

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..routers.change_request import _status_for_odoo_error


@tagged("post_install", "-at_install")
class TestErrorStatusMapping(TransactionCase):
    def test_access_error_is_forbidden(self):
        self.assertEqual(_status_for_odoo_error(AccessError("nope")), 403)

    def test_plain_user_error_is_conflict(self):
        self.assertEqual(_status_for_odoo_error(UserError("wrong state")), 409)

    def test_validation_error_is_conflict(self):
        """Documents current behaviour; arguably 422, but out of scope here."""
        self.assertEqual(_status_for_odoo_error(ValidationError("bad")), 409)

    def test_access_error_is_not_shadowed_by_its_base_class(self):
        """The whole bug: AccessError *is* a UserError, so order matters."""
        self.assertIsInstance(AccessError("nope"), UserError)
        self.assertNotEqual(
            _status_for_odoo_error(AccessError("nope")),
            _status_for_odoo_error(UserError("nope")),
            "an authorization failure must not report the same status as a conflict",
        )

    def test_every_state_transition_handler_uses_the_mapping(self):
        """Guard against a new endpoint reintroducing a bare 409 for UserError."""
        import inspect

        from ..routers import change_request as module

        source = inspect.getsource(module)
        blocks = source.split("except UserError as e:")[1:]
        self.assertTrue(blocks, "expected at least one UserError handler to exist")
        for block in blocks:
            head = block[:200]
            self.assertIn(
                "_status_for_odoo_error",
                head,
                "a UserError handler returns a hard-coded status; AccessError would be reported as a conflict again",
            )
