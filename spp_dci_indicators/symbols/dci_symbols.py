"""DCI Symbol Providers for CEL Expressions.

These providers enable CEL expressions like:
- dr.has_disability == true
- dr.severity('Vision') >= 3
- crvs.is_alive == true
- crvs.birth_verified == true
- ibr.is_enrolled('program_name') == true
- ibr.has_duplicate == true
- sr.is_registered == true
- sr.is_enrolled('program_name') == true
- sr.program_count >= 1

The symbols are lazy-loaded, meaning DCI data is only fetched when actually
accessed in a CEL expression. By default, they read from the local Odoo cache
for performance. Use query_live() to fetch fresh data from DCI registries.
"""

import logging

_logger = logging.getLogger(__name__)


def _get_data_source_by_type(env, registry_type: str):
    """Get the active data source for a registry type.

    Args:
        env: Odoo environment
        registry_type: Type of registry (dr, crvs, ibr)

    Returns:
        spp.dci.data.source record or None
    """
    return env["spp.dci.data.source"].search(
        [
            ("registry_type", "=", registry_type),
            ("state", "=", "active"),
        ],
        limit=1,
    )


class DRSymbolProvider:
    """Disability Registry (DR) Symbol Provider.

    Provides CEL symbols for disability data:
    - dr.has_disability: Boolean indicating if person has any disability
    - dr.severity(disability_type): Integer severity for specific disability (1-4)
    - dr.types: List of disability type strings
    - dr.assessed: Boolean indicating if functional assessment exists
    """

    def __init__(self, env, partner):
        """Initialize DR symbol provider.

        Args:
            env: Odoo environment
            partner: res.partner record
        """
        self.env = env
        self.partner = partner
        self._cache = None
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy-load disability data from cache."""
        if self._loaded:
            return

        self._loaded = True
        self._cache = {
            "has_disability": False,
            "disability_types": [],
            "functional_scores": {},
            "assessed": False,
        }

        if not self.partner:
            return

        # Query disability status cache
        disability_status = self.env["spp.dci.disability.status"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("state", "in", ["active", "draft"]),
            ],
            limit=1,
        )

        if disability_status:
            self._cache["has_disability"] = disability_status.has_disability
            self._cache["disability_types"] = disability_status.get_disability_types_list()
            self._cache["functional_scores"] = disability_status.get_functional_scores_dict()
            self._cache["assessed"] = bool(disability_status.assessment_date)

    @property
    def has_disability(self):
        """Check if person has any disability.

        Returns:
            bool: True if person is registered as PWD
        """
        self._ensure_loaded()
        return self._cache.get("has_disability", False)

    @property
    def types(self):
        """Get list of disability types.

        Returns:
            list: List of disability type strings
        """
        self._ensure_loaded()
        return self._cache.get("disability_types", [])

    @property
    def assessed(self):
        """Check if functional assessment exists.

        Returns:
            bool: True if functional assessment was performed
        """
        self._ensure_loaded()
        return self._cache.get("assessed", False)

    def severity(self, disability_type):
        """Get severity for specific disability type.

        Args:
            disability_type: Type of disability (Vision, Hearing, Mobility, etc.)

        Returns:
            int: Severity score (1=No difficulty, 2=Some difficulty,
                 3=A lot of difficulty, 4=Cannot do)
        """
        self._ensure_loaded()
        scores = self._cache.get("functional_scores", {})
        return scores.get(disability_type, 1)

    def has_type(self, disability_type):
        """Check if person has specific disability type.

        Args:
            disability_type: Type of disability to check

        Returns:
            bool: True if person has this disability type
        """
        self._ensure_loaded()
        types_list = self._cache.get("disability_types", [])
        return disability_type in types_list

    def query_live(self):
        """Query DR registry live and update cache.

        This method bypasses the local cache and fetches data directly
        from the Disability Registry via DCI API, then updates the cache.

        Returns:
            bool: True if query succeeded and cache was updated
        """
        if not self.partner:
            return False

        try:
            from odoo.addons.spp_dci_client_dr.services import DRService

            data_source = _get_data_source_by_type(self.env, "dr")
            if not data_source:
                _logger.warning("[DR Symbol] No active DR data source configured")
                return False

            dr_service = DRService(self.env, data_source.code)
            dr_service.sync_disability_data(self.partner)

            # Reset cache to force reload
            self._loaded = False
            self._cache = None
            return True

        except ImportError:
            _logger.warning("[DR Symbol] spp_dci_client_dr module not available")
            return False
        except Exception as e:
            _logger.error("[DR Symbol] Live query failed: %s", str(e))
            return False


class CRVSSymbolProvider:
    """Civil Registration and Vital Statistics (CRVS) Symbol Provider.

    Provides CEL symbols for vital events:
    - crvs.is_alive: Boolean indicating if person is alive (no death event)
    - crvs.birth_verified: Boolean indicating if birth was registered
    - crvs.is_married: Boolean indicating current marital status
    - crvs.has_event(event_type): Check if specific event type exists
    """

    def __init__(self, env, partner):
        """Initialize CRVS symbol provider.

        Args:
            env: Odoo environment
            partner: res.partner record
        """
        self.env = env
        self.partner = partner
        self._cache = None
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy-load CRVS event data."""
        if self._loaded:
            return

        self._loaded = True
        self._cache = {
            "is_alive": True,
            "birth_verified": False,
            "is_married": False,
            "events": {},
        }

        if not self.partner:
            return

        # Query CRVS events
        events = self.env["spp.dci.crvs.event"].search(
            [
                ("person_id", "=", self.partner.id),
                ("state", "=", "processed"),
            ]
        )

        event_types = set()
        for event in events:
            event_types.add(event.event_type)
            self._cache["events"][event.event_type] = True

        # Check for death event
        if "death" in event_types:
            self._cache["is_alive"] = False

        # Check for birth registration
        if "birth" in event_types:
            self._cache["birth_verified"] = True

        # Check marital status
        if "marriage" in event_types and "divorce" not in event_types:
            self._cache["is_married"] = True
        elif "divorce" in event_types:
            self._cache["is_married"] = False

    @property
    def is_alive(self):
        """Check if person is alive (no death event).

        Returns:
            bool: True if no death event recorded
        """
        self._ensure_loaded()
        return self._cache.get("is_alive", True)

    @property
    def birth_verified(self):
        """Check if birth was registered in CRVS.

        Returns:
            bool: True if birth event exists
        """
        self._ensure_loaded()
        return self._cache.get("birth_verified", False)

    @property
    def is_married(self):
        """Check if person is currently married.

        Returns:
            bool: True if married (marriage event without divorce)
        """
        self._ensure_loaded()
        return self._cache.get("is_married", False)

    def has_event(self, event_type):
        """Check if specific event type exists.

        Args:
            event_type: Type of event (birth, death, marriage, divorce)

        Returns:
            bool: True if event exists
        """
        self._ensure_loaded()
        return self._cache.get("events", {}).get(event_type, False)

    def query_live(self, identifier_type: str = None, identifier_value: str = None):
        """Query CRVS registry live for vital events.

        This method fetches data directly from CRVS via DCI API.
        Note: Unlike DR, CRVS uses event-based updates via subscriptions,
        so live queries are typically for verification purposes.

        Args:
            identifier_type: Identifier type (e.g., 'UIN', 'BRN')
            identifier_value: Identifier value

        Returns:
            dict: Death status and birth verification info, or None on failure
        """
        if not self.partner:
            return None

        try:
            from odoo.addons.spp_dci_client_crvs.services import CRVSService

            data_source = _get_data_source_by_type(self.env, "crvs")
            if not data_source:
                _logger.warning("[CRVS Symbol] No active CRVS data source configured")
                return None

            # Get identifier from partner if not provided
            if not identifier_type or not identifier_value:
                reg_ids = self.env["spp.registry.id"].search(
                    [("partner_id", "=", self.partner.id)],
                    limit=1,
                )
                if reg_ids:
                    identifier_type = reg_ids[0].id_type_id.code
                    identifier_value = reg_ids[0].value
                else:
                    _logger.warning("[CRVS Symbol] No identifier found for partner")
                    return None

            crvs_service = CRVSService(self.env, data_source.code)

            # Check for death
            is_deceased = crvs_service.check_death(identifier_type, identifier_value)

            # Check for birth
            birth_data = crvs_service.verify_birth(identifier_type, identifier_value)

            result = {
                "is_alive": not is_deceased,
                "birth_verified": birth_data is not None,
                "birth_data": birth_data,
            }

            # Reset cache to force reload
            self._loaded = False
            self._cache = None

            return result

        except ImportError:
            _logger.warning("[CRVS Symbol] spp_dci_client_crvs module not available")
            return None
        except Exception as e:
            _logger.error("[CRVS Symbol] Live query failed: %s", str(e))
            return None


