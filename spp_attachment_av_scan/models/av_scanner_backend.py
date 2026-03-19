import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

try:
    import pyclamd
except ImportError:
    pyclamd = None
    _logger.warning("pyclamd library not found. Antivirus scanning will not work.")


class AVScannerBackend(models.Model):
    _name = "spp.av.scanner.backend"
    _description = "Antivirus Scanner Backend"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        help="Name of the antivirus scanner backend",
    )
    sequence = fields.Integer(
        default=10,
        help="Sequence for ordering scanner backends",
    )
    backend_type = fields.Selection(
        [
            ("clamd_socket", "ClamAV Unix Socket"),
            ("clamd_network", "ClamAV Network"),
        ],
        required=True,
        default="clamd_socket",
        help="Type of antivirus scanner backend",
    )
    is_active = fields.Boolean(
        default=True,
        help="Whether this scanner backend is active and should be used for scanning",
    )

    # ClamAV settings
    clamd_socket_path = fields.Char(
        string="ClamAV Socket Path",
        default="/var/run/clamav/clamd.sock",
        help="Path to ClamAV Unix socket",
    )
    clamd_host = fields.Char(
        string="ClamAV Host",
        default="localhost",
        help="Hostname or IP address of ClamAV daemon",
    )
    clamd_port = fields.Integer(
        string="ClamAV Port",
        default=3310,
        help="Port number of ClamAV daemon",
    )

    # Limits
    max_file_size_mb = fields.Integer(
        string="Max File Size (MB)",
        default=100,
        help="Maximum file size to scan in megabytes. Files larger than this will be skipped.",
    )
    scan_timeout_seconds = fields.Integer(
        string="Scan Timeout (seconds)",
        default=60,
        help="Maximum time to wait for scan completion",
    )

    # Statistics
    last_connection_test_date = fields.Datetime(
        string="Last Connection Test",
        readonly=True,
    )
    last_connection_test_result = fields.Boolean(
        string="Last Test Result",
        readonly=True,
    )
    last_connection_error = fields.Text(
        string="Last Connection Error",
        readonly=True,
    )

    @api.constrains("max_file_size_mb")
    def _check_max_file_size(self):
        """Validate max file size is positive."""
        for record in self:
            if record.max_file_size_mb <= 0:
                raise ValidationError(_("Maximum file size must be greater than zero."))

    @api.constrains("scan_timeout_seconds")
    def _check_scan_timeout(self):
        """Validate scan timeout is positive."""
        for record in self:
            if record.scan_timeout_seconds <= 0:
                raise ValidationError(_("Scan timeout must be greater than zero."))

    @api.constrains("clamd_port")
    def _check_clamd_port(self):
        """Validate ClamAV port is in valid range."""
        for record in self:
            if record.backend_type == "clamd_network":
                if not (1 <= record.clamd_port <= 65535):
                    raise ValidationError(_("ClamAV port must be between 1 and 65535."))

    def _get_scanner_instance(self):
        """Get pyclamd scanner instance based on backend type.

        Returns:
            pyclamd instance or None if unavailable

        Raises:
            UserError: If pyclamd library is not installed or connection fails
        """
        self.ensure_one()

        if not pyclamd:
            raise UserError(_("The pyclamd library is not installed. " "Please install it to use antivirus scanning."))

        try:
            if self.backend_type == "clamd_socket":
                _logger.info("Connecting to ClamAV via Unix socket: %s", self.clamd_socket_path)
                scanner = pyclamd.ClamdUnixSocket(filename=self.clamd_socket_path)
            else:  # clamd_network
                _logger.info(
                    "Connecting to ClamAV via network: %s:%s",
                    self.clamd_host,
                    self.clamd_port,
                )
                scanner = pyclamd.ClamdNetworkSocket(
                    host=self.clamd_host,
                    port=self.clamd_port,
                    timeout=self.scan_timeout_seconds,
                )

            # Test if we can ping the scanner
            if not scanner.ping():
                raise UserError(
                    _(
                        "Cannot connect to ClamAV daemon. "
                        "Please check the scanner configuration and ensure ClamAV is running."
                    )
                )

            return scanner

        except Exception as error:
            _logger.error(
                "Failed to connect to ClamAV backend '%s': %s",
                self.name,
                str(error),
                exc_info=True,
            )
            raise UserError(
                _(
                    "Failed to connect to ClamAV daemon: %(error)s",
                    error=str(error),
                )
            ) from error

    def scan_binary(self, binary_data, filename=None):
        """Scan binary data for malware.

        Args:
            binary_data: Binary data to scan
            filename: Optional filename for logging purposes

        Returns:
            dict with keys:
                - status: 'clean', 'infected', 'error', or 'skipped'
                - threat_name: Name of detected threat (if infected)
                - details: Additional details about the scan result
        """
        self.ensure_one()

        if not self.is_active:
            _logger.warning("Scanner backend '%s' is not active, skipping scan", self.name)
            return {
                "status": "skipped",
                "threat_name": None,
                "details": "Scanner backend is not active",
            }

        # Check file size
        file_size_mb = len(binary_data) / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            _logger.info(
                "File size (%.2f MB) exceeds maximum (%.2f MB), skipping scan",
                file_size_mb,
                self.max_file_size_mb,
            )
            return {
                "status": "skipped",
                "threat_name": None,
                "details": f"File size ({file_size_mb:.2f} MB) exceeds maximum ({self.max_file_size_mb} MB)",
            }

        try:
            scanner = self._get_scanner_instance()

            _logger.info(
                "Scanning binary data (%.2f MB)%s",
                file_size_mb,
                f" for file: {filename}" if filename else "",
            )

            # Scan the binary data
            scan_result = scanner.scan_stream(binary_data)

            if scan_result is None:
                # Clean file
                _logger.info("Scan completed: file is clean")
                return {
                    "status": "clean",
                    "threat_name": None,
                    "details": "No malware detected",
                }
            else:
                # Infected file
                # pyclamd scan_stream returns: {'stream': ('FOUND', 'ThreatName')}
                stream_result = scan_result.get("stream", (None, "Unknown"))
                threat_name = stream_result[1] if len(stream_result) > 1 else "Unknown"
                _logger.warning(
                    "Malware detected: %s",
                    threat_name,
                )
                return {
                    "status": "infected",
                    "threat_name": threat_name,
                    "details": f"Malware detected: {threat_name}",
                }

        except UserError:
            # Re-raise UserError (connection issues, etc.)
            raise
        except Exception as error:
            _logger.error(
                "Error during malware scan: %s",
                str(error),
                exc_info=True,
            )
            return {
                "status": "error",
                "threat_name": None,
                "details": f"Scan error: {str(error)}",
            }

    def test_connection(self):
        """Test connection to the scanner backend.

        Returns:
            bool: True if connection successful, False otherwise
        """
        self.ensure_one()

        try:
            scanner = self._get_scanner_instance()
            version = scanner.version()

            self.write(
                {
                    "last_connection_test_date": fields.Datetime.now(),
                    "last_connection_test_result": True,
                    "last_connection_error": None,
                }
            )

            _logger.info(
                "Connection test successful for backend '%s'. ClamAV version: %s",
                self.name,
                version,
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Successful"),
                    "message": _(
                        "Successfully connected to ClamAV daemon.\nVersion: %(version)s",
                        version=version,
                    ),
                    "type": "success",
                    "sticky": False,
                },
            }

        except Exception as error:
            error_msg = str(error)
            self.write(
                {
                    "last_connection_test_date": fields.Datetime.now(),
                    "last_connection_test_result": False,
                    "last_connection_error": error_msg,
                }
            )

            _logger.error(
                "Connection test failed for backend '%s': %s",
                self.name,
                error_msg,
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Failed"),
                    "message": _(
                        "Failed to connect to ClamAV daemon:\n%(error)s",
                        error=error_msg,
                    ),
                    "type": "danger",
                    "sticky": True,
                },
            }

    @api.model
    def get_active_scanner(self):
        """Get the first active scanner backend.

        Returns:
            AVScannerBackend record or empty recordset
        """
        return self.search([("is_active", "=", True)], limit=1, order="sequence, id")
