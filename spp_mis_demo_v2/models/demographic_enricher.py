# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Demographic Enricher — Locale-aware demographic data generation.

Generates and applies address, email, phone, birth_place, civil_status,
ID documents, and bank accounts to registrants. All data is locale-aware
and deterministic (uses a seeded RNG).

Used by both the SeededVolumeGenerator (batch mode) and the story
registrant creator (per-registrant mode).
"""

import logging
import re

_logger = logging.getLogger(__name__)

# Batch size for creating related records
BATCH_SIZE = 200


class DemographicEnricher:
    """Generates and applies locale-aware demographic data to registrants."""

    def __init__(self, env, locale, rng):
        """Initialize the enricher.

        Args:
            env: Odoo environment
            locale: Locale string (e.g., "fil_PH")
            rng: random.Random instance (seeded for determinism)
        """
        self.env = env
        self.rng = rng
        self.locale = locale

        # Load locale provider
        from odoo.addons.spp_demo.locale_providers import get_faker_provider

        self.provider = get_faker_provider(locale)
        if not self.provider:
            _logger.warning("No locale provider found for %s", locale)

        # Cache vocabulary IDs
        self._civil_status_ids = {}
        self._id_type_ids = {}
        self._country_id = None
        self._bank_ids = []

        self._cache_vocab_ids()
        self._resolve_country()
        self._ensure_banks()

    # ═══════════════════════════════════════════════════════════════════
    # INITIALIZATION HELPERS
    # ═══════════════════════════════════════════════════════════════════

    def _cache_vocab_ids(self):
        """Cache vocabulary code IDs for civil status and ID types."""
        xmlid_map = {
            # Civil status
            "S": "spp_vocabulary.code_marital_single",
            "M": "spp_vocabulary.code_marital_married",
            "W": "spp_vocabulary.code_marital_widowed",
            "D": "spp_vocabulary.code_marital_divorced",
            "L": "spp_vocabulary.code_marital_separated",
            "C": "spp_vocabulary.code_marital_consensual",
        }
        for code, xmlid in xmlid_map.items():
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec:
                self._civil_status_ids[code] = rec.id

        # ID types
        id_xmlids = {
            "national_id": "spp_vocabulary.code_id_type_national_id",
            "birth_certificate": "spp_vocabulary.code_id_type_birth_certificate",
        }
        for code, xmlid in id_xmlids.items():
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec:
                self._id_type_ids[code] = rec.id

    def _resolve_country(self):
        """Resolve country_id from the locale provider's country_code."""
        if not self.provider or not hasattr(self.provider, "country_code"):
            return
        country = self.env["res.country"].search([("code", "=", self.provider.country_code)], limit=1)
        if country:
            self._country_id = country.id

    def _ensure_banks(self):
        """Create res.bank records for the locale if they don't exist."""
        if not self.provider or not hasattr(self.provider, "banks"):
            return

        Bank = self.env["res.bank"]
        for full_name, bic in self.provider.banks:
            existing = Bank.search([("name", "=", full_name)], limit=1)
            if existing:
                self._bank_ids.append(existing.id)
            else:
                bank = Bank.create(
                    {
                        "name": full_name,
                        "bic": bic,
                        "country": self._country_id,
                    }
                )
                self._bank_ids.append(bank.id)

    # ═══════════════════════════════════════════════════════════════════
    # DATA GENERATORS
    # ═══════════════════════════════════════════════════════════════════

    def _fill_format(self, fmt):
        """Fill a format template like 'PSN-{d4}-{d4}-{d4}' with random digits."""

        def replacer(match):
            count = int(match.group(1))
            return "".join(str(self.rng.randint(0, 9)) for _ in range(count))

        return re.sub(r"\{d(\d+)\}", replacer, fmt)

    def _generate_address(self):
        """Generate a locale-aware address dict."""
        if not self.provider or not hasattr(self.provider, "cities"):
            return {}

        city_data = self.rng.choice(self.provider.cities)
        city_name = city_data[0]
        zip_code = city_data[2] if len(city_data) > 2 else ""

        street_name = self.rng.choice(self.provider.street_names)
        street_number = self.rng.randint(1, 999)

        vals = {
            "street": f"{street_number} {street_name}",
            "city": city_name,
            "zip": zip_code,
        }
        if self._country_id:
            vals["country_id"] = self._country_id

        return vals

    def _generate_email(self, given_name, family_name):
        """Generate an email address from name parts."""
        if not self.provider or not hasattr(self.provider, "email_domains"):
            return False

        domain = self.rng.choice(self.provider.email_domains)
        # Clean name parts for email
        gn = re.sub(r"[^a-zA-Z]", "", given_name or "user").lower()
        fn = re.sub(r"[^a-zA-Z]", "", family_name or "demo").lower()
        # Add random digits to avoid duplicates
        suffix = self.rng.randint(10, 99)
        return f"{gn}.{fn}{suffix}@{domain}"

    def _generate_phone(self):
        """Generate a locale-aware phone number."""
        if not self.provider or not hasattr(self.provider, "mobile_format"):
            return False
        return self._fill_format(self.provider.mobile_format)

    def _generate_national_id(self):
        """Generate a locale-aware national ID number."""
        if not self.provider or not hasattr(self.provider, "national_id_format"):
            return False
        return self._fill_format(self.provider.national_id_format)

    def _generate_household_id(self):
        """Generate a household registration ID."""
        if not self.provider or not hasattr(self.provider, "household_id_format"):
            return False
        return self._fill_format(self.provider.household_id_format)

    def _generate_birth_place(self):
        """Generate a locale-aware birth place."""
        if not self.provider or not hasattr(self.provider, "birth_places"):
            return False
        return self.rng.choice(self.provider.birth_places)

    def _pick_civil_status(self, age, role):
        """Pick an age-appropriate civil status.

        Args:
            age: Integer age
            role: Member role ("head", "spouse", "child", "adult", "elderly")

        Returns:
            civil_status vocabulary code ID or False
        """
        if not self._civil_status_ids:
            return False

        # Children always single
        if age is not None and age < 18:
            return self._civil_status_ids.get("S", False)

        # Heads and spouses in households are typically married
        if role in ("head", "spouse"):
            return self._civil_status_ids.get("M", False)

        # Elderly more likely widowed
        if role == "elderly" or (age is not None and age >= 65):
            weights = {"S": 5, "M": 35, "W": 35, "D": 10, "L": 10, "C": 5}
        elif age is not None and age >= 40:
            weights = {"S": 5, "M": 60, "W": 10, "D": 10, "L": 10, "C": 5}
        elif age is not None and age >= 25:
            weights = {"S": 20, "M": 55, "C": 10, "D": 5, "L": 5, "W": 5}
        else:
            weights = {"S": 70, "M": 15, "C": 10, "D": 3, "L": 2}

        # Filter to available codes
        available = {k: v for k, v in weights.items() if k in self._civil_status_ids}
        if not available:
            return False

        codes = list(available.keys())
        wts = [available[c] for c in codes]
        chosen = self.rng.choices(codes, weights=wts, k=1)[0]
        return self._civil_status_ids.get(chosen, False)

    def _pick_bank_id(self):
        """Pick a random bank from the locale pool."""
        if not self._bank_ids:
            return False
        return self.rng.choice(self._bank_ids)

    def _generate_bank_account_number(self):
        """Generate a random bank account number."""
        return "".join(str(self.rng.randint(0, 9)) for _ in range(12))

    def _create_individual_ids(self, individual, age):
        """Create ID documents for an individual.

        - Adults (>= 15): National ID
        - Children (< 15): Birth Certificate
        - All get at least one ID document
        """
        RegistryId = self.env["spp.registry.id"]

        # National ID for adults/teens
        national_id_type = self._id_type_ids.get("national_id")
        if national_id_type and age is not None and age >= 15:
            id_value = self._generate_national_id()
            if id_value:
                existing = RegistryId.search(
                    [("partner_id", "=", individual.id), ("id_type_id", "=", national_id_type)],
                    limit=1,
                )
                if not existing:
                    RegistryId.create(
                        {
                            "partner_id": individual.id,
                            "id_type_id": national_id_type,
                            "value": id_value,
                        }
                    )

        # Birth certificate for children (and optionally everyone)
        birth_cert_type = self._id_type_ids.get("birth_certificate")
        if birth_cert_type and age is not None and age < 15:
            bc_value = self._fill_format("BC-{d4}-{d6}")
            existing = RegistryId.search(
                [("partner_id", "=", individual.id), ("id_type_id", "=", birth_cert_type)],
                limit=1,
            )
            if not existing:
                RegistryId.create(
                    {
                        "partner_id": individual.id,
                        "id_type_id": birth_cert_type,
                        "value": bc_value,
                    }
                )

    # ═══════════════════════════════════════════════════════════════════
    # SINGLE-RECORD ENRICHMENT (for story registrants)
    # ═══════════════════════════════════════════════════════════════════

    def enrich_group(self, group):
        """Set address, email, phone, bank, household ID on a single group."""
        if not self.provider:
            return

        # Address + email + phone on partner
        phone_no = self._generate_phone()
        vals = self._generate_address()
        vals["email"] = self._generate_email(group.name, "household")
        vals["phone"] = phone_no
        group.write(vals)

        # Phone number record (one2many)
        if phone_no and "spp.phone.number" in self.env:
            self.env["spp.phone.number"].create(
                {
                    "partner_id": group.id,
                    "phone_no": phone_no,
                    "country_id": self._country_id,
                }
            )

        # Bank account
        bank_id = self._pick_bank_id()
        if bank_id and "res.partner.bank" in self.env:
            self.env["res.partner.bank"].create(
                {
                    "partner_id": group.id,
                    "bank_id": bank_id,
                    "acc_number": self._generate_bank_account_number(),
                }
            )

        # Household registration ID
        hh_id_value = self._generate_household_id()
        national_id_type = self._id_type_ids.get("national_id")
        if hh_id_value and national_id_type and "spp.registry.id" in self.env:
            self.env["spp.registry.id"].create(
                {
                    "partner_id": group.id,
                    "id_type_id": national_id_type,
                    "value": hh_id_value,
                }
            )

    def enrich_individual(self, individual, age=None, gender=None, role=None):
        """Set birth_place, civil_status, national ID, phone, email on one individual."""
        if not self.provider:
            return

        given_name = individual.given_name or individual.name or ""
        family_name = individual.family_name or ""

        # Partner fields
        phone_no = self._generate_phone()
        vals = {}
        vals["birth_place"] = self._generate_birth_place()
        vals["email"] = self._generate_email(given_name, family_name)
        vals["phone"] = phone_no

        civil_status_id = self._pick_civil_status(age, role)
        if civil_status_id:
            vals["civil_status_id"] = civil_status_id

        individual.write(vals)

        # Phone number record (one2many) — for all individuals
        if phone_no and "spp.phone.number" in self.env:
            self.env["spp.phone.number"].create(
                {
                    "partner_id": individual.id,
                    "phone_no": phone_no,
                    "country_id": self._country_id,
                }
            )

        # ID documents
        if "spp.registry.id" in self.env:
            self._create_individual_ids(individual, age)

    # ═══════════════════════════════════════════════════════════════════
    # BATCH ENRICHMENT (for volume generation)
    # ═══════════════════════════════════════════════════════════════════

    def batch_enrich_groups(self, groups_with_metadata):
        """Batch-enrich groups with demographic data.

        Args:
            groups_with_metadata: list of dicts with keys:
                - record: res.partner recordset (single group)
                - name: group name string
        """
        if not self.provider:
            return

        _logger.info("Enriching %d groups with demographic data...", len(groups_with_metadata))

        # Collect partner write vals and related record vals
        partner_writes = []  # [(record_id, vals)]
        bank_vals = []
        registry_id_vals = []
        phone_vals = []

        national_id_type = self._id_type_ids.get("national_id")

        for meta in groups_with_metadata:
            record = meta["record"]
            name = meta.get("name", record.name or "")

            # Address + contact
            phone_no = self._generate_phone()
            vals = self._generate_address()
            vals["email"] = self._generate_email(name, "household")
            vals["phone"] = phone_no
            partner_writes.append((record.id, vals))

            # Phone record (one2many)
            if phone_no:
                phone_vals.append(
                    {
                        "partner_id": record.id,
                        "phone_no": phone_no,
                        "country_id": self._country_id,
                    }
                )

            # Bank account
            bank_id = self._pick_bank_id()
            if bank_id and "res.partner.bank" in self.env:
                bank_vals.append(
                    {
                        "partner_id": record.id,
                        "bank_id": bank_id,
                        "acc_number": self._generate_bank_account_number(),
                    }
                )

            # Household registration ID
            if national_id_type and "spp.registry.id" in self.env:
                hh_id = self._generate_household_id()
                if hh_id:
                    registry_id_vals.append(
                        {
                            "partner_id": record.id,
                            "id_type_id": national_id_type,
                            "value": hh_id,
                        }
                    )

        # Batch write partner fields
        for rec_id, vals in partner_writes:
            self.env["res.partner"].browse(rec_id).write(vals)

        # Batch create related records
        self._batch_create("res.partner.bank", bank_vals)
        self._batch_create("spp.registry.id", registry_id_vals)
        if "spp.phone.number" in self.env:
            self._batch_create("spp.phone.number", phone_vals)

        _logger.info(
            "Enriched %d groups: %d bank accounts, %d registry IDs, %d phone records",
            len(groups_with_metadata),
            len(bank_vals),
            len(registry_id_vals),
            len(phone_vals),
        )

    def batch_enrich_individuals(self, individuals_with_metadata):
        """Batch-enrich individuals with demographic data.

        Args:
            individuals_with_metadata: list of dicts with keys:
                - record: res.partner recordset (single individual)
                - age: integer age
                - gender: "male" or "female"
                - role: "head", "spouse", "child", "adult", "elderly"
                - given_name: first name
                - family_name: last name
        """
        if not self.provider:
            return

        _logger.info("Enriching %d individuals with demographic data...", len(individuals_with_metadata))

        partner_writes = []
        registry_id_vals = []
        phone_vals = []

        national_id_type = self._id_type_ids.get("national_id")
        birth_cert_type = self._id_type_ids.get("birth_certificate")

        for meta in individuals_with_metadata:
            record = meta["record"]
            age = meta.get("age")
            role = meta.get("role", "")
            given_name = meta.get("given_name", "")
            family_name = meta.get("family_name", "")

            # Partner fields
            vals = {}
            vals["birth_place"] = self._generate_birth_place()
            vals["email"] = self._generate_email(given_name, family_name)
            vals["phone"] = self._generate_phone()

            civil_status_id = self._pick_civil_status(age, role)
            if civil_status_id:
                vals["civil_status_id"] = civil_status_id

            partner_writes.append((record.id, vals))

            # Phone record (one2many) — for all individuals
            phone_no_rec = self._generate_phone()
            if phone_no_rec:
                phone_vals.append(
                    {
                        "partner_id": record.id,
                        "phone_no": phone_no_rec,
                        "country_id": self._country_id,
                    }
                )

            # ID documents — national ID for adults (>=15), birth certificate for children (<15)
            if national_id_type and age is not None and age >= 15:
                id_value = self._generate_national_id()
                if id_value:
                    registry_id_vals.append(
                        {
                            "partner_id": record.id,
                            "id_type_id": national_id_type,
                            "value": id_value,
                        }
                    )
            elif birth_cert_type and age is not None and age < 15:
                bc_value = self._fill_format("BC-{d4}-{d6}")
                registry_id_vals.append(
                    {
                        "partner_id": record.id,
                        "id_type_id": birth_cert_type,
                        "value": bc_value,
                    }
                )

        # Batch write partner fields
        for rec_id, vals in partner_writes:
            self.env["res.partner"].browse(rec_id).write(vals)

        # Batch create related records
        if "spp.registry.id" in self.env:
            self._batch_create("spp.registry.id", registry_id_vals)
        if "spp.phone.number" in self.env:
            self._batch_create("spp.phone.number", phone_vals)

        _logger.info(
            "Enriched %d individuals: %d registry IDs, %d phone numbers",
            len(individuals_with_metadata),
            len(registry_id_vals),
            len(phone_vals),
        )

    def _batch_create(self, model_name, vals_list):
        """Create records in batches with performance context."""
        if not vals_list:
            return self.env[model_name]

        model = self.env[model_name].with_context(
            mail_create_nolog=True,
            tracking_disable=True,
        )

        all_records = model
        for i in range(0, len(vals_list), BATCH_SIZE):
            batch = vals_list[i : i + BATCH_SIZE]
            try:
                records = model.create(batch)
                all_records |= records
            except Exception as e:
                _logger.warning("Batch create failed for %s: %s", model_name, e)

        return all_records
