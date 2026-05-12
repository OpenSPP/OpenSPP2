# OpenSPP Storage Backend

Pluggable storage backend configuration for OpenSPP file storage.

## Overview

This module provides a flexible storage backend system that allows OpenSPP to store
files in various storage systems beyond Odoo's default filestore. This is essential for:

- **Scalability**: Store large volumes of files in cloud storage
- **Security**: Isolate sensitive documents in dedicated storage systems
- **Compliance**: Meet regulatory requirements for data storage location
- **Cost Optimization**: Use cost-effective cloud storage for archives

## Supported Backends

### 1. Odoo Default (Filesystem/Database)

Uses Odoo's built-in filestore mechanism. Files are stored in the Odoo filestore
directory or database depending on your configuration.

**Configuration**: No additional configuration required.

**Use Case**: Development, small deployments, or when using Odoo's default storage is
sufficient.

### 2. Amazon S3 / S3-Compatible

Store files in Amazon S3 or S3-compatible services (MinIO, DigitalOcean Spaces, Wasabi,
etc.).

**Configuration**:

- Bucket Name
- Access Key ID
- Secret Access Key
- Region (default: us-east-1)
- Endpoint URL (optional, for S3-compatible services)
- Use SSL (default: True)

**Requirements**: `boto3` Python library

**Use Case**: Production deployments, high availability, automatic backups, content
delivery.

### 3. Azure Blob Storage

Store files in Microsoft Azure Blob Storage.

**Configuration**:

- Connection String
- Container Name

**Requirements**: `azure-storage-blob` Python library

**Use Case**: Azure-based infrastructure, enterprise deployments using Microsoft cloud.

### 4. External Filesystem

Store files in an external filesystem path (network share, mounted volume, etc.).

**Configuration**:

- Base Path (must be absolute)

**Requirements**: Path must be writable by Odoo process

**Use Case**: Network-attached storage (NAS), shared volumes in containerized
deployments.

## Installation

### Basic Installation

```bash
# Install the module
odoo-bin -d <database> -i spp_storage_backend
```

### With S3 Support

```bash
# Install boto3
pip install boto3

# Install the module
odoo-bin -d <database> -i spp_storage_backend
```

### With Azure Support

```bash
# Install azure-storage-blob
pip install azure-storage-blob

# Install the module
odoo-bin -d <database> -i spp_storage_backend
```

## Configuration

1. Navigate to **Settings → Technical → Storage Backends** (requires Storage
   Administrator role)
2. Create a new storage backend or modify the default "Odoo Default Storage"
3. Configure backend-specific settings
4. Click "Test Connection" to verify configuration
5. Set "Is Default" to make this backend the default for new files

## Usage

### For Module Developers

```python
# Get the default backend
backend = self.env["spp.storage.backend"].get_default_backend()

# Store a file
binary_data = b"file contents..."
reference = backend.store(binary_data, "documents/report.pdf")

# Retrieve a file
binary_data = backend.retrieve(reference)

# Get a public URL (if supported by backend)
url = backend.get_public_url(reference, expires_in=3600)

# Delete a file
backend.delete(reference)
```

### Multiple Backends

You can configure multiple backends for different purposes:

```python
# Get a specific backend by name
s3_backend = self.env["spp.storage.backend"].search([("name", "=", "Production S3")], limit=1)

# Or by type
archive_backend = self.env["spp.storage.backend"].search([("backend_type", "=", "filesystem")], limit=1)
```

## Security

- Only users with the **Storage Administrator** role can manage backend configurations
- Credentials (access keys, connection strings) are stored in the database
- Consider encrypting your database if storing sensitive credentials
- S3 and Azure backends support time-limited signed URLs for secure file sharing

### Best Practices

1. **Never log credentials**: The module follows OpenSPP's no-PII-in-logs principle
2. **Use IAM roles when possible**: For S3, prefer IAM instance roles over static
   credentials
3. **Rotate credentials regularly**: Update access keys periodically
4. **Test in development first**: Always test backend configuration in a non-production
   environment
5. **Monitor storage costs**: Cloud storage can incur significant costs at scale

## Architecture Decision Records

This module implements:

- [ADR-018: DMS Security and Storage Enhancements](../../docs/architecture/decisions/ADR-018-dms-security-storage.md)

## Technical Details

### Default Backend Selection

The `get_default_backend()` method follows this priority:

1. Backend with `is_default=True` and `is_active=True`
2. First active Odoo backend
3. First active backend of any type

### Storage Reference Format

- **Odoo**: Base64-encoded binary data (compatibility mode)
- **S3**: S3 object key (path)
- **Azure**: Blob name (path)
- **Filesystem**: Relative path from base directory

### Public URL Generation

- **S3**: Presigned URLs with configurable expiration
- **Azure**: SAS (Shared Access Signature) URLs with configurable expiration
- **Odoo/Filesystem**: Not supported (returns None)

## Troubleshooting

### "boto3 library is not installed"

```bash
pip install boto3
```

### "azure-storage-blob library is not installed"

```bash
pip install azure-storage-blob
```

### "Connection test failed"

- Verify credentials are correct
- Check network connectivity to storage service
- Ensure bucket/container exists
- Verify IAM/access permissions

### "Path is not writable"

For filesystem backends:

- Ensure the path exists
- Check directory permissions
- Verify Odoo process user has write access

## Development Status

**Alpha** - Initial implementation for V2 architecture.

## License

LGPL-3

## Maintainers

- jeremi
- gonzalesedwin1123
