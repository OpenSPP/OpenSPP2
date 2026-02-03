Centralized grievance and complaint management for social protection programs. Receives complaints through multiple channels (email, portal, manual entry), tracks resolution through customizable workflow stages, and monitors service level agreements. Links complaints to individual or group registrants and supports anonymous submissions.

### Key Capabilities

- Multi-channel intake: Email alias integration creates tickets from inbound messages, portal form for beneficiaries, manual entry by officers
- Stage-based workflow: Define stages with access control restrictions, approval requirements, and decision enforcement before closure
- SLA tracking: Automatically compute deadlines based on category/subcategory configuration, monitor status (on track, at risk, breached), post notifications on breach
- Team assignment: Organize handlers into teams with geographic area responsibilities, auto-assign based on category defaults
- Appeals and escalation: Reference original tickets for appeals, track escalation history and reasons, mark tickets as escalated
- Hierarchical categorization: Two-level category/subcategory system with inherited defaults for severity, sensitivity, SLA hours, and team assignment
- Decision tracking: Record final decisions (upheld, partially upheld, rejected, withdrawn, redirected, referred to case) with resolution summaries
- Anonymous complaints: Optional contact fields for complainants not in the registry

### Key Models

| Model                        | Description                                                      |
| ---------------------------- | ---------------------------------------------------------------- |
| `spp.grm.ticket`             | Main complaint/grievance with SLA tracking and decision fields   |
| `spp.grm.ticket.stage`       | Workflow stage with access control and closure configuration     |
| `spp.grm.ticket.category`    | Primary classification with hierarchical structure               |
| `spp.grm.ticket.subcategory` | Second-level classification under category                       |
| `spp.grm.team`               | Team of handlers with manager and geographic areas               |
| `spp.grm.sla.rule`           | Conditional SLA rules with escalation targets                    |
| `spp.grm.ticket.tag`         | Tags for flexible ticket classification                          |
| `spp.grm.ticket.channel`     | Communication channel (email, phone, walk-in, portal, etc.)      |

### Configuration

After installing:

1. Navigate to **Helpdesk > Configuration > Stages** to define workflow stages with closure and approval flags
2. Create categories under **Helpdesk > Configuration > Categories** with default severity, SLA hours, and team assignments
3. Set up teams under **Helpdesk > Configuration > Teams** with members and geographic area assignments
4. Configure SLA rules under **Helpdesk > Configuration > SLA Rules** with conditions and escalation targets
5. Set up email alias under **Settings > Technical > Email > Aliases** to enable automatic ticket creation from inbound messages

### UI Location

- **Menu**: Helpdesk (top-level menu item)
- **Tickets**: Helpdesk > Tickets
- **Configuration**: Helpdesk > Configuration (manager access required)
- **Portal**: Beneficiaries can view and create tickets at `/my/tickets`
- **Registrant Profile**: Stat button shows ticket count and opens related tickets

### Security

| Group                | Access                                     |
| -------------------- | ------------------------------------------ |
| `group_grm_viewer`   | Read only                                  |
| `group_grm_officer`  | Read/Write/Create (no delete)              |
| `group_grm_manager`  | Full CRUD including configuration          |
| `base.group_portal`  | Read/Write/Create tickets (no delete)      |

Stage transitions to approval-required stages are restricted by Python code to users in `group_grm_supervisor` or higher, but this group has no direct model access entries.

### Extension Points

- Override `_compute_sla_deadline()` on `spp.grm.ticket` to implement custom SLA calculation logic
- Install `spp_grm_cel` to provide `spp.grm.escalation.rule` model, which is automatically invoked when SLA status changes to breached
- Inherit `spp.grm.ticket` to add domain-specific fields (extended by `spp_grm_registry`, `spp_grm_programs`)
- Extend `spp.grm.ticket.stage` to add workflow state fields
- Override `evaluate_ticket()` on `spp.grm.sla.rule` to add custom matching conditions

### Dependencies

`base`, `mail`, `portal`, `spp_registry`, `spp_area`, `spp_user_roles`, `spp_security`
