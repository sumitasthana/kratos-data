import json
import logging
import tempfile
from fastapi import APIRouter, UploadFile, File, Body
from fastapi.responses import JSONResponse
from pathlib import Path

from ..agents.pilot_generator import run_pilot

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)


@router.post("/pilot")
async def pilot_generator_endpoint(
    distribution_spec: UploadFile = File(...),
    pilot_config: UploadFile = File(...),
):
    """
    Pilot Generator endpoint.
    
    Accepts:
    - distribution_spec: JSON file (required)
    - pilot_config: JSON file (required)
    
    Returns:
    - pilot_run_manifest: Generation results with row counts and warnings
    """
    try:
        # Read distribution_spec
        spec_content = await distribution_spec.read()
        try:
            spec_dict = json.loads(spec_content)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"error": "distribution_spec must be valid JSON"}
            )
        
        # Read pilot_config
        config_content = await pilot_config.read()
        try:
            config_dict = json.loads(config_content)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"error": "pilot_config must be valid JSON"}
            )
        
        # Run pilot generator
        manifest = run_pilot(spec_dict, config_dict)
        
        return JSONResponse(
            status_code=200,
            content=manifest
        )
    
    except Exception as e:
        logger.error("Pilot generator endpoint failed", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
