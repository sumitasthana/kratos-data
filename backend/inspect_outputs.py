#!/usr/bin/env python
"""Inspect output files from Seed Agent pipeline."""

import json
from pathlib import Path

def inspect_outputs():
    """Display key sections of output files."""
    
    spec_path = Path("outputs/distribution_spec.json")
    report_path = Path("outputs/validation_report.json")
    
    if not spec_path.exists():
        print("❌ distribution_spec.json not found")
        return
    
    with open(spec_path, 'r') as f:
        spec = json.load(f)
    
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║           DISTRIBUTION SPEC - STRUCTURE OVERVIEW              ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    print("📋 METADATA")
    print("─" * 64)
    for key, value in spec['metadata'].items():
        print(f"  {key}: {value}")
    
    print()
    print("📊 GENERATION ORDER")
    print("─" * 64)
    for i, table in enumerate(spec['generation_order'], 1):
        print(f"  {i:2d}. {table}")
    
    print()
    print("🗂️  TABLES SUMMARY")
    print("─" * 64)
    for table in spec['tables']:
        fields = len(table['fields'])
        rules = len(table.get('cross_field_rules', []))
        rcd = 'YES' if table.get('row_count_distribution') else 'NO'
        print(f"  {table['name']:40s} | {fields:3d} fields | {rules:2d} rules | RCD: {rcd}")
    
    print()
    print("✅ VALIDATION REPORT (embedded in spec)")
    print("─" * 64)
    vr = spec.get('validation_report', {})
    print(f"  Status: {vr.get('status')}")
    print(f"  Errors: {len(vr.get('errors', []))}")
    print(f"  Warnings: {len(vr.get('warnings', []))}")
    print(f"  Stats:")
    stats = vr.get('stats', {})
    print(f"    - Total fields: {stats.get('total_fields_in_final_spec')}")
    print(f"    - Phase A: {stats.get('fields_resolved_phase_a')}")
    print(f"    - Phase B: {stats.get('fields_resolved_phase_b')}")
    print(f"    - Unresolved: {stats.get('fields_still_unresolved')}")
    
    print()
    print("📁 FILE LOCATIONS")
    print("─" * 64)
    print("  backend/outputs/distribution_spec.json (196 KB)")
    print("  backend/outputs/validation_report.json (651 B)")
    print("  backend/outputs/distribution_spec_skeleton.json (167 KB)")
    print("  backend/outputs/distribution_spec_delta.json (103 KB)")
    
    print()
    print("🔍 SAMPLE FIELD (account.account_id)")
    print("─" * 64)
    account_table = next((t for t in spec['tables'] if t['name'] == 'account'), None)
    if account_table:
        account_id = next((f for f in account_table['fields'] if f['name'] == 'account_id'), None)
        if account_id:
            for key, value in account_id.items():
                print(f"  {key}: {value}")
    
    print()
    print("🔍 SAMPLE FIELD (account.account_number - Phase B enriched)")
    print("─" * 64)
    if account_table:
        account_number = next((f for f in account_table['fields'] if f['name'] == 'account_number'), None)
        if account_number:
            for key, value in account_number.items():
                print(f"  {key}: {value}")
    
    print()
    print("🔍 SAMPLE CROSS-FIELD RULE (daily_account_balance)")
    print("─" * 64)
    dab_table = next((t for t in spec['tables'] if t['name'] == 'daily_account_balance'), None)
    if dab_table and dab_table.get('cross_field_rules'):
        rule = dab_table['cross_field_rules'][0]
        for key, value in rule.items():
            if isinstance(value, (list, dict)):
                print(f"  {key}: {json.dumps(value, indent=4)}")
            else:
                print(f"  {key}: {value}")

if __name__ == '__main__':
    inspect_outputs()
