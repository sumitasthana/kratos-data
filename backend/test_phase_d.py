#!/usr/bin/env python
"""Test script for Phase D orchestrator."""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agents.seed import run_seed_agent

def test_phase_d():
    """Test Phase D with actual files."""
    state = {
        "schema_graph": "outputs/schema_graph.json",
        "data_dictionary_path": "../../02_DATA_DICTIONARY.txt",
        "domain_supplements_path": None,
    }
    
    print("=" * 60)
    print("Testing Phase D Orchestrator")
    print("=" * 60)
    
    result = run_seed_agent(state)
    
    print(f"\nStatus: {result['seed_agent_status']}")
    print(f"Error: {result['seed_agent_error']}")
    print(f"Has distribution_spec: {result['distribution_spec'] is not None}")
    print(f"Has validation_report: {result['seed_validation_report'] is not None}")
    
    if result['seed_validation_report']:
        report = result['seed_validation_report']
        print(f"\nValidation Report:")
        print(f"  Status: {report.get('status')}")
        print(f"  Errors: {len(report.get('errors', []))}")
        print(f"  Warnings: {len(report.get('warnings', []))}")
        print(f"  Stats:")
        stats = report.get('stats', {})
        print(f"    Total fields: {stats.get('total_fields_in_final_spec')}")
        print(f"    Phase A: {stats.get('fields_resolved_phase_a')}")
        print(f"    Phase B: {stats.get('fields_resolved_phase_b')}")
        print(f"    Unresolved: {stats.get('fields_still_unresolved')}")
    
    if result['distribution_spec']:
        spec = result['distribution_spec']
        print(f"\nDistribution Spec:")
        print(f"  Tables: {len(spec.get('tables', []))}")
        print(f"  Has validation_report: {'validation_report' in spec}")
    
    print("\n" + "=" * 60)
    print("Phase D Test Complete")
    print("=" * 60)
    
    return result['seed_agent_status'] in ['success', 'partial']

if __name__ == '__main__':
    success = test_phase_d()
    sys.exit(0 if success else 1)