class IBRSymbolProvider:
    """Integrated Beneficiary Registry (IBR) Symbol Provider.

    Provides CEL symbols for enrollment and duplication data:
    - ibr.has_duplicate: Boolean indicating if duplication check found matches
    - ibr.is_enrolled(program): Check if enrolled in specific program
    - ibr.last_check_date: Date of last duplication check
    """

    def __init__(self, env, partner):
        """Initialize IBR symbol provider.

        Args:
            env: Odoo environment
            partner: res.partner record
        """
        self.env = env
        self.partner = partner
        self._cache = None
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy-load IBR duplication check data."""
        if self._loaded:
            return

        self._loaded = True
        self._cache = {
            "has_duplicate": False,
            "matched_programs": [],
            "last_check_date": None,
        }

        if not self.partner:
            return

        # Query latest duplication check
        duplication_check = self.env["spp.dci.duplication.check"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("state", "=", "completed"),
            ],
            order="check_date desc",
            limit=1,
        )

        if duplication_check:
            self._cache["has_duplicate"] = duplication_check.result in [
                "possible_match",
                "confirmed_match",
            ]
            self._cache["last_check_date"] = duplication_check.check_date

            # Parse matched programs from text field
            if duplication_check.matched_programs:
                programs = [p.strip() for p in duplication_check.matched_programs.split("\n") if p.strip()]
                self._cache["matched_programs"] = programs

    @property
    def has_duplicate(self):
        """Check if duplication check found matches.

        Returns:
            bool: True if possible or confirmed match found
        """
        self._ensure_loaded()
        return self._cache.get("has_duplicate", False)

    @property
    def last_check_date(self):
        """Get date of last duplication check.

        Returns:
            datetime: Date of last check, or None if no check performed
        """
        self._ensure_loaded()
        return self._cache.get("last_check_date")

    def is_enrolled(self, program_name):
        """Check if enrolled in specific program (based on duplication check).

        Args:
            program_name: Name of program to check

        Returns:
            bool: True if program found in matched programs
        """
        self._ensure_loaded()
        matched_programs = self._cache.get("matched_programs", [])
        # Case-insensitive partial match
        program_name_lower = program_name.lower()
        return any(program_name_lower in p.lower() for p in matched_programs)

    @property
    def matched_programs(self):
        """Get list of programs where duplicates were found.

        Returns:
            list: List of program names
        """
        self._ensure_loaded()
        return self._cache.get("matched_programs", [])

    def query_live(self):
        """Query IBR registry live for duplication check.

        This method performs a duplication check against the IBR via DCI API
        and stores the result in the local cache.

        Returns:
            dict: Duplication check result, or None on failure
        """
        if not self.partner:
            return None

        try:
            from odoo.addons.spp_dci_client_ibr.services import IBRService

            data_source = _get_data_source_by_type(self.env, "ibr")
            if not data_source:
                _logger.warning("[IBR Symbol] No active IBR data source configured")
                return None

            ibr_service = IBRService(data_source, self.env)
            result = ibr_service.check_duplication(self.partner)

            # Store result in duplication_check model
            check_vals = {
                "partner_id": self.partner.id,
                "check_date": self.env["ir.fields"].datetime.now(),
                "result": "confirmed_match" if result.get("is_duplicate") else "no_match",
                "matched_programs": "\n".join(result.get("matched_programs", [])),
                "state": "completed",
            }

            existing_check = self.env["spp.dci.duplication.check"].search(
                [("partner_id", "=", self.partner.id)],
                limit=1,
            )

            if existing_check:
                existing_check.write(check_vals)
            else:
                self.env["spp.dci.duplication.check"].create(check_vals)

            # Reset cache to force reload
            self._loaded = False
            self._cache = None

            return result

        except ImportError:
            _logger.warning("[IBR Symbol] spp_dci_client_ibr module not available")
            return None
        except Exception as e:
            _logger.error("[IBR Symbol] Live query failed: %s", str(e))
            return None


class SRSymbolProvider:
    """Social Registry (SR) Symbol Provider.

    Provides CEL symbols for external SR data when OpenSPP operates as MIS:
    - sr.is_registered: Boolean indicating if person exists in external SR
    - sr.program_count: Number of programs enrolled in
    - sr.enrolled_programs: List of program names
    - sr.is_enrolled(program): Check if enrolled in specific program
    - sr.household_id: Household ID from SR
    """

    def __init__(self, env, partner):
        """Initialize SR symbol provider.

        Args:
            env: Odoo environment
            partner: res.partner record
        """
        self.env = env
        self.partner = partner
        self._cache = None
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy-load SR data from local cache."""
        if self._loaded:
            return

        self._loaded = True
        self._cache = {
            "is_registered": False,
            "program_count": 0,
            "enrolled_programs": [],
            "household_id": None,
            "household_size": 0,
            "is_head_of_household": False,
        }

        if not self.partner:
            return

        # Check if SR client module is installed
        if "spp.dci.sr.record" not in self.env:
            _logger.debug("[SR Symbol] spp_dci_client_sr module not installed")
            return

        # Query SR record cache
        sr_record = self.env["spp.dci.sr.record"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("state", "=", "synced"),
                ("active", "=", True),
            ],
            order="last_sync_date desc",
            limit=1,
        )

        if sr_record:
            self._cache["is_registered"] = True
            self._cache["program_count"] = sr_record.program_count
            self._cache["enrolled_programs"] = sr_record.get_enrolled_programs()
            self._cache["household_id"] = sr_record.household_id
            self._cache["household_size"] = sr_record.household_size or 0
            self._cache["is_head_of_household"] = sr_record.is_head_of_household

    @property
    def is_registered(self):
        """Check if person is registered in external SR.

        Returns:
            bool: True if SR record exists
        """
        self._ensure_loaded()
        return self._cache.get("is_registered", False)

    @property
    def program_count(self):
        """Get number of programs enrolled in.

        Returns:
            int: Count of enrolled programs
        """
        self._ensure_loaded()
        return self._cache.get("program_count", 0)

    @property
    def enrolled_programs(self):
        """Get list of enrolled program names.

        Returns:
            list: List of program name strings
        """
        self._ensure_loaded()
        return self._cache.get("enrolled_programs", [])

    @property
    def household_id(self):
        """Get household ID from SR.

        Returns:
            str: Household identifier or None
        """
        self._ensure_loaded()
        return self._cache.get("household_id")

    @property
    def household_size(self):
        """Get household size from SR.

        Returns:
            int: Number of household members
        """
        self._ensure_loaded()
        return self._cache.get("household_size", 0)

    @property
    def is_head_of_household(self):
        """Check if person is head of household.

        Returns:
            bool: True if person is HoH
        """
        self._ensure_loaded()
        return self._cache.get("is_head_of_household", False)

    def is_enrolled(self, program_name):
        """Check if enrolled in specific program.

        Args:
            program_name: Name of program to check

        Returns:
            bool: True if enrolled in program
        """
        self._ensure_loaded()
        enrolled = self._cache.get("enrolled_programs", [])
        # Case-insensitive partial match
        program_name_lower = program_name.lower()
        return any(program_name_lower in p.lower() for p in enrolled)

    def query_live(self):
        """Query SR registry live and update local cache.

        This method fetches data directly from the external Social Registry
        via DCI API and stores the result in the local SR record cache.

        Returns:
            bool: True if query succeeded and cache was updated
        """
        if not self.partner:
            return False

        try:
            from odoo.addons.spp_dci_client_sr.services import SRService

            data_source = _get_data_source_by_type(self.env, "sr")
            if not data_source:
                _logger.warning("[SR Symbol] No active SR data source configured")
                return False

            # Get identifier from partner
            reg_ids = self.env["spp.registry.id"].search(
                [("partner_id", "=", self.partner.id)],
                limit=1,
            )
            if not reg_ids:
                _logger.warning("[SR Symbol] No identifier found for partner")
                return False

            identifier_type = reg_ids[0].id_type_id.code
            identifier_value = reg_ids[0].value

            sr_service = SRService(data_source, self.env)
            sr_service.sync_person_to_local(
                identifier_type,
                identifier_value,
                partner_id=self.partner.id,
            )

            # Reset cache to force reload
            self._loaded = False
            self._cache = None
            return True

        except ImportError:
            _logger.warning("[SR Symbol] spp_dci_client_sr module not available")
            return False
        except Exception as e:
            _logger.error("[SR Symbol] Live query failed: %s", str(e))
            return False
