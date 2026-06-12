# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ``_smart_op_domain`` value/code label resolution.

The translator resolves human labels (e.g. "male"/"female") against a
many2one comodel that exposes a ``value`` field. Compiling such an
expression must be a read-only operation: it must never create vocabulary
codes (or any other seed records) as a side effect, and it must never use
``sudo()`` to bypass access rights during compilation.

No shipped comodel pairs a ``value`` field with the gender labels, so the
branch is exercised here with a lightweight fake environment that mimics
the ORM surface the method touches.
"""

from odoo.tests import TransactionCase, tagged


class _FakeField:
    def __init__(self, type_, comodel_name):
        self.type = type_
        self.comodel_name = comodel_name


class _FakeRecordset:
    """Minimal recordset stand-in for the label comodel."""

    def __init__(self, fields_, records=None):
        self._fields = fields_
        self._records = records or []

    def with_context(self, **kwargs):
        return self

    def sudo(self):
        return self

    def search(self, domain, limit=None):
        wanted = None
        for clause in domain:
            if isinstance(clause, tuple) and clause[0] == "value":
                wanted = clause[2]
        matched = [r for r in self._records if r["value"] == wanted]
        return _FakeRecordset(self._fields, matched)

    def create(self, vals):  # pylint: disable=method-required-super
        # Must never be called: compilation is read-only.
        raise AssertionError("_smart_op_domain must not create records during compilation")

    def __bool__(self):
        return bool(self._records)

    @property
    def ids(self):
        return [r["id"] for r in self._records]


class _FakeEnv:
    def __init__(self, models):
        self._models = models

    def __getitem__(self, model_name):
        return self._models[model_name]


class _FakeTranslator:
    """Stub exposing only the ``env`` attribute used by ``_smart_op_domain``."""

    def __init__(self, env):
        self.env = env


@tagged("post_install", "-at_install")
class TestSmartOpLookupReadOnly(TransactionCase):
    """``_smart_op_domain`` must resolve labels without writing records."""

    HOST_MODEL = "test.smartop.host"
    COMODEL = "test.smartop.label"

    def setUp(self):
        super().setUp()
        # Bound method off the real model; called with a fake ``self`` so the
        # method only ever touches the stubbed ``env``.
        self._method = type(self.env["spp.cel.translator"])._smart_op_domain

    def _resolve(self, value, records):
        host_fields = {"label_id": _FakeField("many2one", self.COMODEL)}
        comodel_fields = {"value": object(), "code": object(), "name": object()}
        env = _FakeEnv(
            {
                self.HOST_MODEL: _FakeRecordset(host_fields),
                self.COMODEL: _FakeRecordset(comodel_fields, records),
            }
        )
        translator = _FakeTranslator(env)
        return self._method(translator, "label_id", "=", value, self.HOST_MODEL)

    def test_missing_gender_label_does_not_create_records(self):
        """Resolving 'male' when the code is absent must not create records."""
        domain = self._resolve("male", records=[])
        self.assertEqual(
            domain,
            [("id", "=", 0)],
            "A missing gender label must resolve to a match-nothing domain.",
        )

    def test_present_gender_label_resolves_to_record(self):
        """Resolving 'male' when the code exists must target that record."""
        domain = self._resolve("male", records=[{"id": 42, "value": "Male", "code": "M"}])
        self.assertEqual(domain, [("label_id", "=", 42)])
