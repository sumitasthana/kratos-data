# Ontology Agent

**Commit**: `86e0184` - Build Ontology Agent for DDL parsing and schema graph generation

## Overview

The Ontology Agent extracts schema information from PostgreSQL DDL files and generates a comprehensive `schema_graph.json` file. It performs deterministic DDL parsing and uses AWS Bedrock (Claude) for intelligent detection of conditional field groups.

## Architecture

### Components

1. **DDLParser** - Deterministic parser for PostgreSQL DDL
2. **OntologyAgent** - Orchestrates parsing and LLM-assisted extraction
3. **FastAPI Route** - HTTP endpoint for DDL file uploads

### Key Features

- **Deterministic Parsing**: Extracts tables, columns, constraints, enums, and foreign keys without LLM
- **LLM-Assisted Detection**: Uses Claude to identify conditional field groups (e.g., party_type discriminator)
- **Topological Sort**: Computes generation order respecting FK dependencies
- **Self-Validation**: Validates schema consistency and logs warnings
- **No Database Required**: Pure text parsing; no live database connection

## Parsing Rules

### Deterministic Extraction (No LLM)

- **Tables**: All `CREATE TABLE` statements
- **Columns**: Name, type, nullable, default value
- **Primary Keys**: Simple and composite PKs
- **Foreign Keys**: from_table, from_field, to_table, to_field, nullable
- **Unique Constraints**: Fields and WHERE conditions
- **Check Constraints**: Name and expression
- **Enums**: All `CREATE TYPE ... AS ENUM` statements and values

### LLM-Assisted Extraction

- **Conditional Groups**: Fields that only apply when another field has a specific value
  - Example: `party_type='Individual'` → `individual_name_given`, `individual_ssn`, etc.
  - Detected via Claude analysis of column naming patterns and table structure

## Output Schema

### schema_graph.json Structure

```json
{
  "tables": [
    {
      "name": "table_name",
      "primary_key": "id" | ["id1", "id2"],
      "pk_type": "simple" | "composite",
      "columns": [
        {
          "name": "column_name",
          "type": "VARCHAR(50)",
          "enum_name": "enum_name" | null,
          "nullable": boolean,
          "default": "value" | null
        }
      ],
      "conditional_groups": [
        {
          "condition_field": "party_type",
          "condition_value": "Individual",
          "fields": ["individual_name_given", "individual_ssn"]
        }
      ],
      "check_constraints": [
        {
          "name": "ck_balance_non_negative",
          "expression": "current_balance >= 0"
        }
      ],
      "unique_constraints": [
        {
          "fields": ["account_number"],
          "condition": null
        }
      ],
      "foreign_keys": [
        {
          "from_field": "owner_party_id",
          "to_table": "party",
          "to_field": "party_id",
          "nullable": false
        }
      ],
      "referenced_by": ["account_ownership", "account_feature"]
    }
  ],
  "enums": {
    "party_type_enum": ["Individual", "Organization", "Government"],
    "account_status_enum": ["Active", "Dormant", "Closed", "Frozen"]
  },
  "foreign_keys": [
    {
      "from_table": "account",
      "from_field": "primary_owner_party_id",
      "to_table": "party",
      "to_field": "party_id",
      "nullable": false
    }
  ],
  "generation_order": ["party", "account", "account_ownership", ...],
  "generation_order_rationale": {
    "party": "No FK dependencies",
    "account": "Depends on: party"
  },
  "warnings": ["Circular FK dependency detected"]
}
```

## Generation Order

### Topological Sort Algorithm

1. Build dependency graph from FK relationships
2. Compute in-degree for each table
3. Process tables with in-degree 0 first (no FK dependencies)
4. Decrement in-degree as dependencies are satisfied
5. Deterministic ordering via sorted queue

### Special Cases

- **Circular Dependencies**: Detected and logged as warnings; tables still included in order
- **Self-References**: Tables with FKs to themselves (e.g., `transaction.original_transaction_id`)
- **No FK Dependencies**: Tables like `party`, `audit_log`, `gl_deposit_control_account` appear early

## Usage

### Command Line

```bash
python agents/ontology_agent.py --ddl <path_to_ddl.sql> --output <path_to_schema_graph.json>
```

