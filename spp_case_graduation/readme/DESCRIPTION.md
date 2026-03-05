Bridge module linking graduation assessments to case management records. Enables case workers to initiate graduation assessments, monitor readiness scores, and track graduation status directly from case forms. Supports exit management by consolidating graduation tracking within the case lifecycle.

### Key Capabilities

- Link graduation assessments to cases for centralized exit tracking
- Compute graduation status from assessment state and recommendations
- Display readiness scores and assessment counts on case records
- Create new graduation assessments directly from case forms
- View full assessment history with state, pathway, and scores

### Key Models

This module extends existing models without introducing new ones:

| Model                          | Extension                                                     |
| ------------------------------ | ------------------------------------------------------------- |
| `spp.case`                     | Adds graduation assessment tracking and computed status fields |
| `spp.graduation.assessment`    | Adds case linkage field                                       |

### Configuration

No configuration required after installation. The module automatically extends case and graduation assessment forms.

### UI Location

- **Cases**: Navigate to a case record. The "Graduation" tab displays assessment history, status, and readiness score. A stat button in the button box shows assessment count.
- **Assessments**: Graduation assessment forms include a case field for linking to case records.
- **Actions**: Use "New Assessment" button on case graduation tab to create assessments with pre-filled case and partner context.

### Security

This module does not introduce new security groups. Access to graduation features within cases follows the security model of the parent modules:

- Case access governed by `spp_case_base` security groups
- Graduation assessment access governed by `spp_graduation` security groups

### Extension Points

- Override `_compute_graduation_stats()` on `spp.case` to customize graduation status logic or add domain-specific readiness calculations
- Inherit `spp.case` to add fields that influence graduation decisions or extend the status selection

### Dependencies

`spp_security`, `spp_case_base`, `spp_graduation`
