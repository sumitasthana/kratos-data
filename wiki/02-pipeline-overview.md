# Pipeline Overview

## Data Generation Pipeline Stages

### Stage 1: Schema Extraction (Ontology Agent)

**Input**: `data/schemas/01_ATOMIC_DEPOSIT_SYSTEM_DDL.sql`

**Process**:
1. Parse CREATE TABLE statements
2. Extract column definitions with types and constraints
3. Identify primary keys (simple and composite)
4. Map foreign key relationships
5. Extract enum type definitions
6. Parse CHECK constraints
7. Detect conditional groups via LLM
8. Compute topological sort for generation order

**Output**: `outputs/schema_graph.json`

**Key Metrics**:
- 14 tables extracted
- 308 total fields
- All foreign key dependencies resolved
- Generation order: audit_log → gl_deposit_control_account → party → account → ...

### Stage 2: Deterministic Field Resolution (Seed Agent Phase A)

**Input**: 
- `outputs/schema_graph.json`
- Optional: `data/supplements/domain_supplements.json`

**Process**:
1. Classify tables (independent/dependent/derived/computed)
2. Apply 8 deterministic field resolution rules:
   - UUID PKs → sequence strategy
   - Composite PK components → null with role
   - Foreign keys → foreign_key strategy
   - Enum fields → enum strategy
   - Boolean fields → enum [true, false]
   - Audit columns → constant strategy
   - Fields with defaults → null with schema_default
   - Everything else → null for Phase B

3. Apply conditional groups to fields
4. Validate output structure

**Output**: `outputs/distribution_spec_skeleton.json`

**Resolution Rate**: 44.2% (136 of 308 fields resolved)

### Stage 3: LLM-Assisted Resolution (Seed Agent Phase B) - Future

**Input**: `outputs/distribution_spec_skeleton.json`

**Process**:
1. For each unresolved field:
   - Infer distribution strategy (normal, uniform, poisson, etc.)
   - Determine value ranges (min, max)
   - Infer nullable rate
   - Identify cross-field rules

2. For each table:
   - Infer row count distribution
   - Identify generation constraints

**Output**: `outputs/final_distribution_spec.json`

**Expected Resolution**: 100% of fields

### Stage 4: Synthetic Data Generation (Pilot Generator) - Future

**Input**: `outputs/final_distribution_spec.json`

**Process**:
1. For each table in generation order:
   - Generate rows according to row_count_distribution
   - For each field, apply generation strategy
   - Enforce cross-field rules
   - Respect conditional groups

2. Write output to CSV or database

**Output**: `outputs/synthetic_data.csv` or database records

## Field Resolution Strategies

| Strategy | Description | Example |
|----------|-------------|---------|
| `sequence` | Generate sequential values | UUID primary keys |
| `enum` | Pick from predefined values | Status fields, types |
| `foreign_key` | Reference parent table | Account ID in transactions |
| `constant` | Fixed value | CURRENT_TIMESTAMP for created_date |
| `distribution` | Sample from distribution | Numeric amounts |
| `date_range` | Generate dates in range | Transaction dates |
| `regex` | Generate matching pattern | Phone numbers, emails |
| `conditional` | Depends on other field | Individual fields if party_type='Individual' |
| `computed` | Derived from other fields | Total = sum of components |
| `null` | Unresolved, needs Phase B | Domain-specific inference needed |

## Conditional Groups

Fields grouped by a condition field value:

```json
{
  "condition_field": "party_type",
  "condition_value": "Individual",
  "fields": ["individual_name_given", "individual_ssn", "individual_date_of_birth"]
}
```

When generating data:
- If party_type = 'Individual', populate individual_* fields
- If party_type = 'Organization', populate organization_* fields
- If party_type = 'Government', populate government_* fields

## Generation Order

Topologically sorted to respect foreign key dependencies:

1. `audit_log` - No FKs
2. `gl_deposit_control_account` - No FKs
3. `party` - No FKs (root entity)
4. `account` - FK to party
5. `account_feature` - FK to account
6. `account_ownership` - FK to account, party
7. `account_regulatory_classification` - FK to account
8. `daily_account_balance` - FK to account (composite PK)
9. `deposit_insurance_calculation` - FK to account, classification
10. `fiduciary_arrangement` - FK to account, party
11. `fiduciary_beneficiary` - FK to fiduciary_arrangement, party
12. `kyc_cip_verification` - FK to party
13. `official_items` - FK to account
14. `transaction` - FK to account, party, self-referencing

## Validation Checks

Phase A validates:
- All tables from schema_graph present in output
- No enum field has weights filled
- Every single-field UUID PK is sequence
- Every FK field is foreign_key strategy
- Composite PK non-UUID components have role
- Fields in conditional_groups have conditions
- Audit columns are constant
- Reference lookups populated if supplements provided
