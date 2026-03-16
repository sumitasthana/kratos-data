import json
import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone


class DistributionSpecSkeletonBuilder:
    """Deterministic skeleton builder for synthetic data generation.
    
    Phase A of the Seed Agent pipeline. Reads schema_graph.json and optionally
    domain_supplements.json, then deterministically resolves table classifications
    and field strategies, writing distribution_spec_skeleton.json for Phase B LLM processing.
    """

    def __init__(self, schema_graph_path: str, supplements_path: Optional[str] = None):
        self.schema_graph_path = schema_graph_path
        self.supplements_path = supplements_path
        self.schema_graph = None
        self.supplements = None
        self.output = None
        self.resolved_count = 0
        self.unresolved_count = 0

    def load_inputs(self) -> None:
        """Load schema_graph.json and optional domain_supplements.json."""
        with open(self.schema_graph_path, 'r', encoding='utf-8') as f:
            self.schema_graph = json.load(f)

        if self.supplements_path:
            with open(self.supplements_path, 'r', encoding='utf-8') as f:
                self.supplements = json.load(f)
        else:
            self.supplements = {}

    def compute_schema_hash(self) -> str:
        """Compute SHA256 hash of schema_graph.json."""
        with open(self.schema_graph_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def classify_table(self, table_name: str) -> str:
        """Classify table based on domain_supplements and foreign keys."""
        if not self.supplements:
            # No supplements: only dependent/independent
            table = next((t for t in self.schema_graph['tables'] if t['name'] == table_name), None)
            if table and table.get('foreign_keys'):
                return 'dependent'
            return 'independent'

        derived_tables = self.supplements.get('derived_tables', [])
        computed_tables = self.supplements.get('computed_tables', [])

        if table_name in derived_tables:
            return 'derived'
        if table_name in computed_tables:
            return 'computed'

        table = next((t for t in self.schema_graph['tables'] if t['name'] == table_name), None)
        if table and table.get('foreign_keys'):
            return 'dependent'
        return 'independent'

    def resolve_field(self, table_name: str, field: Dict[str, Any], table: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Resolve a field's strategy deterministically.
        Returns (field_spec, is_resolved).
        """
        field_spec = {
            'name': field['name'],
            'strategy': None,
            'params': {},
            'values': None,
            'weights': None,
            'weight_rationale': None,
            'distribution': None,
            'min': None,
            'max': None,
            'pattern': None,
            'condition': None,
            'nullable_rate': None,
            'rationale': None,
            'resolved_by': None
        }

        # Rule 1: Single-field UUID PK with gen_random_uuid() default
        if (table.get('primary_key') == field['name'] and
            field['type'] == 'UUID' and
            field.get('default') == 'gen_random_uuid()'):
            field_spec['strategy'] = 'sequence'
            field_spec['params'] = {'format': 'uuid4'}
            field_spec['resolved_by'] = 'phase_a'
            return field_spec, True

        # Rule 2: Composite PK non-UUID component
        pk = table.get('primary_key')
        if isinstance(pk, list) and field['name'] in pk and field['type'] != 'UUID':
            field_spec['strategy'] = None
            field_spec['params'] = {
                'role': 'composite_pk_component',
                'pk_fields': pk
            }
            field_spec['resolved_by'] = None
            return field_spec, False

        # Rule 3: Foreign key
        for fk in table.get('foreign_keys', []):
            if fk.get('from_field') == field['name']:
                field_spec['strategy'] = 'foreign_key'
                field_spec['params'] = {
                    'references_table': fk['to_table'],
                    'references_field': fk['to_field']
                }
                field_spec['resolved_by'] = 'phase_a'
                if fk.get('nullable'):
                    field_spec['nullable_rate'] = None
                return field_spec, True

        # Rule 4: Enum field
        if field.get('enum_name'):
            enum_name = field['enum_name']
            enum_values = self.schema_graph.get('enums', {}).get(enum_name, [])
            field_spec['strategy'] = 'enum'
            field_spec['values'] = enum_values
            field_spec['weights'] = None
            field_spec['resolved_by'] = 'phase_a'
            return field_spec, True

        # Rule 5: Boolean field
        if field['type'] == 'BOOLEAN':
            field_spec['strategy'] = 'enum'
            field_spec['values'] = [True, False]
            field_spec['weights'] = None
            field_spec['resolved_by'] = 'phase_a'
            return field_spec, True

        # Rule 6: Audit columns
        if field['name'] == 'created_date' or field['name'] == 'modified_date':
            field_spec['strategy'] = 'constant'
            field_spec['params'] = {'value': 'CURRENT_TIMESTAMP'}
            field_spec['resolved_by'] = 'phase_a'
            return field_spec, True

        if field['name'] == 'created_by' or field['name'] == 'modified_by':
            field_spec['strategy'] = 'constant'
            field_spec['params'] = {'value': 'synth_data_studio'}
            field_spec['resolved_by'] = 'phase_a'
            return field_spec, True

        # Rule 7: Has non-null default
        if field.get('default') and field['default'] != 'gen_random_uuid()':
            field_spec['strategy'] = None
            field_spec['params'] = {'schema_default': field['default']}
            field_spec['resolved_by'] = None
            return field_spec, False

        # Rule 8: Everything else
        field_spec['strategy'] = None
        field_spec['resolved_by'] = None
        return field_spec, False

    def apply_conditional_groups(self, table: Dict[str, Any], fields_by_name: Dict[str, Dict[str, Any]]) -> None:
        """Apply conditional groups to fields."""
        for group in table.get('conditional_groups', []):
            condition_field = group.get('condition_field')
            condition_value = group.get('condition_value')

            if not condition_field or not condition_value:
                continue

            condition = {
                'field': condition_field,
                'operator': '==',
                'value': condition_value
            }

            for field_name in group.get('fields', []):
                if field_name in fields_by_name:
                    fields_by_name[field_name]['condition'] = condition

    def build_output(self) -> Dict[str, Any]:
        """Build the distribution_spec_skeleton.json output."""
        schema_hash = self.compute_schema_hash()
        timestamp = datetime.now(timezone.utc).isoformat()

        output = {
            'metadata': {
                'generated_by': 'seed_agent_phase_a',
                'schema_graph_hash': schema_hash,
                'timestamp': timestamp,
                'domain_supplements_provided': bool(self.supplements_path),
                'phase_a_fields_resolved': 0,
                'phase_a_fields_unresolved': 0,
                'total_fields': 0
            },
            'reference_lookups': {},
            'domain_row_count_hints': [],
            'domain_generation_profiles': {},
            'domain_cross_field_rule_hints': [],
            'generation_order': self.schema_graph.get('generation_order', []),
            'tables': []
        }

        # Copy domain supplements sections
        if self.supplements:
            output['reference_lookups'] = self.supplements.get('reference_lookups', {})
            output['domain_row_count_hints'] = self.supplements.get('row_count_hints', [])
            output['domain_generation_profiles'] = self.supplements.get('generation_profiles', {})
            output['domain_cross_field_rule_hints'] = self.supplements.get('cross_field_rule_hints', [])

        total_fields = 0
        resolved_fields = 0

        # Process each table
        for table in self.schema_graph.get('tables', []):
            table_name = table['name']
            classification = self.classify_table(table_name)

            table_spec = {
                'name': table_name,
                'classification': classification,
                'row_count_distribution': None,
                'fields': [],
                'cross_field_rules': []
            }

            # Process fields
            fields_by_name = {}
            for field in table.get('columns', []):
                field_spec, is_resolved = self.resolve_field(table_name, field, table)
                table_spec['fields'].append(field_spec)
                fields_by_name[field['name']] = field_spec

                total_fields += 1
                if is_resolved:
                    resolved_fields += 1

            # Apply conditional groups
            self.apply_conditional_groups(table, fields_by_name)

            output['tables'].append(table_spec)

        # Update metadata
        output['metadata']['total_fields'] = total_fields
        output['metadata']['phase_a_fields_resolved'] = resolved_fields
        output['metadata']['phase_a_fields_unresolved'] = total_fields - resolved_fields

        self.resolved_count = resolved_fields
        self.unresolved_count = total_fields - resolved_fields

        return output

    def validate_output(self) -> List[str]:
        """Validate the output against requirements."""
        errors = []

        # 1. Valid JSON (implicit if we got here)
        # 2. All tables present
        schema_table_names = {t['name'] for t in self.schema_graph['tables']}
        output_table_names = {t['name'] for t in self.output['tables']}
        if schema_table_names != output_table_names:
            errors.append(f"Table mismatch: schema has {schema_table_names}, output has {output_table_names}")

        # 3. No enum field has weights filled
        for table in self.output['tables']:
            for field in table['fields']:
                if field['strategy'] == 'enum' and field['weights'] is not None:
                    errors.append(f"Enum field {table['name']}.{field['name']} has non-null weights")

        # 4. Every single-field UUID PK is sequence
        for table in self.output['tables']:
            schema_table = next((t for t in self.schema_graph['tables'] if t['name'] == table['name']), None)
            if schema_table and schema_table.get('primary_key') and isinstance(schema_table['primary_key'], str):
                pk_field = next((f for f in schema_table['columns'] if f['name'] == schema_table['primary_key']), None)
                if pk_field and pk_field['type'] == 'UUID' and pk_field.get('default') == 'gen_random_uuid()':
                    output_field = next((f for f in table['fields'] if f['name'] == schema_table['primary_key']), None)
                    if output_field and output_field['strategy'] != 'sequence':
                        errors.append(f"UUID PK {table['name']}.{schema_table['primary_key']} is not sequence")

        # 5. Every FK field is foreign_key
        for table in self.output['tables']:
            schema_table = next((t for t in self.schema_graph['tables'] if t['name'] == table['name']), None)
            if schema_table:
                for fk in schema_table.get('foreign_keys', []):
                    output_field = next((f for f in table['fields'] if f['name'] == fk['from_field']), None)
                    if output_field and output_field['strategy'] != 'foreign_key':
                        errors.append(f"FK field {table['name']}.{fk['from_field']} is not foreign_key")

        # 6. Composite PK non-UUID components have role
        for table in self.output['tables']:
            schema_table = next((t for t in self.schema_graph['tables'] if t['name'] == table['name']), None)
            if schema_table and isinstance(schema_table.get('primary_key'), list):
                for pk_field_name in schema_table['primary_key']:
                    pk_field = next((f for f in schema_table['columns'] if f['name'] == pk_field_name), None)
                    if pk_field and pk_field['type'] != 'UUID':
                        output_field = next((f for f in table['fields'] if f['name'] == pk_field_name), None)
                        if output_field and output_field['params'].get('role') != 'composite_pk_component':
                            errors.append(f"Composite PK {table['name']}.{pk_field_name} missing role")

        # 7. Fields in conditional_groups have condition set
        for table in self.output['tables']:
            schema_table = next((t for t in self.schema_graph['tables'] if t['name'] == table['name']), None)
            if schema_table:
                for group in schema_table.get('conditional_groups', []):
                    for field_name in group.get('fields', []):
                        output_field = next((f for f in table['fields'] if f['name'] == field_name), None)
                        if output_field and output_field['condition'] is None:
                            errors.append(f"Field {table['name']}.{field_name} in conditional_groups has no condition")

        # 8. Audit columns are constant
        audit_column_patterns = ['created_date', 'modified_date', 'created_by', 'modified_by']
        for table in self.output['tables']:
            for field in table['fields']:
                if any(field['name'] == pattern for pattern in audit_column_patterns):
                    if field['strategy'] != 'constant':
                        errors.append(f"Audit column {table['name']}.{field['name']} is not constant")

        # 9. If supplements provided: reference_lookups populated, derived/computed classified
        if self.supplements_path:
            if not self.output['reference_lookups'] and self.supplements.get('reference_lookups'):
                errors.append("Supplements provided but reference_lookups not populated")

            derived_tables = self.supplements.get('derived_tables', [])
            computed_tables = self.supplements.get('computed_tables', [])
            for table in self.output['tables']:
                if table['name'] in derived_tables and table['classification'] != 'derived':
                    errors.append(f"Table {table['name']} should be classified as derived")
                if table['name'] in computed_tables and table['classification'] != 'computed':
                    errors.append(f"Table {table['name']} should be classified as computed")

        # 10. If supplements absent: no derived/computed, reference_lookups is empty
        if not self.supplements_path:
            for table in self.output['tables']:
                if table['classification'] in ['derived', 'computed']:
                    errors.append(f"Table {table['name']} classified as {table['classification']} without supplements")
            if self.output['reference_lookups']:
                errors.append("reference_lookups populated without supplements")

        return errors

    def print_summary(self) -> None:
        """Print execution summary."""
        total = self.resolved_count + self.unresolved_count
        rate = (self.resolved_count / total * 100) if total > 0 else 0
        print(f"\n{'='*60}")
        print(f"Seed Agent Phase A Summary")
        print(f"{'='*60}")
        print(f"Total fields processed: {total}")
        print(f"Fields resolved by Phase A: {self.resolved_count}")
        print(f"Fields unresolved (for Phase B): {self.unresolved_count}")
        print(f"Resolution rate: {rate:.1f}%")
        print(f"{'='*60}\n")

    def run(self, output_path: str) -> None:
        """Execute the full pipeline."""
        self.load_inputs()
        self.output = self.build_output()

        errors = self.validate_output()
        if errors:
            print("Validation errors:")
            for error in errors:
                print(f"  - {error}")
            raise ValueError(f"{len(errors)} validation error(s)")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.output, f, indent=2)

        print(f"Distribution spec skeleton written to {output_path}")
        self.print_summary()


def main():
    parser = argparse.ArgumentParser(description='Distribution Spec Skeleton Builder (Seed Agent Phase A)')
    parser.add_argument('schema_graph', help='Path to schema_graph.json')
    parser.add_argument('--supplements', help='Path to domain_supplements.json (optional)')
    parser.add_argument('--output', default='distribution_spec_skeleton.json', help='Output path')

    args = parser.parse_args()

    builder = DistributionSpecSkeletonBuilder(args.schema_graph, args.supplements)
    builder.run(args.output)


if __name__ == '__main__':
    main()
