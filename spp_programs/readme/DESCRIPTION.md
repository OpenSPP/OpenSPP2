Core program management for social protection. Implements programs, cycles, beneficiary enrollment, entitlements (cash and in-kind), payments, and fund tracking. Uses manager pattern for extensible eligibility, deduplication, notifications, and compliance workflows.

### Key Capabilities

- **Program Management**: Define programs with target type (individual/group), states (active/ended), and configurable manager-based logic
- **Cycle Management**: Create time-bound distribution cycles with approval workflows, recurrence, and compliance filtering
- **Enrollment**: Import and enroll registrants as program members, verify eligibility, track enrollment states
- **Deduplication**: Identify and manage duplicate beneficiaries using ID documents or phone numbers
- **Entitlements**: Generate cash or in-kind entitlements with approval workflows, fund balance validation, and CEL expression support
- **Payment Processing**: Create payment batches, track disbursements, reconcile payments via accounting integration
- **Fund Tracking**: Monitor program budgets, available funds, and journal entries through Odoo accounting
- **Stock Integration**: Link in-kind entitlements to inventory, trigger procurements, track warehouse movements
- **Compliance**: Define ongoing beneficiary conditions and filter cycle members by compliance status
- **Manager Architecture**: Extensible pattern for eligibility, deduplication, notification, program, cycle, entitlement, payment, and compliance logic

### Key Models

| Model                                        | Description                                              |
| -------------------------------------------- | -------------------------------------------------------- |
| `spp.program`                                | Main program with managers, target type, and funding    |
| `spp.cycle`                                  | Time-bound distribution cycle within a program           |
| `spp.program.membership`                     | Enrolls registrant in program with state tracking        |
| `spp.cycle.membership`                       | Links registrant to specific cycle for entitlement prep  |
| `spp.entitlement`                            | Cash entitlement with approval workflow                  |
| `spp.entitlement.inkind`                     | In-kind entitlement with product, quantity, warehouse    |
| `spp.payment`                                | Individual payment linked to cash entitlement            |
| `spp.payment.batch`                          | Groups payments for batch processing and reconciliation  |
| `spp.payment.batch.tag`                      | Tags for categorizing payment batches                    |
| `spp.eligibility.manager`                    | Wrapper for eligibility manager implementations          |
| `spp.program.membership.manager`             | Base eligibility manager (abstract)                      |
| `spp.program.membership.manager.default`     | Default eligibility implementation                       |
| `spp.deduplication.manager`                  | Wrapper for deduplication manager implementations        |
| `spp.program.notification.manager`           | Notification manager for beneficiary communications      |
| `spp.program.manager`                        | Wrapper for program lifecycle manager implementations    |
| `spp.program.manager.default`                | Default program manager implementation                   |
| `spp.cycle.manager`                          | Wrapper for cycle manager implementations                |
| `spp.cycle.manager.default`                  | Default cycle manager implementation                     |
| `spp.program.entitlement.manager`            | Wrapper for entitlement manager implementations          |
| `spp.program.entitlement.manager.default`    | Default entitlement manager implementation               |
| `spp.program.entitlement.manager.cash`       | Cash entitlement manager with amount calculation         |
| `spp.program.entitlement.manager.inkind`     | In-kind entitlement manager with product configuration   |
| `spp.program.payment.manager`                | Wrapper for payment manager implementations              |
| `spp.program.payment.manager.default`        | Default payment manager implementation                   |
| `spp.compliance.manager`                     | Wrapper for compliance manager implementations           |
| `spp.compliance.manager.default`             | Default compliance manager with CEL support              |
| `spp.program.fund`                           | Tracks program budget and fund utilization               |
| `spp.program.fund.report.view`              | Fund balance reporting view                              |
| `spp.program.membership.duplicate`           | Tracks duplicate membership records                      |

### Configuration

After installing:

1. Navigate to **Programs > Programs**
2. Create a program, selecting target type (individual/group)
3. In the **Configuration** tab, configure managers:
   - **Eligibility Manager**: Define who can enroll (supports CEL expressions)
   - **Program Manager**: Handles enrollment and cycle creation logic
   - **Cycle Manager**: Manages cycle lifecycle and beneficiary copying
   - **Entitlement Manager**: Generates and approves entitlements (cash or in-kind)
   - **Payment Manager**: Prepares and sends payment batches
   - **Deduplication Manager** (optional): Identify duplicate beneficiaries
   - **Notification Manager** (optional): Send beneficiary notifications
   - **Compliance Manager** (optional): Define ongoing compliance conditions
4. Set up program journal under **Programs > Accounting > Configuration** or via Create Journal button
5. For in-kind programs: configure warehouses and service points via **Programs > In-Kind > Products**

### UI Location

- **Programs**: Programs > Programs
- **Cycles**: Accessed via "Cycles" stat button on program form (no standalone menu)
- **Beneficiaries**: Accessed via "Beneficiaries" stat button on program form (no standalone menu)
- **Cash Entitlements**: Accessed via entitlement buttons on cycle form (no standalone menu)
- **In-Kind Entitlements**: Programs > In-Kind > Entitlements
- **Payment Batches**: Programs > Payments > Payment Batches
- **Individual Payments**: Accessed via payment buttons on cycle form (no standalone menu)
- **Fund Management**: Programs > Accounting

### Security

| Group                                    | Access                                       |
| ---------------------------------------- | -------------------------------------------- |
| `spp_programs.group_programs_viewer`     | Read-only on all program data                |
| `spp_programs.group_programs_officer`    | Read/write/create on all models (no delete)  |
| `spp_programs.group_programs_manager`    | Full CRUD on cycles and memberships, RWC on programs (no program delete) |
| `spp_programs.group_programs_validator`  | Read/write/create on entitlements and cycles (finance validation role) |
| `spp_programs.group_programs_cycle_approver` | Read/write/create on entitlements and cycles (approval role) |
| `spp_programs.group_programs_rejector`   | Read/write/create on entitlements (rejection role) |

### Extension Points

- Override `_pre_enrollment_hook(partner)` and `_post_enrollment_hook(partner)` on `spp.program` for custom enrollment logic
- Inherit manager models and add to `_selection_manager_ref_id()` to register custom manager types:
  - `spp.program.membership.manager` for custom eligibility
  - `spp.cycle.manager` for custom cycle logic
  - `spp.program.entitlement.manager` for custom entitlement generation
  - `spp.compliance.manager` for custom compliance rules
- Extend `spp.entitlement` or `spp.entitlement.inkind` to add domain-specific entitlement fields
- Override `get_compliance_domain(membership)` on compliance managers to define custom compliance criteria
- Use `spp.manager.mixin` pattern to create new manager types

### Dependencies

`account`, `web`, `base`, `mail`, `spp_registry`, `spp_banking`, `calendar`, `product`, `stock`, `spp_security`, `spp_area`, `spp_service_points`, `spp_user_roles`, `spp_base_common`, `spp_approval`, `spp_cel_domain`, `spp_cel_widget`, `job_worker`
