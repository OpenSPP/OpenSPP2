Adds bank account management to registrants (individuals and groups). Stores account details, bank information, and automatically generates IBANs using the schwifty library. Extends the standard Odoo `res.partner.bank` model with automatic IBAN computation.

### Key Capabilities

- Store multiple bank accounts per registrant with account number, bank, and account type
- Automatically generate IBAN from bank country code, BIC, and account number
- Display bank details in individual and group registry forms under the financial section
- Validate and format IBANs according to country-specific standards

### Key Models

| Model              | Description                                          |
| ------------------ | ---------------------------------------------------- |
| `res.partner.bank` | Bank account details with automatic IBAN computation |

### Configuration

No configuration required after installation. Bank accounts can be added directly to registrant profiles.

### UI Location

- **No standalone menu**: Bank account fields are added to existing registrant forms
- **Individuals**: Navigate to a registrant, view the "Profile" tab, bank accounts appear in the Financial Information section
- **Groups**: Navigate to a group registrant, view the "Profile" tab, bank accounts appear in the Financial Information section

Bank accounts are displayed as an editable list with fields for bank, account number, and computed IBAN.

### Security

| Group                                 | Access                       |
| ------------------------------------- | ---------------------------- |
| `spp_registry.group_registry_viewer`  | Read                         |
| `spp_registry.group_registry_officer` | Read/Write/Create (no delete) |
| `spp_registry.group_registry_manager` | Full CRUD                    |

### Extension Points

- Override `_compute_account_number()` in `res.partner.bank` to customize IBAN generation logic
- Inherit `res.partner.bank` to add additional banking fields or validation rules

### Dependencies

`spp_security`, `base`, `mail`, `contacts`, `spp_registry`

**External Python Dependencies**: `schwifty` (IBAN/BIC validation and formatting)
