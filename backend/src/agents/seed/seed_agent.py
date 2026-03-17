import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from . import distribution_spec_skeleton_builder as phase_a
from . import distribution_spec_enricher as phase_b
from . import phase_c_merge as phase_c

logger = logging.getLogger(__name__)


def run_seed_agent(state: dict) -> dict:
    """
    Orchestrator for Seed Agent Phases A, B, C.
    
    Reads from state:
    - schema_graph: dict or file path
    - data_dictionary_path: str (file path)
    - domain_supplements_path: str or None (optional file path)
    
    Writes to state:
    - distribution_spec: dict or None
    - seed_validation_report: dict or None
    - seed_agent_status: "success" | "partial" | "failed"
    - seed_agent_error: str or None
    """
    try:
        schema_graph = state.get("schema_graph")
        data_dictionary_path = state.get("data_dictionary_path")
        supplements_path = state.get("domain_supplements_path")
        
        # Validate required inputs
        if not schema_graph:
            raise ValueError("schema_graph is required in state")
        if not data_dictionary_path:
            raise ValueError("data_dictionary_path is required in state")
        
        # Handle schema_graph: if dict, write to temp file
        if isinstance(schema_graph, dict):
            tmp = tempfile.NamedTemporaryFile(
                suffix=".json", delete=False, mode="w", encoding="utf-8"
            )
            json.dump(schema_graph, tmp)
            tmp.close()
            schema_graph_path = tmp.name
            logger.info(f"Schema graph written to temp file: {schema_graph_path}")
        else:
            schema_graph_path = str(schema_graph)
            if not Path(schema_graph_path).exists():
                raise FileNotFoundError(f"Schema graph file not found: {schema_graph_path}")
        
        # Validate data_dictionary_path exists
        if not Path(data_dictionary_path).exists():
            raise FileNotFoundError(f"Data dictionary file not found: {data_dictionary_path}")
        
        logger.info("Starting Seed Agent pipeline...")
        
        # Phase A: Build skeleton
        logger.info("Phase A: Building distribution spec skeleton...")
        skeleton_builder = phase_a.DistributionSpecSkeletonBuilder(schema_graph_path, supplements_path=supplements_path)
        skeleton_builder.load_inputs()
        skeleton = skeleton_builder.build_output()
        logger.info(f"Phase A complete: {len(skeleton.get('tables', []))} tables, "
                   f"{sum(len(t.get('fields', [])) for t in skeleton.get('tables', []))} fields")
        
        # Phase B: Enrich skeleton with delta
        logger.info("Phase B: Enriching skeleton with delta...")
        # Create a temporary skeleton file for Phase B
        skeleton_tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        json.dump(skeleton, skeleton_tmp)
        skeleton_tmp.close()
        skeleton_path = skeleton_tmp.name
        
        enricher = phase_b.DistributionSpecEnricher(
            skeleton_path=skeleton_path,
            data_dictionary_path=data_dictionary_path,
            schema_graph_path=schema_graph_path
        )
        enricher.load_inputs()
        delta = enricher.build_delta()
        logger.info(f"Phase B complete: {len(delta.get('delta_fields', []))} delta fields, "
                   f"{len(delta.get('cross_field_rules', []))} cross-field rules")
        
        # Phase C: Merge and validate
        logger.info("Phase C: Merging and validating...")
        final_spec, validation_report = phase_c.merge_and_validate(skeleton, delta)
        logger.info(f"Phase C complete: Status={validation_report.get('status')}, "
                   f"Errors={len(validation_report.get('errors', []))}, "
                   f"Warnings={len(validation_report.get('warnings', []))}")
        
        # Persist outputs for debugging
        output_dir = Path(os.getenv("SEED_AGENT_OUTPUT_DIR", "backend/outputs"))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        spec_output = output_dir / "distribution_spec.json"
        report_output = output_dir / "validation_report.json"
        
        spec_output.write_text(json.dumps(final_spec, indent=2), encoding="utf-8")
        report_output.write_text(json.dumps(validation_report, indent=2), encoding="utf-8")
        
        logger.info(f"Outputs written to {output_dir}")
        
        # Clean up temp files
        if isinstance(schema_graph, dict):
            try:
                Path(schema_graph_path).unlink()
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {schema_graph_path}: {e}")
        
        try:
            Path(skeleton_path).unlink()
        except Exception as e:
            logger.warning(f"Failed to clean up skeleton temp file {skeleton_path}: {e}")
        
        return {
            "distribution_spec": final_spec,
            "seed_validation_report": validation_report,
            "seed_agent_status": validation_report.get("status", "unknown"),
            "seed_agent_error": None,
        }
    
    except Exception as e:
        logger.error("Seed agent failed", exc_info=True)
        return {
            "distribution_spec": None,
            "seed_validation_report": None,
            "seed_agent_status": "failed",
            "seed_agent_error": str(e),
        }
