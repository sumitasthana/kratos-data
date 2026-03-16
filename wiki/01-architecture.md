# Architecture Overview

## System Design

The synth-data-studio is a multi-stage synthetic data generation pipeline with clear separation of concerns:

```
DDL File
   ↓
[Ontology Agent] → schema_graph.json
   ↓
[Seed Agent Phase A] → distribution_spec_skeleton.json
   ↓
[Seed Agent Phase B] → final_distribution_spec.json
   ↓
[Pilot Generator] → synthetic_data.csv
```

## Components

### 1. Ontology Agent
- **Purpose**: Extract and analyze database schema from DDL
- **Input**: SQL DDL file
- **Output**: schema_graph.json with complete schema metadata
- **Key Features**:
  - Table and column extraction
  - Primary key detection (simple and composite)
  - Foreign key relationship mapping
  - Enum type extraction
  - CHECK constraint parsing
  - Conditional group detection (LLM-assisted)
  - Topological sort for generation order

### 2. Seed Agent Phase A (Distribution Spec Skeleton Builder)
- **Purpose**: Deterministically resolve table classifications and field strategies
- **Input**: schema_graph.json + optional domain_supplements.json
- **Output**: distribution_spec_skeleton.json with resolved fields
- **Key Features**:
  - Table classification (independent, dependent, derived, computed)
  - Deterministic field resolution (8 rules)
  - Conditional group application
  - Validation of output structure
  - No LLM calls - pure Python logic

### 3. Seed Agent Phase B (Future)
- **Purpose**: LLM-assisted filling of unresolved fields
- **Input**: distribution_spec_skeleton.json
- **Output**: final_distribution_spec.json with all fields resolved
- **Key Features**:
  - Distribution strategy inference
  - Cross-field rule detection
  - Nullable rate inference
  - Domain-specific customization

### 4. Pilot Generator (Future)
- **Purpose**: Generate synthetic data based on distribution spec
- **Input**: final_distribution_spec.json
- **Output**: CSV or database records

## Directory Structure

```
backend/
├── src/
│   ├── agents/
│   │   ├── ontology/        # Schema extraction
│   │   └── seed/            # Data generation spec
│   ├── prompts/             # LLM prompts (YAML)
│   ├── api/                 # FastAPI endpoints
│   ├── config/              # Configuration
│   ├── models/              # Data models
│   └── utils/               # Utilities
├── data/
│   ├── schemas/             # Input DDL files
│   └── supplements/         # Domain supplements
├── outputs/                 # Generated artifacts
├── scripts/                 # CLI entry points
└── tests/                   # Test suite
```

## Data Flow

1. **Schema Extraction**: DDL → Ontology Agent → schema_graph.json
2. **Deterministic Resolution**: schema_graph.json → Phase A → distribution_spec_skeleton.json
3. **LLM Enhancement**: distribution_spec_skeleton.json → Phase B → final_distribution_spec.json
4. **Data Generation**: final_distribution_spec.json → Pilot Generator → synthetic_data

## Key Design Principles

- **Separation of Concerns**: Each agent has a single responsibility
- **Deterministic Phase A**: No randomness or external dependencies in Phase A
- **LLM-Assisted Phase B**: Only Phase B uses LLM for intelligent inference
- **Domain-Agnostic**: Works with any schema without hardcoded business logic
- **Versioned Prompts**: All LLM prompts in YAML with version control
- **Clean Structure**: Source code, data, outputs, and docs clearly separated
