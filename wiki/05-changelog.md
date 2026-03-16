# Change Log

## [Latest] - 2026-03-16

### Added
- **Prompts Directory**: Created `backend/src/prompts/` with versioned YAML files for all agent prompts
  - `ontology_agent_prompts.yaml`: Conditional group detection and schema validation prompts
  - `seed_agent_prompts.yaml`: Field distribution, cross-field rules, and nullable rate inference prompts
  
- **Wiki Documentation**: Created `wiki/` folder with comprehensive project documentation
  - Architecture overview and system design
  - Pipeline stages and data flow
  - Agent responsibilities and features
  - Change log and project history

### Changed
- **Backend Structure**: Reorganized for cleanliness and scalability
  - All source code moved to `src/` directory
  - Agents organized in `src/agents/ontology/` and `src/agents/seed/`
  - Output files moved to `outputs/` (gitignored)
  - Input data in `data/schemas/` and `data/supplements/`
  - CLI scripts in `scripts/` directory

### Documentation
- Added `.gitignore` to exclude outputs and generated artifacts
- Added comprehensive `README.md` with setup and pipeline overview
- Created CLI scripts for easy agent execution

## [v0.1.0] - 2026-03-16

### Completed
- **Ontology Agent**: Full schema extraction from DDL
  - Table and column parsing with all constraints
  - Primary key detection (simple and composite)
  - Foreign key relationship mapping
  - Enum type extraction
  - CHECK constraint parsing (single and multi-line)
  - Conditional group detection via LLM
  - Topological sort for generation order
  - Output: `schema_graph.json` with 14 tables, 308 fields

- **Seed Agent Phase A**: Deterministic field resolution
  - Table classification (independent/dependent)
  - 8 deterministic field resolution rules
  - Conditional group application
  - Output validation with 10 checks
  - Output: `distribution_spec_skeleton.json` with 44.2% resolution rate

- **LLM Integration**: Switched from AWS Bedrock to Anthropic API
  - Updated `.env` with Anthropic credentials
  - Integrated Claude Sonnet model
  - Successful LLM calls for conditional group detection

- **Bug Fixes**:
  - Fixed multi-line CHECK constraint parsing
  - Fixed unnamed inline CHECK constraints
  - Fixed parser bleed into subsequent CREATE statements
  - Removed all fake columns from schema extraction

### Infrastructure
- Created clean backend project structure
- Separated source code, data, outputs, and documentation
- Added CLI scripts for agent execution
- Added comprehensive README and documentation

## Future Roadmap

### Phase B (Seed Agent)
- [ ] LLM-assisted field distribution inference
- [ ] Cross-field rule detection
- [ ] Nullable rate inference
- [ ] Domain-specific customization

### Pilot Generator
- [ ] Synthetic data generation from distribution spec
- [ ] CSV and database output support
- [ ] Data quality validation
- [ ] Performance optimization

### Enhancements
- [ ] Web UI for schema visualization
- [ ] Interactive prompt tuning
- [ ] Multi-schema support
- [ ] Incremental data generation
- [ ] Data quality metrics
