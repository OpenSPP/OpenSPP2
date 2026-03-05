Manages beneficiary graduation from time-bound social protection programs. Defines graduation pathways with weighted criteria, conducts assessments against those criteria, calculates readiness scores, and tracks graduation outcomes with post-graduation monitoring periods. Supports both positive exits (graduation) and negative exits (program removal).

### Key Capabilities

- Define graduation pathways with configurable criteria, exit type, and monitoring duration
- Create weighted criteria with different assessment methods (self-report, verification, computed, observation)
- Conduct beneficiary assessments with criteria responses and evidence attachments
- Calculate readiness scores based on weighted criteria and enforce required criteria
- Submit assessments for manager approval through a draft/submitted/approved/rejected workflow
- Track graduation dates and compute post-graduation monitoring periods
- Filter assessments by assessor, state, pathway, and recommendation

### Key Models

| Model                              | Description                                              |
| ---------------------------------- | -------------------------------------------------------- |
| `spp.graduation.pathway`           | Defines a graduation pathway with criteria and exit type |
| `spp.graduation.criteria`          | Individual criterion within a pathway with weight and method |
| `spp.graduation.assessment`        | Assessment of a beneficiary against a pathway with scores |
| `spp.graduation.criteria.response` | Response to a specific criterion within an assessment    |

### Configuration

After installing:

1. Navigate to **Graduation > Configuration > Pathways**
2. Create graduation pathways specifying exit type (positive/negative) and monitoring months
3. Add criteria to each pathway with weight, assessment method, and required flag
4. Users can then create assessments under **Graduation > Assessments > All Assessments**

### UI Location

- **Menu**: Graduation (top-level menu)
- **Assessments**: Graduation > Assessments > All Assessments / My Assessments
- **Configuration**: Graduation > Configuration > Pathways (managers only)
- **Views**: List, kanban (grouped by state), and form views with approval workflow
- **Pathway Form**: Criteria tab shows inline editable criteria list
- **Assessment Form**: Criteria Responses and Recommendation tabs

### Security

| Group                                      | Access                                                    |
| ------------------------------------------ | --------------------------------------------------------- |
| `spp_graduation.group_spp_graduation_user` | Read pathways/criteria; create/edit own assessments (no delete) |
| `spp_graduation.group_spp_graduation_manager` | Full CRUD on all graduation data and configuration     |

### Extension Points

- Inherit `spp.graduation.assessment` and override `_compute_scores()` to customize readiness calculation
- Inherit `spp.graduation.pathway` to add domain-specific pathway fields
- Extend approval workflow by inheriting assessment actions (`action_submit`, `action_approve`)

### Dependencies

`base`, `spp_security`, `mail`
