# Configuration Guide

This guide covers all configuration files used in the Synth Data Studio.

## Configuration Files Overview

| File | Purpose | Location |
|------|---------|----------|
| `distribution_spec.json` | Field distributions and generation rules | Backend outputs |
| `eval_config.json` | Evaluation thresholds and LLM settings | Backend root |
| `schema_graph.json` | Table schemas and relationships | Backend outputs |

---

## distribution_spec.json

Defines how synthetic data should be generated for each field.

### Structure

```json
{
  "tables": [
    {
      "name": "table_name",
      "fields": [
        {
          "name": "field_name",
          "dtype": "string|integer|float|boolean|date|datetime",
          "strategy": "enum|distribution|unique|computed|fk",
          ...
        }
      ],
      "cross_field_rules": [...]
    }
  ]
}
```

### Field Strategies

#### Enum Strategy

Random selection from predefined values.

```json
{
  "name": "account_status",
  "dtype": "string",
  "strategy": "enum",
  "values": ["Active", "Inactive", "Closed"],
  "weights": {
    "Active": 0.7,
    "Inactive": 0.2,
    "Closed": 0.1
  },
  "nullable_rate": 0.0
}
```

#### Distribution Strategy

Statistical distribution for numeric fields.

**Normal Distribution:**
```json
{
  "name": "account_balance",
  "dtype": "float",
  "strategy": "distribution",
  "distribution": "normal",
  "params": {
    "mean": 10000,
    "std_dev": 5000
  }
}
```

**Lognormal Distribution:**
```json
{
  "name": "transaction_amount",
  "dtype": "float",
  "strategy": "distribution",
  "distribution": "lognormal",
  "params": {
    "mean": 5,
    "sigma": 2
  }
}
```

**Uniform Distribution:**
```json
{
  "name": "transaction_time",
  "dtype": "float",
  "strategy": "distribution",
  "distribution": "uniform",
  "params": {
    "min": 0,
    "max": 100
  }
}
```

#### Unique Strategy

Auto-generated unique identifiers.

```json
{
  "name": "account_id",
  "dtype": "string",
  "strategy": "unique",
  "unique": true
}
```

#### Computed Strategy

Values computed from other fields or functions.

```json
{
  "name": "created_date",
  "dtype": "date",
  "strategy": "computed",
  "expression": "today()"
}
```

#### FK Strategy

Foreign key reference to parent table.

```json
{
  "name": "party_id",
  "dtype": "string",
  "strategy": "fk",
  "fk": {
    "table": "party",
    "field": "party_id"
  }
}
```

### Cross-Field Rules

Rules that validate relationships between fields.

```json
{
  "cross_field_rules": [
    {
      "type": "temporal_ordering",
      "rule": "Ensure start_date <= end_date",
      "field_a": "start_date",
      "field_b": "end_date",
      "enforcement": "validator"
    },
    {
      "type": "sum_constraint",
      "rule": "Sum of fields equals target",
      "fields": ["field1", "field2"],
      "target_field": "total",
      "enforcement": "validator"
    },
    {
      "type": "balance_equation",
      "rule": "Debits + Credits = Total",
      "fields": ["debits", "credits", "total"],
      "enforcement": "validator"
    }
  ]
}
```

---

## eval_config.json

Controls quality evaluation behavior and thresholds.

### Structure

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
  "output_dir": "outputs/eval"
}
```

### Pass Thresholds

| Threshold | Default | Description |
|-----------|---------|-------------|
| `referential_integrity_pass_rate` | 1.0 | FK validation pass rate (zero tolerance) |
| `cross_field_rule_pass_rate` | 0.95 | Rule evaluation pass rate (5% tolerance) |
| `distribution_similarity_threshold` | 0.80 | Distribution match threshold (20% tolerance) |
| `nullable_rate_tolerance` | 0.05 | Nullable rate deviation tolerance |

### LLM Judge Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | false | Enable/disable LLM evaluation |
| `sample_size_per_table` | 20 | Rows sampled per table for LLM review |
| `model` | claude-sonnet-4-20250514 | Claude model ID |

### Other Options

| Option | Default | Description |
|--------|---------|-------------|
| `skip_tables` | [] | Tables to exclude from evaluation |
| `output_dir` | backend/data/outputs/eval | Report output directory |

---

## schema_graph.json

Defines database schema structure and relationships.

### Structure

```json
{
  "tables": [
    {
      "name": "party",
      "columns": [
        {
          "name": "party_id",
          "type": "string",
          "nullable": false,
          "primary_key": true
        },
        {
          "name": "party_name",
          "type": "string",
          "nullable": false
        }
      ],
      "primary_key": "party_id",
      "foreign_keys": []
    },
    {
      "name": "account",
      "columns": [...],
      "primary_key": "account_id",
      "foreign_keys": [
        {
          "column": "party_id",
          "references": {
            "table": "party",
            "column": "party_id"
          }
        }
      ]
    }
  ]
}
```

### Table Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | string | Table name |
| `columns` | array | Column definitions |
| `primary_key` | string/array | Primary key field(s) |
| `foreign_keys` | array | FK relationships |

### Column Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | string | Column name |
| `type` | string | Data type |
| `nullable` | boolean | Whether NULL is allowed |
| `primary_key` | boolean | Is this a PK column |

---

## Environment Variables

### Required

```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

### Optional

```bash
# Database
POSTGRES_CONNECTION_STRING=postgresql://user:pass@host:5432/db

# LLM Judge (Anthropic)
ANTHROPIC_API_KEY=your_anthropic_key
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Eval Agent
EVAL_AGENT_OUTPUT_DIR=custom/output/path

# Generation
PILOT_OUTPUT_DIR=custom/output/path
```
