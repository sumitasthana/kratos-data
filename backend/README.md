# Synth Data Studio Backend

Synthetic data generation pipeline with schema analysis, deterministic field resolution, and LLM-assisted data distribution specification.

## Project Structure

```
backend/
├── src/                          # Source code
│   ├── config/                   # Configuration management
│   ├── agents/                   # Agent implementations
│   │   ├── ontology/             # Schema ontology extraction
│   │   └── seed/                 # Seed data generation specification
│   ├── api/                      # FastAPI routes & endpoints
│   ├── models/                   # Data models & schemas
│   └── utils/                    # Utility functions
├── data/                         # Input data
│   ├── schemas/                  # DDL files
│   └── supplements/              # Domain supplements (optional)
├── outputs/                      # Generated artifacts (gitignored)
├── tests/                        # Test suite
├── scripts/                      # Standalone CLI scripts
├── .env                          # Environment variables
├── requirements.txt              # Python dependencies
└── main.py                       # Application entry point
```

## Pipeline Overview

### 1. Ontology Agent
Extracts schema structure from DDL files.
- **Input**: `data/schemas/01_ATOMIC_DEPOSIT_SYSTEM_DDL.sql`
- **Output**: `outputs/schema_graph.json`
- **Run**: `python scripts/run_ontology_agent.py`

### 2. Seed Agent Phase A (Distribution Spec Skeleton Builder)
Deterministically resolves table classifications and field strategies.
- **Input**: `outputs/schema_graph.json` + optional `data/supplements/domain_supplements.json`
- **Output**: `outputs/distribution_spec_skeleton.json`
- **Run**: `python scripts/run_seed_agent.py`

### 3. Seed Agent Phase B (Future)
LLM-assisted filling of unresolved fields with distributions and patterns.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the pipeline
python main.py
```

## Key Features

- **Domain-agnostic**: Works with any schema + data dictionary
- **Deterministic Phase A**: No LLM calls, pure Python logic
- **Conditional groups**: Supports field conditions based on parent values
- **Composite PKs**: Handles complex primary key scenarios
- **Foreign keys**: Proper FK dependency resolution
- **Audit columns**: Automatic handling of created_date, modified_date, etc.

## Configuration

See `.env` for required environment variables:
- `ANTHROPIC_API_KEY`: Claude API key for Phase B LLM processing
- `ANTHROPIC_MODEL`: Model name (default: claude-sonnet-4-20250514)

## Output Files

All generated artifacts are in `outputs/`:
- `schema_graph.json`: Complete schema structure with enums, FKs, constraints
- `distribution_spec_skeleton.json`: Field strategies and generation specs
