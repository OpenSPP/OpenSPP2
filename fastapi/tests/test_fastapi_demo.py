# Copyright 2022 ACSONE SA/NV
# License LGPL-3.0 or later (http://www.gnu.org/licenses/LGPL).

from functools import partial

from requests import Response

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools.misc import mute_logger

from fastapi import status

from ..dependencies import fastapi_endpoint
from ..routers import demo_router
from ..schemas import DemoEndpointAppInfo, DemoExceptionType
from .common import FastAPITransactionCase


class FastAPIDemoCase(FastAPITransactionCase):
    """The fastapi lib comes with a useful testclient that let's you
    easily test your endpoints. Moreover, the dependency overrides functionality
    allows you to provide specific implementation for part of the code to avoid
    to rely on some tricky http stuff for example: authentication

    This test class is an example on how you can test your own code
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.default_fastapi_router = demo_router
        cls.default_fastapi_running_user = cls._get_or_create_demo_user()
        cls.default_fastapi_authenticated_partner = cls.env["res.partner"].create({"name": "FastAPI Demo"})

    @classmethod
    def _get_or_create_demo_user(cls):
        """Get or create the demo app user (demo data may not be loaded)."""
        try:
            return cls.env.ref("fastapi.my_demo_app_user")
        except ValueError:
            runner_group = cls.env.ref("fastapi.group_fastapi_endpoint_runner")
            user = cls.env["res.users"].create(
                {
                    "name": "My Demo Endpoint User",
                    "login": "my_demo_app_user",
                    "group_ids": [Command.set([runner_group.id])],
                }
            )
            cls.env["ir.model.data"].create(
                {
                    "name": "my_demo_app_user",
                    "module": "fastapi",
                    "model": "res.users",
                    "res_id": user.id,
                }
            )
            return user

    def test_hello_world(self) -> None:
        with self._create_test_client() as test_client:
            response: Response = test_client.get("/demo/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(response.json(), {"Hello": "World"})

    def test_who_ami(self) -> None:
        with self._create_test_client() as test_client:
            response: Response = test_client.get("/demo/who_ami")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        partner = self.default_fastapi_authenticated_partner
        self.assertDictEqual(
            response.json(),
            {
                "name": partner.name,
                "display_name": partner.display_name,
            },
        )

    def _get_or_create_demo_endpoint(self):
        """Get or create the demo endpoint (demo data may not be loaded)."""
        try:
            return self.env.ref("fastapi.fastapi_endpoint_demo")
        except ValueError:
            demo_user = self._get_or_create_demo_user()
            endpoint = self.env["fastapi.endpoint"].create(
                {
                    "name": "Fastapi Demo Endpoint",
                    "app": "demo",
                    "root_path": "/fastapi_demo",
                    "demo_auth_method": "http_basic",
                    "user_id": demo_user.id,
                }
            )
            self.env["ir.model.data"].create(
                {
                    "name": "fastapi_endpoint_demo",
                    "module": "fastapi",
                    "model": "fastapi.endpoint",
                    "res_id": endpoint.id,
                }
            )
            return endpoint

    def test_endpoint_info(self) -> None:
        demo_app = self._get_or_create_demo_endpoint()
        with self._create_test_client(
            dependency_overrides={fastapi_endpoint: partial(lambda a: a, demo_app)}
        ) as test_client:
            response: Response = test_client.get("/demo/endpoint_app_info")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.json(),
            DemoEndpointAppInfo.model_validate(demo_app).model_dump(by_alias=True),
        )

    def test_exception_raised(self) -> None:
        with self.assertRaisesRegex(UserError, "User Error"):
            with self._create_test_client() as test_client:
                test_client.get(
                    "/demo/exception",
                    params={
                        "exception_type": DemoExceptionType.user_error.value,
                        "error_message": "User Error",
                    },
                )

        with self.assertRaisesRegex(NotImplementedError, "Bare Exception"):
            with self._create_test_client() as test_client:
                test_client.get(
                    "/demo/exception",
                    params={
                        "exception_type": DemoExceptionType.bare_exception.value,
                        "error_message": "Bare Exception",
                    },
                )

    @mute_logger("odoo.addons.fastapi.tests.common")
    def test_exception_not_raised(self) -> None:
        with self._create_test_client(raise_server_exceptions=False) as test_client:
            response: Response = test_client.get(
                "/demo/exception",
                params={
                    "exception_type": DemoExceptionType.user_error.value,
                    "error_message": "User Error",
                },
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictEqual(response.json(), {"detail": "User Error"})

        with self._create_test_client(raise_server_exceptions=False) as test_client:
            response: Response = test_client.get(
                "/demo/exception",
                params={
                    "exception_type": DemoExceptionType.bare_exception.value,
                    "error_message": "Bare Exception",
                },
            )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertDictEqual(response.json(), {"detail": "Internal Server Error"})
