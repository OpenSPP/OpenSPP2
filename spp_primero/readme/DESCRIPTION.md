Lets a social worker record a child protection concern on an individual registrant and refer the child to Primero (UNICEF's child protection case management system) through an OpenFn workflow. The referral sends only the child's identifier to an OpenFn webhook; the workflow reads the child and the concern back from the OpenSPP REST API v2 and creates or updates the case in Primero.

### Key Capabilities

- Record a protection concern on an individual: concern types (Primero's protection-concern codes), risk level, urgency, date, notes, and the two consent ticks Primero's referral logic uses
- **Refer to Primero** button on the individual form that posts the child's identifier to the configured OpenFn webhook and records the outcome (referred / failed, OpenFn run reference)
- Expose the concern on `GET /api/v2/spp/Individual/{id}?_extensions=protection-concern` so the OpenFn workflow reads child and concern in one call

### Key Models

| Model         | Description                                                                 |
| ------------- | --------------------------------------------------------------------------- |
| `res.partner` | Adds `protection_*` concern fields and `primero_*` referral tracking fields |

### Vocabularies

| Namespace                                   | Codes                                                 |
| ------------------------------------------- | ----------------------------------------------------- |
| `urn:openspp:vocab:protection-concern`      | Primero's stock `lookup-protection-concerns` codes    |
| `urn:openspp:vocab:protection-risk-level`   | `high`, `medium`, `low`                               |

### UI Location

**Individual Form** (Registry > Individuals):

- "Protection" tab: concern, consent and referral status
- Smart button "Refer to Primero" (registry officers and managers)

**Settings** (Settings > Primero Referral): OpenFn webhook URL and API key.
