Provides a standardized approval workflow engine for OpenSPP models. Adds configurable multi-tier approval sequences with CEL-based conditional routing, SLA tracking, and system-wide freeze periods for regulatory compliance. Models inherit `spp.approval.mixin` to gain submit/approve/reject actions with audit trails and optimistic locking.

### Key Capabilities

- **Approval Mixin**: Add `spp.approval.mixin` to any model to enable approval workflow with state tracking (`draft`, `pending`, `approved`, `rejected`, `revision`)
- **Multi-Tier Workflows**: Define sequential approval tiers with configurable approver types (security group, specific users, submitter's manager, or dynamic field)
- **CEL Rules**: Conditional approval routing using Common Expression Language domain filters
- **Freeze Periods**: System-wide approval suspension during election bans, audits, or maintenance windows
- **SLA Tracking**: Track approval deadlines per tier with escalation support
- **Revision Requests**: Approvers can request revisions instead of outright rejection
- **Optimistic Locking**: Prevents concurrent approval conflicts via version-based locking

### Key Models

| Model                       | Description                                                   |
| --------------------------- | ------------------------------------------------------------- |
| `spp.approval.mixin`        | Abstract mixin providing approval workflow to inheriting models |
| `spp.approval.definition`   | Configures approval rules, approvers, and conditions per model |
| `spp.approval.tier`         | Individual tier in a multi-tier approval sequence             |
| `spp.approval.review`       | Tracks individual approval/rejection actions                  |
| `spp.approval.tier.review`  | Tracks progress through multi-tier workflows                  |
| `spp.approval.freeze`       | Defines system-wide freeze periods blocking approvals         |
| `spp.approval.config`       | System-wide approval configuration settings                   |

### Configuration

After installing:

1. Navigate to **Approvals > Configuration > Approval Definitions**
2. Create a definition selecting the target model, approver type, and optional domain filter
3. For multi-tier workflows, enable "Multi-Tier Approval" and configure tiers in the inline editable list
4. (Optional) Configure freeze periods at **Approvals > Configuration > Freeze Periods**

### UI Location

- **Menu**: Approvals > My Approvals > Pending Approvals
- **Configuration**: Approvals > Configuration > Approval Definitions
- **Freeze Periods**: Approvals > Configuration > Freeze Periods
- **Mixin Integration**: Approval buttons appear on forms of models inheriting the mixin

### Tabs

On **Approval Definition** forms:
- **Conditions**: Domain filter to determine which records require this approval
- **Behavior**: Approval settings (require comment, auto-approve, notifications)
- **SLA & Escalation**: SLA tracking and escalation rules

### Security

| Group                                   | Access                            |
| --------------------------------------- | --------------------------------- |
| `spp_approval.group_approval_viewer`    | Read approval records             |
| `spp_approval.group_approval_officer`   | Read/Write/Create (no delete)     |
| `spp_approval.group_approval_manager`   | Read/Write/Create on all models (delete only for reviews/config; definitions and freezes require admin) |
| `spp_approval.group_approval_approver`  | Approve/reject assigned reviews   |

Note: `approval_definition` and `approval_freeze` models block deletion for managers via Python override - only system administrators can delete these records.

### Extension Points

- Inherit `spp.approval.mixin` to add approval workflow to any model inheriting `mail.thread`
- Override `_on_submit()`, `_on_approve()`, `_on_reject()`, `_on_request_revision()` hooks for custom logic
- Override `_get_approval_definition()` to provide record-specific approval rules (e.g., from a type field)
- Extend `spp.approval.definition` to add custom approver types or matching logic

### Dependencies

`base`, `mail`, `spp_base_common`, `spp_cel_domain`, `spp_security`
