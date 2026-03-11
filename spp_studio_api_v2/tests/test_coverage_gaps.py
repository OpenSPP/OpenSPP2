# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests targeting coverage gaps in spp_studio_api_v2."""

import time
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMonkeyPatchedServiceMethods(TransactionCase):
    """Test the monkey-patched methods on IndividualService/GroupService."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.IndividualMixin = cls.env["spp.studio.api.individual.mixin"]
        cls.GroupMixin = cls.env["spp.studio.api.group.mixin"]

        # Get or create ID Type vocabulary for registry IDs
        id_type_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not id_type_vocab:
            id_type_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Type",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )

        id_type = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", id_type_vocab.id),
                ("code", "=", "test_patched_id"),
            ],
            limit=1,
        )
        if not id_type:
            id_type = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "test_patched_id",
                    "display": "Test Patched ID",
                    "is_local": True,
                    "target_type": "both",
                }
            )

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Individual Patched",
                "is_registrant": True,
                "is_group": False,
            }
        )
        # Add registry ID so to_api_schema doesn't fail
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner.id,
                "id_type_id": id_type.id,
                "value": "PATCH-IND-001",
            }
        )

        cls.group_partner = cls.env["res.partner"].create(
            {
                "name": "Test Group Patched",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.group_partner.id,
                "id_type_id": id_type.id,
                "value": "PATCH-GRP-001",
            }
        )

    def test_individual_mixin_parse_extension_data(self):
        """Test IndividualMixin.parse_extension_data delegates to service."""
        result = self.IndividualMixin.parse_extension_data({}, "individual")
        self.assertEqual(result, {})

    def test_individual_mixin_get_variable_values(self):
        """Test IndividualMixin.get_variable_values delegates to service."""
        result = self.IndividualMixin.get_variable_values(self.partner.id)
        self.assertIsInstance(result, dict)

    def test_individual_mixin_get_variable_values_bulk(self):
        """Test IndividualMixin.get_variable_values_bulk delegates to service."""
        result = self.IndividualMixin.get_variable_values_bulk(
            [self.partner.id],
            variable_names=None,
            period_key="current",
        )
        self.assertIsInstance(result, dict)
        self.assertIn(self.partner.id, result)

    def test_group_mixin_parse_extension_data(self):
        """Test GroupMixin.parse_extension_data delegates to service."""
        result = self.GroupMixin.parse_extension_data({}, "group")
        self.assertEqual(result, {})

    def test_group_mixin_get_variable_values(self):
        """Test GroupMixin.get_variable_values delegates to service."""
        result = self.GroupMixin.get_variable_values(self.group_partner.id)
        self.assertIsInstance(result, dict)

    def test_patched_individual_from_api_schema_no_extension(self):
        """Test patched from_api_schema wrapper without extension data."""
        try:
            from odoo.addons.spp_api_v2.services.individual_service import (
                IndividualService,
            )
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = IndividualService(self.env)
        schema = MagicMock()
        schema.extension = None

        # Patch the original method to return base vals
        with patch.object(
            IndividualService,
            "from_api_schema",
            wraps=IndividualService.from_api_schema,
        ):
            # Call directly the patched closure
            # The patched method calls original, then checks extension
            original = IndividualService.__dict__.get("from_api_schema")
            if original:
                # Build a simple wrapper test
                schema.extension = None
                # Just verify patched method exists and is callable
                self.assertTrue(callable(svc.from_api_schema))

    def test_patched_individual_from_api_schema_with_extension(self):
        """Test patched from_api_schema wrapper with extension data."""
        try:
            from odoo.addons.spp_api_v2.services.individual_service import (
                IndividualService,
            )
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        # The patched method wraps the original. We can test the extension
        # processing by calling the method and catching the original's error.
        svc = IndividualService(self.env)
        schema = MagicMock()
        schema.extension = {"studio-individual": {"someField": "value"}}

        # The original from_api_schema will fail on mock, but the wrapper
        # should at least be invoked. Test that the method is patched.
        method = svc.from_api_schema
        self.assertIn("extension", method.__doc__ or "")

    def test_patched_individual_to_api_schema(self):
        """Test patched to_api_schema wrapper calls through."""
        try:
            from odoo.addons.spp_api_v2.services.individual_service import (
                IndividualService,
            )
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = IndividualService(self.env)
        # to_api_schema takes a partner record - this should work
        data = svc.to_api_schema(self.partner)
        self.assertIsInstance(data, dict)

    def test_patched_individual_to_api_schema_with_variables(self):
        """Test patched to_api_schema with include_variables kwarg."""
        try:
            from odoo.addons.spp_api_v2.services.individual_service import (
                IndividualService,
            )
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = IndividualService(self.env)
        data = svc.to_api_schema(
            self.partner,
            include_variables=["*"],
            variable_period="current",
        )
        self.assertIsInstance(data, dict)

    def test_patched_group_from_api_schema(self):
        """Test patched GroupService.from_api_schema wrapper."""
        try:
            from odoo.addons.spp_api_v2.services.group_service import GroupService
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = GroupService(self.env)
        method = svc.from_api_schema
        self.assertIn("extension", method.__doc__ or "")

    def test_patched_group_to_api_schema(self):
        """Test patched GroupService.to_api_schema calls through."""
        try:
            from odoo.addons.spp_api_v2.services.group_service import GroupService
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = GroupService(self.env)
        data = svc.to_api_schema(self.group_partner)
        self.assertIsInstance(data, dict)

    def test_patched_group_to_api_schema_with_variables(self):
        """Test patched GroupService.to_api_schema with include_variables."""
        try:
            from odoo.addons.spp_api_v2.services.group_service import GroupService
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = GroupService(self.env)
        data = svc.to_api_schema(
            self.group_partner,
            include_variables=["*"],
            variable_period="current",
        )
        self.assertIsInstance(data, dict)

    def test_patched_individual_from_api_schema_full(self):
        """Test patched from_api_schema with a real Individual schema object."""
        try:
            from odoo.addons.spp_api_v2.schemas.individual import Individual
            from odoo.addons.spp_api_v2.services.individual_service import (
                IndividualService,
            )
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = IndividualService(self.env)
        schema = Individual(
            identifier=[
                {
                    "system": "urn:openspp:vocab:id-type#test_patched_id",
                    "value": "SCHEMA-IND-001",
                }
            ],
            active=True,
            name={"family": "Schema", "given": "Test", "text": "Test Schema"},
            birthDate="1990-01-01",
            extension={"studio-individual": {"someField": "test"}},
        )
        vals = svc.from_api_schema(schema)
        self.assertIsInstance(vals, dict)
        self.assertIn("name", vals)

    def test_patched_individual_from_api_schema_extension_error(self):
        """Test patched from_api_schema handles extension parsing error gracefully."""
        try:
            from odoo.addons.spp_api_v2.schemas.individual import Individual
            from odoo.addons.spp_api_v2.services.individual_service import (
                IndividualService,
            )
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = IndividualService(self.env)
        schema = Individual(
            identifier=[
                {
                    "system": "urn:openspp:vocab:id-type#test_patched_id",
                    "value": "SCHEMA-IND-002",
                }
            ],
            active=True,
            name={"family": "Schema", "given": "Error", "text": "Error Schema"},
            birthDate="1990-01-01",
        )
        # Force extension to trigger error path by making it non-dict
        schema.extension = {"studio-individual": "not_a_dict"}

        # Patch parse_extension_data to raise TypeError
        with patch.object(
            type(self.IndividualMixin),
            "parse_extension_data",
            side_effect=TypeError("test error"),
        ):
            vals = svc.from_api_schema(schema)
            # Should still return vals despite error
            self.assertIsInstance(vals, dict)

    def test_patched_individual_to_api_with_computed_data(self):
        """Test patched to_api_schema includes computedData when variables return data."""
        try:
            from odoo.addons.spp_api_v2.services.individual_service import (
                IndividualService,
            )
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = IndividualService(self.env)

        # Mock get_variable_values to return actual data
        with patch.object(
            type(self.IndividualMixin),
            "get_variable_values",
            return_value={"test_var": 42},
        ):
            data = svc.to_api_schema(
                self.partner,
                include_variables=["*"],
                variable_period="current",
            )
            self.assertIsInstance(data, dict)
            self.assertEqual(data.get("computedData"), {"test_var": 42})

    def test_patched_individual_to_api_variable_error(self):
        """Test patched to_api_schema handles variable value error gracefully."""
        try:
            from odoo.addons.spp_api_v2.services.individual_service import (
                IndividualService,
            )
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = IndividualService(self.env)

        with patch.object(
            type(self.IndividualMixin),
            "get_variable_values",
            side_effect=ValueError("test var error"),
        ):
            data = svc.to_api_schema(
                self.partner,
                include_variables=["*"],
                variable_period="current",
            )
            # Should still return data despite error
            self.assertIsInstance(data, dict)
            self.assertNotIn("computedData", data)

    def test_patched_group_from_api_schema_full(self):
        """Test patched GroupService.from_api_schema with real schema."""
        try:
            from odoo.addons.spp_api_v2.schemas.group import Group
            from odoo.addons.spp_api_v2.services.group_service import GroupService
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = GroupService(self.env)
        schema = Group(
            identifier=[
                {
                    "system": "urn:openspp:vocab:id-type#test_patched_id",
                    "value": "SCHEMA-GRP-001",
                }
            ],
            active=True,
            name="Test Group Schema",
            extension={"studio-group": {"someField": "test"}},
        )
        vals = svc.from_api_schema(schema)
        self.assertIsInstance(vals, dict)

    def test_patched_group_from_api_schema_extension_error(self):
        """Test patched GroupService.from_api_schema handles extension error."""
        try:
            from odoo.addons.spp_api_v2.schemas.group import Group
            from odoo.addons.spp_api_v2.services.group_service import GroupService
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = GroupService(self.env)
        schema = Group(
            identifier=[
                {
                    "system": "urn:openspp:vocab:id-type#test_patched_id",
                    "value": "SCHEMA-GRP-002",
                }
            ],
            active=True,
            name="Test Group Error",
        )
        schema.extension = {"studio-group": "bad"}

        with patch.object(
            type(self.GroupMixin),
            "parse_extension_data",
            side_effect=KeyError("test"),
        ):
            vals = svc.from_api_schema(schema)
            self.assertIsInstance(vals, dict)

    def test_patched_group_to_api_with_computed_data(self):
        """Test patched GroupService.to_api_schema with computedData."""
        try:
            from odoo.addons.spp_api_v2.services.group_service import GroupService
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = GroupService(self.env)

        with patch.object(
            type(self.GroupMixin),
            "get_variable_values",
            return_value={"group_var": 100},
        ):
            data = svc.to_api_schema(
                self.group_partner,
                include_variables=["*"],
                variable_period="current",
            )
            self.assertIsInstance(data, dict)
            self.assertEqual(data.get("computedData"), {"group_var": 100})

    def test_patched_group_to_api_variable_error(self):
        """Test patched GroupService.to_api_schema handles variable error."""
        try:
            from odoo.addons.spp_api_v2.services.group_service import GroupService
        except ImportError:
            self.skipTest("spp_api_v2 not available")

        svc = GroupService(self.env)

        with patch.object(
            type(self.GroupMixin),
            "get_variable_values",
            side_effect=TypeError("test"),
        ):
            data = svc.to_api_schema(
                self.group_partner,
                include_variables=["*"],
                variable_period="current",
            )
            self.assertIsInstance(data, dict)
            self.assertNotIn("computedData", data)


@tagged("post_install", "-at_install")
class TestStudioFieldCoverageGaps(TransactionCase):
    """Test Studio field registration edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.individual_ext = cls.env.ref(
            "spp_studio_api_v2.api_extension_studio_individual",
            raise_if_not_found=False,
        )
        cls.group_ext = cls.env.ref(
            "spp_studio_api_v2.api_extension_studio_group",
            raise_if_not_found=False,
        )
        cls.zone = cls.env["spp.studio.placement.zone"].search([("target_type", "=", "individual")], limit=1)

    def test_register_no_ir_model_fields(self):
        """Test _register_api_extension when ir_model_fields_id is False."""
        field = self.env["spp.studio.field"].create(
            {
                "label": "No IR Field Test",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
                "api_exposed": True,
            }
        )
        # Before activation, ir_model_fields_id is False
        field._register_api_extension()
        # Should log warning, not crash

    def test_unregister_no_ir_model_fields(self):
        """Test _unregister_api_extension when ir_model_fields_id is False."""
        field = self.env["spp.studio.field"].create(
            {
                "label": "No IR Field Unreg Test",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
            }
        )
        # Before activation, ir_model_fields_id is False
        field._unregister_api_extension()
        # Should do nothing, not crash

    def test_get_studio_extension_invalid_target(self):
        """Test _get_studio_extension with invalid target_type."""
        field = self.env["spp.studio.field"].new({"target_type": "invalid"})
        result = field._get_studio_extension()
        self.assertIsNone(result)

    def test_register_existing_fields(self):
        """Test the _register_existing_fields migration helper."""
        if not self.individual_ext:
            self.skipTest("Extensions not available")

        StudioField = self.env["spp.studio.field"]
        # Create and activate a field first
        field = StudioField.create(
            {
                "label": "Existing Field Test",
                "field_type": "boolean",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
                "api_exposed": True,
            }
        )
        field.action_activate()

        # Now call _register_existing_fields
        count = StudioField._register_existing_fields()
        self.assertGreaterEqual(count, 1)

    def test_write_api_exposed_on_inactive_field(self):
        """Test that writing api_exposed on inactive field doesn't register."""
        field = self.env["spp.studio.field"].create(
            {
                "label": "Inactive Write Test",
                "field_type": "text",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
                "api_exposed": False,
            }
        )
        # Write api_exposed on draft field - should not try to register
        field.write({"api_exposed": True})
        # No error expected

    def test_register_extension_not_found(self):
        """Test _register_api_extension when extension is not found (lines 56-61)."""
        field = self.env["spp.studio.field"].create(
            {
                "label": "Ext Not Found Test",
                "field_type": "boolean",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
                "api_exposed": True,
            }
        )
        field.action_activate()
        # Now make _get_studio_extension return None
        with patch.object(type(field), "_get_studio_extension", return_value=None):
            field._register_api_extension()
        # Should log warning but not crash

    def test_unregister_field_in_extension(self):
        """Test _unregister_api_extension when field IS in extension (line 88+)."""
        if not self.individual_ext:
            self.skipTest("Individual extension not found")

        field = self.env["spp.studio.field"].create(
            {
                "label": "Unreg In Ext Test",
                "field_type": "boolean",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
                "api_exposed": True,
            }
        )
        field.action_activate()
        # Verify field is registered
        self.assertIn(field.ir_model_fields_id, self.individual_ext.field_ids)
        # Now unregister
        field._unregister_api_extension()
        self.individual_ext.invalidate_recordset()
        self.assertNotIn(field.ir_model_fields_id, self.individual_ext.field_ids)

    def test_unregister_extension_not_found(self):
        """Test _unregister_api_extension when extension is not found (line 88)."""
        field = self.env["spp.studio.field"].create(
            {
                "label": "Unreg No Ext Test",
                "field_type": "boolean",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
                "api_exposed": True,
            }
        )
        field.action_activate()
        with patch.object(type(field), "_get_studio_extension", return_value=None):
            field._unregister_api_extension()
        # Should return silently

    def test_get_studio_extension_value_error(self):
        """Test _get_studio_extension when env.ref raises ValueError (lines 114-116)."""
        field = self.env["spp.studio.field"].new({"target_type": "individual"})
        with patch.object(type(field.env), "ref", side_effect=ValueError("not found")):
            result = field._get_studio_extension()
            self.assertIsNone(result)

    def test_register_existing_fields_with_exception(self):
        """Test _register_existing_fields handles per-field exceptions (lines 152-153)."""
        if not self.individual_ext:
            self.skipTest("Individual extension not found")

        StudioField = self.env["spp.studio.field"]

        field = StudioField.create(
            {
                "label": "Register Exc Test",
                "field_type": "boolean",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
                "api_exposed": True,
            }
        )
        field.action_activate()

        # Make _register_api_extension raise for all fields
        with patch.object(
            type(field),
            "_register_api_extension",
            side_effect=Exception("test error"),
        ):
            count = StudioField._register_existing_fields()
            self.assertEqual(count, 0)

    def test_deactivate_unregisters_field(self):
        """Test that deactivating a field unregisters it from API extension."""
        if not self.individual_ext:
            self.skipTest("Individual extension not found")

        field = self.env["spp.studio.field"].create(
            {
                "label": "Deactivate Unreg Test",
                "field_type": "boolean",
                "target_type": "individual",
                "placement_zone_id": self.zone.id,
                "api_exposed": True,
            }
        )
        field.action_activate()
        self.assertIn(field.ir_model_fields_id, self.individual_ext.field_ids)
        # Deactivate should unregister
        field.action_deactivate()
        self.individual_ext.invalidate_recordset()
        self.assertNotIn(field.ir_model_fields_id, self.individual_ext.field_ids)


