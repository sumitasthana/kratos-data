# Pilot Generator Documentation

The Pilot Generator creates synthetic data based on schema graphs and distribution specifications, with full foreign key resolution.

## Overview

The Pilot Generator is a standalone agent that:
- Reads table schemas from `schema_graph.json`
- Uses field distributions from `distribution_spec.json`
- Generates realistic synthetic data with proper relationships
- Outputs CSV files for each table

## Key Features

### Schema-Aware Generation
- Respects table schemas, types, and constraints
- Handles nullable fields with configured rates
- Supports various data types: string, integer, float, boolean, date, datetime

### Foreign Key Resolution
- Builds parent registry from generated data
- Resolves FK values from parent table PKs
- Supports composite primary keys (uses first field)
- Normalizes lookup keys for reliable matching

### Distribution Strategies

| Strategy | Description | Example |
|----------|-------------|---------|
| `enum` | Random selection from values | `transaction_type`: Deposit, Withdrawal |
| `distribution` | Statistical distribution | `balance`: normal(10000, 5000) |
| `unique` | Unique identifier generation | `account_id`: UUID or sequence |
| `computed` | Value computed from other fields | `created_date`: today |
| `fk` | Foreign key reference | `party_id`: references party table |

### Cross-Field Rules Enforcement

Handles rule types:
- `temporal_ordering`: Ensures date sequences
- `sum_constraint`: Validates field sums
- `balance_equation`: Maintains accounting balances
- `consistency`: Derived field matching
- `conditional_population`: Conditional nulls
- `mutual_exclusion`: XOR field population
- `referential_alignment`: Cross-table consistency

## Usage

### CLI

```bash
python src/agents/pilot_generator/pilot_generator.py \
  <schema_graph.json> \
  <distribution_spec.json> \
  <output_dir> \
  [--row-counts {"table1": 100, "table2": 500}]
```

### API

```python
from agents.pilot_generator import run_pilot

result = run_pilot(
    schema_graph=schema_graph_dict,
    distribution_spec=dist_spec_dict,
    output_dir="outputs/pilot",
    row_counts={"account": 500, "party": 100}
)
```

### FastAPI Endpoint

```bash
POST /agents/pilot
Content-Type: application/json

{
  "schema_graph": {...},
  "distribution_spec": {...},
  "output_dir": "outputs/pilot",
  "row_counts": {"account": 500}
}
```

## Data Generation Process

### Phase 1: Schema Analysis
1. Parse `schema_graph.json` for table schemas
2. Extract primary key information
3. Identify foreign key relationships
4. Build dependency graph (parent → child tables)

### Phase 2: Generation Order
Tables are generated in dependency order:
1. Tables with no FK dependencies first (root tables)
2. Tables with resolved FK dependencies next
3. Circular dependencies logged as warnings

### Phase 3: Field Value Generation

For each field, based on strategy:

**Enum Strategy:**
```python
random.choice(field['values'])
# With weights: random.choices(values, weights=weights)
```

**Distribution Strategy:**
```python
if distribution == 'normal':
    value = random.gauss(mean, std_dev)
elif distribution == 'uniform':
    value = random.uniform(min_val, max_val)
elif distribution == 'lognormal':
    value = random.lognormal(mean, sigma)  # mean in log-space
```

**FK Strategy:**
```python
# Look up parent table values
parent_key = f"{parent_table}.{parent_pk_field}"
if parent_key in parent_registry:
    value = random.choice(parent_registry[parent_key])
```

**Unique Strategy:**
```python
if dtype == 'integer':
    value = sequence_counter
else:
    value = str(uuid.uuid4())
```

### Phase 4: Registry Population

After each table generation:
1. Extract primary key field(s)
2. Build normalized key: `table_name.pk_field`
3. Store all PK values in `parent_registry`
4. Used by child tables for FK resolution

## Configuration

### Row Count Specification

Default row counts if not specified:

| Table Type | Default Rows |
|------------|-------------|
| Small reference tables | 100 |
| Standard tables | 500 |
| Large transaction tables | 2500 |

Override via `row_counts` parameter:
```json
{
  "party": 100,
  "account": 500,
  "transaction": 2500
}
```

### Field Distribution Parameters

**Normal Distribution:**
```json
{
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
  "strategy": "distribution",
  "distribution": "lognormal",
  "params": {
    "mean": 5,        // Log-space μ
    "sigma": 2        // Log-space σ
  }
}
```

**Enum with Weights:**
```json
{
  "strategy": "enum",
  "values": ["Active", "Inactive", "Closed"],
  "weights": {
    "Active": 0.7,
    "Inactive": 0.2,
    "Closed": 0.1
  }
}
```

## Output

Generated CSV files in specified output directory:

```
output_dir/
├── party.csv
├── account.csv
├── transaction.csv
└── ...
```

Each CSV includes:
- All fields from schema
- Properly typed values
- Resolved foreign keys
- Nullable fields populated according to rates

## Troubleshooting

### FK resolution failures
- Check parent table was generated before child
- Verify primary_key exists in schema_graph
- Review parent_registry logging for key formats

### Data type errors
- Ensure distribution params match field dtype
- Check enum values are valid for field type
- Verify date formats in computed fields

### Circular dependency warnings
- Agent logs warning but continues
- May result in null FK values
- Consider breaking circular refs in schema

## Architecture

```
PilotGenerator
├── load_inputs()          # Load schema_graph, dist_spec
├── _determine_generation_order()  # Topological sort
├── _generate_table()      # Generate single table
│   ├── _generate_field_value()   # Per-field generation
│   └── _resolve_fk()     # FK resolution
├── _write_csv()          # Output CSV files
└── run()                 # Main execution
```
