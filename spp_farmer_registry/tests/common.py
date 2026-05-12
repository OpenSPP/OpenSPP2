# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Common test utilities for Farmer Registry V2 tests.

This module provides mixins and helpers for creating test data without
relying on XML seed data, ensuring tests are isolated and deterministic.
"""

import time


class FarmerTestDataMixin:
    """Mixin for creating farmer registry test data.

    This mixin provides helper methods for creating test data that doesn't
    rely on XML seed data being present. Each test class should use unique
    identifiers to avoid conflicts when tests run in parallel.

    Usage:
        class TestMyFeature(TransactionCase, FarmerTestDataMixin):
            @classmethod
            def setUpClass(cls):
                super().setUpClass()
                cls._test_id = int(time.time() * 1000)
                cls.test_vocab = cls._create_farm_type_vocabulary()
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
        values = {
            "vocabulary_id": vocabulary.id,
            "code": code,
            "display": display,
        }
        values.update(kwargs)
        return VocabularyCode.create(values)

    @classmethod
    def _create_farm_type_vocabulary(cls):
        """Create farm type vocabulary with standard codes.

        Returns:
            dict: Contains 'vocabulary' and code records (crop, livestock, mixed, aquaculture)
        """
        test_id = cls._get_unique_test_id()
        namespace_uri = f"urn:test:farm-type:{test_id}"

        vocab = cls._create_test_vocabulary(
            name=f"Farm Type {test_id}",
            namespace_uri=namespace_uri,
        )

        VocabCode = cls.env["spp.vocabulary.code"]
        crop = VocabCode.create(
            {
                "vocabulary_id": vocab.id,
                "namespace_uri": namespace_uri,
                "code": "crop",
                "display": "Crop Farming",
            }
        )
        livestock = VocabCode.create(
            {
                "vocabulary_id": vocab.id,
                "namespace_uri": namespace_uri,
                "code": "livestock",
                "display": "Livestock Farming",
            }
        )
        mixed = VocabCode.create(
            {
                "vocabulary_id": vocab.id,
                "namespace_uri": namespace_uri,
                "code": "mixed",
                "display": "Mixed Farming",
            }
        )
        aquaculture = VocabCode.create(
            {
                "vocabulary_id": vocab.id,
                "namespace_uri": namespace_uri,
                "code": "aquaculture",
                "display": "Aquaculture",
            }
        )

        return {
            "vocabulary": vocab,
            "namespace_uri": namespace_uri,
            "crop": crop,
            "livestock": livestock,
            "mixed": mixed,
            "aquaculture": aquaculture,
        }

    @classmethod
    def _create_land_tenure_vocabulary(cls):
        """Create land tenure vocabulary with standard codes.

        Returns:
            dict: Contains 'vocabulary' and code records
        """
        test_id = cls._get_unique_test_id()
        namespace_uri = f"urn:test:land-tenure:{test_id}"

        vocab = cls._create_test_vocabulary(
            name=f"Land Tenure {test_id}",
            namespace_uri=namespace_uri,
        )

        VocabCode = cls.env["spp.vocabulary.code"]
        self_owned = VocabCode.create(
            {
                "vocabulary_id": vocab.id,
                "namespace_uri": namespace_uri,
                "code": "self",
                "display": "Self-owned",
            }
        )
        family = VocabCode.create(
            {
                "vocabulary_id": vocab.id,
                "namespace_uri": namespace_uri,
                "code": "family",
                "display": "Family-owned",
            }
        )
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
            "family": family,
            "leased": leased,
        }

    @classmethod
    def _get_or_create_vocabulary(cls, namespace_uri, name):
        """Get existing vocabulary or create new one.

        Args:
            namespace_uri: The namespace URI to look up
            name: Name for the vocabulary if creating new

        Returns:
            spp.vocabulary record
        """
        Vocabulary = cls.env["spp.vocabulary"]
        vocab = Vocabulary.search([("namespace_uri", "=", namespace_uri)], limit=1)
        if not vocab:
            vocab = Vocabulary.create(
                {
                    "name": name,
                    "namespace_uri": namespace_uri,
                    "is_system": False,
                }
            )
        return vocab

    @classmethod
    def _get_or_create_vocabulary_code(cls, vocabulary, namespace_uri, code, display):
        """Get existing vocabulary code or create new one.

        For system vocabularies, only returns existing codes.
        For non-system vocabularies, creates new codes if needed.

        Args:
            vocabulary: Parent vocabulary record
            namespace_uri: Namespace URI for the code
            code: Code value
            display: Display name

        Returns:
            spp.vocabulary.code record
        """
        VocabCode = cls.env["spp.vocabulary.code"]
        existing = VocabCode.search(
            [
                ("namespace_uri", "=", namespace_uri),
                ("code", "=", code),
            ],
            limit=1,
        )
        if existing:
            return existing

        # Only create new codes for non-system vocabularies
        if vocabulary.is_system:
            # For system vocabularies, search more broadly by display name
            existing = VocabCode.search(
                [
                    ("namespace_uri", "=", namespace_uri),
                    ("display", "ilike", display.split(",")[0]),  # Match first part of name
                ],
                limit=1,
            )
            if existing:
                return existing
            # Return any code from this vocabulary as a fallback
            fallback = VocabCode.search(
                [
                    ("namespace_uri", "=", namespace_uri),
                ],
                limit=1,
            )
            if fallback:
                return fallback
            raise ValueError(f"No codes found for system vocabulary {namespace_uri}")

        return VocabCode.create(
            {
                "vocabulary_id": vocabulary.id,
                "namespace_uri": namespace_uri,
                "code": code,
                "display": display,
            }
        )

    @classmethod
    def _create_species_vocabularies(cls):
        """Create or reuse FAO-aligned species vocabularies for testing.

        Uses actual FAO namespace URIs. Reuses existing vocabularies if present.

        Returns:
            dict: Contains vocabularies for crops, livestock, aquaculture
        """
        # Crop vocabulary (ICC) - uses actual FAO namespace
        crop_ns = "urn:fao:icc:1.1"
        crop_vocab = cls._get_or_create_vocabulary(crop_ns, "ICC Crops")

        rice = cls._get_or_create_vocabulary_code(crop_vocab, crop_ns, "0113", "Rice, paddy")
        maize = cls._get_or_create_vocabulary_code(crop_vocab, crop_ns, "0112", "Maize (corn)")

        # Livestock vocabulary - uses actual FAO namespace
        livestock_ns = "urn:fao:livestock:2020"
        livestock_vocab = cls._get_or_create_vocabulary(livestock_ns, "FAO Livestock")

        cattle = cls._get_or_create_vocabulary_code(livestock_vocab, livestock_ns, "11", "Cattle")
        goats = cls._get_or_create_vocabulary_code(livestock_vocab, livestock_ns, "22", "Goats")

        # Aquaculture vocabulary (ASFIS) - uses actual FAO namespace
        aqua_ns = "urn:fao:asfis:2024"
        aqua_vocab = cls._get_or_create_vocabulary(aqua_ns, "ASFIS Aquaculture")

        tilapia = cls._get_or_create_vocabulary_code(aqua_vocab, aqua_ns, "TLP", "Tilapia")

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
                "goats": goats,
            },
            "aquaculture": {
                "vocabulary": aqua_vocab,
                "namespace_uri": aqua_ns,
                "tilapia": tilapia,
            },
        }

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
    def _create_test_farmer(cls, name=None, **kwargs):
        """Create a test farmer (res.partner as individual).

        Args:
            name: Farmer name. If not provided, generates unique name
            **kwargs: Additional fields to pass to create()

        Returns:
            res.partner record
        """
        test_id = cls._get_unique_test_id()
        name = name or f"Test Farmer {test_id}"

        Partner = cls.env["res.partner"]
        values = {
            "name": name,
            "is_registrant": True,
            "is_group": False,
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
        from datetime import date, timedelta

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
