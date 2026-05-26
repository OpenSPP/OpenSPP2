# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Data-integrity constraints on registry models.

Covers:
- res.partner (group) ``_validate_unique_membership_types`` — only one
  ``head`` membership per group, exercised on both ``create`` and ``write``.
- res.partner (registrant) ``_check_registration_date`` — registration
  date cannot be in the future, and cannot precede the birthdate.
- spp.id.type ``_check_namespace_uri_format`` (ADR-007) plus the
  lowercase-normalisation behaviour of ``create`` / ``write``.
"""

from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import RegistryCommon


@tagged("post_install", "-at_install")
class TestUniqueMembershipTypes(RegistryCommon):
    """spp_registry/models/group.py::_validate_unique_membership_types"""

    def test_single_head_membership_allowed(self):
        """A group with exactly one head member writes without error."""
        self.Membership.create(
            {
                "group": self.group.id,
                "individual": self.individual_a.id,
                "membership_type_ids": [(6, 0, [self.head_code.id])],
            }
        )
        # write() override runs validation again — should be a no-op.
        self.group.write({"name": "Renamed Household"})

    def test_two_heads_rejected_on_create(self):
        """Creating a group with two heads in one transaction is rejected."""
        with self.assertRaises(ValidationError):
            self.Partner.create(
                {
                    "name": "Twin-headed Household",
                    "is_registrant": True,
                    "is_group": True,
                    "group_membership_ids": [
                        (
                            0,
                            0,
                            {
                                "individual": self.individual_a.id,
                                "membership_type_ids": [(6, 0, [self.head_code.id])],
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "individual": self.individual_b.id,
                                "membership_type_ids": [(6, 0, [self.head_code.id])],
                            },
                        ),
                    ],
                }
            )

    def test_two_heads_rejected_on_group_write(self):
        """The group-side validator only fires from ``group.write/create``,
        not from membership-side writes. Trip it by editing the group's
        ``group_membership_ids`` o2m through ``res.partner.write``.

        The form-side membership onchange catches the membership-write
        path separately — covered in ``test_membership_constraints.py``.
        """
        self.Membership.create(
            {
                "group": self.group.id,
                "individual": self.individual_a.id,
                "membership_type_ids": [(6, 0, [self.head_code.id])],
            }
        )
        second = self.Membership.create(
            {
                "group": self.group.id,
                "individual": self.individual_b.id,
            }
        )
        with self.assertRaises(ValidationError):
            # Rewriting the membership through the group's o2m triggers
            # group.write() and re-runs ``_validate_unique_membership_types``.
            self.group.write(
                {
                    "group_membership_ids": [
                        (1, second.id, {"membership_type_ids": [(6, 0, [self.head_code.id])]}),
                    ],
                }
            )

    def test_no_head_code_in_vocabulary_short_circuits(self):
        """When the 'head' code is missing the validator must be a no-op.

        Some deployments customise the vocabulary; the validator's first
        branch (``if not head_code: return``) guards against false positives.
        """
        # TODO: simulate a missing head code by archiving / replacing the
        # vocabulary code in a savepoint, then assert ``create`` succeeds
        # even with multiple memberships that *would* have been heads.
        self.skipTest("not yet implemented — see TODO")


@tagged("post_install", "-at_install")
class TestRegistrationDateConstraint(RegistryCommon):
    """spp_registry/models/registrant.py::_check_registration_date"""

    def test_future_registration_date_rejected(self):
        """Registration date in the future raises ValidationError."""
        future = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.individual_a.write({"registration_date": future})

    def test_today_is_allowed(self):
        """Registration date == today is the boundary that must pass."""
        self.individual_a.write({"registration_date": date.today()})
        self.assertEqual(self.individual_a.registration_date, date.today())

    def test_registration_before_birthdate_rejected(self):
        """Registration date < birthdate raises ValidationError.

        Requires the ``birthdate`` field added by individual.py; if running
        with a pruned dependency tree the constraint's defensive
        ``"birthdate" in record`` short-circuits, which is itself part of
        the contract.
        """
        if "birthdate" not in self.individual_a:
            self.skipTest("birthdate field not present in this build")
        self.individual_a.write({"birthdate": date(1990, 1, 1)})
        with self.assertRaises(ValidationError):
            self.individual_a.write({"registration_date": date(1989, 12, 31)})

    def test_registration_equal_to_birthdate_allowed(self):
        """Same-day birth + registration is the boundary that must pass."""
        if "birthdate" not in self.individual_a:
            self.skipTest("birthdate field not present in this build")
        self.individual_a.write(
            {
                "birthdate": date(1990, 1, 1),
                "registration_date": date(1990, 1, 1),
            }
        )


@tagged("post_install", "-at_install")
class TestIDTypeNamespaceURI(RegistryCommon):
    """spp_registry/models/reg_id.py::SPPIDType — ADR-007 URI handling."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.IDType = cls.env["spp.id.type"]

    def test_valid_uri_accepted(self):
        rec = self.IDType.create(
            {"name": "PSA National ID", "namespace_uri": "urn:gov:ph:psa:national-id"}
        )
        self.assertEqual(rec.namespace_uri, "urn:gov:ph:psa:national-id")

    def test_create_lowercases_namespace(self):
        """create() override should normalise to lowercase + trim whitespace."""
        rec = self.IDType.create(
            {"name": "Mixed Case Type", "namespace_uri": "  URN:GOV:PH:Mixed  "}
        )
        self.assertEqual(rec.namespace_uri, "urn:gov:ph:mixed")

    def test_write_lowercases_namespace(self):
        """write() override should normalise to lowercase + trim whitespace."""
        rec = self.IDType.create(
            {"name": "Writable Type", "namespace_uri": "urn:gov:ph:initial"}
        )
        rec.write({"namespace_uri": "  URN:GOV:PH:UPDATED  "})
        self.assertEqual(rec.namespace_uri, "urn:gov:ph:updated")

    def test_invalid_scheme_rejected(self):
        """Non-``urn:`` URIs violate the ADR-007 pattern."""
        with self.assertRaises(ValidationError):
            self.IDType.create(
                {"name": "Bad Scheme", "namespace_uri": "http://example.org/id"}
            )

    def test_missing_type_component_rejected(self):
        """``urn:<namespace>`` without the trailing ``:<type>`` is rejected."""
        with self.assertRaises(ValidationError):
            self.IDType.create({"name": "Truncated", "namespace_uri": "urn:gov"})

    def test_disallowed_characters_rejected(self):
        """The pattern only permits [a-z0-9._-] in each segment."""
        with self.assertRaises(ValidationError):
            self.IDType.create(
                {"name": "Spaces", "namespace_uri": "urn:gov:ph:national id"}
            )

    def test_empty_namespace_is_allowed(self):
        """Empty / falsy namespace_uri short-circuits validation (see code)."""
        rec = self.IDType.create({"name": "No Namespace", "namespace_uri": False})
        self.assertFalse(rec.namespace_uri)

    def test_duplicate_namespace_uri_rejected(self):
        """The ``_unique_namespace_uri`` SQL constraint must fire."""
        self.IDType.create(
            {"name": "First", "namespace_uri": "urn:gov:ph:psa:national-id"}
        )
        # TODO: assert IntegrityError via with self.assertRaises + flush().
        # SQL constraints raise on flush, not on the ORM call, so the
        # idiomatic Odoo pattern is ``with mute_logger(...): self.env.flush_all()``.
        self.skipTest("not yet implemented — see TODO")

    def test_duplicate_name_rejected(self):
        """spp.id.type._check_name forbids duplicate names (case-sensitive)."""
        self.IDType.create({"name": "National ID"})
        with self.assertRaises(ValidationError):
            self.IDType.create({"name": "National ID"})

    def test_empty_name_rejected(self):
        with self.assertRaises(ValidationError):
            self.IDType.create({"name": False})
