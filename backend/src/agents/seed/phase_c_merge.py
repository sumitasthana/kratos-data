import json
import argparse
import copy
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime, timezone


class PhaseCMerger:
    """Phase C: Merge skeleton + delta, validate, produce final spec + report."""

    def __init__(self, skeleton_path: str, delta_path: str):
        self.skeleton_path = skeleton_path
        self.delta_path = delta_path
        self.skeleton = None
        self.delta = None
        self.final_spec = None
        self.validation_report = None
        self.errors = []
        self.warnings = []

    def load_inputs(self) -> None:
        """Load skeleton and delta."""
        with open(self.skeleton_path, 'r', encoding='utf-8') as f:
            self.skeleton = json.load(f)
        
        with open(self.delta_path, 'r', encoding='utf-8') as f:
            self.delta = json.load(f)

    def merge_and_validate(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Merge skeleton + delta and validate."""
        # Deep copy skeleton to avoid modifying original
        self.final_spec = copy.deepcopy(self.skeleton)
        
        # Build table lookup
        table_map = {t['name']: t for t in self.final_spec.get('tables', [])}
        
        # Track stats
        stats = {
            'delta_fields_accepted': 0,
            'delta_fields_rejected': 0,
            'delta_fields_clamped': 0,
            'cross_field_rules_added': 0,
            'row_count_distributions_added': 0,
            'total_fields_in_final_spec': 0,
            'fields_resolved_phase_a': 0,
            'fields_resolved_phase_b': 0,
            'fields_still_unresolved': 0
        }
        
        # 1. Merge delta_fields
        for delta_field in self.delta.get('delta_fields', []):
            table_name = delta_field.get('table')
            field_name = delta_field.get('field')
            updates = delta_field.get('updates', {})
            
            # Validate table exists
            if table_name not in table_map:
                self.errors.append({
                    'type': 'unknown_table',
                    'table': table_name,
                    'field': field_name,
                    'message': f'Table "{table_name}" not found in skeleton'
                })
                stats['delta_fields_rejected'] += 1
                continue
            
            # Find field in table
            table = table_map[table_name]
            field = None
            for f in table.get('fields', []):
                if f['name'] == field_name:
                    field = f
                    break
            
            if field is None:
                self.errors.append({
                    'type': 'unknown_field',
                    'table': table_name,
                    'field': field_name,
                    'message': f'Field "{field_name}" not found in table "{table_name}"'
                })
                stats['delta_fields_rejected'] += 1
                continue
            
            # Check if already resolved by phase_a
            if field.get('resolved_by') == 'phase_a':
                self.errors.append({
                    'type': 'overwriting_phase_a',
                    'table': table_name,
                    'field': field_name,
                    'message': f'Cannot overwrite field already resolved by phase_a'
                })
                stats['delta_fields_rejected'] += 1
                continue
            
            # Validate and merge updates
            clamped = self._validate_and_merge_field(field, updates, table_name, field_name)
            field['resolved_by'] = 'phase_b'
            
            if clamped:
                stats['delta_fields_clamped'] += 1
            else:
                stats['delta_fields_accepted'] += 1
        
        # 2. Merge row_count_distributions
        for rcd_entry in self.delta.get('row_count_distributions', []):
            table_name = rcd_entry.get('table')
            
            if table_name not in table_map:
                self.warnings.append({
                    'type': 'unknown_table_rcd',
                    'table': table_name,
                    'field': None,
                    'message': f'Table "{table_name}" not found for row_count_distribution',
                    'original_value': None,
                    'clamped_to': None
                })
                continue
            
            table = table_map[table_name]
            table['row_count_distribution'] = rcd_entry.get('entries', [])
            stats['row_count_distributions_added'] += 1
        
        # 3. Merge cross_field_rules
        for rule_entry in self.delta.get('cross_field_rules', []):
            table_name = rule_entry.get('table')
            
            if table_name not in table_map:
                self.warnings.append({
                    'type': 'unknown_table_cfr',
                    'table': table_name,
                    'field': None,
                    'message': f'Table "{table_name}" not found for cross_field_rules',
                    'original_value': None,
                    'clamped_to': None
                })
                continue
            
            table = table_map[table_name]
            if 'cross_field_rules' not in table:
                table['cross_field_rules'] = []
            
            # Validate and append rules
            for rule in rule_entry.get('rules', []):
                validated_rule = self._validate_cross_field_rule(rule, table_name)
                if validated_rule:
                    table['cross_field_rules'].append(validated_rule)
                    stats['cross_field_rules_added'] += 1
        
        # 4. Count total fields and resolution status
        for table in self.final_spec.get('tables', []):
            for field in table.get('fields', []):
                stats['total_fields_in_final_spec'] += 1
                resolved_by = field.get('resolved_by')
                
                if resolved_by == 'phase_a':
                    stats['fields_resolved_phase_a'] += 1
                elif resolved_by == 'phase_b':
                    stats['fields_resolved_phase_b'] += 1
                elif resolved_by is None and field.get('strategy') is None:
                    stats['fields_still_unresolved'] += 1
                    self.warnings.append({
                        'type': 'unresolved_field',
                        'table': table['name'],
                        'field': field['name'],
                        'message': f'Field still unresolved after Phase B',
                        'original_value': None,
                        'clamped_to': None
                    })
        
        # 5. Build validation report
        status = 'success'
        if self.errors:
            status = 'failed'
        elif self.warnings or stats['fields_still_unresolved'] > 0:
            status = 'partial'
        
        self.validation_report = {
            'status': status,
            'errors': self.errors,
            'warnings': self.warnings,
            'stats': stats
        }
        
        return self.final_spec, self.validation_report

    def _validate_and_merge_field(self, field: Dict[str, Any], updates: Dict[str, Any], 
                                   table_name: str, field_name: str) -> bool:
        """Validate and merge field updates. Returns True if clamped."""
        clamped = False
        
        # Merge all update keys
        for key, value in updates.items():
            if key == 'nullable_rate':
                # Validate nullable_rate is in [0, 1]
                if value is not None and (value < 0 or value > 1):
                    original = value
                    value = max(0, min(1, value))
                    self.warnings.append({
                        'type': 'nullable_rate_out_of_bounds',
                        'table': table_name,
                        'field': field_name,
                        'message': f'nullable_rate {original} clamped to [{0}, {1}]',
                        'original_value': original,
                        'clamped_to': value
                    })
                    clamped = True
                
                # Check if conditional field
                if value is not None and value > 0 and field.get('condition'):
                    original = value
                    value = 0
                    self.warnings.append({
                        'type': 'conditional_field_nullable',
                        'table': table_name,
                        'field': field_name,
                        'message': f'Conditional field cannot be nullable; clamped to 0',
                        'original_value': original,
                        'clamped_to': value
                    })
                    clamped = True
            
            elif key == 'values' and isinstance(value, dict):
                # Validate enum weights sum to ~1.0
                total_weight = sum(value.values())
                if total_weight > 0 and abs(total_weight - 1.0) > 0.01:
                    # Normalize weights
                    normalized = {k: v / total_weight for k, v in value.items()}
                    self.warnings.append({
                        'type': 'enum_weights_not_normalized',
                        'table': table_name,
                        'field': field_name,
                        'message': f'Enum weights sum to {total_weight}; normalized to 1.0',
                        'original_value': total_weight,
                        'clamped_to': 1.0
                    })
                    value = normalized
                    clamped = True
            
            field[key] = value
        
        # Check for missing rationale
        if 'rationale' not in updates or not updates.get('rationale'):
            self.warnings.append({
                'type': 'missing_rationale',
                'table': table_name,
                'field': field_name,
                'message': f'Field missing rationale',
                'original_value': None,
                'clamped_to': None
            })
        
        return clamped

    def _validate_cross_field_rule(self, rule: Dict[str, Any], table_name: str) -> Optional[Dict[str, Any]]:
        """Validate cross-field rule. Returns rule or None if invalid."""
        rule_type = rule.get('type', 'other')
        
        # Validate rule type
        valid_types = ['temporal_ordering', 'sum_constraint', 'conditional_population', 
                      'balance_equation', 'consistency', 'other']
        if rule_type not in valid_types:
            self.warnings.append({
                'type': 'unknown_rule_type',
                'table': table_name,
                'field': None,
                'message': f'Unknown rule type "{rule_type}"; changed to "other"',
                'original_value': rule_type,
                'clamped_to': 'other'
            })
            rule = copy.deepcopy(rule)
            rule['type'] = 'other'
        
        return rule

    def save_outputs(self, spec_output: str, report_output: str) -> None:
        """Save final spec and validation report."""
        with open(spec_output, 'w', encoding='utf-8') as f:
            json.dump(self.final_spec, f, indent=2)
        
        with open(report_output, 'w', encoding='utf-8') as f:
            json.dump(self.validation_report, f, indent=2)

    def print_summary(self) -> None:
        """Print execution summary."""
        stats = self.validation_report.get('stats', {})
        
        print(f"\n{'='*60}")
        print(f"Seed Agent Phase C Summary")
        print(f"{'='*60}")
        print(f"Status: {self.validation_report.get('status').upper()}")
        print(f"\nMerge Statistics:")
        print(f"  Delta fields accepted: {stats.get('delta_fields_accepted', 0)}")
        print(f"  Delta fields rejected: {stats.get('delta_fields_rejected', 0)}")
        print(f"  Delta fields clamped: {stats.get('delta_fields_clamped', 0)}")
        print(f"  Cross-field rules added: {stats.get('cross_field_rules_added', 0)}")
        print(f"  Row count distributions added: {stats.get('row_count_distributions_added', 0)}")
        
        print(f"\nResolution Coverage:")
        total = stats.get('total_fields_in_final_spec', 1)
        phase_a = stats.get('fields_resolved_phase_a', 0)
        phase_b = stats.get('fields_resolved_phase_b', 0)
        unresolved = stats.get('fields_still_unresolved', 0)
        
        print(f"  Phase A: {phase_a}/{total} ({100*phase_a/total:.1f}%)")
        print(f"  Phase B: {phase_b}/{total} ({100*phase_b/total:.1f}%)")
        print(f"  Unresolved: {unresolved}/{total} ({100*unresolved/total:.1f}%)")
        
        print(f"\nValidation:")
        print(f"  Errors: {len(self.validation_report.get('errors', []))}")
        print(f"  Warnings: {len(self.validation_report.get('warnings', []))}")
        print(f"{'='*60}\n")


def merge_and_validate(skeleton: dict, delta: dict) -> Tuple[dict, dict]:
    """Merge skeleton + delta and validate. Returns (final_spec, validation_report)."""
    merger = PhaseCMerger.__new__(PhaseCMerger)
    merger.skeleton = skeleton
    merger.delta = delta
    merger.errors = []
    merger.warnings = []
    
    final_spec, validation_report = merger.merge_and_validate()
    return final_spec, validation_report


def main():
    parser = argparse.ArgumentParser(description='Seed Agent Phase C: Merge + Validate')
    parser.add_argument('skeleton_path', help='Path to distribution_spec_skeleton.json')
    parser.add_argument('delta_path', help='Path to distribution_spec_delta.json')
    parser.add_argument('--spec-output', default='outputs/distribution_spec.json',
                       help='Output path for final distribution spec')
    parser.add_argument('--report-output', default='outputs/validation_report.json',
                       help='Output path for validation report')
    
    args = parser.parse_args()
    
    # Load inputs
    merger = PhaseCMerger(args.skeleton_path, args.delta_path)
    merger.load_inputs()
    
    # Merge and validate
    final_spec, validation_report = merger.merge_and_validate()
    
    # Save outputs
    merger.final_spec = final_spec
    merger.validation_report = validation_report
    merger.save_outputs(args.spec_output, args.report_output)
    
    # Print summary
    merger.print_summary()
    
    print(f"Final spec written to {args.spec_output}")
    print(f"Validation report written to {args.report_output}")


if __name__ == '__main__':
    main()
