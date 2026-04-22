Demo data generator for the Grievance Redress Mechanism. Creates both story-based tickets linked to specific personas (Juan Dela Cruz, Ibrahim Hassan, Fatima Al-Rahman, Ahmed Said, David Martinez, Maria Santos, Rosa Garcia, Carlos Morales) and volume tickets using scenario templates. Simulates realistic ticket workflows including resolution paths, escalations, and timeline distribution. Uses Faker for locale-aware random data (non-deterministic — each run produces different volume tickets).

### Key Capabilities

- Generate story tickets for specific demo personas that align with `spp_mis_demo_v2` and `spp_case_demo`
- Generate volume tickets using YAML scenario templates or built-in fallback scenarios
- Simulate ticket workflows: resolution notes, stage transitions, escalations, and assignments
- Link tickets to beneficiaries, programs, and teams with configurable distribution
- Control resolved vs. unresolved ratios, severity distribution, and timeline spread
- Backdate ticket creation and workflow events across a configurable time range

### Key Models

| Model                    | Description                                                           |
| ------------------------ | --------------------------------------------------------------------- |
| `spp.grm.demo.generator` | Transient model containing generation logic and workflow simulation   |
| `spp.grm.demo.wizard`    | Transient model inheriting from generator for wizard UI configuration |

### Configuration

After installing:

1. Ensure registrants exist (run `spp_demo` story generation first)
2. Verify GRM ticket stages and channels are configured in `spp_grm`
3. Optionally install `spp_demo_scenarios` for extended scenario library

### UI Location

- **Menu**: Helpdesk > Configuration > Generate Demo Data
- **Wizard**: Configure story vs. volume generation, ticket count, time range, and resolution percentages

### Security

| Group                          | Access    |
| ------------------------------ | --------- |
| `spp_security.group_spp_admin` | Full CRUD |

### Data Generated

The generator creates `spp.grm.ticket` records with:

- Story tickets: 8 predefined personas with specific scenarios (payment issues, eligibility inquiries, service requests)
- Volume tickets: Scenario-based tickets distributed over time with realistic progression
- Ticket categories: Payment Issues, Eligibility Questions, Service Delivery, Information Requests, Data Update Requests, General, Complaint, Feedback
- Workflow progression: Resolution notes, stage transitions, escalation notes, and user assignments with backdated timestamps

### Integration

Story personas align with `spp_mis_demo_v2` and `spp_case_demo` for cross-module demos. Tickets can reference programs and beneficiaries, and story tickets include `escalate_to_case` flags for GRM-to-case workflow demonstrations.

### Dependencies

`spp_demo`, `spp_grm`, `spp_grm_registry`, `spp_grm_programs`, `spp_security`, `faker` (Python)
