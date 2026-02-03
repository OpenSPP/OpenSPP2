import copy
import json
import logging
import os

from odoo import api, models
from odoo.tools.misc import file_path

_logger = logging.getLogger(__name__)


# Profile caching support
_profile_cache = {}
_profile_cache_enabled = True


def invalidate_profile_cache():
    """Clear the profile configuration cache."""
    global _profile_cache
    _profile_cache.clear()
    _logger.info("[CEL Registry] Profile cache cleared")


DEFAULT_PRESETS = {
    "registry_individuals": {
        "root_model": "res.partner",
        "base_domain": [["is_registrant", "=", True], ["is_group", "=", False]],
        "m2o_name_match": "equals",
        "symbols": {
            "r": {"model": "res.partner"},  # ADR-008: 'r' for current record
            "enrollments": {
                "relation": "rel",
                "through": "spp.program.membership",
                "parent": "partner_id",
                "link_field": "id",
                "child_model": "spp.program.membership",
            },
            "entitlements": {
                "relation": "rel",
                "through": "spp.entitlement",
                "parent": "partner_id",
                "link_field": "id",
                "child_model": "spp.entitlement",
            },
        },
    },
    "registry_groups": {
        "root_model": "res.partner",
        "base_domain": [["is_registrant", "=", True], ["is_group", "=", True]],
        "m2o_name_match": "equals",
        "symbols": {
            "r": {"model": "res.partner"},  # ADR-008: 'r' for current record
            "members": {
                "relation": "rel",
                "through": "spp.group.membership",
                "parent": "group",
                "link_to": "individual",
                "default_domain": [["is_ended", "=", False]],
            },
            "enrollments": {
                "relation": "rel",
                "through": "spp.program.membership",
                "parent": "partner_id",
                "link_field": "id",
                "child_model": "spp.program.membership",
            },
            "entitlements": {
                "relation": "rel",
                "through": "spp.entitlement",
                "parent": "partner_id",
                "link_field": "id",
                "child_model": "spp.entitlement",
            },
        },
        "roles": {"head": ["Head", "Household Head", "HoH"]},
    },
    "program_memberships": {
        "root_model": "spp.program.membership",
        "symbols": {
            "r": {"model": "spp.program.membership"},  # ADR-008: 'r' for current record
            "registrant": {"relation": "many2one", "field": "partner_id", "model": "res.partner"},
            "program": {"relation": "many2one", "field": "program_id", "model": "spp.program"},
        },
    },
    "entitlements": {
        "root_model": "spp.entitlement",
        "symbols": {
            "r": {"model": "spp.entitlement"},  # ADR-008: 'r' for current record
            "registrant": {"relation": "many2one", "field": "partner_id", "model": "res.partner"},
            "program": {"relation": "many2one", "field": "program_id", "model": "spp.program"},
        },
    },
    "grm_tickets": {
        "root_model": "spp.grm.ticket",
        "description": "GRM Ticket evaluation context with time-based helper functions",
        "symbols": {
            "ticket": {"model": "spp.grm.ticket"},
            "r": {"model": "spp.grm.ticket"},  # ADR-008: 'r' alias for current record
            "category": {"relation": "many2one", "field": "category_id", "model": "spp.grm.category"},
            "channel": {"relation": "many2one", "field": "channel_id", "model": "spp.grm.channel"},
            "stage": {"relation": "many2one", "field": "stage_id", "model": "spp.grm.stage"},
            "partner": {"relation": "many2one", "field": "partner_id", "model": "res.partner"},
            "team": {"relation": "many2one", "field": "team_id", "model": "spp.grm.team"},
            "user": {"relation": "many2one", "field": "user_id", "model": "res.users"},
        },
        "functions": [
            "days_since",
            "hours_since",
            "is_business_day",
        ],
        "context_fields": [
            "severity",
            "priority",
            "sla_status",
            "days_open",
            "is_escalated",
        ],
    },
}


