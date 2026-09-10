# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Engine wiring: a metric() call with a named arg threads params -> params_hash,
so the cache lookup is keyed by the parameter.

This exercises the spp_cel_domain change (translator reads kwargs into
MetricCompare.params; executor hashes them) directly via metric(), independent
of the DCI resolver/fetcher.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDCICelParams(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DV = cls.env["spp.data.value"]
        cls.svc = cls.env["spp.cel.service"]
        cls.partner = cls.env["res.partner"].create({"name": "Param Person", "is_registrant": True, "is_group": False})
        # Two cached values for the same metric, distinguished only by params.
        cls.DV.upsert_values(
            [
                {
                    "variable_name": "zz.test.severity",
                    "subject_model": "res.partner",
                    "subject_id": cls.partner.id,
                    "period_key": "current",
                    "value_json": {"value": 4},
                    "value_type": "number",
                    "source_type": "external",
                    "params": {"arg": "Vision"},
                    "ttl_seconds": 3600,
                },
                {
                    "variable_name": "zz.test.severity",
                    "subject_model": "res.partner",
                    "subject_id": cls.partner.id,
                    "period_key": "current",
                    "value_json": {"value": 1},
                    "value_type": "number",
                    "source_type": "external",
                    "params": {"arg": "Hearing"},
                    "ttl_seconds": 3600,
                },
            ]
        )

    def _match(self, expr):
        r = self.svc.compile_expression(
            expr,
            profile="registry_individuals",
            base_domain=[("id", "in", [self.partner.id])],
            limit=0,
            materialize_sql=True,
        )
        self.assertTrue(r.get("valid"), r.get("error"))
        return self.env["res.partner"].search(r["domain"])

    def test_param_selects_the_matching_row(self):
        # Vision=4 >= 3  -> matches
        self.assertIn(self.partner, self._match("metric('zz.test.severity', me, arg='Vision') >= 3"))

    def test_param_discriminates_by_params_hash(self):
        # Hearing=1 >= 3 -> excluded (proves the lookup keyed on params, not just name)
        self.assertNotIn(self.partner, self._match("metric('zz.test.severity', me, arg='Hearing') >= 3"))

    def test_param_query_ignores_unparameterized_row(self):
        """A parameterized query must NOT fall back to an unparameterized cache
        row for the same metric. Seed a legacy/default row (no params -> params_hash
        "") whose value would satisfy the comparison; querying with a param whose
        own row does NOT satisfy it must still exclude the subject.

        Before the fix, _provider_clause appended (provider, "") / ("", "")
        combos, so the unparameterized value=4 row matched arg='Hearing' >= 3.
        """
        # Unparameterized row (params_hash "") with a value that satisfies >= 3.
        self.DV.upsert_values(
            [
                {
                    "variable_name": "zz.test.severity",
                    "subject_model": "res.partner",
                    "subject_id": self.partner.id,
                    "period_key": "current",
                    "value_json": {"value": 4},
                    "value_type": "number",
                    "source_type": "external",
                    # no "params" -> params_hash == ""
                    "ttl_seconds": 3600,
                },
            ]
        )
        # Hearing's own value is 1 (< 3); the unparameterized 4 must not leak in.
        self.assertNotIn(self.partner, self._match("metric('zz.test.severity', me, arg='Hearing') >= 3"))

    def test_unparameterized_query_still_matches_unparameterized_row(self):
        """No regression for legacy metrics: an unparameterized query still
        matches an unparameterized cache row."""
        self.DV.upsert_values(
            [
                {
                    "variable_name": "zz.test.plain",
                    "subject_model": "res.partner",
                    "subject_id": self.partner.id,
                    "period_key": "current",
                    "value_json": {"value": 4},
                    "value_type": "number",
                    "source_type": "external",
                    "ttl_seconds": 3600,
                },
            ]
        )
        self.assertIn(self.partner, self._match("metric('zz.test.plain', me) >= 3"))
