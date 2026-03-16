from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from utils.bedrock_client import get_bedrock_client
from routes.ontology import router as ontology_router

load_dotenv()

app = FastAPI(title="synth-data-studio")

# Register routes
app.include_router(ontology_router)

# Configuration
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "json").lower()
SUPPORTED_FORMATS = ["json", "csv", "parquet"]

if OUTPUT_FORMAT not in SUPPORTED_FORMATS:
    OUTPUT_FORMAT = "json"

# AWS Bedrock Configuration
AWS_BEDROCK_REGION = os.getenv("AWS_BEDROCK_REGION", "us-east-1")
AWS_BEDROCK_MODEL = os.getenv("AWS_BEDROCK_MODEL", "anthropic.claude-sonnet-4-5-20250929-v1:0")
AWS_BEARER_TOKEN = os.getenv("AWS_BEARER_TOKEN")

# Initialize Bedrock client
bedrock_client = get_bedrock_client()
bedrock_available = bedrock_client is not None and bedrock_client.is_available() if bedrock_client else False

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "output_format": OUTPUT_FORMAT,
        "supported_formats": SUPPORTED_FORMATS,
        "bedrock": {
            "available": bedrock_available,
            "region": AWS_BEDROCK_REGION,
            "model": AWS_BEDROCK_MODEL
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
