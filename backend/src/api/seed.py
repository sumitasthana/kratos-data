import json
import logging
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pathlib import Path
import tempfile

from ..agents.seed import run_seed_agent

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)


@router.post("/seed")
async def seed_agent_endpoint(
    schema_graph: UploadFile = File(...),
    data_dictionary: UploadFile = File(...),
    domain_supplements: UploadFile = File(None),
):
    """
    Seed Agent orchestrator endpoint.
    
    Accepts:
    - schema_graph: JSON file or dict (required)
    - data_dictionary: Text file (required)
    - domain_supplements: JSON file (optional)
    
    Returns:
    - distribution_spec: Final merged specification
    - seed_agent_status: "success" | "partial" | "failed"
    - seed_validation_report: Validation results with errors/warnings
    """
    try:
        # Read schema_graph
        schema_graph_content = await schema_graph.read()
        try:
            schema_graph_dict = json.loads(schema_graph_content)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"error": "schema_graph must be valid JSON"}
            )
        
        # Write data_dictionary to temp file
        data_dict_content = await data_dictionary.read()
        data_dict_tmp = tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8"
        )
        data_dict_tmp.write(data_dict_content.decode("utf-8"))
        data_dict_tmp.close()
        data_dictionary_path = data_dict_tmp.name
        
        # Handle optional domain_supplements
        supplements_path = None
        if domain_supplements:
            supplements_content = await domain_supplements.read()
            supplements_tmp = tempfile.NamedTemporaryFile(
                suffix=".json", delete=False, mode="w", encoding="utf-8"
            )
            try:
                supplements_dict = json.loads(supplements_content)
                json.dump(supplements_dict, supplements_tmp)
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "domain_supplements must be valid JSON"}
                )
            supplements_tmp.close()
            supplements_path = supplements_tmp.name
        
        # Run seed agent
        state = {
            "schema_graph": schema_graph_dict,
            "data_dictionary_path": data_dictionary_path,
            "domain_supplements_path": supplements_path,
        }
        
        result = run_seed_agent(state)
        
        # Clean up temp files
        try:
            Path(data_dictionary_path).unlink()
            if supplements_path:
                Path(supplements_path).unlink()
        except Exception as e:
            logger.warning(f"Failed to clean up temp files: {e}")
        
        # Return result
        return JSONResponse(
            status_code=200,
            content={
                "distribution_spec": result.get("distribution_spec"),
                "seed_agent_status": result.get("seed_agent_status"),
                "seed_validation_report": result.get("seed_validation_report"),
                "seed_agent_error": result.get("seed_agent_error"),
            }
        )
    
    except Exception as e:
        logger.error("Seed agent endpoint failed", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
