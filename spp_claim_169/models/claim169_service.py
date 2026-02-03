import logging
from datetime import UTC, datetime, timedelta

import claim169 as c169

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Mapping from claim numbers to Claim169Input property names
# Based on MOSIP Claim 169 specification
CLAIM_NUMBER_TO_PROPERTY = {
    1: "id",
    2: "version",
    4: "full_name",
    5: "first_name",
    6: "middle_name",
    7: "last_name",
    8: "date_of_birth",
    9: "gender",
    10: "address",
    11: "email",
    12: "phone",
    13: "nationality",
    14: "country_of_issuance",
    15: "language",
    16: "secondary_language",
    17: "secondary_full_name",
    18: "guardian",
    19: "marital_status",
    20: "legal_status",
    21: "location_code",
    # Photo and biometric claims (22+) handled separately
}


class Claim169Service(models.AbstractModel):
    """
    Main service for Claim 169 credential generation and verification.

    This service uses the claim169 library for encoding/decoding QR credentials
    and integrates with spp_key_management for cryptographic key operations.
    """

    _name = "spp.claim169.service"
    _description = "Claim 169 Service"

    @api.model
    def generate_cwt_for_partner(self, partner_id, issuer_config_id):
        """
        Generate a signed CWT for a partner.

        Args:
            partner_id: ID of res.partner
            issuer_config_id: ID of spp.claim169.issuer.config

        Returns:
            Tuple of (cwt_bytes, qr_data)
            - cwt_bytes: Raw CWT bytes (None when using claim169 library)
            - qr_data: Base45 encoded string for QR code

        Raises:
            UserError: If generation fails
        """
        partner = self.env["res.partner"].browse(partner_id)
        issuer_config = self.env["spp.claim169.issuer.config"].browse(issuer_config_id)

        if not partner.exists():
            raise UserError(_("Partner not found: %s") % partner_id)

        if not issuer_config.exists():
            raise UserError(_("Issuer configuration not found: %s") % issuer_config_id)

        # Build Claim169Input from attribute mappings
        claim_input = self._build_claim169_input(partner)

        # Build CwtMetaInput from issuer config
        cwt_meta = self._build_cwt_meta_input(issuer_config)

        # Get signing key and determine algorithm
        signing_key = issuer_config.signing_key_id
        if not signing_key:
            raise UserError(_("Issuer configuration '%s' has no signing key") % issuer_config.name)

        algorithm = self._get_signing_algorithm(signing_key)

        # Create signer callback that uses spp_key_management
        def signer_callback(alg, key_id, data):
            return self._sign_data(signing_key, alg, data)

        # Generate QR code using claim169 library
        try:
            qr_data = c169.encode_with_signer(
                claim_input,
                cwt_meta,
                signer_callback,
                algorithm,
                key_id=signing_key.kid.encode() if signing_key.kid else None,
                skip_biometrics=True,  # Skip biometrics by default to reduce QR size
            )
        except Exception as e:
            _logger.error("Failed to encode credential: %s", str(e), exc_info=True)
            raise UserError(_("Credential encoding failed: %s") % str(e)) from e

        _logger.debug(
            "Generated Claim 169 credential for partner %s using issuer %s",
            partner.id,
            issuer_config.name,
        )

        # Return None for cwt_bytes as the library handles encoding internally
        # The qr_data is the Base45-encoded credential
        return None, qr_data

    def _build_claim169_input(self, partner):
        """
        Build Claim169Input from active attribute mappings.

        Args:
            partner: res.partner record

        Returns:
            claim169.Claim169Input populated with partner data
        """
        claim_input = c169.Claim169Input()

        # Get active attribute mappings
        mappings = self.env["spp.claim169.attribute.mapping"].search(
            [("is_active", "=", True)], order="sequence, claim_number"
        )

        # Extract values from partner and set on Claim169Input
        for mapping in mappings:
            try:
                value = mapping.get_value(partner)
                if value is None or value is False:
                    continue

                # Get the property name from claim number or claim_name
                property_name = mapping.claim_name or CLAIM_NUMBER_TO_PROPERTY.get(mapping.claim_number)
                if not property_name:
                    _logger.warning(
                        "No property mapping for claim number %s, skipping",
                        mapping.claim_number,
                    )
                    continue

                # Convert value to string if needed (claim169 expects strings for most fields)
                if property_name == "date_of_birth":
                    # claim169 expects ISO format: "YYYY-MM-DD" (e.g., "1984-04-18")
                    if hasattr(value, "strftime"):
                        value = value.strftime("%Y-%m-%d")
                    else:
                        # Use Odoo's date parsing for robustness
                        try:
                            parsed_date = fields.Date.from_string(str(value))
                            value = parsed_date.strftime("%Y-%m-%d")
                        except (ValueError, TypeError):
                            # Fallback: ensure ISO format if already a string
                            _logger.warning(
                                "Could not parse date '%s' for partner %s, using as-is",
                                value,
                                partner.id,
                            )
                            value = str(value)
                elif property_name == "gender":
                    # gender can be int (1=male, 2=female, 3=other)
                    pass  # Keep as int
                elif not isinstance(value, str | int):
                    value = str(value)

                # Set the property on Claim169Input
                if hasattr(claim_input, property_name):
                    setattr(claim_input, property_name, value)
                else:
                    _logger.warning(
                        "Claim169Input has no property '%s' (claim %s), skipping",
                        property_name,
                        mapping.claim_number,
                    )

            except Exception as e:
                _logger.warning(
                    "Failed to extract value for mapping '%s' (claim %s) from partner %s: %s",
                    mapping.name,
                    mapping.claim_number,
                    partner.id,
                    str(e),
                )
                # Continue with other mappings

        _logger.debug("Built Claim169Input for partner %s with %d mappings", partner.id, len(mappings))

        return claim_input

    def _build_cwt_meta_input(self, issuer_config):
        """
        Build CwtMetaInput from issuer configuration.

        Args:
            issuer_config: spp.claim169.issuer.config record

        Returns:
            claim169.CwtMetaInput populated with issuer data
        """
        cwt_meta = c169.CwtMetaInput()

        # Set issuer
        cwt_meta.issuer = issuer_config.issuer_id

        # Set timestamps
        now = datetime.now(UTC)
        expires = now + timedelta(days=issuer_config.default_validity_days)

        cwt_meta.issued_at = int(now.timestamp())
        cwt_meta.expires_at = int(expires.timestamp())

        return cwt_meta

    def _get_signing_algorithm(self, signing_key):
        """
        Determine the signing algorithm based on key type.

        Args:
            signing_key: spp.asymmetric.key record

        Returns:
            Algorithm string for claim169 ("EdDSA" or "ES256")

        Raises:
            UserError: If key type is not supported
        """
        key_type = signing_key.key_type

        if key_type == "ed25519":
            return "EdDSA"
        elif key_type == "ec":
            curve = signing_key.curve or "P-256"
            if curve == "P-256":
                return "ES256"
            else:
                raise UserError(_("Unsupported EC curve '%s'. Only P-256 (ES256) is supported by claim169.") % curve)
        elif key_type == "rsa":
            raise UserError(_("RSA keys are not supported by claim169. Use Ed25519 or EC P-256."))
        else:
            raise UserError(_("Unsupported key type: %s") % key_type)

    def _sign_data(self, signing_key, algorithm, data):
        """
        Sign data using the signing key from spp_key_management.

        This method delegates to the key's sign() method, which supports:
        - HSM/KMS signing (private key never leaves the secure hardware)
        - Local signing (for local-mode keys)

        Args:
            signing_key: spp.asymmetric.key record
            algorithm: Algorithm string ("EdDSA" or "ES256")
            data: Bytes to sign

        Returns:
            Signature bytes
        """
        # Use the key's sign() method which handles HSM/KMS routing
        return signing_key.sign(data, algorithm)

    @api.model
    def encode_for_qr(self, cwt_bytes):
        """
        Legacy method for backward compatibility.

        Note: With the claim169 library, encoding is done internally.
        This method is kept for any code that might call it directly.
        """
        _logger.warning("encode_for_qr is deprecated when using claim169 library")
        # The claim169 library handles compression and Base45 encoding internally
        raise UserError(_("encode_for_qr is deprecated. Use generate_cwt_for_partner instead."))

    @api.model
    def decode_from_qr(self, qr_data):
        """
        Decode QR data back to claims (unverified).

        Args:
            qr_data: Base45 encoded string from QR code

        Returns:
            Dictionary with claim data using property names as keys
            (e.g., 'full_name', 'date_of_birth', not claim numbers)

        Raises:
            UserError: If decoding fails
        """
        try:
            result = c169.decode_unverified(qr_data)
            raw_claims = result.claim169.to_dict()
            # Translate claim keys to snake_case property names
            return self._translate_claim_keys(raw_claims)
        except Exception as e:
            _logger.error("Failed to decode QR data: %s", str(e), exc_info=True)
            raise UserError(_("QR decoding failed: %s") % str(e)) from e

    def _translate_claim_keys(self, raw_claims):
        """
        Translate claim keys to snake_case property names.

        The claim169 library returns keys in various formats:
        - Integer keys (e.g., 4 for full_name) - from CBOR encoding
        - String numeric keys (e.g., "4") - from some serialization formats
        - camelCase string keys (e.g., "fullName") - from to_dict() method
        - snake_case keys (e.g., "full_name") - already correct

        This method normalizes all formats to snake_case property names.

        Args:
            raw_claims: Dictionary with claims in any of the above formats

        Returns:
            Dictionary with snake_case property names as keys
        """
        # Mapping from camelCase to snake_case for known claims
        camel_to_snake = {
            "fullName": "full_name",
            "firstName": "first_name",
            "middleName": "middle_name",
            "lastName": "last_name",
            "dateOfBirth": "date_of_birth",
            "countryOfIssuance": "country_of_issuance",
            "secondaryLanguage": "secondary_language",
            "secondaryFullName": "secondary_full_name",
            "maritalStatus": "marital_status",
            "legalStatus": "legal_status",
            "locationCode": "location_code",
        }

        translated = {}
        for key, value in raw_claims.items():
            # Handle integer keys (CBOR claim numbers)
            if isinstance(key, int):
                property_name = CLAIM_NUMBER_TO_PROPERTY.get(key)
                if property_name:
                    translated[property_name] = value
                else:
                    translated[key] = value
            # Handle string numeric keys (e.g., "4")
            elif isinstance(key, str) and key.isdigit():
                claim_number = int(key)
                property_name = CLAIM_NUMBER_TO_PROPERTY.get(claim_number)
                if property_name:
                    translated[property_name] = value
                else:
                    translated[key] = value
            # Handle camelCase string keys
            elif isinstance(key, str) and key in camel_to_snake:
                translated[camel_to_snake[key]] = value
            else:
                # Keep other string keys as-is (already snake_case or unknown)
                translated[key] = value
        return translated

    @api.model
    def verify_credential(self, qr_data, public_key_id):
        """
        Verify a credential from QR data.

        Args:
            qr_data: Base45 encoded QR data
            public_key_id: ID of spp.asymmetric.key (public key) for verification

        Returns:
            Dictionary with verification results:
            {
                'valid': Boolean,
                'claims': Dictionary of claims (if valid),
                'error': Error message (if invalid)
            }
        """
        try:
            # Get the public key from spp_key_management
            public_key = self.env["spp.asymmetric.key"].browse(public_key_id)
            if not public_key.exists():
                return {"valid": False, "claims": None, "error": "Public key not found"}

            # Validate key type is supported (will raise if not)
            self._get_signing_algorithm(public_key)

            # Create verifier callback that uses spp_key_management
            def verifier_callback(alg, key_id, data, signature):
                return self._verify_signature(public_key, alg, data, signature)

            # Verify using claim169 library
            result = c169.decode_with_verifier(qr_data, verifier_callback)

            if not result.is_verified():
                raw_claims = result.claim169.to_dict()
                return {
                    "valid": False,
                    "claims": self._translate_claim_keys(raw_claims),
                    "error": "Signature verification failed",
                }

            # Check expiration
            if result.cwt_meta.is_expired():
                raw_claims = result.claim169.to_dict()
                return {
                    "valid": False,
                    "claims": self._translate_claim_keys(raw_claims),
                    "error": "Credential expired",
                }

            raw_claims = result.claim169.to_dict()
            return {"valid": True, "claims": self._translate_claim_keys(raw_claims), "error": None}

        except c169.SignatureError as e:
            _logger.warning("Signature verification failed: %s", str(e))
            return {"valid": False, "claims": None, "error": f"Signature error: {str(e)}"}
        except Exception as e:
            _logger.warning("Credential verification failed: %s", str(e))
            return {"valid": False, "claims": None, "error": str(e)}

    def _verify_signature(self, public_key, algorithm, data, signature):
        """
        Verify signature using the public key from spp_key_management.

        This method delegates to the key's verify() method.

        Args:
            public_key: spp.asymmetric.key record
            algorithm: Algorithm string ("EdDSA" or "ES256")
            data: Bytes that were signed
            signature: Signature bytes to verify

        Raises:
            Exception if verification fails
        """
        if not public_key.verify(data, signature, algorithm):
            raise ValueError("Signature verification failed")
