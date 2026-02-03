# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Vocabulary Adapter - Maps between OpenSPP vocabularies and DCI codes."""

import logging

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class DCIVocabularyAdapter:
    """Maps between OpenSPP vocabularies and DCI standard codes.

    Uses spp_vocabulary.mapping.map_code() for runtime translation with
    fallback to hardcoded mappings when vocabulary mappings don't exist.

    DCI Standard Vocabulary Namespaces:
    - urn:dci:sex:iso5218 - Sex/gender codes (male, female, other, unknown)
    - urn:dci:marital-status - Marital status codes
    - urn:dci:relationship-type - Family relationship codes
    - urn:dci:disability-type - Disability category codes
    """

    # DCI standard vocabulary namespaces
    DCI_SEX_NAMESPACE = "urn:dci:sex:iso5218"
    DCI_MARITAL_STATUS_NAMESPACE = "urn:dci:marital-status"
    DCI_RELATIONSHIP_NAMESPACE = "urn:dci:relationship-type"
    DCI_DISABILITY_NAMESPACE = "urn:dci:disability-type"

    # Fallback mappings when vocabulary mapping doesn't exist
    FALLBACK_GENDER_MAP = {
        "male": "male",
        "m": "male",
        "1": "male",
        "female": "female",
        "f": "female",
        "2": "female",
        "other": "other",
        "o": "other",
        "3": "other",
    }

    FALLBACK_MARITAL_STATUS_MAP = {
        "single": "S",
        "s": "S",
        "married": "M",
        "m": "M",
        "widowed": "W",
        "w": "W",
        "divorced": "D",
        "d": "D",
        "separated": "L",
        "l": "L",
        "annulled": "A",
        "a": "A",
        "unknown": "U",
        "u": "U",
    }

    def __init__(self, env: Environment):
        """Initialize adapter with Odoo environment.

        Args:
            env: Odoo environment
        """
        self.env = env
        self._mapping_model = None

    @property
    def mapping_model(self):
        """Lazy-load vocabulary mapping model."""
        if self._mapping_model is None:
            if "spp.vocabulary.mapping" in self.env:
                self._mapping_model = self.env["spp.vocabulary.mapping"]
            else:
                _logger.warning("spp.vocabulary.mapping model not available")
        return self._mapping_model

    def map_gender_to_dci(self, gender_id) -> str | None:
        """Map OpenSPP gender_id to DCI SexCategory.

        Args:
            gender_id: spp.vocabulary.code record for gender

        Returns:
            DCI sex string (male, female, other, unknown) or None
        """
        if not gender_id:
            return None

        # Try vocabulary mapping first
        if self.mapping_model and hasattr(gender_id, "vocabulary_id"):
            try:
                target_code = self.mapping_model.map_code(
                    source_namespace=gender_id.vocabulary_id.namespace_uri,
                    source_code=gender_id.code,
                    target_namespace=self.DCI_SEX_NAMESPACE,
                )
                if target_code:
                    return target_code.code
            except Exception as e:
                _logger.debug("Vocabulary mapping failed for gender: %s", e)

        # Fallback mapping
        return self._fallback_gender_map(gender_id)

    def map_gender_from_string(self, gender_value: str) -> str | None:
        """Map string gender value to DCI SexCategory.

        Args:
            gender_value: String gender value from partner.gender

        Returns:
            DCI sex string (male, female, other, unknown) or None
        """
        if not gender_value:
            return None

        gender_lower = str(gender_value).lower().strip()
        return self.FALLBACK_GENDER_MAP.get(gender_lower, "unknown")

    def map_marital_status_to_dci(self, marital_status_id) -> str | None:
        """Map OpenSPP marital_status to DCI MaritalStatusCode.

        Args:
            marital_status_id: spp.vocabulary.code record for marital status

        Returns:
            DCI marital status code or None
        """
        if not marital_status_id:
            return None

        # Try vocabulary mapping first
        if self.mapping_model and hasattr(marital_status_id, "vocabulary_id"):
            try:
                target_code = self.mapping_model.map_code(
                    source_namespace=marital_status_id.vocabulary_id.namespace_uri,
                    source_code=marital_status_id.code,
                    target_namespace=self.DCI_MARITAL_STATUS_NAMESPACE,
                )
                if target_code:
                    return target_code.code
            except Exception as e:
                _logger.debug("Vocabulary mapping failed for marital status: %s", e)

        # Fallback mapping
        return self._fallback_marital_status_map(marital_status_id)

    def map_relationship_to_dci(self, relationship_type) -> str | None:
        """Map OpenSPP relationship type to DCI relationship code.

        Args:
            relationship_type: Relationship type code or record

        Returns:
            DCI relationship type code or None
        """
        if not relationship_type:
            return None

        # Try vocabulary mapping
        if self.mapping_model:
            if hasattr(relationship_type, "vocabulary_id"):
                try:
                    target_code = self.mapping_model.map_code(
                        source_namespace=relationship_type.vocabulary_id.namespace_uri,
                        source_code=relationship_type.code,
                        target_namespace=self.DCI_RELATIONSHIP_NAMESPACE,
                    )
                    if target_code:
                        return target_code.code
                except Exception as e:
                    _logger.debug("Vocabulary mapping failed for relationship: %s", e)

        # Return raw value as fallback
        if hasattr(relationship_type, "code"):
            return relationship_type.code
        return str(relationship_type) if relationship_type else None

    def map_disability_type_to_dci(self, disability_type) -> str | None:
        """Map OpenSPP disability type to DCI disability limitation type.

        DCI uses: Vision, Hearing, Mobility, Cognition, SelfCare, Communication

        Args:
            disability_type: Disability type code or record

        Returns:
            DCI disability limitation type code or None
        """
        if not disability_type:
            return None

        # Try vocabulary mapping
        if self.mapping_model:
            if hasattr(disability_type, "vocabulary_id"):
                try:
                    target_code = self.mapping_model.map_code(
                        source_namespace=disability_type.vocabulary_id.namespace_uri,
                        source_code=disability_type.code,
                        target_namespace=self.DCI_DISABILITY_NAMESPACE,
                    )
                    if target_code:
                        return target_code.code
                except Exception as e:
                    _logger.debug("Vocabulary mapping failed for disability type: %s", e)

        # Return raw value as fallback
        if hasattr(disability_type, "code"):
            return disability_type.code
        return str(disability_type) if disability_type else None

    def _fallback_gender_map(self, gender_id) -> str | None:
        """Fallback gender mapping when vocabulary mapping unavailable.

        Args:
            gender_id: Gender record or value

        Returns:
            DCI sex string or None
        """
        if hasattr(gender_id, "code") and gender_id.code:
            code_lower = str(gender_id.code).lower().strip()
            return self.FALLBACK_GENDER_MAP.get(code_lower, "unknown")

        if hasattr(gender_id, "name") and gender_id.name:
            name_lower = str(gender_id.name).lower().strip()
            return self.FALLBACK_GENDER_MAP.get(name_lower, "unknown")

        return None

    def _fallback_marital_status_map(self, marital_status_id) -> str | None:
        """Fallback marital status mapping.

        Args:
            marital_status_id: Marital status record or value

        Returns:
            DCI marital status code or None
        """
        if hasattr(marital_status_id, "code") and marital_status_id.code:
            code_lower = str(marital_status_id.code).lower().strip()
            return self.FALLBACK_MARITAL_STATUS_MAP.get(code_lower, "U")

        if hasattr(marital_status_id, "name") and marital_status_id.name:
            name_lower = str(marital_status_id.name).lower().strip()
            return self.FALLBACK_MARITAL_STATUS_MAP.get(name_lower, "U")

        return None
