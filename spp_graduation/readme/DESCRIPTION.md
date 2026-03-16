Manages beneficiary graduation and exit from time-bound social protection programs. Defines
graduation pathways with weighted criteria, conducts assessments against those criteria, calculates
readiness scores, and tracks graduation outcomes with post-graduation monitoring periods. Supports
both positive exits (graduation) and negative exits (program removal).

### Key Capabilities

- Define graduation pathways with configurable criteria, exit type (`is_positive_exit`), and monitoring duration
- Create weighted criteria with four assessment methods: self-report, verification, computed, observation
- Conduct beneficiary assessments with per-criterion scores, a manual met/not-met judgment, and notes
- Calculate weighted readiness scores (0–1) from `score` fields and enforce required criteria via `is_met` flags through `_compute_scores()`. The `score` (numeric, 0–1) and `is_met` (boolean) fields serve different purposes: `score` drives the weighted readiness score, while `is_met` is a qualitative assessor judgment used to check whether required criteria are satisfied. They are intentionally independent because some assessment methods (e.g., field observation) may not map cleanly to a numeric score.
- Approve assessments through a draft → submitted → approved/rejected workflow; approval auto-sets `graduation_date` when recommendation is "graduate"
- Compute `monitoring_end_date` from `graduation_date` + pathway's `post_graduation_monitoring_months`
- Ships with three pre-configured pathways: Standard Graduation (12 months monitoring), Early Graduation (18 months), and Administrative Exit (negative, 0 months)

### Key Models

| Model                              | Description                                                              |
| ---------------------------------- | ------------------------------------------------------------------------ |
| `spp.graduation.pathway`           | Graduation pathway with exit type, approval/assessment flags, and criteria |
| `spp.graduation.criteria`          | Weighted criterion within a pathway; has assessment method and required flag |
| `spp.graduation.assessment`        | Assessment of a beneficiary against a pathway; tracks scores and approval state |
| `spp.graduation.criteria.response` | Per-criterion response with `score`, `is_met`, `value`, `notes`, and `evidence_attachment_ids` |

### Configuration

After installing:

1. Navigate to **Graduation > Configuration > Pathways** (managers only)
2. Three default pathways are pre-installed; create additional ones as needed
3. On each pathway, set `is_positive_exit`, `is_assessment_required`, `is_approval_required`, and `post_graduation_monitoring_months`
4. Open the **Criteria** tab on the pathway form to add criteria with weight, assessment method, and required flag (inline editable list)
5. Users create assessments under **Graduation > Assessments > All Assessments**

### UI Location

- **Top-level menu**: Graduation (visible to `group_spp_graduation_user` and above)
- **Graduation > Assessments > All Assessments**: List, kanban (grouped by state), form, graph, and pivot views
- **Graduation > Assessments > My Assessments**: Same views, pre-filtered to current user's assessments
- **Graduation > Configuration > Pathways**: List and form views (managers only)
- **Pathway form**: Two-column layout with a **Criteria** tab containing an inline editable list
- **Assessment form**: **Overview** tab (beneficiary, pathway, scores, dates), **Criteria Responses** tab (inline editable list with `criteria_id`, `score`, `is_met`, `value`, `notes`, `evidence_attachment_ids`), **Recommendation** tab (selection + notes), and **History** tab (audit metadata). Statusbar shows draft/submitted/approved. Alert banners for submitted and rejected states.
- **Assessment form buttons**: Submit (draft), Approve/Reject (submitted, managers only), Reset to Draft (submitted or rejected, managers only)

### Security

| Group                                         | Access                                                                  |
| --------------------------------------------- | ----------------------------------------------------------------------- |
| `spp_graduation.group_spp_graduation_user`    | Read pathways/criteria; read/write/create own assessments (no delete); full CRUD on own criteria responses |
| `spp_graduation.group_spp_graduation_manager` | Full CRUD on all graduation models                                      |

Record rules restrict users to assessments where `assessor_id = current user` and responses on those assessments. Managers have unrestricted access. Multi-company isolation rules apply to pathways and assessments.

### Extension Points

- Override `_compute_scores()` on `spp.graduation.assessment` to customize readiness calculation logic
- Override `_compute_monitoring_end()` to change how monitoring end dates are derived
- Inherit `spp.graduation.pathway` to add domain-specific pathway fields
- Inherit assessment workflow actions (`action_submit`, `action_approve`, `action_reject`, `action_reset_draft`)
### Dependencies

`base`, `spp_registry`, `spp_security`, `mail`
