# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Covers the smaller methods on the registrant model.

Audit items addressed:

- ``enable_registrant`` — inverse of ``disable_registrant`` (which is
  driven by the wizard, covered in ``test_wizard_disable_registrant.py``).
- ``_onchange_negative_restrict`` — onchange that returns a warning and
  resets ``income`` to 0 when a negative value is entered.
- ``_check_company_domain`` — override that adds the default company to
  the allowed-companies domain. The justification (and reproduction
  steps) live in the docstring on the impl: it fixes an
  "Incompatible companies on records" error that occurs when ``stock``
  and ``spp_registry_base`` are both installed.
- ``_compute_reg_ids_count`` — tab-badge count of ``spp.registry.id``
  records linked to the partner.
- ``_compute_relationships_count`` — tab-badge count of
  ``spp.registry.relationship`` records (source + destination).
"""

from odoo import fields
from odoo.tests import Form, tagged

from .common import RegistryCommon


@tagged("post_install", "-at_install")
class TestEnableRegistrant(RegistryCommon):
    """``enable_registrant`` — clears disabled flag and audit fields."""

    def setUp(self):
        super().setUp()
        # Stamp the registrant as disabled, mimicking what the wizard does.
        self.individual_a.write(
            {
                "disabled": fields.Datetime.now(),
                "disabled_reason": "test",
                "disabled_by": self.env.user.id,
            }
        )

    def test_enable_clears_disabled(self):
        self.individual_a.enable_registrant()
        self.assertFalse(self.individual_a.disabled)
        self.assertFalse(self.individual_a.disabled_by)
        self.assertFalse(self.individual_a.disabled_reason)

    def test_enable_on_active_is_noop(self):
        """The ``if rec.disabled`` guard means an already-active registrant
        is left untouched."""
        # individual_b was never disabled in setUp.
        self.individual_b.enable_registrant()
        self.assertFalse(self.individual_b.disabled)
        self.assertFalse(self.individual_b.disabled_by)
        self.assertFalse(self.individual_b.disabled_reason)

    def test_enable_iterates_over_recordset(self):
        """Multi-record enable should re-activate every disabled record."""
        self.individual_b.write(
            {
                "disabled": fields.Datetime.now(),
                "disabled_reason": "also test",
                "disabled_by": self.env.user.id,
            }
        )
        (self.individual_a | self.individual_b).enable_registrant()
        self.assertFalse(self.individual_a.disabled)
        self.assertFalse(self.individual_b.disabled)


@tagged("post_install", "-at_install")
class TestOnchangeNegativeIncomeRestrict(RegistryCommon):
    """``_onchange_negative_restrict`` — warn and reset on negative income.

    The impl returns a dict with a ``warning`` key (rendered by the web
    client) AND sets ``value: {"income": 0}``. ``Form`` applies the
    ``value`` payload back onto the form, so we can assert the side
    effect via form state.
    """

    def test_negative_income_resets_to_zero(self):
        form = Form(self.individual_a)
        form.income = -100.0
        self.assertEqual(form.income, 0.0)

    def test_zero_income_is_unchanged(self):
        form = Form(self.individual_a)
        form.income = 0.0
        self.assertEqual(form.income, 0.0)

    def test_positive_income_passes_through(self):
        form = Form(self.individual_a)
        form.income = 1500.50
        self.assertEqual(form.income, 1500.50)


@tagged("post_install", "-at_install")
class TestCheckCompanyDomain(RegistryCommon):
    """``_check_company_domain`` — override to allow the default company.

    This is hard to test directly because the override only changes the
    domain returned by ``_check_company_domain``, which is consumed by
    Odoo's framework code. The observable symptom (the reason the
    override exists) is from the docstring:

        Install stock + spp_registry_base, create a new company, the
        framework would otherwise raise "Incompatible companies on
        records".

    We pin the contract by calling the method directly and asserting
    the returned domain includes the default-company clause.
    """

    def test_domain_includes_default_company(self):
        """The override OR-extends the inherited domain with
        ``("company_id", "=", env.company.id)``."""
        domain = self.individual_a._check_company_domain(self.env.company)
        # The returned object is a Domain; render to string-ish list.
        rendered = str(domain)
        self.assertIn(
            f"'company_id', '=', {self.env.company.id}",
            rendered,
            "default-company clause missing from extended domain",
        )

    def test_creating_partner_in_new_company_succeeds(self):
        """End-to-end behavioural test of the regression the override
        fixes. Creating a partner under a second company should not raise.

        TODO: this needs a fresh ``res.company`` plus a user assigned to
        it. Worth wiring up once ``test_check_company_domain`` becomes
        the canonical regression test for the docstring's repro.
        """
        self.skipTest("not yet implemented — see TODO")


@tagged("post_install", "-at_install")
class TestComputeRegIdsCount(RegistryCommon):
    """``_compute_reg_ids_count`` — tab badge."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.RegId = cls.env["spp.registry.id"]
        cls.id_type_national = cls.env.ref("spp_vocabulary.code_id_type_national_id")
        cls.id_type_passport = cls.env.ref("spp_vocabulary.code_id_type_passport")

    def test_count_zero_when_no_ids(self):
        self.assertEqual(self.individual_a.reg_ids_count, 0)

    def test_count_one(self):
        self.RegId.create(
            {
                "partner_id": self.individual_a.id,
                "id_type_id": self.id_type_national.id,
                "value": "ABC-123",
            }
        )
        self.individual_a.invalidate_recordset(["reg_ids_count"])
        self.assertEqual(self.individual_a.reg_ids_count, 1)

    def test_count_multiple(self):
        self.RegId.create(
            {
                "partner_id": self.individual_a.id,
                "id_type_id": self.id_type_national.id,
                "value": "ABC-123",
            }
        )
        self.RegId.create(
            {
                "partner_id": self.individual_a.id,
                "id_type_id": self.id_type_passport.id,
                "value": "P1234567",
            }
        )
        self.individual_a.invalidate_recordset(["reg_ids_count"])
        self.assertEqual(self.individual_a.reg_ids_count, 2)

    def test_count_is_per_partner(self):
        """Adding an ID to alice must not affect bob's count."""
        self.RegId.create(
            {
                "partner_id": self.individual_a.id,
                "id_type_id": self.id_type_national.id,
                "value": "ABC-123",
            }
        )
        self.individual_a.invalidate_recordset(["reg_ids_count"])
        self.individual_b.invalidate_recordset(["reg_ids_count"])
        self.assertEqual(self.individual_a.reg_ids_count, 1)
        self.assertEqual(self.individual_b.reg_ids_count, 0)

    def test_count_empty_recordset_does_not_raise(self):
        """``if not self.ids`` early return — must not crash."""
        empty = self.Partner.browse()
        # Triggering the compute on an empty recordset is a no-op.
        empty._compute_reg_ids_count()


