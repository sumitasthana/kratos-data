import json
import logging
from fastapi import APIRouter, UploadFile, File, Form
from pathlib import Path
import tempfile
import shutil

from agents.eval_agent import run_eval

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/agents/eval")
async def eval_endpoint(
    csv_dir: str = Form(...),
    distribution_spec_file: UploadFile = File(...),
    eval_config_file: UploadFile = None
):
    """
    Evaluate generated synthetic data quality.
    
    Args:
        csv_dir: Path to directory containing generated CSV files
        distribution_spec_file: distribution_spec.json file
        eval_config_file: Optional eval_config.json file
    
    Returns:
        Evaluation report with pass/fail signal
    """
    try:
        # Read distribution spec
        spec_content = await distribution_spec_file.read()
        distribution_spec = json.loads(spec_content.decode('utf-8'))
        
        # Read eval config or use defaults
        if eval_config_file:
            config_content = await eval_config_file.read()
            eval_config = json.loads(config_content.decode('utf-8'))
        else:
            eval_config = {
                'pass_threshold': {
                    'referential_integrity_pass_rate': 1.0,
                    'cross_field_rule_pass_rate': 0.95,
                    'distribution_similarity_threshold': 0.80,
                    'nullable_rate_tolerance': 0.05
                },
                'llm_judge': {
                    'enabled': False,
                    'sample_size_per_table': 20,
                    'model': 'claude-sonnet-4-20250514'
                },
                'skip_tables': [],
                'output_dir': None
            }
        
        # Run evaluation
        report = run_eval(csv_dir, distribution_spec, eval_config)
        
        return {
            'status': 'success',
            'pass_signal': report.get('pass_signal', False),
            'report': report
        }
    
    except Exception as e:
        logger.error(f"Eval endpoint failed: {e}", exc_info=True)
        return {
            'status': 'error',
            'pass_signal': False,
            'error': str(e)
        }
