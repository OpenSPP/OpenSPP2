Links cases to required training or group sessions and tracks client attendance. Computes attendance rates and compliance status based on configurable thresholds. Enables case managers to monitor whether case clients meet session attendance requirements.

### Key Capabilities

- Link cases to required sessions via many-to-many relationship
- Track attendance records for case clients at linked sessions
- Calculate attendance rate as percentage of required sessions attended
- Classify compliance: compliant (≥80%), partial (≥50%), non-compliant (<50%), or N/A
- Navigate between cases and sessions via stat buttons

### Key Models

| Model         | Description                                    |
| ------------- | ---------------------------------------------- |
| `spp.case`    | Extended with session links and compliance     |
| `spp.session` | Extended with reverse relationship to cases    |

### Configuration

No configuration required after installation. The module automatically extends existing case and session forms with session tracking fields and navigation.

### UI Location

- **Case Form**: "Sessions" tab displays linked sessions, attendance records, compliance badge, and attendance rate progress bar
- **Case Form**: Stat button opens list of linked sessions
- **Session Form**: Stat button opens list of related cases

No standalone menus are defined. All features are accessed via existing case and session forms.

### Security

This module defines no new models or access control records. Security is inherited from `spp_case_base` and `spp_session_tracking`. Users with access to cases and sessions can view and manage session links.

### Extension Points

- Override `_compute_session_stats()` on `spp.case` to customize compliance thresholds (default: 80% compliant, 50% partial)
- Override `_compute_session_attendance()` on `spp.case` to filter which attendance records are included in calculations
- Inherit `spp.case` to add domain-specific session tracking fields or workflows

### Dependencies

`spp_security`, `spp_case_base`, `spp_session_tracking`
