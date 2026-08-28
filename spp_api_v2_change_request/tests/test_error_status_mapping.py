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

import ast
import inspect
from unittest.mock import patch

from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.fastapi.tests.common import FastAPITransactionCase
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from ..routers.change_request import (
    _detail_for_odoo_error,
    _status_for_odoo_error,
    change_request_router,
)
from ..services.change_request_service import ChangeRequestService
from .common import ChangeRequestTestCase


def _caught_exception_names(handler):
    """Names of the exception classes an ``except`` clause catches."""
    node = handler.type
    if node is None:
        return set()
    elts = node.elts if isinstance(node, ast.Tuple) else [node]
    names = set()
    for elt in elts:
        if isinstance(elt, ast.Name):
            names.add(elt.id)
        elif isinstance(elt, ast.Attribute):
            names.add(elt.attr)
    return names


@tagged("post_install", "-at_install")
class TestErrorStatusMapping(TransactionCase):
    def test_access_error_is_forbidden(self):
        self.assertEqual(_status_for_odoo_error(AccessError("nope")), 403)

    def test_access_denied_is_forbidden(self):
        """Both authorization exceptions map to 403, mirroring the platform's
        global handler (``fastapi.error_handlers`` groups them the same way)."""
        self.assertEqual(_status_for_odoo_error(AccessDenied()), 403)

    def test_plain_user_error_is_conflict(self):
        self.assertEqual(_status_for_odoo_error(UserError("wrong state")), 409)

    def test_validation_error_is_unprocessable(self):
        """A validation failure is invalid input, and reports 422 -- the same
        status the create and update endpoints use for the same condition."""
        self.assertEqual(_status_for_odoo_error(ValidationError("bad")), 422)

    def test_missing_error_is_not_found(self):
        """A record that vanished mid-transition is 404, mirroring the
        platform's global handler (``fastapi.error_handlers``)."""
        self.assertEqual(_status_for_odoo_error(MissingError("gone")), 404)

    def test_forbidden_detail_is_generic(self):
        """An AccessError message carries model names and rule text; the
        client gets a generic detail instead (anti-enumeration)."""
        detail = _detail_for_odoo_error(AccessError("secret record rule on spp.change.request"))
        self.assertNotIn("secret", detail)
        self.assertNotIn("spp.change.request", detail)
        self.assertEqual(detail, _detail_for_odoo_error(AccessDenied()))

    def test_non_forbidden_detail_passes_through(self):
        self.assertEqual(_detail_for_odoo_error(UserError("wrong state")), "wrong state")
        self.assertEqual(
            _detail_for_odoo_error(ValidationError("Rejection reason is required")),
            "Rejection reason is required",
        )

    def test_access_error_is_not_shadowed_by_its_base_class(self):
        """The whole bug: AccessError *is* a UserError, so order matters."""
        self.assertIsInstance(AccessError("nope"), UserError)
        self.assertNotEqual(
            _status_for_odoo_error(AccessError("nope")),
            _status_for_odoo_error(UserError("nope")),
            "an authorization failure must not report the same status as a conflict",
        )

    def test_every_state_transition_handler_uses_the_mapping(self):
        """Guard against a handler reintroducing a bare 409 for UserError.

        Matched on the AST, not on a source substring: a string match on
        ``except UserError as e:`` is blind to the tuple form
        ``except (UserError, ValidationError) as e:`` and to renamed bindings,
        which is exactly how the handlers this guard once missed spelled it.
        Handlers that catch only ``ValidationError`` (create/update map it to
        422) are intentionally out of scope: ``ValidationError`` never carries
        an authorization failure.
        """
        from ..routers import change_request as module

        tree = ast.parse(inspect.getsource(module))
        handlers = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler) and "UserError" in _caught_exception_names(node)
        ]
        self.assertTrue(handlers, "expected at least one UserError handler to exist")
        for handler in handlers:
            names_used = {node.id for stmt in handler.body for node in ast.walk(stmt) if isinstance(node, ast.Name)}
            self.assertIn(
                "_status_for_odoo_error",
                names_used,
                f"the UserError handler at line {handler.lineno} returns a hard-coded status; "
                "AccessError would be reported as a conflict again",
            )


