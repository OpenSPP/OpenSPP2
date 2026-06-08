Pluggable storage backend configuration for file storage in OpenSPP. Supports Odoo's default filestore, Amazon S3/S3-compatible services (MinIO), Azure Blob Storage, and external filesystem locations. Provides a unified API for storing, retrieving, and deleting binary data regardless of the underlying storage mechanism.

### Key Capabilities

- Configure multiple storage backends with type-specific settings (bucket names, credentials, paths)
- Designate one backend as default via `is_default` flag
- Store, retrieve, and delete binary data through unified `store()`, `retrieve()`, and `delete()` methods
- Generate presigned URLs (S3) and SAS tokens (Azure) for temporary public access
- Test backend connectivity via `test_connection()` before use
- Prevent path traversal attacks for filesystem backends via `_validate_path_within_base()`

### Key Models

| Model                 | Description                                             |
| --------------------- | ------------------------------------------------------- |
| `spp.storage.backend` | Storage backend configuration with type-specific fields |

### Configuration

After installing:

1. Navigate to **Settings > Administration > Storage Backends**
2. The "Odoo Default Storage" backend is created automatically and set as default
3. Create additional backends as needed:
   - **S3**: Bucket name, access key, secret key, region, optional endpoint URL for S3-compatible services
   - **Azure**: Connection string and container name
   - **Filesystem**: Absolute path to base directory
4. Use **Test Connection** button to verify configuration
5. Optionally set a backend as default using `is_default` field

### UI Location

- **Menu**: Settings > Administration > Storage Backends
- **Form**: Type-specific configuration fields appear based on `backend_type` selection

### Security

| Group                                     | Access    |
| ----------------------------------------- | --------- |
| `spp_storage_backend.group_storage_admin` | Full CRUD |
| `base.group_user`                         | Read-only |

Storage Administrator privilege is automatically granted to OpenSPP Administrators.

### Extension Points

- Override backend-specific methods (`_store_s3()`, `_retrieve_azure()`, `_delete_filesystem()`, etc.) to customize storage behavior
- Add new backend types by extending the `backend_type` selection field and implementing corresponding `_store_*()`, `_retrieve_*()`, `_delete_*()` methods
- Call `get_default_backend()` to retrieve the default backend for file operations in other modules

### Dependencies

`base`, `spp_security`
