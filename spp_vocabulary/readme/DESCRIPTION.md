Standardized vocabulary and code list management system. Supports international standards (ISO, WHO, ILO), local extensions, cross-vocabulary mappings, and deployment-specific code filtering. Vocabularies define code lists (gender, relationship types, ID types, education levels) that are reused across OpenSPP modules.

### Key Capabilities

- Define vocabularies with globally unique namespace URIs for interoperability
- Manage hierarchical codes with lifecycle tracking (active, deprecated, replaced)
- Create local code extensions that map to standard codes with equivalence tracking
- Map codes between different vocabularies for translation and interoperability
- Filter active codes per deployment using deployment profiles
- Group codes semantically via concept groups for business logic abstraction

### Key Models

| Model                          | Description                                                   |
| ------------------------------ | ------------------------------------------------------------- |
| `spp.vocabulary`               | Collection of codes with a namespace (e.g., Gender, ID Type)  |
| `spp.vocabulary.code`          | Individual code within a vocabulary (e.g., 'M', 'female')     |
| `spp.vocabulary.mapping`       | Maps codes between different vocabularies                     |
| `spp.vocabulary.concept.group` | Semantic grouping of codes for business logic abstraction     |
| `spp.deployment.profile`       | Deployment-specific configuration for active code subsets     |
| `spp.vocabulary.selection`     | Code selection within a deployment profile with inheritance   |

### Configuration

After installing:

1. Navigate to **Settings > Vocabularies > Manage Vocabularies**
2. Review pre-loaded vocabularies (gender, occupation, education, disability, etc.)
3. Create deployment profiles via **Settings > Vocabularies > Deployment Profiles**
4. Configure code selections for each vocabulary within a profile
5. Activate the deployment profile to filter available codes

### UI Location

- **Menu**: Settings > Vocabularies
- **Submenus**: Manage Vocabularies, All Codes, Code Mappings, Concept Groups, Deployment Profiles, Vocabulary Selections
- **Vocabulary Form Tabs**: Details, Codes, Technical

### Security

| Group                                     | Access                            |
| ----------------------------------------- | --------------------------------- |
| `spp_vocabulary.group_vocabulary_viewer`  | Read                              |
| `spp_vocabulary.group_vocabulary_officer` | Read/Write/Create (no delete)     |
| `spp_vocabulary.group_vocabulary_manager` | Full CRUD                         |

System vocabularies are protected from modification in production. Only active, deprecated, and sequence fields can be changed on system codes. Local extensions (`is_local=True`) can be added to system vocabularies.

### Extension Points

- Override `spp.vocabulary.code.get_or_create_local()` to customize local code creation
- Inherit `spp.vocabulary.concept.group` and override `contains()` for custom membership logic
- Use `spp.vocabulary.code.resolve_by_uri()` for URI-based code resolution in interoperability scenarios
- Use `spp.deployment.profile.get_active_domain()` to filter code fields by active deployment profile

### Dependencies

`base`, `mail`, `spp_security`
