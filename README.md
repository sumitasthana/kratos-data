# Cardinal

Cardinal generates fake but realistic synthetic data for US retail credit cards.

Two halves:

- **Cardinal Studio** — a conversational web app. You describe what you need in plain
  language; an assistant interviews you, then hands a structured contract to a builder
  that produces a validated Cardinal spec, a design graph, and a data sample.
- **The engine** — deterministic, seeded NumPy/SciPy. No LLM ever touches generated
  data rows. Accounts advance as month-by-month events, so any number can be explained.

The design principle: an **ontology** (a stored map of how credit-card billing works and
what the law requires) is the source of correctness; the LLM only handles the human
conversation. The ontology decides what is mandatory; the LLM never invents fields.

## How it fits together

```
frontend/                     # React + TypeScript + Vite + Tailwind + Zustand (Cardinal Studio)
  src/
    pages/Studio.tsx          # chat (left) + Graph / Spec / Data tabs (right)
    interviewStore.ts         # session state
    api.ts                    # calls the backend
    components/Graph.tsx      # Cytoscape design graph

backend/
  main.py                     # FastAPI: /api/session/{start,message}, /generate, /spec.zip
  src/cardinal/               # the engine (flat modules; kept flat until they grow)
    spec.py dag.py dist.py rng.py money.py state.py invariants.py emit.py cli.py
    cycle.py                  # the shared per-account cycle loop (the "shared counter")
    billing.py                # first domain module: correct billing on that loop
    agents/                   # LLM + ontology, spec-authoring time only (never imported by the engine)
      interviewer.py          # LangGraph conversational agent (Claude via Bedrock)
      builder.py              # deterministic: contract -> ontology completion -> validated spec
      contract.py             # the handoff schema between the two agents
      ontology_service.py     # loads/reasons over the ontology (rdflib + owlrl + pyshacl)
      spec_export.py          # ontology design -> runnable engine spec bundle
      ontology/               # core.ttl (vocabulary), billing.ttl (generated), billing_ontology.xlsx
  specs/                      # the skeleton's own example spec bundle
  tests/                      # determinism, reconciliation, cycle-detection, ablation

docs/                         # architecture-flow.html, STATUS.md (dev log + next steps)
```

## Design rules (non-negotiable)

1. **The engine never imports `agents/`.** Generation runs with no network and no model.
2. **LLMs build the machine; deterministic code runs it.** No LLM produces data rows.
3. **Same seed, same bytes.** Every entity draws from its own RNG stream.
4. **Money is `Decimal`, never float.** A cent of drift is a bug the system catches.
5. **No hardcoded numbers in domain logic.** Distribution params live in specs/config, not code.

## Prerequisites

- Python 3.11+ (developed on 3.14)
- Node.js 18+
- For live Claude: Amazon Bedrock access via a `.env` at the project root (see below)

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt          # engine deps
pip install -r requirements-agents.txt   # Studio agents deps (rdflib, owlrl, pyshacl, langgraph, langchain-aws)
python -m uvicorn main:app --port 8000
```

`.env` (project root, git-ignored) for live Claude on Bedrock:

```
AWS_BEARER_TOKEN_BEDROCK=...
AWS_BEDROCK_REGION=us-east-1
AWS_BEDROCK_MODEL=us.anthropic.claude-sonnet-4-6
```

Without a key the Studio runs in an offline mode that builds a default portfolio.

### Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000 (proxies /api to :8000)
```

### Engine only (no UI)

```bash
cd backend
python -m cardinal.cli validate --spec specs/portfolio.yaml
python -m cardinal.cli generate --spec specs/portfolio.yaml --out data
```

## Status

See [docs/STATUS.md](docs/STATUS.md) for what is built, what is honest-but-simplified,
and the next steps.
