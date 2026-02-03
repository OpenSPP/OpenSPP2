# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.data.value model (Unified Value Cache).

This module tests the data caching infrastructure added as part of
the Unified Variable System implementation.
"""

import time
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from .common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestDataValueCRUD(TransactionCase, CELTestDataMixin):
    """Tests for basic CRUD operations on spp.data.value."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.DataValue = cls.env["spp.data.value"]
        cls.test_partner = cls._create_test_partner()
        cls.test_category = cls._create_test_category()
        cls.test_variable = cls._create_test_variable(
            name=f"test_cache_var_{cls._test_id}",
            category=cls.test_category,
            source_type="computed",
            cache_strategy="ttl",
        )

    def test_create_data_value_basic(self):
        """Test basic data value creation."""
        value = self.DataValue.create(
            {
                "variable_name": self.test_variable.name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 42},
                "value_type": "number",
            }
        )

        self.assertTrue(value.id)
        self.assertEqual(value.variable_name, self.test_variable.name)
        self.assertEqual(value.subject_id, self.test_partner.id)
        self.assertEqual(value.value_json, {"value": 42})
        self.assertEqual(value.company_id, self.env.company)

    def test_create_data_value_with_period(self):
        """Test data value creation with period key."""
        value = self.DataValue.create(
            {
                "variable_name": f"period_test_{self._test_id}",
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "period_key": "2024-12",
                "value_json": {"value": 100},
            }
        )

        self.assertEqual(value.period_key, "2024-12")

    def test_create_data_value_with_provider(self):
        """Test data value creation with provider info."""
        value = self.DataValue.create(
            {
                "variable_name": f"provider_test_{self._test_id}",
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "provider": "education_ministry",
                "source_type": "external",
                "value_json": {"value": "enrolled"},
                "value_type": "string",
            }
        )

        self.assertEqual(value.provider, "education_ministry")
        self.assertEqual(value.source_type, "external")

    def test_compute_variable_id(self):
        """Test variable_id is computed from variable_name."""
        value = self.DataValue.create(
            {
                "variable_name": self.test_variable.name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 1},
            }
        )

        self.assertEqual(value.variable_id, self.test_variable)

    def test_compute_subject_ref(self):
        """Test subject_ref is computed from subject."""
        value = self.DataValue.create(
            {
                "variable_name": f"ref_test_{self._test_id}",
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 1},
            }
        )

        self.assertIn(self.test_partner.name, value.subject_ref)

    def test_get_value_simple(self):
        """Test get_value extracts value from JSON."""
        value = self.DataValue.create(
            {
                "variable_name": f"get_val_test_{self._test_id}",
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 42.5},
            }
        )

        self.assertEqual(value.get_value(), 42.5)

    def test_set_value_simple(self):
        """Test set_value updates value JSON."""
        value = self.DataValue.create(
            {
                "variable_name": f"set_val_test_{self._test_id}",
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 0},
            }
        )

        value.set_value(99)
        self.assertEqual(value.get_value(), 99)

    def test_set_value_with_metadata(self):
        """Test set_value with additional metadata."""
        value = self.DataValue.create(
            {
                "variable_name": f"meta_test_{self._test_id}",
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 0},
            }
        )

        value.set_value(85, confidence=0.95, source="verified")
        self.assertEqual(value.get_value(), 85)
        self.assertEqual(value.value_json.get("confidence"), 0.95)
        self.assertEqual(value.value_json.get("source"), "verified")


