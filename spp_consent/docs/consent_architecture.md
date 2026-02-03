# Consent Architecture

## Overview

OpenSPP's consent management implements ISO/IEC TS 27560:2023 (Consent Record Information Structure) and ISO/IEC
29184:2020 (Privacy Notices and Consent) for data protection compliant data sharing.

This architecture ensures:

- Beneficiaries give informed consent before data is shared
- Consent records are immutable and auditable
- API access is filtered based on consent

## Key Concepts

### Privacy Notice (`spp.consent.notice`)

Defines the **legal boundary** for what can be consented to:

- Which organization types can receive data
- What purposes data can be used for
- What categories of personal data are covered

The notice is shown to beneficiaries **before** obtaining consent. It cannot be changed after consents reference it
(versioning is used for updates).

### Consent Record (`spp.consent`)

Records the **actual agreement** with the data subject (beneficiary):

- Must be a **subset** of what the notice describes
- Cannot exceed notice boundaries (that would be uninformed consent)
- **Immutable once given** - corrections require invalidation + new consent

### Organization Types (`spp.consent.org.type`)

Categories of organizations for consent matching:

- Used by API clients to identify their organization type
- Used by consents to define allowed recipients
- Enables flexible consent like "all NGOs" vs specific "UNICEF only"

## Notice as Boundary Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                     Privacy Notice                               │
│  (Defines MAXIMUM scope - what's legally described)              │
│                                                                   │
│  max_recipient_types: [NGO, Government, UN Agency]               │
│  purpose_ids: [Service Delivery, Research, Identity Verification]│
│  data_category_ids: [Identifying, Contact, Financial]            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │  consent ⊆ notice
                              │  (subset relationship enforced)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Consent Record                               │
│  (Beneficiary's ACTUAL choices - can narrow, cannot exceed)      │
│                                                                   │
│  allowed_recipient_types: [NGO, Government]  ← subset of notice  │
│  purpose_ids: [Service Delivery]              ← subset of notice │
│  personal_data_ids: [Identifying, Contact]    ← subset of notice │
└─────────────────────────────────────────────────────────────────┘
```

The boundary constraint is enforced at the database level:

- When saving a consent, a validation check ensures consent ⊆ notice
- Validation error if consent tries to include something not in the notice

## Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Privacy Notice  │────►│ Consent Record  │────►│ API Filtering   │
│ (max scope)     │     │ (actual terms)  │     │ (enforcement)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        │ defines boundary      │ ⊆ notice scope       │ checks consent
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Org Types       │     │ Org Types       │     │ API Client      │
│ Purposes        │     │ Purposes        │     │ org_type_id     │
│ Data Categories │     │ Data Categories │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Consent Checking Modes

### Category-Based (Recommended)

Beneficiary consents to share with **categories** of organizations:

```python
consent.recipient_mode = "category"
consent.allowed_recipient_types = [org_type_ngo, org_type_government]
```

API client with `organization_type_id.code = "ngo"` → Access granted

Benefits:

- Simpler for beneficiaries to understand
- Automatic coverage of new NGOs added to system
- Reduces consent update burden

### Specific Organizations

Beneficiary consents to share with **named** organizations:

```python
consent.recipient_mode = "specific"
consent.recipient_ids = [unicef_partner, wfp_partner]
```

API client with `partner_id = unicef_partner` → Access granted

Use when:

- Beneficiary wants fine-grained control
- Sensitive data requiring explicit authorization

## Immutability

Once consent status changes from "requested" to "given":

1. **All substantive fields are locked** via UI `readonly` attributes
2. **Server-side protection** via `write()` override raises error
3. **Evidence attachments can still be added** (add-only)
4. **Changes require**: Invalidate existing + create new consent

Protected fields include: signatory, purposes, data categories, org types, legal basis, expiry, effective date,
collection method, etc.

This ensures the consent record accurately represents what was agreed at that point in time - critical for legal
compliance and audit.

## Performance: Consent Summary Cache

For O(1) consent lookups in API filtering, a cached JSON summary is stored on each registrant
(`res.partner.consent_summary`):

```json
{
  "organization_types": ["ngo", "government"],
  "purposes": ["service_delivery", "ResearchAndDevelopment"],
  "specific_recipients": [123, 456],
  "last_updated": "2024-01-15T10:30:00Z"
}
```

The summary is automatically recomputed when consents are created/modified.

### API Usage

```python
# Instead of querying consents per-registrant:
def can_access(registrant, org_type_code):
    summary = registrant.consent_summary or {}
    return org_type_code in summary.get("organization_types", [])

# Batch filtering example:
def filter_registrants(registrant_ids, org_type_code):
    return self.env["res.partner"].search([
        ("id", "in", registrant_ids),
        ("consent_summary", "!=", False),
    ]).filtered(
        lambda p: org_type_code in (p.consent_summary or {}).get("organization_types", [])
    )
```

## Audit Trail

All consent changes are recorded in `spp.consent.history`:

- Action type (create, give, withdraw, invalidate, renew, etc.)
- Previous and new status
- Timestamp and user
- Reason for change (if applicable)

This provides a complete audit trail for compliance.

## Related Models

| Model                       | Description                  |
| --------------------------- | ---------------------------- |
| `spp.consent`               | Main consent record          |
| `spp.consent.notice`        | Privacy notice template      |
| `spp.consent.history`       | Audit trail                  |
| `spp.consent.purpose`       | DPV-aligned purposes         |
| `spp.consent.personal.data` | DPV-aligned data categories  |
| `spp.consent.processing`    | DPV-aligned processing types |
| `spp.consent.org.type`      | Organization type categories |

## Standards Compliance

- **ISO/IEC TS 27560:2023**: Consent Record Information Structure
- **ISO/IEC 29184:2020**: Privacy Notices and Consent
- **W3C DPV**: Data Privacy Vocabulary for purposes, data categories, processing
- **GDPR Article 7**: Conditions for consent
- **GDPR Article 6**: Lawfulness of processing (legal basis)
