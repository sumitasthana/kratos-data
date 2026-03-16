import asyncio
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from agents.ontology_agent import OntologyAgent

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/ontology")
async def extract_ontology(file: UploadFile = File(...)) -> JSONResponse:
    """
    Extract schema graph from uploaded DDL file.
    
    Returns schema_graph.json with complete schema information.
    """
    if not file.filename.endswith('.sql'):
        raise HTTPException(status_code=400, detail="File must be a .sql file")

    try:
        # Write uploaded file to temporary location
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as tmp_ddl:
            content = await file.read()
            tmp_ddl.write(content.decode('utf-8'))
            tmp_ddl_path = tmp_ddl.name

        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_output:
            tmp_output_path = tmp_output.name

        try:
            # Process DDL
            agent = OntologyAgent()
            await agent.process_ddl(tmp_ddl_path, tmp_output_path)

            # Read output
            with open(tmp_output_path, 'r', encoding='utf-8') as f:
                import json
                schema_graph = json.load(f)

            return JSONResponse(content=schema_graph)

        finally:
            # Cleanup temporary files
            Path(tmp_ddl_path).unlink(missing_ok=True)
            Path(tmp_output_path).unlink(missing_ok=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process DDL: {str(e)}")
