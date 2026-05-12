Scans uploaded file attachments for malware using ClamAV antivirus engine. Automatically queues scans for binary attachments on create or update using queue_job. Quarantines infected files by encrypting them with spp_encryption and removing original data. Provides forensic tools for security administrators to restore false positives or download quarantined files for analysis.

### Key Capabilities

- Auto-scan binary attachments on upload or update via background jobs
- Quarantine infected files with encrypted backup and SHA256 hash verification
- Block read access to quarantined attachment data
- Manual rescan, restore, forensic download, and permanent deletion of quarantined files
- Notify security administrators when malware is detected
- Scheduled cleanup of old quarantined files and forensic downloads
- Support ClamAV via Unix socket or network connection

### Key Models

| Model                    | Description                                              |
| ------------------------ | -------------------------------------------------------- |
| `spp.av.scanner.backend` | Configures ClamAV connection (socket/network) and limits |
| `ir.attachment`          | Extended with scan status, threat name, and quarantine   |

### Configuration

After installing:

1. Navigate to **Settings > Administration > Antivirus Scanners**
2. Create a scanner backend with ClamAV connection details (default: `/var/run/clamav/clamd.sock`)
3. Click **Test Connection** to verify ClamAV is running
4. Set **Active** to enable scanning
5. Configure system parameters:
   - `spp_attachment_av_scan.quarantine_encryption_provider_id`: Encryption provider for quarantine
   - `spp_attachment_av_scan.quarantine_retention_days`: Days before purging quarantined files (default: 90)
   - `spp_attachment_av_scan.forensic_download_retention_hours`: Hours before cleaning forensic downloads (default: 24)

### UI Location

- **Scanner Configuration**: Settings > Administration > Antivirus Scanners
- **Quarantined Files**: Settings > Technical > Security > Quarantined Files
- **Attachment Forms**: Scan status and quarantine actions appear in "Antivirus Scan" section

### Tabs

**Scanner Backend form** (`spp.av.scanner.backend`):

- **Connection Settings**: Unix socket or network configuration for ClamAV
- **Connection Status**: Last connection test results and error details

### Security

| Group                                   | Model                    | Access                      |
| --------------------------------------- | ------------------------ | --------------------------- |
| `base.group_user`                       | `spp.av.scanner.backend` | Read                        |
| `base.group_user`                       | `ir.attachment`          | Read scan status            |
| `spp_attachment_av_scan.group_av_admin` | `spp.av.scanner.backend` | Full CRUD                   |
| `spp_attachment_av_scan.group_av_admin` | `ir.attachment`          | Manage quarantined files    |

### Extension Points

- Override `ir.attachment._scan_for_malware()` to customize scan logic or add pre/post-scan hooks
- Inherit `spp.av.scanner.backend` and extend `scan_binary()` to support additional antivirus engines
- Override `ir.attachment._quarantine()` to add custom quarantine handling or external storage

### Dependencies

`base`, `mail`, `queue_job`, `spp_encryption`, `spp_security`

External: `pyclamd` (Python library for ClamAV integration)
