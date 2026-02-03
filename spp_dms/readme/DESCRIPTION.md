Document management system for organizing program-related files in hierarchical directories. Stores binary content with automatic metadata capture (size, MIME type, SHA512 checksum), optional version history with restore capability, and category-based validation for file types and size limits.

### Key Capabilities

- Organize files in nested directory structures with root directories and subdirectories
- Automatically capture file metadata on upload: size, MIME type, extension, SHA512 checksum
- Enable optional versioning per file with automatic snapshots on content changes and manual restore
- Enforce file type restrictions (allowed/blocked extensions, MIME types) and size limits per category
- Generate thumbnails automatically for image files using Pillow
- Compute directory statistics recursively: total file count, subdirectory count, and cumulative size

### Key Models

| Model                            | Description                                             |
| -------------------------------- | ------------------------------------------------------- |
| `spp.dms.directory`              | Directory with parent/child hierarchy and file storage  |
| `spp.dms.file`                   | File record with binary content and optional versioning |
| `spp.dms.file.version`           | Version snapshot with content, checksum, and comment    |
| `spp.dms.category`               | File classification with validation rules               |
| `spp.dms.restore.version.wizard` | Transient wizard for restoring file versions            |

### Configuration

After installing:

1. Navigate to **DMS > Configuration > Categories**
2. Create categories defining allowed file extensions (e.g., `pdf,jpg,png`), blocked extensions, MIME types, and maximum file size in MB
3. Upload files via **DMS > Files**, assign categories, and enable versioning per file as needed

### UI Location

- **Files**: DMS > Files
- **Directories**: DMS > Directories
- **Configuration**: DMS > Configuration > Categories
- **Version History**: Accessed via stat button on file forms when versioning is enabled

### Security

| Group                         | Access                                         |
| ----------------------------- | ---------------------------------------------- |
| `spp_dms.group_dms_viewer`    | Read directories, files, versions, categories  |
| `spp_dms.group_dms_officer`   | Create/edit files and directories (no delete)  |
| `spp_dms.group_dms_manager`   | Full CRUD on all models including categories   |

### Extension Points

- Override `validate_file()` on `spp.dms.category` to add custom validation logic
- Inherit `spp.dms.file` to add domain-specific metadata fields
- Override `_create_new_version()` on `spp.dms.file` to customize versioning behavior

### Dependencies

`base`, `web`, `spp_security`