@tagged("post_install", "-at_install")
class TestDataValueConstraints(TransactionCase, CELTestDataMixin):
    """Tests for spp.data.value constraints and validation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.DataValue = cls.env["spp.data.value"]
        cls.test_partner = cls._create_test_partner()

    @mute_logger("odoo.sql_db")
    def test_unique_constraint_same_record(self):
        """Test unique constraint prevents duplicate records.

        The unique constraint (company_id, variable_name, subject_model,
        subject_id, period_key, provider, params_hash) ensures that each
        combination of these values is unique.
        """
        var_name = f"unique_test_{self._test_id}"
        create_vals = {
            "variable_name": var_name,
            "subject_model": "res.partner",
            "subject_id": self.test_partner.id,
            "period_key": "current",
            "provider": "test",
            "params_hash": "abc123",
            "value_json": {"value": 1},
        }

        # Create first record
        first = self.DataValue.create(create_vals)
        self.assertTrue(first.id)

        # Attempt to create duplicate should fail with IntegrityError
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.DataValue.create(
                    {
                        "variable_name": var_name,
                        "subject_model": "res.partner",
                        "subject_id": self.test_partner.id,
                        "period_key": "current",
                        "provider": "test",
                        "params_hash": "abc123",
                        "value_json": {"value": 2},
                    }
                )

    def test_unique_constraint_different_period(self):
        """Test same variable can have different period values."""
        var_name = f"period_unique_{self._test_id}"

        # Create for current period
        val1 = self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "period_key": "2024-11",
                "value_json": {"value": 100},
            }
        )

        # Create for different period - should succeed
        val2 = self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "period_key": "2024-12",
                "value_json": {"value": 110},
            }
        )

        self.assertTrue(val1.id)
        self.assertTrue(val2.id)
        self.assertNotEqual(val1.id, val2.id)

    def test_unique_constraint_different_provider(self):
        """Test same variable can have values from different providers."""
        var_name = f"provider_unique_{self._test_id}"

        # Create from provider A
        val1 = self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "provider": "provider_a",
                "value_json": {"value": 50},
            }
        )

        # Create from provider B - should succeed
        val2 = self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "provider": "provider_b",
                "value_json": {"value": 55},
            }
        )

        self.assertTrue(val1.id)
        self.assertTrue(val2.id)

    def test_unique_constraint_different_subject(self):
        """Test same variable can have values for different subjects."""
        var_name = f"subject_unique_{self._test_id}"
        partner2 = self._create_test_partner(name="Second Partner")

        val1 = self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 1},
            }
        )

        val2 = self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": partner2.id,
                "value_json": {"value": 2},
            }
        )

        self.assertTrue(val1.id)
        self.assertTrue(val2.id)


@tagged("post_install", "-at_install")
class TestDataValueTTL(TransactionCase, CELTestDataMixin):
    """Tests for TTL expiration and is_stale computation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.DataValue = cls.env["spp.data.value"]
        cls.test_partner = cls._create_test_partner()

    def test_is_stale_false_when_no_expiry(self):
        """Test is_stale is False when expires_at is not set."""
        value = self.DataValue.create(
            {
                "variable_name": f"no_expiry_{self._test_id}",
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 1},
                "expires_at": False,
            }
        )

        self.assertFalse(value.is_stale)

    def test_is_stale_false_when_not_expired(self):
        """Test is_stale is False when value hasn't expired."""
        future = fields.Datetime.now() + timedelta(hours=1)
        value = self.DataValue.create(
            {
                "variable_name": f"future_expiry_{self._test_id}",
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 1},
                "expires_at": future,
            }
        )

        self.assertFalse(value.is_stale)

    def test_is_stale_true_when_expired(self):
        """Test is_stale is True when value has expired."""
        past = fields.Datetime.now() - timedelta(hours=1)
        value = self.DataValue.create(
            {
                "variable_name": f"past_expiry_{self._test_id}",
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 1},
                "expires_at": past,
            }
        )

        self.assertTrue(value.is_stale)

    def test_invalidate_sets_expires_at(self):
        """Test invalidate method sets expires_at and marks as stale."""
        var_name = f"invalidate_test_{self._test_id}"
        future_time = fields.Datetime.now() + timedelta(days=1)

        value = self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 1},
                "expires_at": future_time,
            }
        )

        self.assertFalse(value.is_stale)
        self.assertFalse(value.invalidated_at)

        # Invalidate using the model method (searches and updates)
        count = self.DataValue.invalidate(variable_name=var_name, subject_ids=[self.test_partner.id])
        self.assertEqual(count, 1)

        # Re-fetch the record from database to get updated values
        value = self.DataValue.browse(value.id)

        # Check invalidation fields are set
        self.assertTrue(value.invalidated_at)
        self.assertEqual(value.invalidated_by_id, self.env.user)
        # expires_at should now be <= current time (invalidated)
        self.assertLessEqual(value.expires_at, fields.Datetime.now())