@tagged("post_install", "-at_install")
class TestComputeRelationshipsCount(RegistryCommon):
    """``_compute_relationships_count`` — sums source + destination."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Relationship = cls.env["spp.registry.relationship"]
        cls.rel_sibling = cls.env.ref("spp_vocabulary.code_rel_sibling")

    def test_count_zero_when_no_relationships(self):
        self.assertEqual(self.individual_a.relationships_count, 0)

    def test_count_includes_source_side(self):
        self.Relationship.create(
            {
                "source": self.individual_a.id,
                "destination": self.individual_b.id,
                "relation_id": self.rel_sibling.id,
            }
        )
        self.individual_a.invalidate_recordset(["relationships_count"])
        self.assertEqual(self.individual_a.relationships_count, 1)

    def test_count_includes_destination_side(self):
        """A relationship pointing AT a partner counts too."""
        self.Relationship.create(
            {
                "source": self.individual_b.id,
                "destination": self.individual_a.id,
                "relation_id": self.rel_sibling.id,
            }
        )
        self.individual_a.invalidate_recordset(["relationships_count"])
        self.assertEqual(self.individual_a.relationships_count, 1)

    def test_count_sums_both_sides(self):
        """alice as source in one, destination in another → count is 2."""
        # alice as source.
        self.Relationship.create(
            {
                "source": self.individual_a.id,
                "destination": self.individual_b.id,
                "relation_id": self.rel_sibling.id,
            }
        )
        # alice as destination. Use a third individual to keep the
        # source ≠ destination constraint happy.
        carol = self.Partner.create({"name": "Carol", "is_registrant": True, "is_group": False})
        self.Relationship.create(
            {
                "source": carol.id,
                "destination": self.individual_a.id,
                "relation_id": self.rel_sibling.id,
            }
        )
        self.individual_a.invalidate_recordset(["relationships_count"])
        self.assertEqual(self.individual_a.relationships_count, 2)

    def test_count_empty_recordset_does_not_raise(self):
        """Same early-return contract as ``_compute_reg_ids_count``."""
        empty = self.Partner.browse()
        empty._compute_relationships_count()
