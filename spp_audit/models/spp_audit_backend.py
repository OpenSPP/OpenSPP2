"""Abstract audit backend system.

Provides a pluggable backend architecture for audit logging. Multiple backends
can be active simultaneously, allowing audit logs to be written to database,
files, syslog, and external HTTP endpoints concurrently.
"""

import json
import logging
import os
import socket
import syslog
import threading
from datetime import UTC, datetime

import requests

from odoo import api, models

from ..tools.config import AuditConfig

_logger = logging.getLogger(__name__)


class AuditBackendRegistry:
    """Registry for audit backend instances.

    Maintains singleton instances of each backend type and handles
    dispatching audit entries to all enabled backends.

    Note on sequence numbers:
        Sequence numbers are per-process and reset on restart. In a
        multi-worker/multi-process Odoo deployment, different workers will
        have independent sequence counters. For truly unique identification,
        use the combination of (node, ts, seq) as a composite key.
    """

    _backends = {}
    _lock = threading.Lock()
    _sequence = 0
    _sequence_lock = threading.Lock()
    _node_id = None

    @classmethod
    def get_node_id(cls):
        """Get unique node identifier for this Odoo instance."""
        if cls._node_id is None:
            cls._node_id = socket.gethostname()
        return cls._node_id

    @classmethod
    def get_next_sequence(cls):
        """Get next monotonic sequence number (thread-safe).

        Note: Sequence is per-process and resets on restart. Use (node, ts, seq)
        tuple for unique identification across processes and restarts.
        """
        with cls._sequence_lock:
            cls._sequence += 1
            return cls._sequence

    @classmethod
    def register_backend(cls, backend_type, backend_instance):
        """Register a backend instance."""
        with cls._lock:
            cls._backends[backend_type] = backend_instance

    @classmethod
    def get_backend(cls, backend_type):
        """Get a registered backend instance."""
        with cls._lock:
            return cls._backends.get(backend_type)

    @classmethod
    def dispatch(cls, entry, env=None):
        """Dispatch an audit entry to all enabled backends.

        :param entry: Dict containing audit entry data (not modified)
        :param env: Odoo environment
        :return: Dict of backend_type -> result
        """
        results = {}
        enabled_backends = AuditConfig.get_enabled_backends(env)

        # Create enriched entry with metadata (don't mutate input)
        enriched_entry = {
            **entry,
            "seq": cls.get_next_sequence(),
            "ts": datetime.now(UTC).isoformat(),
            "node": cls.get_node_id(),
        }

        for backend_type in enabled_backends:
            backend_class = cls.get_backend(backend_type)
            if backend_class:
                try:
                    # Get the model from env if available
                    if env and hasattr(backend_class, "_name"):
                        backend = env[backend_class._name]
                        results[backend_type] = backend.write_entry(enriched_entry, env)
                    else:
                        # Without env, we cannot properly instantiate Odoo models
                        # Skip this backend and log a warning
                        _logger.debug("Skipping %s backend: no environment available", backend_type)
                        results[backend_type] = False
                except Exception as e:
                    _logger.exception("Failed to write to %s backend: %s", backend_type, e)
                    results[backend_type] = False

        return results


class SppAuditBackend(models.AbstractModel):
    """Abstract base class for audit backends.

    Subclasses must implement _write_entry() to handle the actual
    storage of audit entries.
    """

    _name = "spp.audit.backend"
    _description = "Abstract Audit Backend"

    @api.model
    def write_entry(self, entry, env=None):
        """Write an audit entry to this backend.

        :param entry: Dict containing audit entry data with keys:
            - seq: Sequence number
            - ts: ISO timestamp
            - node: Node identifier
            - rule_name: Name of the audit rule
            - model: Model name being audited
            - res_id: Record ID
            - method: Operation type (create/write/unlink/etc)
            - user_id: User ID performing the action
            - user_login: User login name
            - data: Dict with 'old' and 'new' values
        :param env: Odoo environment
        :return: True on success, False on failure
        """
        raise NotImplementedError("Subclasses must implement write_entry()")

    @api.model
    def is_enabled(self, env=None):
        """Check if this backend is enabled."""
        raise NotImplementedError("Subclasses must implement is_enabled()")


class SppAuditBackendDb(models.AbstractModel):
    """Database audit backend - stores logs in spp.audit.log model."""

    _name = "spp.audit.backend.db"
    _inherit = "spp.audit.backend"
    _description = "Database Audit Backend"

    @api.model
    def is_enabled(self, env=None):
        return AuditConfig.get_bool("backend_db", env=env)

    @api.model
    def write_entry(self, entry, env=None):
        """Write audit entry to database.

        This backend creates spp.audit.log records, maintaining
        compatibility with the existing UI and queries.
        """
        if env is None:
            env = self.env

        # The database backend is handled specially by the rule.log() method
        # which creates spp.audit.log records directly. This method is
        # provided for completeness but the main flow uses the original code.
        return True


