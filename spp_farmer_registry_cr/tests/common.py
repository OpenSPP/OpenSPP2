# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Common test utilities for Farmer Registry CR tests.

This module provides mixins and helpers for creating test data for
change request testing in the farmer registry context.
"""

import time
from datetime import date, timedelta


class FarmerCRTestMixin:
    """Mixin for creating farmer registry CR test data.

    This mixin extends the base farmer test data mixin with CR-specific
    helpers for creating change requests and testing CR workflows.

    Usage:
        class TestMyFeature(TransactionCase, FarmerCRTestMixin):
            @classmethod
            def setUpClass(cls):
                super().setUpClass()
                cls._test_id = int(time.time() * 1000)
    """

    @classmethod
    def _get_unique_test_id(cls):
        """Get a unique test ID based on timestamp."""
        if not hasattr(cls, "_test_id"):
            cls._test_id = int(time.time() * 1000)
        return cls._test_id

    @classmethod
    def _create_test_vocabulary(cls, name=None, namespace_uri=None, **kwargs):
        """Create a test vocabulary.

        Args:
            name: Vocabulary name. If not provided, generates unique name
            namespace_uri: Vocabulary namespace URI. If not provided, generates unique URI
            **kwargs: Additional fields to pass to create()

        Returns:
            spp.vocabulary record
        """
        test_id = cls._get_unique_test_id()
        name = name or f"Test Vocabulary {test_id}"
        namespace_uri = namespace_uri or f"urn:test:vocab:{test_id}"

        Vocabulary = cls.env["spp.vocabulary"]
        # Check for existing vocabulary with same namespace_uri
        existing = Vocabulary.search([("namespace_uri", "=", namespace_uri)], limit=1)
        if existing:
            return existing

        values = {
            "name": name,
            "namespace_uri": namespace_uri,
            "is_system": False,
        }
        values.update(kwargs)
        return Vocabulary.create(values)

    @classmethod
    def _create_test_vocabulary_code(cls, vocabulary=None, code=None, display=None, **kwargs):
        """Create a test vocabulary code.

        Args:
            vocabulary: Vocabulary record. If not provided, creates one
            code: Code value. If not provided, generates unique code
            display: Display name. If not provided, uses code
            **kwargs: Additional fields to pass to create()

        Returns:
            spp.vocabulary.code record
        """
        test_id = cls._get_unique_test_id()

        if vocabulary is None:
            vocabulary = cls._create_test_vocabulary()

        code = code or f"CODE_{test_id}"
        display = display or code

        VocabularyCode = cls.env["spp.vocabulary.code"]

        # Check for existing code in this vocabulary
        existing = VocabularyCode.search(
            [("namespace_uri", "=", vocabulary.namespace_uri), ("code", "=", code)],
            limit=1,
        )
        if existing:
            return existing

        values = {
            "vocabulary_id": vocabulary.id,
            "namespace_uri": vocabulary.namespace_uri,
            "code": code,
            "display": display,
        }
        values.update(kwargs)
        # Use is_local context to allow adding to system vocabularies
        return VocabularyCode.with_context(is_local=True).create(values)

    @classmethod
    def _create_test_farm(cls, name=None, is_group=True, **kwargs):
        """Create a test farm (res.partner as group).

        Args:
            name: Farm name. If not provided, generates unique name
            is_group: Whether farm is a group (default: True)
            **kwargs: Additional fields to pass to create()

        Returns:
            res.partner record
        """
        test_id = cls._get_unique_test_id()
        name = name or f"Test Farm {test_id}"

        Partner = cls.env["res.partner"]
        values = {
            "name": name,
            "is_registrant": True,
            "is_group": is_group,
        }
        values.update(kwargs)
        return Partner.with_context(tracking_disable=True).create(values)

    @classmethod
    def _create_test_season(cls, name=None, state="active", **kwargs):
        """Create a test agricultural season.

        Args:
            name: Season name. If not provided, generates unique name
            state: Season state (default: 'active')
            **kwargs: Additional fields to pass to create()

        Returns:
            spp.farm.season record
        """
        test_id = cls._get_unique_test_id()
        name = name or f"Test Season {test_id}"
        today = date.today()

        Season = cls.env["spp.farm.season"]
        values = {
            "name": name,
            "date_start": today - timedelta(days=30),
            "date_end": today + timedelta(days=60),
            "state": state,
            "allow_overlap": True,
        }
        values.update(kwargs)
        return Season.create(values)

    @classmethod
    def _create_test_activity(cls, farm=None, activity_type="crop", **kwargs):
        """Create a test farm activity.

        Args:
            farm: Farm (res.partner) to link to. If not provided, creates one
            activity_type: Activity type (crop, livestock, aquaculture)
            **kwargs: Additional fields to pass to create()

        Returns:
            spp.farm.activity record
        """
        if farm is None:
            farm = cls._create_test_farm()

        Activity = cls.env["spp.farm.activity"]
        values = {
            "activity_type": activity_type,
            "quantity": 100.0,
            "quantity_unit": "kg",
        }

        # Link to farm based on activity type
        farm_field_map = {
            "crop": "crop_farm_id",
            "livestock": "livestock_farm_id",
            "aquaculture": "aquaculture_farm_id",
        }
        farm_field = farm_field_map.get(activity_type)
        if farm_field:
            values[farm_field] = farm.id

        values.update(kwargs)
        return Activity.create(values)

    @classmethod
    def _create_cr_type(cls, name=None, code=None, detail_model=None, apply_model=None, **kwargs):
        """Create a test CR type.

        Args:
            name: CR type name. If not provided, generates unique name
            code: CR type code. If not provided, generates unique code
            detail_model: Detail model name (e.g., 'spp.cr.detail.farm_details')
            apply_model: Apply model name (e.g., 'spp.cr.apply.update_farm_details')
            **kwargs: Additional fields to pass to create()

        Returns:
            spp.change.request.type record
        """
        test_id = cls._get_unique_test_id()
        name = name or f"Test CR Type {test_id}"
        code = code or f"test_cr_{test_id}"

        CRType = cls.env["spp.change.request.type"]
        values = {
            "name": name,
            "code": code,
            "detail_model": detail_model or "spp.cr.detail.farm_details",
        }
        if apply_model:
            values["apply_strategy"] = "custom"
            values["apply_model"] = apply_model

        values.update(kwargs)
        return CRType.create(values)

    @classmethod
    def _create_change_request(cls, cr_type=None, registrant=None, **kwargs):
        """Create a test change request.

        Args:
            cr_type: CR type record. If not provided, creates one
            registrant: Registrant (res.partner). If not provided, creates one
            **kwargs: Additional fields to pass to create()

        Returns:
            spp.change.request record
        """
        if cr_type is None:
            cr_type = cls._create_cr_type()
        if registrant is None:
            registrant = cls._create_test_farm()

        CR = cls.env["spp.change.request"]
        values = {
            "request_type_id": cr_type.id,
            "registrant_id": registrant.id,
        }
        values.update(kwargs)
        return CR.create(values)

    @classmethod
    def _create_farm_type_vocabulary(cls):
        """Create farm type vocabulary with standard codes.

        Returns:
            dict: Contains 'vocabulary' and code records
        """
        test_id = cls._get_unique_test_id()
        namespace_uri = "urn:openspp:vocab:farm-type"

        # Check if vocabulary already exists
        Vocabulary = cls.env["spp.vocabulary"]
        vocab = Vocabulary.search([("namespace_uri", "=", namespace_uri)], limit=1)

        if not vocab:
            vocab = Vocabulary.create(
                {
                    "name": f"Farm Type {test_id}",
                    "namespace_uri": namespace_uri,
                    "is_system": False,
                }
            )

        VocabCode = cls.env["spp.vocabulary.code"]

        # Create or get codes
        crop = VocabCode.search([("namespace_uri", "=", namespace_uri), ("code", "=", "crop")], limit=1)
        if not crop:
            crop = VocabCode.create(
                {
                    "vocabulary_id": vocab.id,
                    "namespace_uri": namespace_uri,
                    "code": "crop",
                    "display": "Crop Farming",
                }
            )

        livestock = VocabCode.search([("namespace_uri", "=", namespace_uri), ("code", "=", "livestock")], limit=1)
        if not livestock:
            livestock = VocabCode.create(
                {
                    "vocabulary_id": vocab.id,
                    "namespace_uri": namespace_uri,
                    "code": "livestock",
                    "display": "Livestock Farming",
                }
            )

        return {
            "vocabulary": vocab,
            "namespace_uri": namespace_uri,
            "crop": crop,
            "livestock": livestock,
        }

    @classmethod
    def _create_land_tenure_vocabulary(cls):
        """Create land tenure vocabulary with standard codes.

        Returns:
            dict: Contains 'vocabulary' and code records
        """
        test_id = cls._get_unique_test_id()
        namespace_uri = "urn:openspp:vocab:land-tenure"

        # Check if vocabulary already exists
        Vocabulary = cls.env["spp.vocabulary"]
        vocab = Vocabulary.search([("namespace_uri", "=", namespace_uri)], limit=1)

        if not vocab:
            vocab = Vocabulary.create(
                {
                    "name": f"Land Tenure {test_id}",
                    "namespace_uri": namespace_uri,
                    "is_system": False,
                }
            )

        VocabCode = cls.env["spp.vocabulary.code"]

        # Create or get codes
        self_owned = VocabCode.search([("namespace_uri", "=", namespace_uri), ("code", "=", "self")], limit=1)
        if not self_owned:
            self_owned = VocabCode.create(
                {
                    "vocabulary_id": vocab.id,
                    "namespace_uri": namespace_uri,
                    "code": "self",
                    "display": "Self-owned",
                }
            )

        leased = VocabCode.search([("namespace_uri", "=", namespace_uri), ("code", "=", "leased")], limit=1)
        if not leased:
            leased = VocabCode.create(
                {
                    "vocabulary_id": vocab.id,
                    "namespace_uri": namespace_uri,
                    "code": "leased",
                    "display": "Leased",
                }
            )

        return {
            "vocabulary": vocab,
            "namespace_uri": namespace_uri,
            "self": self_owned,
            "leased": leased,
        }

    @classmethod
    def _create_species_vocabularies(cls):
        """Create or reuse FAO-aligned species vocabularies for testing.

        Returns:
            dict: Contains vocabularies for crops, livestock, aquaculture
        """
        VocabCode = cls.env["spp.vocabulary.code"]
        Vocabulary = cls.env["spp.vocabulary"]

        # Crop vocabulary (ICC) - uses actual FAO namespace
        crop_ns = "urn:fao:icc:1.1"
        crop_vocab = Vocabulary.search([("namespace_uri", "=", crop_ns)], limit=1)
        if not crop_vocab:
            crop_vocab = Vocabulary.create(
                {
                    "name": "ICC Crops",
                    "namespace_uri": crop_ns,
                    "is_system": True,
                }
            )

        # For system vocabularies, search for existing codes
        rice = VocabCode.search([("namespace_uri", "=", crop_ns), ("code", "=", "0113")], limit=1)
        if not rice:
            # If code doesn't exist, use first available code as fallback
            rice = VocabCode.search([("namespace_uri", "=", crop_ns)], limit=1)
            if not rice:
                # Create with is_local flag to allow adding to system vocabulary
                rice = VocabCode.with_context(is_local=True).create(
                    {
                        "vocabulary_id": crop_vocab.id,
                        "namespace_uri": crop_ns,
                        "code": "0113",
                        "display": "Rice, paddy",
                        "is_local": True,
                    }
                )

        maize = VocabCode.search([("namespace_uri", "=", crop_ns), ("code", "=", "0112")], limit=1)
        if not maize:
            maize = VocabCode.search([("namespace_uri", "=", crop_ns)], limit=1, offset=1)
            if not maize:
                maize = VocabCode.with_context(is_local=True).create(
                    {
                        "vocabulary_id": crop_vocab.id,
                        "namespace_uri": crop_ns,
                        "code": "0112",
                        "display": "Maize (corn)",
                        "is_local": True,
                    }
                )

        # Livestock vocabulary
        livestock_ns = "urn:fao:livestock:2020"
        livestock_vocab = Vocabulary.search([("namespace_uri", "=", livestock_ns)], limit=1)
        if not livestock_vocab:
            livestock_vocab = Vocabulary.create(
                {
                    "name": "FAO Livestock",
                    "namespace_uri": livestock_ns,
                    "is_system": True,
                }
            )

        cattle = VocabCode.search([("namespace_uri", "=", livestock_ns), ("code", "=", "11")], limit=1)
        if not cattle:
            cattle = VocabCode.search([("namespace_uri", "=", livestock_ns)], limit=1)
            if not cattle:
                cattle = VocabCode.with_context(is_local=True).create(
                    {
                        "vocabulary_id": livestock_vocab.id,
                        "namespace_uri": livestock_ns,
                        "code": "11",
                        "display": "Cattle",
                        "is_local": True,
                    }
                )

        # Aquaculture vocabulary (ASFIS)
        aqua_ns = "urn:fao:asfis:2024"
        aqua_vocab = Vocabulary.search([("namespace_uri", "=", aqua_ns)], limit=1)
        if not aqua_vocab:
            aqua_vocab = Vocabulary.create(
                {
                    "name": "ASFIS Aquaculture",
                    "namespace_uri": aqua_ns,
                    "is_system": True,
                }
            )

        tilapia = VocabCode.search([("namespace_uri", "=", aqua_ns), ("code", "=", "TLP")], limit=1)
        if not tilapia:
            tilapia = VocabCode.search([("namespace_uri", "=", aqua_ns)], limit=1)
            if not tilapia:
                tilapia = VocabCode.with_context(is_local=True).create(
                    {
                        "vocabulary_id": aqua_vocab.id,
                        "namespace_uri": aqua_ns,
                        "code": "TLP",
                        "display": "Tilapia",
                        "is_local": True,
                    }
                )

        return {
            "crop": {
                "vocabulary": crop_vocab,
                "namespace_uri": crop_ns,
                "rice": rice,
                "maize": maize,
            },
            "livestock": {
                "vocabulary": livestock_vocab,
                "namespace_uri": livestock_ns,
                "cattle": cattle,
            },
            "aquaculture": {
                "vocabulary": aqua_vocab,
                "namespace_uri": aqua_ns,
                "tilapia": tilapia,
            },
        }