class CelRegistry(models.AbstractModel):
    _name = "spp.cel.registry"
    _description = "CEL Symbol Registry"

    @api.model
    def load_profile(self, profile: str, force_reload: bool = False) -> dict:
        """
        Load a CEL profile configuration from multiple sources (in priority order):
        1. System parameter (ir.config_parameter) - highest priority
        2. YAML file in module's data/ directory
        3. Hardcoded DEFAULT_PRESETS - lowest priority (fallback)

        YAML profiles override/merge with defaults.

        Args:
            profile: Profile name to load
            force_reload: If True, bypass cache and reload from source
        """
        global _profile_cache, _profile_cache_enabled

        # Create cache key including company context
        company_id = self.env.company.id if hasattr(self.env, "company") else None
        cache_key = (profile, company_id)

        # Check cache first (unless force_reload)
        if not force_reload and _profile_cache_enabled and cache_key in _profile_cache:
            _logger.debug(f"[CEL Registry] Using cached profile '{profile}' (company: {company_id})")
            return copy.deepcopy(_profile_cache[cache_key])  # Return deep copy to prevent mutation

        # Priority 1: System parameter (for admin customization)
        params = self.env["ir.config_parameter"]
        key = f"cel_domain.profile.{profile}"
        raw = params.sudo().get_param(key)
        if raw:
            try:
                config = json.loads(raw)
                _logger.info(f"[CEL Registry] Loaded profile '{profile}' from system parameter")
                # Cache the result
                if _profile_cache_enabled:
                    _profile_cache[cache_key] = copy.deepcopy(config)
                return copy.deepcopy(config)
            except Exception as e:
                _logger.warning(f"[CEL Registry] Failed to parse system parameter for profile '{profile}': {e}")

        # Priority 2: YAML file (for deployment customization)
        yaml_config = self._load_yaml_profiles()
        if yaml_config and profile in yaml_config:
            yaml_profile = yaml_config[profile]
            # Merge with defaults (YAML overrides defaults)
            default_profile = DEFAULT_PRESETS.get(profile, {})
            merged = self._deep_merge(default_profile, yaml_profile)
            _logger.info(f"[CEL Registry] Loaded profile '{profile}' from YAML (merged with defaults)")
            # Cache the result
            if _profile_cache_enabled:
                _profile_cache[cache_key] = copy.deepcopy(merged)
            return copy.deepcopy(merged)

        # Priority 3: Hardcoded defaults (fallback)
        if profile in DEFAULT_PRESETS:
            _logger.debug(f"[CEL Registry] Using hardcoded defaults for profile '{profile}'")
            result = DEFAULT_PRESETS[profile]
            # Cache the result
            if _profile_cache_enabled:
                _profile_cache[cache_key] = copy.deepcopy(result)
            return copy.deepcopy(result)

        _logger.warning(f"[CEL Registry] Profile '{profile}' not found in any source")
        return {}

    @api.model
    def _load_yaml_profiles(self) -> dict:
        """
        Load profile configurations from YAML files in ALL installed modules.

        Scans for 'data/cel_profiles.yaml' in every installed module,
        allowing modules to contribute CEL profiles without depending on cel_domain.

        Returns dict of profile_name -> config, or empty dict if no profiles found.
        Later modules can override profiles from earlier modules.
        """
        try:
            # Try importing PyYAML
            try:
                import yaml
            except ImportError:
                _logger.warning("[CEL Registry] PyYAML not installed, YAML configuration disabled")
                return {}

            all_profiles = {}
            modules_with_profiles = []

            # First, load from cel_domain itself (for backward compatibility)
            module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cel_domain_yaml = os.path.join(module_path, "data", "cel_symbols.template.yaml")

            if os.path.exists(cel_domain_yaml):
                try:
                    with open(cel_domain_yaml, encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if data and isinstance(data, dict):
                            presets = data.get("presets", {})
                            if presets:
                                all_profiles.update(presets)
                                modules_with_profiles.append("cel_domain")
                except Exception as e:
                    _logger.warning(f"[CEL Registry] Error loading cel_domain YAML: {e}")

            # Then, scan ALL installed modules for cel_profiles.yaml
            try:
                # Get all installed modules
                IrModule = self.env["ir.module.module"]
                installed_modules = IrModule.search([("state", "=", "installed")])

                for module in installed_modules:
                    if module.name == "cel_domain":
                        continue  # Already loaded above

                    try:
                        # Look for cel_profiles.yaml in this module using the supported helper
                        yaml_path = file_path(f"{module.name}/data/cel_profiles.yaml")

                        with open(yaml_path, encoding="utf-8") as f:
                            data = yaml.safe_load(f)

                        if data and isinstance(data, dict):
                            presets = data.get("presets", {})
                            if presets and isinstance(presets, dict):
                                # Merge profiles from this module
                                all_profiles.update(presets)
                                modules_with_profiles.append(module.name)
                                _logger.info(  # nosemgrep: odoo-pii-fstring-name - Logs module names for CEL profiles, not person names.
                                    f"[CEL Registry] Loaded {len(presets)} profile(s) from {module.name}"
                                )
                    except FileNotFoundError:
                        # Module does not expose CEL profiles; skip quietly
                        continue
                    except Exception as e:
                        _logger.debug(  # nosemgrep: odoo-pii-fstring-name - Logs module names for CEL profiles, not person names.
                            f"[CEL Registry] No CEL profiles in {module.name}: {e}"
                        )

            except Exception as e:
                _logger.warning(f"[CEL Registry] Error scanning modules for profiles: {e}")

            if all_profiles:
                _logger.info(
                    f"[CEL Registry] Loaded {len(all_profiles)} profile(s) from YAML: "
                    f"{list(all_profiles.keys())} (from modules: {', '.join(modules_with_profiles)})"
                )
            else:
                _logger.debug("[CEL Registry] No YAML profiles found in any module")

            return all_profiles

        except Exception as e:
            _logger.error(f"[CEL Registry] Error loading YAML profiles: {e}", exc_info=True)
            return {}

    @api.model
    def _deep_merge(self, base: dict, override: dict) -> dict:
        """
        Deep merge two dictionaries. Override values take precedence.
        Used to merge YAML profiles with hardcoded defaults.
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dicts
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override takes precedence
                result[key] = value

        return result

    @api.model
    def invalidate_cache(self):
        """Invalidate the profile cache. Call when system parameters change."""
        invalidate_profile_cache()

    @api.model
    def profile_root_model(self, profile: str) -> str:
        cfg = self.load_profile(profile)
        return cfg.get("root_model")
