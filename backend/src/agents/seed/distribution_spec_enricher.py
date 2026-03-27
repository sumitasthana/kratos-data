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

    def __init__(self, skeleton_path: str, data_dictionary_path: str, schema_graph_path: Optional[str] = None):
        self.skeleton_path = skeleton_path
        self.data_dictionary_path = data_dictionary_path
        self.schema_graph_path = schema_graph_path or skeleton_path.replace('distribution_spec_skeleton', 'schema_graph')
        self.skeleton = None
        self.data_dictionary = None
        self.schema_graph = None
        self.delta = None
        self.field_types = {}  # Cache of table.field -> type

    def load_inputs(self) -> None:
        """Load skeleton, schema_graph, and data dictionary."""
        with open(self.skeleton_path, 'r', encoding='utf-8') as f:
            self.skeleton = json.load(f)

        with open(self.data_dictionary_path, 'r', encoding='utf-8') as f:
            self.data_dictionary = f.read()
        
        # Load schema_graph to get field types
        try:
            with open(self.schema_graph_path, 'r', encoding='utf-8') as f:
                self.schema_graph = json.load(f)
                # Build field type cache
                for table in self.schema_graph.get('tables', []):
                    for col in table.get('columns', []):
                        key = f"{table['name']}.{col['name']}"
                        self.field_types[key] = col.get('type', 'UNKNOWN')
        except FileNotFoundError:
            print(f"WARNING: schema_graph not found at {self.schema_graph_path}, using field names for inference")

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

    def infer_strategy_and_params(self, field: Dict[str, Any], field_name: str, table_name: str) -> tuple:
        """Infer strategy and params based on field type and context.
        
        Returns: (strategy, distribution_type, params, min, max, pattern, rationale)
        """
        # Get field type from cache (loaded from schema_graph)
        cache_key = f"{table_name}.{field_name}"
        field_type = self.field_types.get(cache_key, field.get('type', '')).upper()
        field_name_lower = field_name.lower()
        
        # Check for aggregate constraint fields (e.g. percentages that sum to 100)
        if any(x in field_name_lower for x in ['percentage', 'percent', 'weight', 'proportion', 'share']):
            return ('computed', None, {'formula': f'{field_name} must sum to 100 with sibling rows'}, None, None, None,
                    f'{field_name} is an aggregate field that must maintain constraints across sibling rows')
        
        # Composite PK components
        if field.get('params', {}).get('role') == 'composite_pk_component':
            if 'DATE' in field_type or 'TIMESTAMP' in field_type:
                return ('date_range', None, {}, '2015-01-01', '2025-12-31', None,
                        f'Date component of composite PK in {table_name}')
            elif 'INT' in field_type or 'NUMERIC' in field_type or 'DECIMAL' in field_type:
                return ('distribution', 'uniform', {'min': 1, 'max': 1000}, None, None, None,
                        f'Numeric component of composite PK in {table_name}')
            return ('distribution', 'uniform', {'min': 0, 'max': 100}, None, None, None,
                    f'Composite PK component in {table_name}')
        
        # Date/timestamp fields
        if 'DATE' in field_type or 'TIMESTAMP' in field_type:
            return ('date_range', None, {}, '2015-01-01', '2025-12-31', None,
                    f'{field_name} is a date/timestamp field')
        
        # Numeric fields - use appropriate distributions
        if 'INT' in field_type or 'NUMERIC' in field_type or 'DECIMAL' in field_type or 'FLOAT' in field_type:
            # Check for balance/amount fields - use lognormal
            if any(x in field_name_lower for x in ['balance', 'amount', 'total', 'sum', 'value']):
                return ('distribution', 'lognormal', {'mu': 5, 'sigma': 2}, None, None, None,
                        f'{field_name} is a financial amount - using lognormal distribution (mu/sigma in log-space)')
            # Check for count/quantity fields - use poisson
            if any(x in field_name_lower for x in ['count', 'quantity', 'number', 'num_']):
                return ('distribution', 'poisson', {'lambda': 10}, None, None, None,
                        f'{field_name} is a count field - using poisson distribution')
            # Default numeric - uniform
            return ('distribution', 'uniform', {'min': 0, 'max': 1000}, None, None, None,
                    f'{field_name} is numeric - using uniform distribution')
        
        # String fields - use regex or constant
        if 'VARCHAR' in field_type or 'TEXT' in field_type or 'CHAR' in field_type:
            # Check for specific patterns
            if any(x in field_name_lower for x in ['email', 'mail']):
                return ('regex', None, {}, None, None, r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
                        f'{field_name} is an email field')
            if any(x in field_name_lower for x in ['phone', 'telephone']):
                return ('regex', None, {}, None, None, r'^\+?1?\d{9,15}$',
                        f'{field_name} is a phone number field')
            if any(x in field_name_lower for x in ['zip', 'postal', 'code']):
                return ('regex', None, {}, None, None, r'^\d{5}(-\d{4})?$',
                        f'{field_name} is a postal code field')
            if any(x in field_name_lower for x in ['name', 'title', 'description']):
                return ('regex', None, {}, None, None, r'^[a-zA-Z\s\-\.]{1,100}$',
                        f'{field_name} is a text field - using regex pattern')
            # Generic string
            return ('regex', None, {}, None, None, r'^[a-zA-Z0-9_\-]{1,50}$',
                    f'{field_name} is a string field')
        
        # UUID fields
        if 'UUID' in field_type:
            return ('sequence', None, {'format': 'uuid4'}, None, None, None,
                    f'{field_name} is a UUID field')
        
        # Default
        return ('distribution', 'uniform', {'min': 0, 'max': 100}, None, None, None,
                f'{field_name} - default uniform distribution')

    def build_delta_fields(self) -> List[Dict[str, Any]]:
        """Build delta_fields with proper strategy inference per field type."""
        unresolved = self.get_unresolved_fields()
        delta_fields = []
        
        # Debug: log stripped fields count
        resolved_count = sum(1 for table in self.skeleton.get('tables', [])
                           for field in table.get('fields', [])
                           if field.get('resolved_by') == 'phase_a')
        print(f"DEBUG: Stripped {resolved_count} phase_a resolved fields before LLM processing")
        
        for item in unresolved:
            field = item['field_spec']
            strategy, dist_type, params, min_val, max_val, pattern, rationale = \
                self.infer_strategy_and_params(field, item['field_name'], item['table'])
            
            updates = {
                'strategy': strategy,
                'values': None,
                'weights': None,
                'weight_rationale': None,
                'distribution': dist_type,
                'params': params,
                'min': min_val,
                'max': max_val,
                'pattern': pattern,
                'nullable_rate': 0.0 if not field.get('nullable') else 0.05,
                'rationale': rationale
            }
            
            delta_fields.append({
                'table': item['table'],
                'field': item['field_name'],
                'updates': updates
            })
        
        return delta_fields

    def build_row_count_distributions(self) -> List[Dict[str, Any]]:
        """Build row_count_distributions for all non-derived/computed tables with entries array."""
        row_counts = []
        
        for table in self.skeleton.get('tables', []):
            if table['classification'] not in ['derived', 'computed']:
                # Determine appropriate distribution based on table type
                if table['classification'] == 'independent':
                    # Root tables - larger counts
                    distribution = 'normal'
                    params = {'mean': 1000, 'std_dev': 100}
                    rationale = f'{table["name"]} is independent - normal distribution with mean 1000'
                else:
                    # Dependent tables - smaller counts, per parent row
                    distribution = 'poisson'
                    params = {'lambda': 5}
                    rationale = f'{table["name"]} is dependent - poisson distribution per parent'
                
                row_counts.append({
                    'table': table['name'],
                    'entries': [
                        {
                            'distribution': distribution,
                            'params': params,
                            'unit': 'per_parent_row' if table['classification'] == 'dependent' else 'total',
                            'bounds': [1, 10000],
                            'condition': None,
                            'rationale': rationale
                        }
                    ]
                })
        
        return row_counts

    def build_cross_field_rules(self) -> List[Dict[str, Any]]:
        """Build explicit cross-field rules nested under 'rules' array per table."""
        rules_by_table = {}
        
        # Get schema_graph tables for field type info
        schema_tables = {t['name']: t for t in self.schema_graph.get('tables', [])} if self.schema_graph else {}
        
        for table in self.skeleton.get('tables', []):
            table_name = table['name']
            schema_table = schema_tables.get(table_name, {})
            schema_columns = {c['name']: c for c in schema_table.get('columns', [])}
            table_rules = []
            
            # 1. Temporal ordering rules - for tables with 2+ date fields
            date_fields = [c for c in schema_table.get('columns', []) 
                          if 'DATE' in c.get('type', '').upper() or 'TIMESTAMP' in c.get('type', '').upper()]
            if len(date_fields) >= 2:
                table_rules.append({
                    'type': 'temporal_ordering',
                    'rule': f'Ensure {date_fields[0]["name"]} <= {date_fields[1]["name"]} for temporal consistency',
                    'fields_involved': [f['name'] for f in date_fields[:2]],
                    'rationale': 'Temporal fields must follow logical ordering (e.g., created_date <= modified_date)'
                })
            
            # 2. Sum constraint rules - for tables with 2+ amount/balance fields (exclude date fields)
            amount_fields = [c for c in schema_table.get('columns', [])
                           if any(x in c['name'].lower() for x in ['amount', 'balance', 'total', 'sum'])
                           and 'DATE' not in c.get('type', '').upper() and 'TIMESTAMP' not in c.get('type', '').upper()]
            if len(amount_fields) >= 2:
                table_rules.append({
                    'type': 'sum_constraint',
                    'rule': f'Sum of {", ".join([f["name"] for f in amount_fields[:-1]])} should equal {amount_fields[-1]["name"]}',
                    'fields_involved': [f['name'] for f in amount_fields],
                    'rationale': 'Financial amounts must satisfy sum constraints for data integrity'
                })
            
            # 3. Conditional population rules - for tables with conditional groups
            if table.get('conditional_groups'):
                for group in table['conditional_groups']:
                    table_rules.append({
                        'type': 'conditional_population',
                        'rule': f'When {group.get("condition_field")} = {group.get("condition_value")}, populate {", ".join(group.get("fields", []))}',
                        'fields_involved': [group.get('condition_field')] + group.get('fields', []),
                        'rationale': f'Conditional group: {group.get("condition_field")} determines which fields are populated'
                    })
            
            # 4. Balance equation rules - for accounting/financial tables (exclude date fields)
            if 'balance' in table_name.lower() or 'account' in table_name.lower():
                balance_fields = [c['name'] for c in schema_table.get('columns', [])
                                if any(x in c['name'].lower() for x in ['debit', 'credit', 'balance', 'total'])
                                and 'DATE' not in c.get('type', '').upper() and 'TIMESTAMP' not in c.get('type', '').upper()]
                if balance_fields:
                    table_rules.append({
                        'type': 'balance_equation',
                        'rule': f'Maintain balance equation: debits + credits = total for {table_name}',
                        'fields_involved': balance_fields,
                        'rationale': 'Accounting tables must satisfy balance equations'
                    })
            
            # 5. Consistency rules - for all tables with foreign keys
            if table.get('foreign_keys'):
                table_rules.append({
                    'type': 'consistency',
                    'rule': f'All foreign key references must point to valid parent rows',
                    'fields_involved': [fk['from_field'] for fk in table['foreign_keys']],
                    'rationale': 'Referential integrity: foreign keys must reference existing parent rows'
                })
            
            # Only add table entry if it has rules
            if table_rules:
                rules_by_table[table_name] = {
                    'table': table_name,
                    'rules': table_rules
                }
        
        return list(rules_by_table.values())

    def build_delta(self) -> Dict[str, Any]:
        """Build the complete delta."""
        return {
            'delta_fields': self.build_delta_fields(),
            'row_count_distributions': self.build_row_count_distributions(),
            'cross_field_rules': self.build_cross_field_rules()
        }

    def validate_cross_field_rules(self) -> List[str]:
        """Validate cross-field rules: reject any rule with date fields in arithmetic operations."""
        errors = []
        
        # Build set of date fields
        date_fields = set()
        for table in self.skeleton.get('tables', []):
            table_name = table['name']
            for col in self.schema_graph.get('tables', []):
                if col['name'] == table_name:
                    for c in col.get('columns', []):
                        if 'DATE' in c.get('type', '').upper() or 'TIMESTAMP' in c.get('type', '').upper():
                            date_fields.add(f"{table_name}.{c['name']}")
        
        # Validate rules
        rules_to_remove = []
        for rule_entry in self.delta.get('cross_field_rules', []):
            table_name = rule_entry.get('table')
            for rule in rule_entry.get('rules', []):
                rule_type = rule.get('type')
                fields_involved = rule.get('fields_involved', [])
                
                # Check if any date field appears in sum_constraint or balance_equation
                if rule_type in ['sum_constraint', 'balance_equation']:
                    for field_name in fields_involved:
                        full_key = f"{table_name}.{field_name}"
                        if full_key in date_fields:
                            error_msg = (f"REJECTED: {rule_type} rule in {table_name} references "
                                       f"date field '{field_name}' - date fields cannot be used in arithmetic rules")
                            print(f"VALIDATION: {error_msg}")
                            errors.append(error_msg)
                            rules_to_remove.append((rule_entry, rule))
        
        # Remove invalid rules
        for rule_entry, rule in rules_to_remove:
            rule_entry['rules'].remove(rule)
        
        return errors

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

        # 4. Validate cross-field rules for date field usage
        cross_field_errors = self.validate_cross_field_rules()
        errors.extend(cross_field_errors)

        return errors

    def print_summary(self) -> None:
        """Print execution summary."""
        delta_field_count = len(self.delta.get('delta_fields', []))
        tables_covered = set()
        for delta_field in self.delta.get('delta_fields', []):
            tables_covered.add(delta_field.get('table'))

        # Count rules across all tables
        cross_field_rules_count = 0
        for rule_entry in self.delta.get('cross_field_rules', []):
            cross_field_rules_count += len(rule_entry.get('rules', []))
        
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