@tagged("post_install", "-at_install")
class TestDataValueBulkOperations(TransactionCase, CELTestDataMixin):
    """Tests for bulk upsert and read operations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.DataValue = cls.env["spp.data.value"]
        cls.partners = [cls._create_test_partner(name=f"Partner {i}") for i in range(5)]

    def test_upsert_values_insert(self):
        """Test bulk insert of new values."""
        var_name = f"bulk_insert_{self._test_id}"
        values_list = [
            {
                "variable_name": var_name,
                "subject_id": p.id,
                "value_json": {"value": i * 10},
            }
            for i, p in enumerate(self.partners)
        ]

        result = self.DataValue.upsert_values(values_list)

        self.assertEqual(result["inserted"], 5)
        self.assertEqual(result["updated"], 0)

    def test_upsert_values_update(self):
        """Test bulk update of existing values."""
        var_name = f"bulk_update_{self._test_id}"

        # First insert
        values_list = [
            {
                "variable_name": var_name,
                "subject_id": p.id,
                "value_json": {"value": 0},
            }
            for p in self.partners
        ]
        self.DataValue.upsert_values(values_list)

        # Verify initial values
        partner_ids = [p.id for p in self.partners]
        values = self.DataValue.read_values(var_name, partner_ids)
        for p in self.partners:
            self.assertEqual(values.get(p.id), 0)

        # Then update with new values
        values_list = [
            {
                "variable_name": var_name,
                "subject_id": p.id,
                "value_json": {"value": 100},
            }
            for p in self.partners
        ]
        result = self.DataValue.upsert_values(values_list)

        # Verify records were processed (bulk SQL returns total count)
        self.assertEqual(result["inserted"], 5)

        # Verify values were actually updated in the database
        values = self.DataValue.read_values(var_name, partner_ids)
        for p in self.partners:
            self.assertEqual(values.get(p.id), 100, f"Value for partner {p.id} not updated")

        # Verify no duplicate records (upsert should update, not insert new)
        records = self.DataValue.search([("variable_name", "=", var_name)])
        self.assertEqual(len(records), 5, "Upsert created duplicates instead of updating")

    def test_upsert_values_with_ttl(self):
        """Test bulk insert with TTL sets expires_at."""
        var_name = f"bulk_ttl_{self._test_id}"
        values_list = [
            {
                "variable_name": var_name,
                "subject_id": self.partners[0].id,
                "value_json": {"value": 42},
                "ttl_seconds": 3600,  # 1 hour
            }
        ]

        self.DataValue.upsert_values(values_list)

        value = self.DataValue.search(
            [
                ("variable_name", "=", var_name),
                ("subject_id", "=", self.partners[0].id),
            ]
        )

        self.assertTrue(value.expires_at)
        self.assertFalse(value.is_stale)

    def test_read_values_basic(self):
        """Test reading cached values."""
        var_name = f"read_test_{self._test_id}"

        # Insert values
        values_list = [
            {
                "variable_name": var_name,
                "subject_id": p.id,
                "value_json": {"value": i * 10},
            }
            for i, p in enumerate(self.partners)
        ]
        self.DataValue.upsert_values(values_list)

        # Read values
        subject_ids = [p.id for p in self.partners]
        result = self.DataValue.read_values(var_name, subject_ids)

        self.assertEqual(len(result), 5)
        self.assertEqual(result[self.partners[0].id], 0)
        self.assertEqual(result[self.partners[2].id], 20)

    def test_read_values_excludes_expired(self):
        """Test read_values excludes expired values by default."""
        var_name = f"read_expired_{self._test_id}"
        past = fields.Datetime.now() - timedelta(hours=1)

        # Insert expired value
        self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": self.partners[0].id,
                "value_json": {"value": 999},
                "expires_at": past,
            }
        )

        # Read should return empty
        result = self.DataValue.read_values(var_name, [self.partners[0].id])
        self.assertEqual(len(result), 0)

    def test_read_values_with_metadata(self):
        """Test reading values with full metadata."""
        var_name = f"read_meta_{self._test_id}"

        self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": self.partners[0].id,
                "value_json": {"value": 75, "confidence": 0.9},
                "source_type": "scoring",
                "coverage": 0.85,
            }
        )

        result = self.DataValue.read_values_with_metadata(var_name, [self.partners[0].id])

        self.assertIn(self.partners[0].id, result)
        meta = result[self.partners[0].id]
        self.assertEqual(meta["value"], 75)
        self.assertEqual(meta["source_type"], "scoring")
        self.assertEqual(meta["coverage"], 0.85)


@tagged("post_install", "-at_install")
class TestDataValueParamsHash(TransactionCase, CELTestDataMixin):
    """Tests for params_hash functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.DataValue = cls.env["spp.data.value"]
        cls.test_partner = cls._create_test_partner()

    def test_hash_params_deterministic(self):
        """Test params hash is deterministic."""
        params = {"threshold": 100, "mode": "strict"}

        hash1 = self.DataValue._hash_params(params)
        hash2 = self.DataValue._hash_params(params)

        self.assertEqual(hash1, hash2)

    def test_hash_params_order_independent(self):
        """Test params hash is independent of key order."""
        params1 = {"a": 1, "b": 2, "c": 3}
        params2 = {"c": 3, "a": 1, "b": 2}

        hash1 = self.DataValue._hash_params(params1)
        hash2 = self.DataValue._hash_params(params2)

        self.assertEqual(hash1, hash2)

    def test_hash_params_empty(self):
        """Test empty params returns empty string."""
        self.assertEqual(self.DataValue._hash_params({}), "")
        self.assertEqual(self.DataValue._hash_params(None), "")

    def test_upsert_with_params_creates_hash(self):
        """Test upsert with params creates hash."""
        var_name = f"params_upsert_{self._test_id}"

        self.DataValue.upsert_values(
            [
                {
                    "variable_name": var_name,
                    "subject_id": self.test_partner.id,
                    "value_json": {"value": 1},
                    "params": {"filter": "active"},
                }
            ]
        )

        value = self.DataValue.search(
            [
                ("variable_name", "=", var_name),
                ("subject_id", "=", self.test_partner.id),
            ]
        )

        self.assertTrue(value.params_hash)
        self.assertEqual(len(value.params_hash), 16)  # SHA256[:16]


