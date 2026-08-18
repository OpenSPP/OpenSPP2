# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for program creation wizard with geofence eligibility."""

import json
import uuid

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCreateProgramWizardGeofence(TransactionCase):
    """Verify the wizard creates a geofence eligibility manager when geofences are set."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
                tracking_disable=True,
            )
        )

        cls.geofence = cls.env["spp.gis.geofence"].create(
            {
                "name": "Wizard Test Geofence",
                "geometry": json.dumps(
                    {
                        "type": "Polygon",
                        "coordinates": [[[100, 0], [101, 0], [101, 1], [100, 1], [100, 0]]],
                    }
                ),
                "geofence_type": "custom",
            }
        )

        # Create a test product for entitlement items (required by wizard)
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product [TEST]",
                "type": "consu",
            }
        )

    def _create_wizard(self, geofence_ids=None, **kwargs):
        """Helper to create a wizard with sensible defaults."""
        vals = {
            "name": f"Program {uuid.uuid4().hex[:8]} [TEST]",
            "rrule_type": "monthly",
            "eligibility_domain": "[]",
            "cycle_duration": 1,
            "currency_id": self.env.company.currency_id.id,
            "entitlement_type": "cash",
            "entitlement_cash_item_ids": [Command.create({"amount": 100.0})],
        }
        if geofence_ids is not None:
            vals["geofence_ids"] = [Command.set(geofence_ids)]
        vals.update(kwargs)
        return self.env["spp.program.create.wizard"].create(vals)

    def test_wizard_with_geofence_creates_geofence_manager(self):
        """When geofences are configured, the wizard should create a geofence eligibility manager."""
        wiz = self._create_wizard(geofence_ids=self.geofence.ids)
        action = wiz.create_program()

        program = self.env["spp.program"].browse(action["params"]["program_id"])
        self.assertTrue(program.geofence_ids, "Program should have geofences linked")

        # The eligibility manager should be a geofence manager, not default
        managers = program.get_managers(program.MANAGER_ELIGIBILITY)
        self.assertEqual(len(managers), 1, "Should have exactly one eligibility manager")
        self.assertEqual(
            managers[0]._name,
            "spp.program.membership.manager.geofence",
            "Eligibility manager should be geofence type, not default",
        )

    def test_wizard_without_geofence_creates_default_manager(self):
        """When no geofences are configured, the wizard should create the default eligibility manager."""
        wiz = self._create_wizard()
        action = wiz.create_program()

        program = self.env["spp.program"].browse(action["params"]["program_id"])
        managers = program.get_managers(program.MANAGER_ELIGIBILITY)
        self.assertEqual(len(managers), 1)
        self.assertEqual(
            managers[0]._name,
            "spp.program.membership.manager.default",
            "Eligibility manager should be default type when no geofences",
        )

    def test_wizard_geofence_manager_has_correct_program(self):
        """The geofence manager should reference the correct program."""
        wiz = self._create_wizard(geofence_ids=self.geofence.ids)
        action = wiz.create_program()

        program = self.env["spp.program"].browse(action["params"]["program_id"])
        manager = program.get_managers(program.MANAGER_ELIGIBILITY)[0]
        self.assertEqual(manager.program_id, program)

    def test_wizard_geofence_manager_defaults(self):
        """The geofence manager should have sensible defaults."""
        wiz = self._create_wizard(geofence_ids=self.geofence.ids)
        action = wiz.create_program()

        program = self.env["spp.program"].browse(action["params"]["program_id"])
        manager = program.get_managers(program.MANAGER_ELIGIBILITY)[0]
        self.assertTrue(
            manager.include_area_fallback,
            "Area fallback should be enabled by default",
        )

    def test_wizard_passes_area_fallback_disabled(self):
        """When area fallback is disabled in the wizard, the manager should reflect that."""
        wiz = self._create_wizard(
            geofence_ids=self.geofence.ids,
            include_area_fallback=False,
        )
        action = wiz.create_program()

        program = self.env["spp.program"].browse(action["params"]["program_id"])
        manager = program.get_managers(program.MANAGER_ELIGIBILITY)[0]
        self.assertFalse(
            manager.include_area_fallback,
            "Area fallback should be disabled when wizard sets it to False",
        )

    def test_wizard_passes_fallback_area_type(self):
        """When a fallback area type is selected, the manager should have it."""
        area_type = self.env["spp.area.type"].create({"name": "Test Municipality"})
        wiz = self._create_wizard(
            geofence_ids=self.geofence.ids,
            include_area_fallback=True,
            fallback_area_type_id=area_type.id,
        )
        action = wiz.create_program()

        program = self.env["spp.program"].browse(action["params"]["program_id"])
        manager = program.get_managers(program.MANAGER_ELIGIBILITY)[0]
        self.assertEqual(
            manager.fallback_area_type_id,
            area_type,
            "Fallback area type should be passed through from wizard",
        )
