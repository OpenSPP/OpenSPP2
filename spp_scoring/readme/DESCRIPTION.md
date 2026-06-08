Configurable scoring framework for poverty assessment, vulnerability analysis, and beneficiary targeting. Supports Proxy Means Test (PMT), Social Welfare Development Index (SWDI), and custom eligibility formulas. Calculates scores using weighted indicators, CEL expressions, or lookup tables, then classifies results into threshold-based categories.

### Key Capabilities

- Define scoring models with weighted indicators, calculation methods, and classification thresholds
- Calculate scores using weighted sums, CEL formulas, lookup tables, or range mappings
- Classify results into categories (e.g., extremely poor, moderate, non-poor) based on score ranges
- Batch process registrants with async queue_job support for large datasets
- Track per-indicator breakdown with field value snapshots and weighted contributions
- Version scoring models with effective dates and activation controls

### Key Models

| Model                       | Description                                                  |
| --------------------------- | ------------------------------------------------------------ |
| `spp.scoring.model`         | Defines a scoring methodology with indicators and thresholds |
| `spp.scoring.indicator`     | Individual scoring component with field mapping and weight   |
| `spp.scoring.result`        | Calculated score with classification and audit trail        |
| `spp.scoring.threshold`     | Maps score ranges to classification categories               |
| `spp.scoring.value_mapping` | Maps field values to scores for indicators                   |
| `spp.scoring.result.detail` | Per-indicator breakdown for a scoring result                 |
| `spp.scoring.engine`        | Abstract model providing scoring calculation service         |
| `spp.scoring.batch.job`     | Tracks progress of async batch scoring operations            |

### Configuration

After installing:

1. Navigate to **Scoring > Scoring Models**
2. Create a model, set calculation method (weighted sum, CEL formula, etc.)
3. Add indicators under the "Indicators" tab, configure field paths and weights
4. Add thresholds under the "Thresholds" tab to define classification ranges
5. Click "Activate" to validate and enable the model

For async batch processing, verify the **Scoring Batch** queue job channel exists under **Settings > Technical > Queue Job Channels**.

### UI Location

- **Menu**: Scoring (top-level menu)
- **Scoring Models**: Scoring > Scoring Models
- **Results**: Scoring > Scoring Results
- **Batch Scoring**: Scoring > Batch Scoring
- **Configuration**: Scoring > Configuration > Indicators / Thresholds

### Security

| Group                               | Access                                               |
| ----------------------------------- | ---------------------------------------------------- |
| `spp_scoring.group_scoring_viewer`  | Read scoring models and results                      |
| `spp_scoring.group_scoring_officer` | Run scoring calculations, create/edit results (no delete) |
| `spp_scoring.group_scoring_manager` | Full CRUD including model configuration              |

### Extension Points

- Inherit `spp.scoring.indicator` and override `_calculate_derived()` to add custom calculation types
- Inherit `spp.scoring.engine` and override `_build_cel_context()` to expose additional registrant fields to CEL
- Override `_validate_configuration()` on `spp.scoring.model` to add custom validation rules
- Use CEL formulas for complex scoring logic without code changes

### Dependencies

`base`, `mail`, `spp_security`, `spp_registry`, `spp_cel_domain`, `spp_cel_widget`