**Options:**
- `--ddl` (required): Path to PostgreSQL DDL file
- `--output` (required): Path to output schema_graph.json
- `--model` (optional): Bedrock model ID (default: `anthropic.claude-sonnet-4-20250514`)

### FastAPI Endpoint

```bash
POST /agents/ontology
Content-Type: multipart/form-data

file: <ddl_file.sql>
```

**Response:**
```json
{
  "tables": [...],
  "enums": {...},
  "generation_order": [...],
  "warnings": [...]
}
```

## Implementation Details

### DDLParser Class

**Methods:**
- `parse_file(ddl_path)` - Main entry point
- `_extract_enums(content)` - Extract CREATE TYPE statements
- `_extract_tables(content)` - Extract CREATE TABLE statements
- `_parse_table(table_name, table_body)` - Parse single table
- `_parse_column(line, table_name)` - Parse column definition
- `_build_referenced_by()` - Build reverse FK relationships

### OntologyAgent Class

**Methods:**
- `process_ddl(ddl_path, output_path)` - Orchestrate full pipeline
- `_detect_conditional_groups()` - LLM-assisted detection
- `_call_bedrock(prompt)` - Invoke Claude via boto3
- `_compute_generation_order()` - Topological sort
- `_validate_schema(generation_order)` - Consistency checks
- `_build_output()` - Construct final JSON

### Validation

**Checks:**
1. All FK targets exist in tables list
2. Generation order contains all tables exactly once
3. Generation order respects FK dependencies (no table before its dependency)
4. Circular dependencies detected and logged

**Warnings Logged:**
- Missing or extra tables in generation order
- Generation order violations
- Bedrock API errors (conditional group detection)
- Circular FK dependencies

## AWS Bedrock Integration

### Credentials

Uses boto3 default credential chain:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. IAM role (EC2, Lambda, ECS)
3. Shared credentials file (`~/.aws/credentials`)
4. Shared config file (`~/.aws/config`)

**No hardcoded credentials.**

### Model

- Default: `anthropic.claude-sonnet-4-20250514` (latest Claude Sonnet)
- Configurable via `--model` flag
- Async invocation with JSON response parsing

## Files

### Created
- `backend/agents/ontology_agent.py` - Main agent implementation (400+ lines)
- `backend/routes/ontology.py` - FastAPI route handler
- `backend/schema_graph.json` - Example output

### Modified
- `backend/main.py` - Register ontology router
- `backend/requirements.txt` - Add boto3 dependency

## Testing

### Test with Example DDL

```bash
cd backend
python agents/ontology_agent.py --ddl ../../01_ATOMIC_DEPOSIT_SYSTEM_DDL.sql --output schema_graph.json
```

**Expected Output:**
- 14 tables parsed
- 40+ enums extracted
- 50+ foreign keys identified
- Generation order respects all FK dependencies
- Warnings logged for circular dependencies (transaction self-reference)

### Verify Output

```bash
# Check table count
jq '.tables | length' schema_graph.json

# Check enum count
jq '.enums | length' schema_graph.json

# Check generation order
jq '.generation_order' schema_graph.json

# Check warnings
jq '.warnings' schema_graph.json
```

## Known Limitations

1. **Conditional Groups**: Requires Bedrock API access; falls back gracefully if unavailable
2. **Circular Dependencies**: Detected but not resolved; tables still included in order
3. **Complex Constraints**: Multi-line CHECK constraints may not parse perfectly
4. **Type Parsing**: Assumes standard PostgreSQL types; custom types treated as enums if defined

## Future Enhancements

1. Support for table partitioning
2. Support for indexes with expressions
3. Support for generated columns
4. Support for triggers and stored procedures
5. Improved circular dependency resolution
6. Schema diff generation (compare two DDL files)

## Notes

- Parser is deterministic and reproducible
- No data generation or inference
- All information derived directly from DDL
- Suitable for documentation generation and data pipeline orchestration
- Can be extended for other SQL dialects (MySQL, SQL Server, etc.)

## Build Status

✅ Ontology Agent functional
✅ DDL parsing working
✅ FastAPI route integrated
✅ Schema graph generation verified
⚠️ Conditional group detection requires Bedrock credentials
