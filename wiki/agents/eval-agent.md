# Eval Agent Documentation

The Eval Agent provides comprehensive quality evaluation for synthetic data through a three-stage pipeline.

## Overview

The Eval Agent evaluates generated CSV data against a `distribution_spec.json` and produces a structured report with a pass/fail signal.

## Three-Stage Evaluation Pipeline

### Stage 1: Programmatic Checks (No LLM)

#### 1.1 Referential Integrity
- Validates all foreign key values exist in parent primary key columns
- Builds parent registry from CSV files keyed by table_name.field_name
- Infers parent table from FK field names (e.g., `party_id` → `party` table)
- Reports violations with child table, field, and invalid values

**Pass Criteria:** 100% pass rate (zero tolerance for FK violations)

#### 1.2 Cross-Field Rules
Evaluates rules with `enforcement: validator` (or all rules if none tagged):

| Rule Type | Description | Check |
|-----------|-------------|-------|
| `temporal_ordering` | Date field A ≤ Date field B | `field_a <= field_b` |
| `sum_constraint` | Sum of fields equals target | `sum(fields) == target` |
| `balance_equation` | Accounting balance | `debits + credits == total` |
| `consistency` | Derived field matches source | `source == derived` |
| `conditional_population` | Field null when condition false | Conditional null check |
| `mutual_exclusion` | Only one field populated | XOR check |
| `referential_alignment` | Cross-table value match | FK value exists in ref table |

**Pass Criteria:** 95% pass rate (5% tolerance)

#### 1.3 Distribution Similarity
Checks numeric and enum field distributions:

**Numeric Fields:**
- Compares actual mean vs expected mean
- Flags if deviation > 20%
- Supports: normal, uniform, lognormal distributions

**Lognormal Parameterization:**
- `numpy.random.lognormal(mean, sigma)` expects LOG-SPACE mean (μ)
- If spec param named `mean` → treat as log-space μ
- If spec param named `actual_mean` → convert: μ = log(actual_mean)

**Enum Fields:**
- Compares actual value frequencies vs expected weights
- Flags if any value weight deviation > 15%

**Pass Criteria:** 80% pass rate (20% tolerance)

### Stage 2: LLM Judge (Optional)

When enabled (`llm_judge.enabled: true`):
- Samples rows per table (default: 20)
- Sends to Claude for quality assessment
- Evaluates:
  1. Realism: Do values look like real-world data?
  2. Anomalies: Any impossible or suspicious values?
  3. Conditional correctness: Are conditional fields appropriate?
  4. Quality score: Integer 0-10

**Quality Warning:** Average score < 6.0 triggers warning (advisory only)

### Stage 3: Pass/Fail Signal

Computes overall pass based on thresholds:

```python
pass_signal = (
    referential_integrity.passed and
    cross_field_rules.passed and
    distribution_similarity.passed
)
```

## Configuration

### eval_config.json

```json
{
  "pass_threshold": {
    "referential_integrity_pass_rate": 1.0,
    "cross_field_rule_pass_rate": 0.95,
    "distribution_similarity_threshold": 0.80,
    "nullable_rate_tolerance": 0.05
  },
  "llm_judge": {
    "enabled": true,
    "sample_size_per_table": 20,
    "model": "claude-sonnet-4-20250514"
  },
  "skip_tables": [],
  "output_dir": null
}
```

## CLI Usage

```bash
python src/agents/eval_agent/eval_agent.py \
  <csv_directory> \
  <distribution_spec.json> \
  [--config eval_config.json] \
  [--output report.json]
```

## Report Schema

```json
{
  "run_id": "uuid",
  "timestamp": "2024-01-01T00:00:00+00:00",
  "distribution_spec_hash": "sha256_hash",
  "status": "pass|fail",
  "pass_signal": true|false,
  "stages": {
    "referential_integrity": {
      "pass_rate": 1.0,
      "passed": true,
      "violations": []
    },
    "cross_field_rules": {
      "pass_rate": 1.0,
      "passed": true,
      "results": []
    },
    "distribution_similarity": {
      "pass_rate": 0.85,
      "passed": true,
      "results": []
    },
    "llm_judge": {
      "enabled": true,
      "average_quality_score": 8.5,
      "llm_quality_warning": false,
      "table_results": []
    }
  },
  "summary": {
    "tables_evaluated": 7,
    "total_rows_evaluated": 8600,
    "rules_evaluated": 12,
    "rules_passed": 12,
    "fk_violations": 0,
    "distribution_flags": 3,
    "llm_quality_warning": false
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | LLM model for judge |
| `EVAL_AGENT_OUTPUT_DIR` | `backend/data/outputs/eval` | Output directory |

## Troubleshooting

### No rules evaluated
Check if `cross_field_rules` in distribution_spec have `enforcement: validator`. If missing, agent will evaluate all rules with a warning.

### Distribution flags on numeric fields
Verify lognormal parameters are in log-space (not actual mean). Check agent logs for parameter interpretation.

### LLM Judge authentication errors
Set `ANTHROPIC_API_KEY` environment variable or disable judge in config.
