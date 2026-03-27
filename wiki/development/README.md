# Development Guide

This guide covers development practices, setup, and contribution guidelines.

## Development Environment Setup

### Prerequisites

- **Node.js** 18+ (frontend development)
- **Python** 3.11+ (backend development)
- **Git** (version control)
- **AWS CLI** configured (for Bedrock access)

### Repository Structure

```
synth-data-studio/
├── frontend/           # React + TypeScript + Vite
├── backend/            # FastAPI + LangGraph
├── wiki/               # Documentation
└── .github/            # GitHub workflows
```

## Backend Development

### Setup

1. **Create virtual environment:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run development server:**
   ```bash
   uvicorn main:app --reload
   ```

### Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Document functions with docstrings
- Keep functions focused and small

### Testing

Run tests (when available):
```bash
pytest
```

## Frontend Development

### Setup

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```

3. **Run development server:**
   ```bash
   npm run dev
   ```

### Code Style

- Use TypeScript for type safety
- Follow React best practices
- Use functional components with hooks
- Style with Tailwind CSS
- Use shadcn/ui components

### Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server |
| `npm run build` | Build for production |
| `npm run lint` | Run ESLint |
| `npm run preview` | Preview production build |

## Git Workflow

### Branching

- `main` - Production-ready code
- `feature/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates

### Commit Messages

Use descriptive commit messages:

```
<type>: <short description>

<longer description if needed>
```

Types:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Code style (formatting)
- `refactor` - Code refactoring
- `test` - Tests
- `chore` - Maintenance

### Example

```
feat: add LLM judge to Eval Agent

Implements Stage 2 evaluation using Claude for
quality assessment of synthetic data.
```

## Adding New Agents

1. **Create agent directory:**
   ```
   backend/src/agents/<agent_name>/
   ├── __init__.py
   └── <agent_name>.py
   ```

2. **Implement agent class:**
   ```python
   class NewAgent:
       def __init__(self, config):
           self.config = config
       
       def run(self):
           # Agent logic
           pass
   ```

3. **Add to API routes:**
   ```python
   @router.post("/agents/<agent_name>")
   async def new_agent_endpoint():
       result = NewAgent(config).run()
       return result
   ```

4. **Update documentation:**
   - Add to wiki/agents/
   - Update API reference

## Documentation

### Updating Wiki

When making significant changes:

1. Update relevant wiki pages
2. Add change log entry
3. Update README if needed

### Documentation Structure

```
wiki/
├── agents/           # Agent documentation
├── api/              # API documentation
├── configuration/    # Config guides
└── development/      # Dev guides
```

## Debugging

### Backend Logs

Set logging level in code:
```python
logging.basicConfig(level=logging.DEBUG)
```

### Frontend Debugging

- Use browser DevTools
- Check console for errors
- Verify API responses in Network tab

## Common Issues

### Backend won't start

- Check `.env` file exists and is configured
- Verify AWS credentials are valid
- Check port 8000 is not in use

### Frontend won't connect

- Verify backend is running
- Check `VITE_API_BASE_URL` in `.env`
- Check CORS configuration

### Agent failures

- Check input file formats
- Verify environment variables
- Review agent logs for errors

## Release Process

1. Update version numbers
2. Update CHANGELOG.md
3. Create pull request
4. Merge to main
5. Tag release

## Support

For development questions:
- Check existing documentation
- Review similar agent implementations
- Ask in team chat
