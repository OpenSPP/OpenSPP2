# Copyright 2021 Camptocamp SA
# @author: Simone Orsi <simone.orsi@camptocamp.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import contextlib

import odoo
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import DotDict


class MockRequest(contextlib.AbstractContextManager):
    """Minimal request shim for Odoo 19 tests.

    Odoo 19 no longer exposes website.tools.MockRequest, so we provide a small
    replacement that mirrors the few attributes our tests rely on.
    """

    def __init__(self, env):
        self.env = env
        # fake underlying httprequest object
        self.httprequest = DotDict(headers={})
        # registry reference used by tests to tweak _init_modules
        self.registry = env.registry
        self._previous = None

    def __enter__(self):
        # stash existing request and install ourselves
        self._previous = getattr(odoo.http, "request", None)
        odoo.http.request = self
        # mirror the attr used in the tests
        self.registry._init_modules = set()
        return self

    def __exit__(self, exc_type, exc, tb):
        # restore previous global request
        odoo.http.request = self._previous
        return False


@tagged("-at_install", "post_install")
class CommonEndpoint(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_env()
        cls._setup_records()
        cls.route_handler = cls.env["endpoint.route.handler"]

    @classmethod
    def _setup_env(cls):
        cls.env = cls.env(context=cls._setup_context())

    @classmethod
    def _setup_context(cls):
        return dict(
            cls.env.context,
            tracking_disable=True,
        )

    @classmethod
    def _setup_records(cls):
        pass

    @contextlib.contextmanager
    def _get_mocked_request(self, env=None, httprequest=None, extra_headers=None, request_attrs=None):
        with MockRequest(env or self.env) as mocked_request:
            mocked_request.httprequest = DotDict(httprequest) if httprequest else mocked_request.httprequest
            headers = {}
            headers.update(extra_headers or {})
            mocked_request.httprequest.headers = headers
            request_attrs = request_attrs or {}
            for k, v in request_attrs.items():
                setattr(mocked_request, k, v)
            mocked_request.make_response = lambda data, **kw: data
            mocked_request.registry._init_modules = set()
            yield mocked_request
