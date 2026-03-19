# OpenSPP Attachment Antivirus Scan

System-wide antivirus scanning for file attachments in OpenSPP.

## Overview

This module provides automatic malware scanning for all file attachments uploaded to the
system using ClamAV antivirus engine. It integrates with the `queue_job` module for
asynchronous scanning to avoid blocking file uploads.

## Features

- **Automatic Scanning**: All binary attachments are automatically queued for malware
  scanning upon upload
- **Configurable Backends**: Support for ClamAV via Unix socket or network connection
- **Quarantine**: Infected files are automatically quarantined and access is blocked
- **Security Notifications**: Security administrators are notified when malware is
  detected
- **Manual Rescans**: Administrators can manually trigger rescans of attachments
- **File Size Limits**: Configurable maximum file size to avoid scanning large files
- **Scan Timeouts**: Configurable timeout to prevent long-running scans

## Dependencies

- `base`: Odoo base module
- `queue_job`: For asynchronous job processing
- `spp_security`: OpenSPP security module for security groups
- `pyclamd`: Python library for ClamAV integration (external)

## Installation

1. Install ClamAV on your server:

   ```bash
   # Ubuntu/Debian
   sudo apt-get install clamav clamav-daemon

   # Start the daemon
   sudo systemctl start clamav-daemon
   sudo systemctl enable clamav-daemon
   ```

2. Install the Python library:

   ```bash
   pip install pyclamd
   ```

3. Install the module in Odoo:
   - Update the apps list
   - Search for "OpenSPP Attachment Antivirus Scan"
   - Click Install

## Configuration

### Scanner Backend Setup

1. Go to **Settings > Technical > Antivirus Scanners**
2. Edit the "Default ClamAV Scanner" record
3. Configure the connection settings:
   - **Backend Type**: Choose "ClamAV Unix Socket" or "ClamAV Network"
   - **Socket Path**: Path to ClamAV socket (default: `/var/run/clamav/clamd.sock`)
   - Or **Host/Port**: Network connection details
   - **Max File Size**: Maximum file size to scan in MB (default: 100)
   - **Scan Timeout**: Maximum time for scan in seconds (default: 60)
4. Enable the backend by toggling the "Active" button
5. Click "Test Connection" to verify the configuration

### Security Groups

- **Antivirus Administrator** (`group_av_admin`): Can manage scanner backends and view
  detailed scan results

## Usage

### Automatic Scanning

When a user uploads a file:

1. The attachment is created immediately
2. A scan job is queued in the background
3. The scan status shows "Pending Scan"
4. Once scanned, the status updates to:
   - **Clean**: No malware detected
   - **Infected**: Malware detected (file is quarantined)
   - **Error**: Scan failed
   - **Skipped**: File too large or no scanner configured

### Viewing Scan Status

Scan status is visible on the attachment form and list views:

- Navigate to any attachment (e.g., in Documents or via Technical > Attachments)
- Check the "Antivirus Scan" section for scan status and details

### Manual Rescans

As an AV Administrator:

1. Open an attachment
2. Click the "Rescan" button
3. The file is queued for scanning

### Infected Files

When malware is detected:

1. The file is marked as "Infected"
2. The threat name is recorded
3. The file is quarantined (access to file data is blocked)
4. Security administrators receive an activity notification
5. The file cannot be downloaded until reviewed

## Technical Details

### Models

#### `spp.av.scanner.backend`

Stores configuration for antivirus scanner backends.

**Key Fields**:

- `backend_type`: Type of scanner (ClamAV socket or network)
- `is_active`: Whether this backend is active
- `clamd_socket_path`: Path to ClamAV Unix socket
- `clamd_host`, `clamd_port`: Network connection details
- `max_file_size_mb`: Maximum file size to scan
- `scan_timeout_seconds`: Scan timeout

**Key Methods**:

- `scan_binary(binary_data, filename)`: Scan binary data for malware
- `test_connection()`: Test connection to scanner
- `get_active_scanner()`: Get the active scanner backend

#### `ir.attachment` (inherited)

Extended with antivirus scan fields and logic.

**New Fields**:

- `scan_status`: Status of malware scan
- `scan_date`: When the file was scanned
- `scan_result`: Detailed scan result (JSON)
- `threat_name`: Name of detected threat
- `is_quarantined`: Whether file is quarantined

**Key Methods**:

- `_scan_for_malware()`: Async job to scan attachment
- `_quarantine()`: Quarantine infected file
- `_notify_security_admins()`: Notify admins of infection
- `action_rescan()`: Manually trigger rescan

### Queue Jobs

The module uses `queue_job` for asynchronous scanning:

- Scans are queued when attachments are created or updated
- Priority 20 for automatic scans, priority 10 for manual rescans
- Jobs are named "Scan attachment {id} for malware"

### Security

- AV Administrators can manage scanner backends
- All users can view scan status on their attachments
- Quarantined files block access to binary data via `read()` override

## Logging

The module uses structured logging:

- Info level: Scan results, connection tests
- Warning level: Malware detections, configuration issues
- Error level: Scan failures, connection errors

No PII (personally identifiable information) is logged.

## Performance Considerations

- File scanning is asynchronous via queue_job
- Large files can be skipped via `max_file_size_mb` setting
- Scan timeouts prevent long-running operations
- Failed scans don't block file uploads

## Limitations

- Currently only supports ClamAV
- Requires ClamAV daemon to be running
- Files are scanned after upload (not during)
- Very large files may be skipped

## Future Enhancements

- Support for additional antivirus engines
- Real-time scanning before upload completion
- Scan result caching
- Scheduled rescans of all attachments
- Quarantine management interface
- Detailed scan statistics and reports

## License

LGPL-3

## Author

OpenSPP.org

## Maintainers

- jeremi
- gonzalesedwin1123
- reichie020212