@tagged("post_install", "-at_install")
class TestTransitionRoutesStatusMapping(FastAPITransactionCase, ChangeRequestTestCase):
    """The AccessError -> 403 mapping, exercised through the real routes.

    The unit tests above call ``_status_for_odoo_error`` in isolation; these
    call the actual FastAPI handlers over HTTP. The change-request record rules
    apply one domain to read and write alike, so a CR that is readable but not
    writable cannot be constructed from data alone; the ``AccessError`` is
    therefore injected at the service boundary. The route, the handler and its
    ``except`` clause are the real ones.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.default_fastapi_router = change_request_router

        org_type = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not org_type:
            org_type = cls.env["spp.consent.org.type"].create(
                {
                    "name": "Government",
                    "code": "government",
                }
            )
        partner = cls.env["res.partner"].create({"name": "Route Test Org"})
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Route Test Client",
                "partner_id": partner.id,
                "organization_type_id": org_type.id,
            }
        )
        # The action selection has no per-verb "approve"/"apply" values, so
        # "all" is the only value that satisfies those scope checks.
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "change_request",
                "action": "all",
            }
        )
        api_client = cls.api_client
        cls.default_fastapi_dependency_overrides = {get_authenticated_client: lambda: api_client}

        cls.change_request = cls.cr_model.create(
            {
                "request_type_id": cls.cr_type_edit.id,
                "registrant_id": cls.registrant.id,
            }
        )

    def _post(self, action, json=None):
        with self._create_test_client() as client:
            return client.post(f"/ChangeRequest/{self.change_request.name}/{action}", json=json)

    def test_reject_reports_access_error_as_forbidden(self):
        with patch.object(ChangeRequestService, "reject", side_effect=AccessError("denied")):
            response = self._post("$reject", json={"reason": "duplicate request"})
        self.assertEqual(response.status_code, 403)

    def test_request_revision_reports_access_error_as_forbidden(self):
        with patch.object(ChangeRequestService, "request_revision", side_effect=AccessError("denied")):
            response = self._post("$request-revision", json={"notes": "please clarify"})
        self.assertEqual(response.status_code, 403)

    def test_apply_reports_access_error_as_forbidden(self):
        with patch.object(ChangeRequestService, "apply", side_effect=AccessError("denied")):
            response = self._post("$apply")
        self.assertEqual(response.status_code, 403)

    def test_reject_reports_plain_user_error_as_conflict(self):
        with patch.object(ChangeRequestService, "reject", side_effect=UserError("wrong state")):
            response = self._post("$reject", json={"reason": "duplicate request"})
        self.assertEqual(response.status_code, 409)

    def test_reject_reports_validation_error_as_unprocessable(self):
        with patch.object(ChangeRequestService, "reject", side_effect=ValidationError("bad")):
            response = self._post("$reject", json={"reason": "duplicate request"})
        self.assertEqual(response.status_code, 422)

    def test_reject_forbidden_detail_is_generic(self):
        with patch.object(
            ChangeRequestService,
            "reject",
            side_effect=AccessError("record rule on spp.change.request denied user 7"),
        ):
            response = self._post("$reject", json={"reason": "duplicate request"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("record rule", response.json()["detail"])

    def test_create_reports_access_error_as_forbidden(self):
        """create() used to swallow AccessError in its bare except and report
        500; an authorization failure there is 403 like everywhere else."""
        payload = {
            "type": "ChangeRequest",
            "requestType": {"code": "edit_individual"},
            "registrant": {"system": "urn:openspp:vocab:id-type", "value": "TEST-123"},
            "detail": {"given_name": "Blocked"},
        }
        with (
            patch.object(ChangeRequestService, "create", side_effect=AccessError("denied")),
            self._create_test_client() as client,
        ):
            response = client.post("/ChangeRequest", json=payload)
        self.assertEqual(response.status_code, 403)
