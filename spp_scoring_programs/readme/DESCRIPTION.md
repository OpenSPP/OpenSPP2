Bridge module linking the scoring framework with program eligibility and enrollment. Enables score-based and classification-based eligibility criteria, automatic scoring during enrollment, and tracking of score changes throughout program lifecycle. Auto-installs when both `spp_scoring` and `spp_programs` are present.

### Key Capabilities

- Define eligibility criteria based on score ranges (minimum/maximum thresholds)
- Define eligibility criteria based on classification codes (e.g., "POOR,EXTREME_POOR")
- Validate eligibility against scoring criteria before enrollment via pre-enrollment hook
- Automatically calculate scores when registrants enroll in programs
- Control score recalculation frequency via maximum score age settings
- Track enrollment-time score separately from latest score for comparison
- View which programs use a specific scoring model

### Key Models

| Model                    | Description                                                      |
| ------------------------ | ---------------------------------------------------------------- |
| `spp.program`            | Extended with scoring model reference and eligibility settings   |
| `spp.program.membership` | Extended with enrollment score and latest score tracking fields  |
| `spp.scoring.model`      | Extended with program relationship showing which programs use it |

### Configuration

After installing (auto-installs with `spp_scoring` + `spp_programs`):

1. Navigate to **Programs > Programs**
2. Open a program and select the **Scoring** tab
3. Select a **Scoring Model** from active models
4. Enable **Use Scoring for Eligibility** to enforce criteria
5. Set eligibility via score range (min/max) or classification codes
6. Optionally enable **Auto-Score on Enrollment** and set **Maximum Score Age (Days)**

### UI Location

- **Program Scoring Configuration**: Programs > Programs > Scoring tab
- **Membership Scoring Info**: Visible as "Scoring Information" group on membership forms when program uses scoring
- **Scoring Model Programs**: Scoring > Scoring Models > Programs tab (also accessible via stat button)

### Security

Inherits access rights from parent modules:
- `spp.program` access controlled by `spp_programs` module ACLs
- `spp.program.membership` access controlled by `spp_programs` module ACLs
- `spp.scoring.model` access controlled by `spp_scoring` module ACLs

### Extension Points

- Override `check_scoring_eligibility(registrant)` on `spp.program` to customize eligibility logic
- Inherit `spp.program.membership` to add fields for score-based benefit calculations
- Hook into `_pre_enrollment_hook(partner)` for custom validation (called before eligibility check)
- Hook into `_post_enrollment_hook(partner)` for additional scoring actions (called after auto-score)

### Dependencies

`spp_scoring`, `spp_programs`
