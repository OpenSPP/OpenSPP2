# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Common test utilities for CEL tests.

This module provides mixins and helpers for creating test data without
relying on XML seed data, ensuring tests are isolated and deterministic.
"""

import time


class CELTestDataMixin:
    """Mixin for creating CEL test data.

    This mixin provides helper methods for creating test data that doesn't
    rely on XML seed data being present. Each test class should use unique
    identifiers to avoid conflicts when tests run in parallel.

    Usage:
        class TestMyFeature(TransactionCase, CELTestDataMixin):
            @classmethod
            def setUpClass(cls):
                super().setUpClass()
                cls._test_id = int(time.time() * 1000)  # Unique ID per test run
                cls.test_category = cls._create_test_category()
                cls.test_variable = cls._create_test_variable(
                    category=cls.test_category
                )
    """

    @classmethod
    def _create_test_category(cls, name=None, code=None):
        """Create a test variable category.

        Args:
            name: Optional category name. If not provided, generates unique name
            code: Optional category code. If not provided, generates unique code

        Returns:
            spp.cel.variable.category record
        """
        test_id = getattr(cls, "_test_id", int(time.time() * 1000))
        name = name or f"Test Category {test_id}"
        code = code or f"test_cat_{test_id}"

        VariableCategory = cls.env["spp.cel.variable.category"]
        return VariableCategory.create(
            {
                "name": name,
                "code": code,
            }
        )

    @classmethod
    def _create_test_variable(
        cls,
        name=None,
        cel_accessor=None,
        value_type="number",
        source_type="field",
        category=None,
        applies_to="both",
        **kwargs,
    ):
        """Create a test variable.

        Args:
            name: Variable name. If not provided, generates unique name
            cel_accessor: CEL accessor. If not provided, uses name
            value_type: Variable value type (default: "number")
            source_type: Variable source type (default: "field")
            category: Variable category record. If not provided, creates one
            applies_to: Context applicability (default: "both")
            **kwargs: Additional fields to pass to create()

        Returns:
            spp.cel.variable record

        Note:
            The 'label' field is only available when spp_studio is installed.
            This base mixin works with core spp_cel_domain fields only.
        """
        test_id = getattr(cls, "_test_id", int(time.time() * 1000))
        name = name or f"test_var_{test_id}"
        cel_accessor = cel_accessor or name

        if category is None:
            category = cls._create_test_category()

        LogicVariable = cls.env["spp.cel.variable"]
        values = {
            "name": name,
            "cel_accessor": cel_accessor,
            "value_type": value_type,
            "source_type": source_type,
            "category_id": category.id,
            "applies_to": applies_to,
        }
        values.update(kwargs)
        return LogicVariable.create(values)

    @classmethod
    def _create_test_partner(cls, name=None, is_registrant=True, is_group=False, **kwargs):
        """Create a test partner/registrant.

        Args:
            name: Partner name. If not provided, generates unique name
            is_registrant: Whether partner is a registrant (default: True)
            is_group: Whether partner is a group (default: False)
            **kwargs: Additional fields to pass to create()

        Returns:
            res.partner record
        """
        test_id = getattr(cls, "_test_id", int(time.time() * 1000))
        name = name or f"Test Partner {test_id}"

        Partner = cls.env["res.partner"]
        values = {
            "name": name,
            "is_registrant": is_registrant,
            "is_group": is_group,
        }
        values.update(kwargs)
        return Partner.create(values)

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
        test_id = getattr(cls, "_test_id", int(time.time() * 1000))
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
        test_id = getattr(cls, "_test_id", int(time.time() * 1000))

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
    def _create_test_concept_group(cls, name=None, display_name=None, cel_function=None, codes=None, **kwargs):
        """Create a test concept group.

        Args:
            name: Group name. If not provided, generates unique name
            display_name: Display name. If not provided, uses name
            cel_function: CEL function name
            codes: List of vocabulary code records to add to group
            **kwargs: Additional fields to pass to create()

        Returns:
            spp.vocabulary.concept.group record
        """
        test_id = getattr(cls, "_test_id", int(time.time() * 1000))
        name = name or f"test_group_{test_id}"
        display_name = display_name or name.replace("_", " ").title()

        ConceptGroup = cls.env["spp.vocabulary.concept.group"]
        values = {
            "name": name,
            "display_name": display_name,
        }
        if cel_function:
            values["cel_function"] = cel_function
        values.update(kwargs)

        group = ConceptGroup.create(values)

        if codes:
            group.write({"code_ids": [(6, 0, [c.id for c in codes])]})

        return group

    @classmethod
    def _get_unique_test_id(cls):
        """Get a unique test ID based on timestamp.

        Returns:
            int: Unique test ID
        """
        if not hasattr(cls, "_test_id"):
            cls._test_id = int(time.time() * 1000)
        return cls._test_id