class SppAuditBackendFile(models.AbstractModel):
    """File audit backend - writes JSONL to files."""

    _name = "spp.audit.backend.file"
    _inherit = "spp.audit.backend"
    _description = "File Audit Backend"

    _file_handle = None
    _file_lock = threading.Lock()
    _current_date = None

    @api.model
    def is_enabled(self, env=None):
        return AuditConfig.get_bool("backend_file", env=env)

    @classmethod
    def _get_file_path(cls, env=None):
        """Get the current audit file path based on date."""
        base_path = AuditConfig.get_file_path(env)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return os.path.join(base_path, f"audit-{today}.jsonl")

    @classmethod
    def _ensure_directory(cls, env=None):
        """Ensure the audit directory exists."""
        base_path = AuditConfig.get_file_path(env)
        if not os.path.exists(base_path):
            try:
                os.makedirs(base_path, mode=0o750)
                _logger.info("Created audit log directory: %s", base_path)
            except OSError as e:
                _logger.error("Failed to create audit directory %s: %s", base_path, e)
                raise

    @classmethod
    def _get_file_handle(cls, env=None):
        """Get file handle, rotating if needed."""
        today = datetime.utcnow().strftime("%Y-%m-%d")

        with cls._file_lock:
            # Check if we need to rotate
            if cls._current_date != today or cls._file_handle is None:
                # Close old handle
                if cls._file_handle is not None:
                    try:
                        cls._file_handle.close()
                    except OSError as e:
                        _logger.warning("Failed to close old audit file handle: %s", e)

                # Ensure directory exists
                cls._ensure_directory(env)

                # Open new file
                file_path = cls._get_file_path(env)
                cls._file_handle = open(file_path, "a", encoding="utf-8")
                cls._current_date = today
                _logger.info("Opened audit log file: %s", file_path)

            return cls._file_handle

    @api.model
    def write_entry(self, entry, env=None):
        """Write audit entry to JSONL file."""
        try:
            file_handle = self._get_file_handle(env)

            # Write JSON line
            with self._file_lock:
                json_line = json.dumps(entry, default=str, ensure_ascii=False)
                file_handle.write(json_line + "\n")
                file_handle.flush()  # Ensure immediate write for audit integrity

            return True

        except Exception as e:
            _logger.exception("Failed to write audit entry to file: %s", e)
            return False


class SppAuditBackendSyslog(models.AbstractModel):
    """Syslog audit backend - sends logs to syslog."""

    _name = "spp.audit.backend.syslog"
    _inherit = "spp.audit.backend"
    _description = "Syslog Audit Backend"

    _syslog_initialized = False

    @api.model
    def is_enabled(self, env=None):
        return AuditConfig.get_bool("backend_syslog", env=env)

    @classmethod
    def _init_syslog(cls, env=None):
        """Initialize syslog connection."""
        if cls._syslog_initialized:
            return

        facility_map = {
            "local0": syslog.LOG_LOCAL0,
            "local1": syslog.LOG_LOCAL1,
            "local2": syslog.LOG_LOCAL2,
            "local3": syslog.LOG_LOCAL3,
            "local4": syslog.LOG_LOCAL4,
            "local5": syslog.LOG_LOCAL5,
            "local6": syslog.LOG_LOCAL6,
            "local7": syslog.LOG_LOCAL7,
            "user": syslog.LOG_USER,
        }

        facility_name = AuditConfig.get("syslog_facility", env=env)
        facility = facility_map.get(facility_name, syslog.LOG_LOCAL0)

        syslog.openlog(ident="openspp-audit", logoption=syslog.LOG_PID, facility=facility)
        cls._syslog_initialized = True

    @api.model
    def write_entry(self, entry, env=None):
        """Write audit entry to syslog."""
        try:
            self._init_syslog(env)

            # Format as JSON for structured logging
            json_line = json.dumps(entry, default=str, ensure_ascii=False)
            syslog.syslog(syslog.LOG_INFO, json_line)

            return True

        except Exception as e:
            _logger.exception("Failed to write audit entry to syslog: %s", e)
            return False


class SppAuditBackendHttp(models.AbstractModel):
    """HTTP webhook audit backend - sends logs to external endpoint."""

    _name = "spp.audit.backend.http"
    _inherit = "spp.audit.backend"
    _description = "HTTP Webhook Audit Backend"

    @api.model
    def is_enabled(self, env=None):
        if not AuditConfig.get_bool("backend_http", env=env):
            return False
        # Also check that endpoint is configured
        endpoint = AuditConfig.get("http_endpoint", env=env)
        return bool(endpoint)

    @api.model
    def write_entry(self, entry, env=None):
        """Write audit entry to HTTP endpoint."""
        endpoint = AuditConfig.get("http_endpoint", env=env)
        if not endpoint:
            return False

        timeout = AuditConfig.get_int("http_timeout", default=5, env=env)

        # Build headers with optional authentication
        headers = {
            "Content-Type": "application/json",
            "X-OpenSPP-Audit": "1",
        }

        # Add authentication header if configured
        auth_header = AuditConfig.get("http_auth_header", env=env)
        if auth_header:
            headers["Authorization"] = auth_header

        try:
            response = requests.post(
                endpoint,
                json=entry,
                timeout=timeout,
                headers=headers,
            )
            response.raise_for_status()
            return True

        except requests.exceptions.Timeout:
            _logger.warning("HTTP audit backend timeout for endpoint: %s", endpoint)
            return False
        except requests.exceptions.RequestException as e:
            _logger.exception("Failed to write audit entry to HTTP endpoint: %s", e)
            return False


# Initialize backend registry at module load
def _init_backends():
    """Initialize backend singletons in registry."""
    AuditBackendRegistry.register_backend("db", SppAuditBackendDb)
    AuditBackendRegistry.register_backend("file", SppAuditBackendFile)
    AuditBackendRegistry.register_backend("syslog", SppAuditBackendSyslog)
    AuditBackendRegistry.register_backend("http", SppAuditBackendHttp)


_init_backends()
