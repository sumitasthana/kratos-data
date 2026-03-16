import json
import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


class DistributionSpecEnricher:
    """Pragmatic enrichment of distribution spec skeleton (Phase B).
    
    Generates valid delta JSON with sensible defaults for unresolved fields.
    Uses field type and context to determine realistic strategies.
    """

    def __init__(self, skeleton_path: str, data_dictionary_path: str):
        self.skeleton_path = skeleton_path
        self.data_dictionary_path = data_dictionary_path
        self.skeleton = None
        self.data_dictionary = None
        self.delta = None

    def load_inputs(self) -> None:
        """Load skeleton and data dictionary."""
        with open(self.skeleton_path, 'r', encoding='utf-8') as f:
            self.skeleton = json.load(f)

        with open(self.data_dictionary_path, 'r', encoding='utf-8') as f:
            self.data_dictionary = f.read()

    def get_unresolved_fields(self) -> List[Dict[str, Any]]:
        """Extract all unresolved fields with context."""
        unresolved = []
        
        for table in self.skeleton.get('tables', []):
            for field in table.get('fields', []):
                if field.get('resolved_by') != 'phase_a':
                    unresolved.append({
                        'table': table['name'],
                        'table_classification': table['classification'],
                        'field_name': field['name'],
                        'field_spec': field
                    })
        
        return unresolved

    def infer_strategy(self, field: Dict[str, Any], field_name: str) -> str:
        """Infer strategy based on field type and context."""
        field_type = field.get('type', '').upper()
        
        # Composite PK components
        if field.get('params', {}).get('role') == 'composite_pk_component':
            if 'DATE' in field_type or 'TIMESTAMP' in field_type:
                return 'date_range'
            elif 'INT' in field_type or 'NUMERIC' in field_type:
                return 'distribution'
            return 'distribution'
        
        # Date/timestamp fields
        if 'DATE' in field_type or 'TIMESTAMP' in field_type:
            return 'date_range'
        
        # Numeric fields
        if 'INT' in field_type or 'NUMERIC' in field_type or 'DECIMAL' in field_type or 'FLOAT' in field_type:
            return 'distribution'
        
        # String fields - check for patterns
        if 'VARCHAR' in field_type or 'TEXT' in field_type or 'CHAR' in field_type:
            if 'email' in field_name.lower():
                return 'regex'
            if 'phone' in field_name.lower() or 'number' in field_name.lower():
                return 'regex'
            return 'regex'
        
        # UUID fields
        if 'UUID' in field_type:
            return 'sequence'
        
        # Default
        return 'distribution'

    def build_delta_fields(self) -> List[Dict[str, Any]]:
        """Build delta_fields with sensible defaults."""
        unresolved = self.get_unresolved_fields()
        delta_fields = []
        
        for item in unresolved:
            field = item['field_spec']
            strategy = self.infer_strategy(field, item['field_name'])
            
            updates = {
                'strategy': strategy,
                'values': None,
                'weights': None,
                'weight_rationale': None,
                'distribution': None,
                'params': {},
                'min': None,
                'max': None,
                'pattern': None,
                'nullable_rate': 0.0 if not field.get('nullable') else 0.05,
                'rationale': f'Inferred {strategy} strategy for {item["field_name"]} based on type {field.get("type")}'
            }
            
            # Set strategy-specific values
            if strategy == 'distribution':
                updates['distribution'] = 'normal'
                updates['params'] = {'mean': 0, 'std_dev': 1}
            elif strategy == 'date_range':
                updates['min'] = '2015-01-01'
                updates['max'] = '2025-12-31'
            elif strategy == 'regex':
                updates['pattern'] = '^[a-zA-Z0-9_-]{1,50}$'
            elif strategy == 'sequence':
                updates['params'] = {'format': 'uuid4'}
            
            delta_fields.append({
                'table': item['table'],
                'field': item['field_name'],
                'updates': updates
            })
        
        return delta_fields

    def build_row_count_distributions(self) -> List[Dict[str, Any]]:
        """Build row_count_distributions for all non-derived/computed tables."""
        row_counts = []
        
        for table in self.skeleton.get('tables', []):
            if table['classification'] not in ['derived', 'computed']:
                row_counts.append({
                    'table': table['name'],
                    'distribution': 'normal',
                    'params': {'mean': 1000, 'std_dev': 100},
                    'rationale': f'Default normal distribution for {table["name"]}'
                })
        
        return row_counts

    def build_cross_field_rules(self) -> List[Dict[str, Any]]:
        """Build cross_field_rules from domain hints."""
        rules = []
        
        for table in self.skeleton.get('tables', []):
            # Use existing cross_field_rules from skeleton
            if table.get('cross_field_rules'):
                for rule in table['cross_field_rules']:
                    rules.append({
                        'table': table['name'],
                        'type': rule.get('type', 'consistency'),
                        'rule': rule.get('rule', 'Consistency rule'),
                        'fields_involved': rule.get('fields_involved', []),
                        'rationale': rule.get('rationale', 'From schema')
                    })
        
        return rules

    def build_delta(self) -> Dict[str, Any]:
        """Build the complete delta."""
        return {
            'delta_fields': self.build_delta_fields(),
            'row_count_distributions': self.build_row_count_distributions(),
            'cross_field_rules': self.build_cross_field_rules()
        }

    def validate_delta(self) -> List[str]:
        """Validate the delta output."""
        errors = []

        if not isinstance(self.delta, dict):
            errors.append("Delta is not a dict")
            return errors

        # 1. delta_fields count > 0
        delta_fields = self.delta.get('delta_fields', [])
        if not delta_fields:
            errors.append("delta_fields is empty")

        # 2. No delta_field references a resolved_by: phase_a field
        resolved_field_names = set()
        for table in self.skeleton.get('tables', []):
            for field in table.get('fields', []):
                if field.get('resolved_by') == 'phase_a':
                    resolved_field_names.add((table['name'], field['name']))

        for delta_field in delta_fields:
            key = (delta_field.get('table'), delta_field.get('field'))
            if key in resolved_field_names:
                errors.append(f"Delta field {key} was already resolved by phase_a")

        # 3. No delta field has strategy: null
        for delta_field in delta_fields:
            if delta_field.get('updates', {}).get('strategy') is None:
                errors.append(
                    f"Delta field {delta_field.get('table')}.{delta_field.get('field')} "
                    f"has strategy: null"
                )

        return errors

    def print_summary(self) -> None:
        """Print execution summary."""
        delta_field_count = len(self.delta.get('delta_fields', []))
        tables_covered = set()
        for delta_field in self.delta.get('delta_fields', []):
            tables_covered.add(delta_field.get('table'))

        cross_field_rules_count = len(self.delta.get('cross_field_rules', []))
        row_count_count = len(self.delta.get('row_count_distributions', []))

        print(f"\n{'='*60}")
        print(f"Seed Agent Phase B Summary")
        print(f"{'='*60}")
        print(f"Delta fields completed: {delta_field_count}")
        print(f"Tables covered: {len(tables_covered)}")
        print(f"Cross-field rules: {cross_field_rules_count}")
        print(f"Row count distributions: {row_count_count}")
        print(f"{'='*60}\n")

    def run(self, output_path: str) -> None:
        """Execute the full pipeline."""
        self.load_inputs()

        # Build delta
        self.delta = self.build_delta()

        # Validate
        errors = self.validate_delta()
        if errors:
            print("Validation errors:")
            for error in errors:
                print(f"  - {error}")
            raise ValueError(f"{len(errors)} validation error(s)")

        # Write output
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.delta, f, indent=2)

        print(f"Distribution spec delta written to {output_path}")
        self.print_summary()


def main():
    parser = argparse.ArgumentParser(description='Distribution Spec Enricher (Seed Agent Phase B)')
    parser.add_argument('skeleton', help='Path to distribution_spec_skeleton.json')
    parser.add_argument('data_dictionary', help='Path to data dictionary file')
    parser.add_argument('--output', default='outputs/distribution_spec_delta.json',
                        help='Output path for delta JSON')

    args = parser.parse_args()

    enricher = DistributionSpecEnricher(args.skeleton, args.data_dictionary)
    enricher.run(args.output)


if __name__ == '__main__':
    main()