@tagged("post_install", "-at_install")
class TestDataValuePurge(TransactionCase, CELTestDataMixin):
    """Tests for purge and cleanup operations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.DataValue = cls.env["spp.data.value"]
        cls.test_partner = cls._create_test_partner()

    def test_cron_purge_expired_by_source_type(self):
        """Test purge respects source-type-specific retention."""
        var_name = f"purge_test_{self._test_id}"
        old_date = fields.Datetime.now() - timedelta(days=100)

        # Create old external value (90 day retention)
        value = self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "source_type": "external",
                "value_json": {"value": 1},
                "recorded_at": old_date,
            }
        )

        value_id = value.id

        # Purge with 90 day retention for external
        deleted = self.DataValue.cron_purge_expired(retention_days={"external": 90})

        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(self.DataValue.search([("id", "=", value_id)]))

    def test_cron_purge_keeps_recent(self):
        """Test purge keeps recent values."""
        var_name = f"keep_recent_{self._test_id}"

        # Create recent value
        value = self.DataValue.create(
            {
                "variable_name": var_name,
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "source_type": "external",
                "value_json": {"value": 1},
            }
        )

        value_id = value.id

        # Purge
        self.DataValue.cron_purge_expired(retention_days={"external": 90})

        # Should still exist
        self.assertTrue(self.DataValue.search([("id", "=", value_id)]))
