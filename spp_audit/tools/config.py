"""Audit configuration manager with tamper-resistant settings.

Configuration is read with the following priority (highest to lowest):
1. Environment variables (OPENSPP_AUDIT_*)
2. Config file (odoo.conf) settings (spp_audit_*)
3. Database settings (ir.config_parameter) - only if not locked by higher levels

Settings locked by config file or environment variables CANNOT be overridden
via database, preventing DBA tampering of critical audit settings.
"""

import logging
import os

from odoo.tools import config

_logger = logging.getLogger(__name__)

# Default configuration values
DEFAULTS = {
    "force_enabled": False,
    "backend_db": True,
    "backend_file": False,
    "backend_syslog": False,
    "backend_http": False,
    "file_path": "/var/log/openspp/audit",
    "file_format": "jsonl",
    "file_rotation": "daily",
    "file_max_size_mb": 100,
    "syslog_host": "localhost",
    "syslog_port": 514,
    "syslog_facility": "local0",
    "http_endpoint": "",
    "http_timeout": 5,
    "http_auth_header": "",  # e.g., "Bearer <token>" or "ApiKey <key>"
    "mandatory_models": "",  # Empty by default - no mandatory models enforced
    "mail_thread_default": False,
    "sequence_file": ".audit_sequence",
}

# Keys that can be set via config file and become locked
LOCKABLE_KEYS = {
    "force_enabled",
    "backend_db",
    "backend_file",
    "backend_syslog",
    "backend_http",
    "file_path",
    "mandatory_models",
    "mail_thread_default",
}


def _parse_bool(value):
    """Parse a boolean value from string."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


def _parse_int(value, default=0):
    """Parse an integer value from string."""
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_list(value):
    """Parse a comma-separated list from string."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


class AuditConfig:
    """Audit configuration manager with priority-based settings."""

    _cache = {}
    _locked_keys = None

    @classmethod
    def _get_env_key(cls, key):
        """Get environment variable name for a config key."""
        return f"OPENSPP_AUDIT_{key.upper()}"

    @classmethod
    def _get_conf_key(cls, key):
        """Get odoo.conf key for a config key."""
        return f"spp_audit_{key}"

    @classmethod
    def _get_param_key(cls, key):
        """Get ir.config_parameter key for a config key."""
        return f"spp_audit.{key}"

    @classmethod
    def get_raw(cls, key, default=None):
        """Get raw config value without type conversion.

        Priority: Environment > Config file > Default
        Does not check database (use get() for full lookup).
        """
        # 1. Environment variable (highest priority)
        env_key = cls._get_env_key(key)
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return env_value

        # 2. Config file
        conf_key = cls._get_conf_key(key)
        conf_value = config.get(conf_key)
        if conf_value is not None:
            return conf_value

        # 3. Default
        return default if default is not None else DEFAULTS.get(key)

    @classmethod
    def is_locked(cls, key):
        """Check if a setting is locked by config file or environment.

        Locked settings cannot be overridden via database.
        """
        if key not in LOCKABLE_KEYS:
            return False

        # Check environment
        env_key = cls._get_env_key(key)
        if os.environ.get(env_key) is not None:
            return True

        # Check config file
        conf_key = cls._get_conf_key(key)
        if config.get(conf_key) is not None:
            return True

        return False

    @classmethod
    def get(cls, key, default=None, env=None):
        """Get config value with full priority lookup.

        Priority: Environment > Config file > Database > Default

        :param key: Configuration key
        :param default: Default value if not found
        :param env: Odoo environment (needed for database lookup)
        :return: Configuration value
        """
        # Get from environment or config file first
        value = cls.get_raw(key, None)
        if value is not None:
            return value

        # 3. Database (ir.config_parameter) - only if not locked and env provided
        if env is not None and not cls.is_locked(key):
            param_key = cls._get_param_key(key)
            try:
                db_value = (
                    env["ir.config_parameter"].sudo().get_param(param_key)  # nosemgrep: odoo-sudo-without-context
                )  # nosemgrep: odoo-sudo-without-context
                if db_value is not None:
                    return db_value
            except (AttributeError, KeyError, RuntimeError):
                # Database might not be available during module load
                _logger.debug("Could not read config param %s from database", param_key)

        # 4. Default
        return default if default is not None else DEFAULTS.get(key)

    @classmethod
    def get_bool(cls, key, default=None, env=None):
        """Get boolean config value."""
        value = cls.get(key, default, env)
        return _parse_bool(value)

    @classmethod
    def get_int(cls, key, default=None, env=None):
        """Get integer config value."""
        value = cls.get(key, default, env)
        return _parse_int(value, default or DEFAULTS.get(key, 0))

    @classmethod
    def get_list(cls, key, default=None, env=None):
        """Get list config value (comma-separated in string form)."""
        value = cls.get(key, default, env)
        return _parse_list(value)

    @classmethod
    def is_audit_enabled(cls, env=None):
        """Check if audit is enabled (cannot be disabled if force_enabled)."""
        if cls.get_bool("force_enabled", env=env):
            return True
        return cls.get_bool("backend_db", env=env) or cls.get_bool("backend_file", env=env)

    @classmethod
    def is_model_mandatory(cls, model_name, env=None):
        """Check if a model is in the mandatory audit list."""
        mandatory = cls.get_list("mandatory_models", env=env)
        return model_name in mandatory

    @classmethod
    def get_enabled_backends(cls, env=None):
        """Get list of enabled backend types."""
        backends = []
        if cls.get_bool("backend_db", env=env):
            backends.append("db")
        if cls.get_bool("backend_file", env=env):
            backends.append("file")
        if cls.get_bool("backend_syslog", env=env):
            backends.append("syslog")
        if cls.get_bool("backend_http", env=env):
            backends.append("http")
        return backends

    @classmethod
    def get_file_path(cls, env=None):
        """Get the audit file path."""
        return cls.get("file_path", env=env)

    @classmethod
    def get_locked_settings(cls):
        """Get dict of all locked settings and their values."""
        locked = {}
        for key in LOCKABLE_KEYS:
            if cls.is_locked(key):
                locked[key] = cls.get_raw(key)
        return locked

    @classmethod
    def log_config_status(cls, env=None):
        """Log current configuration status for debugging."""
        _logger.info("Audit configuration status:")
        _logger.info("  Enabled backends: %s", cls.get_enabled_backends(env))
        _logger.info("  Force enabled: %s", cls.get_bool("force_enabled", env=env))
        _logger.info("  Mandatory models: %s", cls.get_list("mandatory_models", env=env))
        _logger.info("  Locked settings: %s", list(cls.get_locked_settings().keys()))
        if cls.get_bool("backend_file", env=env):
            _logger.info("  File path: %s", cls.get_file_path(env))
