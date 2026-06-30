# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security tests for the Data API pull/list endpoints.

These drive the async router functions to completion via asyncio.run so the
endpoint bodies actually execute (a bare ``async def test_*`` on a unittest
TestCase is collected but never awaited, i.e. a silent no-op). They verify the
allowlist guard added to /Data/pull and /Data/variables.
"""

import asyncio

from odoo.tests.common import TransactionCase

from fastapi import HTTPException, status


class TestDataApiPullSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        org_type = cls.env.ref("spp_consent.org_type_government", raise_if_not_found=False)
        if not org_type:
            org_type = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

        cls.partner = cls.env["res.partner"].create({"name": "Subject 1", "ref": "EDU-001"})

        cls.provider = cls.env["spp.data.provider"].create(
            {"name": "Edu Ministry", "code": "edu_sec_t", "active": True}
        )
        cls.ext_var = cls.env["spp.cel.variable"].create(
            {
                "name": "School Attendance Sec",
                "cel_accessor": "school_attendance_sec",
                "source_type": "external",
                "external_provider_id": cls.provider.id,
                "value_type": "number",
                "cache_strategy": "ttl",
            }
        )
        cls.computed_var = cls.env["spp.cel.variable"].create(
            {
                "name": "Computed Sec",
                "cel_accessor": "computed_sec",
                "source_type": "computed",
                "value_type": "number",
                "cache_strategy": "none",
            }
        )

        api_partner = cls.env["res.partner"].create({"name": "API Partner Sec"})
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Sec Client",
                "partner_id": api_partner.id,
                "organization_type_id": org_type.id,
            }
        )
        cls.env["spp.api.client.scope"].create({"client_id": cls.api_client.id, "resource": "data", "action": "read"})

    def _run(self, coro):
        return asyncio.run(coro)

    def _cache(self, variable_name, source_type="external", company=None):
        self.env["spp.data.value"].create(
            {
                "company_id": (company or self.env.company).id,
                "variable_name": variable_name,
                "subject_id": self.partner.id,
                "period_key": "current",
                "value_json": {"value": 0.95},
                "value_type": "number",
                "source_type": source_type,
            }
        )

    # --- pull ---------------------------------------------------------------

    def test_pull_ordinary_external_variable_succeeds(self):
        from ..routers.data import pull_values

        self._cache("school_attendance_sec")
        result = self._run(
            pull_values(
                env=self.env,
                api_client=self.api_client,
                variable="school_attendance_sec",
                subject_external_ids="EDU-001",
                period_key="current",
                _count=100,
            )
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].value, 0.95)

    def test_pull_unknown_variable_rejected(self):
        from ..routers.data import pull_values

        with self.assertRaises(HTTPException) as cm:
            self._run(
                pull_values(
                    env=self.env,
                    api_client=self.api_client,
                    variable="does_not_exist",
                    subject_external_ids="EDU-001",
                    period_key="current",
                    _count=100,
                )
            )
        self.assertEqual(cm.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_pull_non_pullable_variable_rejected(self):
        from ..routers.data import pull_values

        # computed_var has a cached row but is not pullable -> 403 before read.
        self._cache("computed_sec", source_type="computed")
        with self.assertRaises(HTTPException) as cm:
            self._run(
                pull_values(
                    env=self.env,
                    api_client=self.api_client,
                    variable="computed_sec",
                    subject_external_ids="EDU-001",
                    period_key="current",
                    _count=100,
                )
            )
        self.assertEqual(cm.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_pull_other_company_value_not_returned(self):
        from ..routers.data import pull_values

        other = self.env["res.company"].create({"name": "Other Co Sec"})
        self._cache("school_attendance_sec", company=other)
        result = self._run(
            pull_values(
                env=self.env,
                api_client=self.api_client,
                variable="school_attendance_sec",
                subject_external_ids="EDU-001",
                period_key="current",
                _count=100,
            )
        )
        self.assertEqual(result.total, 0)

    # --- list ---------------------------------------------------------------

    def test_list_variables_excludes_non_external(self):
        from ..routers.data import list_variables

        result = self._run(
            list_variables(
                env=self.env,
                api_client=self.api_client,
                provider_code=None,
                source_type=None,
                _count=500,
                _last_id=None,
            )
        )
        accessors = [v.cel_accessor for v in result.items]
        self.assertIn("school_attendance_sec", accessors)
        self.assertNotIn("computed_sec", accessors)
        # total is computed on the same filtered domain, so it matches the items.
        self.assertEqual(result.total, len(result.items))
        self.assertTrue(all(v.source_type == "external" for v in result.items))
