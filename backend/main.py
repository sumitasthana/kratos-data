from __future__ import annotations
import os
import sys
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# .env lives one level up (project root .env); load it regardless of cwd
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()  # also pick up a backend/.env if present

# make the cardinal package importable (backend/src on the path)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from cardinal.agents.builder import Builder  # noqa: E402
from cardinal.agents.interviewer import make_interviewer  # noqa: E402
from cardinal.agents.spec_export import zip_bytes  # noqa: E402
from cardinal.billing import BillingModule  # noqa: E402
from cardinal.cycle import generate_portfolio, portfolio_kpis  # noqa: E402

app = FastAPI(title="cardinal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BUILDER = Builder()          # one shared builder (loads/validates the ontology once)
SESSIONS: dict = {}          # session_id -> interviewer
BUILT: dict = {}             # session_id -> spec_files (for the .zip download)
CONTRACTS: dict = {}         # session_id -> contract dict (for sample generation)
PREVIEW_ACCOUNTS = 100       # small sample for the in-studio preview
PREVIEW_ROWS = 25


def make_llm():
    """Claude via Bedrock (this project) or a direct Anthropic key; else None (offline)."""
    if os.getenv("AWS_BEARER_TOKEN_BEDROCK") or os.getenv("AWS_BEDROCK_MODEL"):
        from langchain_aws import ChatBedrockConverse
        return ChatBedrockConverse(
            model=os.getenv("AWS_BEDROCK_MODEL", "us.anthropic.claude-sonnet-4-6"),
            region_name=os.getenv("AWS_BEDROCK_REGION", "us-east-1"),
            max_tokens=1024,
        )
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-opus-5", max_tokens=1024)
    return None


LLM_ENABLED = bool(
    os.getenv("AWS_BEARER_TOKEN_BEDROCK") or os.getenv("AWS_BEDROCK_MODEL")
    or os.getenv("ANTHROPIC_API_KEY"))


class MessageReq(BaseModel):
    session_id: str
    text: str


@app.get("/api/health")
def health_check():
    return {"status": "ok", "llm_enabled": LLM_ENABLED}


@app.post("/api/session/start")
def session_start():
    session_id = uuid.uuid4().hex[:12]
    agent = make_interviewer(make_llm(), BUILDER, session_id)
    SESSIONS[session_id] = agent
    return {"session_id": session_id, "llm_enabled": LLM_ENABLED, **agent.start()}


@app.post("/api/session/message")
def session_message(req: MessageReq):
    agent = SESSIONS.get(req.session_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="unknown session")
    result = agent.message(req.text)
    spec_files = result.pop("spec_files", None)  # keep server-side for the zip
    if spec_files:
        BUILT[req.session_id] = spec_files
        CONTRACTS[req.session_id] = result.get("contract") or {}
    return {"session_id": req.session_id, **result}


@app.post("/api/session/{session_id}/generate")
def generate_sample(session_id: str):
    contract = CONTRACTS.get(session_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="no spec built for this session yet")
    behaviors = set(contract.get("behaviors") or []) or {"grace_period", "fees", "minimum_payment"}
    mix = contract.get("revolver_mix", "mixed")
    scale = contract.get("scale") or {}
    accounts = min(int(scale.get("accounts", PREVIEW_ACCOUNTS)), PREVIEW_ACCOUNTS)
    cycles = min(int(scale.get("cycles", 24)), 24)

    df = generate_portfolio([BillingModule(behaviors=behaviors, revolver_mix=mix)],
                            accounts=accounts, cycles=cycles, seed=42)
    cols = ["account_id", "cycle_seq", "archetype", "purchases", "payment", "paid_in_full",
            "grace_eligible", "interest", "fees", "ending_balance", "minimum_due",
            "utilization", "dpd"]
    preview = df[cols].head(PREVIEW_ROWS).round(2).to_dict(orient="records")
    return {"kpis": portfolio_kpis(df), "columns": cols, "rows": preview,
            "n_accounts": accounts, "n_cycles": cycles}


@app.get("/api/session/{session_id}/spec.zip")
def download_spec(session_id: str):
    files = BUILT.get(session_id)
    if not files:
        raise HTTPException(status_code=404, detail="no spec built for this session yet")
    return Response(
        content=zip_bytes(files),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=cardinal_spec.zip"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
