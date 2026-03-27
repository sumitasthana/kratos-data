# Synth Data Studio

A full-stack application for synthetic data generation, schema inference, and quality evaluation using LangGraph, AWS Bedrock, and Claude.

## Overview

Synth Data Studio provides an end-to-end pipeline for generating high-quality synthetic financial data:

1. **Schema Extraction** - Automatically extract table schemas from PostgreSQL databases
2. **Distribution Analysis** - Analyze field distributions and patterns using LLM-powered inference
3. **Synthetic Data Generation** - Generate realistic synthetic data using multi-agent workflows
4. **Quality Evaluation** - Comprehensive evaluation with programmatic checks and LLM judge

## Features

### Core Capabilities

- **Multi-Agent Architecture**: LangGraph-based workflow with specialized agents
- **Schema-Aware Generation**: Respects foreign key relationships and constraints
- **Distribution Matching**: Generates data matching statistical distributions
- **Quality Validation**: Three-stage evaluation pipeline with pass/fail signals
- **Cross-Field Rules**: Enforces temporal ordering, sum constraints, balance equations
- **LLM Judge**: Optional quality assessment using Claude

### Agents

| Agent | Purpose | Status |
|-------|---------|--------|
| Schema Extractor | Extract table schemas from PostgreSQL | ✅ Active |
| Distribution Analyzer | Infer field distributions using LLM | ✅ Active |
| Pilot Generator | Generate synthetic data with FK resolution | ✅ Active |
| Eval Agent | Quality evaluation with 3-stage pipeline | ✅ Active |

## Project Structure

```
synth-data-studio/
├── frontend/              # React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── components/  # React components (shadcn/ui)
│   │   ├── pages/       # Page components
│   │   ├── store/       # Zustand state management
│   │   ├── hooks/       # Custom React hooks
│   │   ├── types/       # TypeScript definitions
│   │   └── lib/         # Utilities and API client
│   └── public/          # Static assets
├── backend/             # FastAPI + LangGraph
│   ├── src/
│   │   ├── agents/      # Agent implementations
│   │   │   ├── eval_agent/        # Quality evaluation
│   │   │   ├── pilot_generator/   # Data generation
│   │   │   └── schema_analyzer/   # Schema extraction
│   │   ├── api/         # FastAPI routes
│   │   ├── graph/       # LangGraph workflows
│   │   └── utils/       # Helper functions
│   ├── outputs/         # Generated outputs
│   └── data/            # Data directories
└── wiki/                # Detailed documentation
    ├── agents/          # Agent documentation
    ├── api/             # API documentation
    ├── configuration/   # Config file guides
    └── development/     # Development guides
```

## Prerequisites

- Node.js 18+ (for frontend)
- Python 3.11+ (for backend)
- npm or yarn (for frontend package management)
- pip (for backend package management)

## Setup Instructions

### Backend Setup

1. **Install Python dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in your AWS credentials and other configuration:
   ```
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_REGION=us-east-1
   BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
   POSTGRES_CONNECTION_STRING=postgresql://user:password@localhost:5432/synthdata
   ```

3. **Run the backend server:**
   ```bash
   uvicorn main:app --reload
   ```
   The server will start on `http://localhost:8000`

### Frontend Setup

1. **Install Node dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   The default configuration points to the local backend:
   ```
   VITE_API_BASE_URL=http://localhost:8000
   ```

3. **Run the development server:**
   ```bash
   npm run dev
   ```
   The frontend will start on `http://localhost:3000`

## Verification

### Backend Health Check

Test the backend health endpoint:
```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{"status": "ok"}
```

### Frontend

Open your browser and navigate to `http://localhost:3000`. The frontend should load without TypeScript errors.

### CORS Configuration

The backend is configured to accept requests from `http://localhost:3000`. The frontend dev server proxies `/api` requests to `http://localhost:8000`.

## API Endpoints

### Data Generation
- `POST /agents/pilot` - Generate synthetic data from schema graph

### Quality Evaluation
- `POST /agents/eval` - Evaluate generated data quality

### Schema Operations
- `POST /agents/extract-schema` - Extract schema from PostgreSQL
- `POST /analyze-schema` - Analyze schema using LLM

## Configuration Files

| File | Purpose |
|------|---------|
| `distribution_spec.json` | Field distributions and generation rules |
| `eval_config.json` | Evaluation thresholds and settings |
| `schema_graph.json` | Table schemas and relationships |

## Documentation

See the [wiki/](wiki/) folder for detailed documentation:

- [Eval Agent](wiki/agents/eval-agent.md) - Quality evaluation pipeline
- [Pilot Generator](wiki/agents/pilot-generator.md) - Data generation
- [API Reference](wiki/api/endpoints.md) - Endpoint documentation
- [Configuration Guide](wiki/configuration/README.md) - Config file formats

## Environment Variables

### Required
```bash
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

### Optional
```bash
ANTHROPIC_API_KEY=your_key  # For LLM Judge
EVAL_AGENT_OUTPUT_DIR=path/to/eval/outputs
```

## Development

### Frontend Commands

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run lint` - Run ESLint
- `npm run preview` - Preview production build

### Backend Commands

- `uvicorn main:app --reload` - Start development server with auto-reload
- `python -m pytest` - Run tests (when added)

## Project Structure Details

### Frontend (`/frontend`)

- `/src/components` - React components organized by feature
  - `/layout` - Layout components
  - `/chat` - Chat-related components
  - `/tabs` - Tab components
  - `/forms` - Form components
  - `/shared` - Shared/reusable components
- `/src/pages` - Page components
- `/src/store` - Zustand store definitions
- `/src/hooks` - Custom React hooks
- `/src/types` - TypeScript type definitions
- `/src/lib` - Utility functions and API client
- `/public` - Static assets

### Backend (`/backend`)

- `/agents` - LangGraph agent definitions
- `/graph` - Graph workflow definitions
- `/routes` - FastAPI route handlers
- `/models` - Pydantic models and data schemas
- `/utils` - Utility functions
- `/data` - Data directories
  - `/uploads` - User uploaded files
  - `/outputs` - Generated outputs

## Dependencies

### Frontend

- React 18
- TypeScript
- Vite
- React Router v6
- Zustand
- Tailwind CSS v3
- shadcn/ui

### Backend

- FastAPI
- Uvicorn
- LangChain
- LangGraph
- AWS Bedrock (via boto3)
- PostgreSQL (psycopg2)
- Pandas & PyArrow
- Python-dotenv

## Notes

- Ensure both frontend and backend are running for full functionality
- The frontend proxies `/api` requests to the backend
- CORS is configured to allow requests from the frontend dev server
- Environment files (`.env`) are git-ignored; use `.env.example` as a template
