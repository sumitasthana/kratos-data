# synth-data-studio

A full-stack application for synthetic data generation using LangGraph and AWS Bedrock.

## Project Structure

```
synth-data-studio/
├── frontend/          # React 18 + TypeScript + Vite
├── backend/           # FastAPI + LangGraph
└── README.md
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