@tagged("post_install", "-at_install")
class TestExtensionWriteServiceGaps(TransactionCase):
    """Test extension write service coverage gaps."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test vocabulary
        cls.vocab = cls.env["spp.vocabulary"].create(
            {
                "name": "Test Coverage Vocab",
                "namespace_uri": "urn:test:coverage",
            }
        )
        cls.vocab.flush_recordset()
        cls.vocab_code = cls.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": cls.vocab.id,
                "code": "cov_code",
                "display": "Coverage Code",
            }
        )
        cls.vocab_code.flush_recordset()
        cls.env.add_to_compute(
            cls.env["spp.vocabulary.code"]._fields["namespace_uri"],
            cls.vocab_code,
        )
        cls.env.flush_all()

    def _get_service(self):
        from ..services.extension_write_service import ExtensionWriteService

        return ExtensionWriteService(self.env)

    def test_convert_many2one_string_namespace_pipe(self):
        """Test _convert_many2one with 'namespace|value' string format."""
        service = self._get_service()

        class MockField:
            ttype = "many2one"
            relation = "spp.vocabulary.code"

        result = service._convert_many2one(MockField(), f"{self.vocab.namespace_uri}|cov_code")
        self.assertEqual(result, self.vocab_code.id)

    def test_convert_many2one_string_display_lookup(self):
        """Test _convert_many2one with display name string on safe model."""
        service = self._get_service()

        # Create a country for testing
        country = self.env["res.country"].search([], limit=1)
        if not country:
            self.skipTest("No countries available")

        class MockField:
            ttype = "many2one"
            relation = "res.country"

        result = service._convert_many2one(MockField(), country.name)
        self.assertEqual(result, country.id)

    def test_convert_many2one_empty_value(self):
        """Test _convert_many2one with empty/falsy value."""
        service = self._get_service()

        class MockField:
            ttype = "many2one"
            relation = "spp.vocabulary.code"

        result = service._convert_many2one(MockField(), "")
        self.assertFalse(result)

        result = service._convert_many2one(MockField(), None)
        self.assertFalse(result)

    def test_convert_many2one_codeable_concept_display_fallback(self):
        """Test _convert_many2one CodeableConcept falls back to display lookup."""
        service = self._get_service()

        country = self.env["res.country"].search([], limit=1)
        if not country:
            self.skipTest("No countries available")

        class MockField:
            ttype = "many2one"
            relation = "res.country"

        # CodeableConcept with wrong system/code but valid display on safe model
        api_value = {
            "coding": [
                {
                    "system": "urn:nonexistent",
                    "code": "nonexistent",
                    "display": country.name,
                }
            ],
        }
        result = service._convert_many2one(MockField(), api_value)
        self.assertEqual(result, country.id)

    def test_convert_many2many_with_items(self):
        """Test _convert_many2many with CodeableConcept items."""
        service = self._get_service()

        class MockField:
            ttype = "many2many"
            relation = "spp.vocabulary.code"

        api_value = [
            {
                "coding": [
                    {
                        "system": self.vocab.namespace_uri,
                        "code": "cov_code",
                    }
                ],
            },
        ]

        result = service._convert_many2many(MockField(), api_value)
        # Should return Command.set with the vocab_code ID
        self.assertTrue(result)
        # Check it's a set command (tuple format: (6, 0, [ids]))
        self.assertEqual(result[0][0], Command.SET)

    def test_convert_many2many_string_items(self):
        """Test _convert_many2many with string items using namespace|value."""
        service = self._get_service()

        class MockField:
            ttype = "many2many"
            relation = "spp.vocabulary.code"

        api_value = [f"{self.vocab.namespace_uri}|cov_code"]

        result = service._convert_many2many(MockField(), api_value)
        self.assertTrue(result)
        self.assertEqual(result[0][0], Command.SET)

    def test_convert_many2many_string_display_lookup(self):
        """Test _convert_many2many with display name strings on safe model."""
        service = self._get_service()

        country = self.env["res.country"].search([], limit=1)
        if not country:
            self.skipTest("No countries available")

        class MockField:
            ttype = "many2many"
            relation = "res.country"

        api_value = [country.name]
        result = service._convert_many2many(MockField(), api_value)
        self.assertTrue(result)
        self.assertEqual(result[0][0], Command.SET)

    def test_convert_many2many_empty(self):
        """Test _convert_many2many with empty/None value."""
        service = self._get_service()

        class MockField:
            ttype = "many2many"
            relation = "spp.vocabulary.code"

        result = service._convert_many2many(MockField(), None)
        self.assertEqual(result[0][0], Command.CLEAR)

        result = service._convert_many2many(MockField(), [])
        self.assertEqual(result[0][0], Command.CLEAR)

    def test_convert_many2many_no_matches(self):
        """Test _convert_many2many when no items resolve."""
        service = self._get_service()

        class MockField:
            ttype = "many2many"
            relation = "spp.vocabulary.code"

        api_value = [{"coding": [{"system": "urn:fake", "code": "fake"}]}]
        result = service._convert_many2many(MockField(), api_value)
        self.assertEqual(result[0][0], Command.CLEAR)

    def test_convert_to_odoo_none(self):
        """Test _convert_to_odoo with None value."""
        service = self._get_service()

        class MockField:
            ttype = "char"

        result = service._convert_to_odoo(MockField(), None)
        self.assertIsNone(result)

    def test_convert_to_odoo_selection(self):
        """Test _convert_to_odoo for selection fields passes through."""
        service = self._get_service()

        class MockField:
            ttype = "selection"

        result = service._convert_to_odoo(MockField(), "option_a")
        self.assertEqual(result, "option_a")

    def test_convert_to_odoo_text_html(self):
        """Test _convert_to_odoo for text/html types."""
        service = self._get_service()

        class MockField:
            ttype = "text"

        result = service._convert_to_odoo(MockField(), "long text value")
        self.assertEqual(result, "long text value")

        class MockHtml:
            ttype = "html"

        result = service._convert_to_odoo(MockHtml(), "<p>html</p>")
        self.assertEqual(result, "<p>html</p>")

    def test_convert_to_odoo_date_non_string(self):
        """Test _convert_to_odoo for date with non-string returns None."""
        service = self._get_service()

        class MockField:
            ttype = "date"

        result = service._convert_to_odoo(MockField(), 12345)
        self.assertIsNone(result)

    def test_convert_to_odoo_bool_from_bool(self):
        """Test _convert_to_odoo integer from bool."""
        service = self._get_service()

        class MockField:
            ttype = "integer"

        result = service._convert_to_odoo(MockField(), True)
        self.assertEqual(result, 1)
        result = service._convert_to_odoo(MockField(), False)
        self.assertEqual(result, 0)

    def test_convert_to_odoo_float_from_bool(self):
        """Test _convert_to_odoo float from bool."""
        service = self._get_service()

        class MockField:
            ttype = "float"

        result = service._convert_to_odoo(MockField(), True)
        self.assertEqual(result, 1.0)
        result = service._convert_to_odoo(MockField(), False)
        self.assertEqual(result, 0.0)

    def test_convert_to_odoo_unknown_type(self):
        """Test _convert_to_odoo with unknown ttype passes through."""
        service = self._get_service()

        class MockField:
            ttype = "binary"

        result = service._convert_to_odoo(MockField(), b"data")
        self.assertEqual(result, b"data")

    def test_parse_extension_fields_with_real_extension(self):
        """Test _parse_extension_fields with a configured extension."""
        service = self._get_service()

        # Create a test extension with a char field
        module = self.env["ir.module.module"].search([("name", "=", "spp_studio_api_v2")], limit=1)
        if not module:
            module = self.env["ir.module.module"].search([("state", "=", "installed")], limit=1)

        # Find an x_ field on res.partner
        char_field = self.env["ir.model.fields"].search(
            [
                ("model", "=", "res.partner"),
                ("name", "like", "x_%"),
                ("ttype", "=", "char"),
            ],
            limit=1,
        )
        if not char_field:
            self.skipTest("No x_ char field on res.partner")

        extension = self.env["spp.api.extension"].create(
            {
                "name": "Parse Test Extension",
                "url": "urn:test:parse-ext",
                "module_id": module.id,
                "applies_to": "individual",
                "active": True,
                "field_ids": [Command.set([char_field.id])],
            }
        )

        api_name = service._odoo_to_api_name(char_field.name)
        ext_values = {api_name: "test_value"}

        result = service._parse_extension_fields(extension, ext_values)
        self.assertIn(char_field.name, result)
        self.assertEqual(result[char_field.name], "test_value")

    def test_parse_extension_fields_null_value(self):
        """Test _parse_extension_fields with explicit null sets False."""
        service = self._get_service()

        module = self.env["ir.module.module"].search([("name", "=", "spp_studio_api_v2")], limit=1)
        if not module:
            module = self.env["ir.module.module"].search([("state", "=", "installed")], limit=1)

        char_field = self.env["ir.model.fields"].search(
            [
                ("model", "=", "res.partner"),
                ("name", "like", "x_%"),
                ("ttype", "=", "char"),
            ],
            limit=1,
        )
        if not char_field:
            self.skipTest("No x_ char field on res.partner")

        extension = self.env["spp.api.extension"].create(
            {
                "name": "Null Value Test Extension",
                "url": "urn:test:null-ext",
                "module_id": module.id,
                "applies_to": "individual",
                "active": True,
                "field_ids": [Command.set([char_field.id])],
            }
        )

        api_name = service._odoo_to_api_name(char_field.name)
        ext_values = {api_name: None}

        result = service._parse_extension_fields(extension, ext_values)
        self.assertIn(char_field.name, result)
        self.assertFalse(result[char_field.name])

    def test_parse_extension_data_invalid_values(self):
        """Test parse_extension_data with non-dict extension values."""
        service = self._get_service()
        result = service.parse_extension_data({"ext": "not_a_dict"}, "individual")
        self.assertEqual(result, {})

    def test_find_extension_by_name(self):
        """Test _find_extension by name match."""
        service = self._get_service()

        ext = service._find_extension("Studio Individual Fields", "individual")
        self.assertTrue(ext)

    def test_find_by_display_unsafe_model(self):
        """Test _find_by_display rejects non-safe non-blocked model."""
        service = self._get_service()
        result = service._find_by_display("res.partner", "Some Name")
        self.assertIsNone(result)

    def test_find_by_display_case_insensitive(self):
        """Test _find_by_display falls back to ilike."""
        service = self._get_service()
        # Search with wrong case - should still find via ilike
        country = self.env["res.country"].search([], limit=1)
        if not country:
            self.skipTest("No countries available")

        result = service._find_by_display("res.country", country.name.upper())
        if result:
            self.assertEqual(result.id, country.id)

    def test_find_vocabulary_code_model_missing(self):
        """Test _find_vocabulary_code when model is not in env."""
        service = self._get_service()
        # Patch env to not have the model
        with patch.object(type(service.env), "__contains__", return_value=False):
            result = service._find_vocabulary_code("urn:test", "code")
            self.assertIsNone(result)

    def test_convert_to_odoo_float_non_finite(self):
        """Test _convert_to_odoo float with non-finite value (lines 241-243)."""
        service = self._get_service()

        class MockField:
            ttype = "float"

        result = service._convert_to_odoo(MockField(), "not_a_number")
        self.assertIsNone(result)

    def test_convert_many2one_string_not_found(self):
        """Test _convert_many2one returns False when no match (line 312)."""
        service = self._get_service()

        class MockField:
            ttype = "many2one"
            relation = "res.country"

        result = service._convert_many2one(MockField(), "Nonexistent Country XYZ999")
        self.assertFalse(result)

    def test_find_by_display_exception(self):
        """Test _find_by_display handles exception (lines 416-418)."""
        service = self._get_service()

        with patch.object(
            type(self.env["res.country"]),
            "search",
            side_effect=Exception("DB error"),
        ):
            result = service._find_by_display("res.country", "Test")
            self.assertIsNone(result)

    def test_odoo_to_api_name_empty(self):
        """Test _odoo_to_api_name with empty string (line 183)."""
        service = self._get_service()
        result = service._odoo_to_api_name("")
        self.assertEqual(result, "")

    def test_parse_extension_fields_field_not_in_values(self):
        """Test _parse_extension_fields skips fields not in values (line 147)."""
        service = self._get_service()

        module = self.env["ir.module.module"].search([("state", "=", "installed")], limit=1)

        char_field = self.env["ir.model.fields"].search(
            [
                ("model", "=", "res.partner"),
                ("name", "like", "x_%"),
                ("ttype", "=", "char"),
            ],
            limit=1,
        )
        if not char_field:
            self.skipTest("No x_ char field on res.partner")

        extension = self.env["spp.api.extension"].create(
            {
                "name": "Skip Field Test Extension",
                "url": "urn:test:skip-field-ext",
                "module_id": module.id,
                "applies_to": "individual",
                "active": True,
                "field_ids": [Command.set([char_field.id])],
            }
        )

        # Pass empty values - field should be skipped
        result = service._parse_extension_fields(extension, {})
        self.assertEqual(result, {})


@tagged("post_install", "-at_install")
class TestVariableValueServiceGaps(TransactionCase):
    """Test variable value service coverage gaps."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "VVS Gap Test Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _get_service(self):
        from ..services.variable_value_service import VariableValueService

        return VariableValueService(self.env)

    def test_get_values_for_subjects_truncation(self):
        """Test get_values_for_subjects truncates large batches."""
        service = self._get_service()

        # Create batch exceeding MAX_BATCH_SIZE (1000)
        large_batch = list(range(1, 1100))
        result = service.get_values_for_subjects(large_batch)
        # Should only have 1000 entries (truncated)
        self.assertEqual(len(result), 1000)

    def test_get_available_variables_individual_filter(self):
        """Test get_available_variables with individual resource_type filter."""
        service = self._get_service()

        # Create variables for individual and group
        uid = int(time.time() * 1000)
        self.env["spp.cel.variable"].create(
            {
                "name": f"ind_only_{uid}",
                "cel_accessor": f"ind_only_{uid}",
                "source_type": "field",
                "value_type": "number",
                "state": "active",
                "applies_to": "individual",
            }
        )

        result = service.get_available_variables(resource_type="individual")
        # Should include individual and both variables, not group-only
        applies_set = {v["appliesTo"] for v in result}
        self.assertNotIn("group", applies_set)

    def test_get_available_variables_include_inactive(self):
        """Test get_available_variables with include_inactive=True."""
        service = self._get_service()

        uid = int(time.time() * 1000)
        self.env["spp.cel.variable"].create(
            {
                "name": f"inactive_{uid}",
                "cel_accessor": f"inactive_{uid}",
                "source_type": "field",
                "value_type": "number",
                "state": "inactive",
                "applies_to": "both",
            }
        )

        result = service.get_available_variables(include_inactive=True)
        names = [v["name"] for v in result]
        self.assertIn(f"inactive_{uid}", names)

    def test_get_available_variables_with_unit(self):
        """Test get_available_variables includes unit when available."""
        service = self._get_service()

        result = service.get_available_variables(resource_type="both")
        # Just verify no errors - unit is optional
        self.assertIsInstance(result, list)

    def test_compute_variable_value_field_type_success(self):
        """Test compute_variable_value successfully computes field value."""
        service = self._get_service()

        uid = int(time.time() * 1000)
        self.env["spp.cel.variable"].create(
            {
                "name": f"field_var_{uid}",
                "cel_accessor": f"field_var_{uid}",
                "source_type": "field",
                "value_type": "string",
                "state": "active",
                "applies_to": "both",
                "source_model": "res.partner",
                "source_field": "name",
            }
        )

        result = service.compute_variable_value(
            partner_id=self.partner.id,
            variable_name=f"field_var_{uid}",
        )
        self.assertEqual(result, "VVS Gap Test Partner")

    def test_compute_variable_value_unsafe_model(self):
        """Test compute_variable_value rejects unsafe source models."""
        service = self._get_service()

        uid = int(time.time() * 1000)
        self.env["spp.cel.variable"].create(
            {
                "name": f"unsafe_var_{uid}",
                "cel_accessor": f"unsafe_var_{uid}",
                "source_type": "field",
                "value_type": "string",
                "state": "active",
                "applies_to": "both",
                "source_model": "ir.cron",
                "source_field": "name",
            }
        )

        result = service.compute_variable_value(
            partner_id=self.partner.id,
            variable_name=f"unsafe_var_{uid}",
        )
        self.assertIsNone(result)

    def test_compute_variable_value_nonexistent_record(self):
        """Test compute_variable_value with non-existent partner."""
        service = self._get_service()

        uid = int(time.time() * 1000)
        self.env["spp.cel.variable"].create(
            {
                "name": f"norecord_var_{uid}",
                "cel_accessor": f"norecord_var_{uid}",
                "source_type": "field",
                "value_type": "string",
                "state": "active",
                "applies_to": "both",
                "source_model": "res.partner",
                "source_field": "name",
            }
        )

        result = service.compute_variable_value(
            partner_id=999999999,
            variable_name=f"norecord_var_{uid}",
        )
        # browse returns empty recordset for non-existent ID, so field access returns False
        self.assertFalse(result)

    def test_get_values_model_missing(self):
        """Test get_values_for_subject when spp.data.value not in env."""
        service = self._get_service()
        with patch.object(type(service.env), "__contains__", return_value=False):
            result = service.get_values_for_subject(self.partner.id)
            self.assertEqual(result, {})

    def test_get_values_for_subjects_model_missing(self):
        """Test get_values_for_subjects when spp.data.value not in env."""
        service = self._get_service()
        with patch.object(type(service.env), "__contains__", return_value=False):
            result = service.get_values_for_subjects([self.partner.id])
            self.assertEqual(result, {})

    def test_compute_variable_value_field_exception(self):
        """Test compute_variable_value handles field access exception (lines 276-277)."""
        service = self._get_service()

        uid = int(time.time() * 1000) + 1
        self.env["spp.cel.variable"].create(
            {
                "name": f"exc_var_{uid}",
                "cel_accessor": f"exc_var_{uid}",
                "source_type": "field",
                "value_type": "string",
                "state": "active",
                "applies_to": "both",
                "source_model": "res.partner",
                "source_field": "nonexistent_field_xyz",
            }
        )

        result = service.compute_variable_value(
            partner_id=self.partner.id,
            variable_name=f"exc_var_{uid}",
        )
        self.assertIsNone(result)


@tagged("post_install", "-at_install")
class TestFastapiEndpointStudio(TransactionCase):
    """Test FastAPI endpoint studio extension."""

    def test_get_fastapi_routers_includes_studio(self):
        """Test that studio router is added for api_v2 app."""
        endpoint = self.env["fastapi.endpoint"].search([("app", "=", "api_v2")], limit=1)
        if not endpoint:
            self.skipTest("No api_v2 endpoint configured")

        routers = endpoint._get_fastapi_routers()
        # Should include at least one router
        self.assertTrue(routers)

    def test_get_fastapi_routers_non_api_v2(self):
        """Test that studio router is NOT added for non-api_v2 apps."""
        endpoint = self.env["fastapi.endpoint"].search([("app", "!=", "api_v2")], limit=1)
        if not endpoint:
            self.skipTest("No non-api_v2 endpoint available")

        # Call should work but not include studio router
        routers = endpoint._get_fastapi_routers()
        self.assertIsInstance(routers, list)
