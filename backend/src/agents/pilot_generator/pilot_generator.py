import os
import json
import csv
import logging
import hashlib
import argparse
import uuid
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from collections import defaultdict

try:
    import numpy as np
except ImportError:
    np = None

try:
    import rstr
except ImportError:
    rstr = None

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class PilotGenerator:
    """Deterministic synthetic data generator for smoke testing."""

    def __init__(self, distribution_spec: dict, pilot_config: dict):
        self.spec = distribution_spec
        self.config = pilot_config
        self.random_seed = pilot_config.get('random_seed', 42)
        self.base_counts = pilot_config.get('base_counts', {})
        self.smoke_test_tables = set(pilot_config.get('smoke_test_tables', []))
        self.output_dir = Path(
            pilot_config.get('output_dir') or 
            os.getenv('PILOT_GENERATOR_OUTPUT_DIR', 'backend/data/outputs/pilot')
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.warnings = []
        self.errors = []
        self.generated_data = {}
        self.row_counts = {}
        self.tables_generated = []
        self.tables_skipped = []
        self.parent_registry = {}  # FK parent registry: table_name -> {pk_field: [values]}
        
        # Set random seed for reproducibility
        random.seed(self.random_seed)
        if np:
            np.random.seed(self.random_seed)

    def run(self) -> dict:
        """Generate pilot data and return manifest."""
        try:
            # Build table lookup
            table_map = {t['name']: t for t in self.spec.get('tables', [])}
            
            # Load schema_graph for primary key information
            schema_graph_path = os.path.join(os.path.dirname(__file__), '../../..', 'outputs', 'schema_graph.json')
            schema_graph = {}
            if os.path.exists(schema_graph_path):
                with open(schema_graph_path, 'r', encoding='utf-8') as f:
                    schema_graph_data = json.load(f)
                    schema_graph = {t['name']: t for t in schema_graph_data.get('tables', [])}
                    logger.info(f"Loaded schema_graph with {len(schema_graph)} tables")
            else:
                logger.warning(f"schema_graph.json not found at {schema_graph_path}")
            
            # Calculate row counts
            self._calculate_row_counts(table_map)
            
            # Generate data in generation_order
            for table_name in self.spec.get('generation_order', []):
                if table_name not in self.smoke_test_tables:
                    self.tables_skipped.append(table_name)
                    continue
                
                if table_name not in table_map:
                    self.warnings.append(f"Table {table_name} not found in spec")
                    continue
                
                table = table_map[table_name]
                row_count = self.row_counts.get(table_name, 0)
                
                logger.info(f"Generating {table_name}: {row_count} rows")
                rows = self._generate_table(table, table_map, row_count)
                self.generated_data[table_name] = rows
                self.tables_generated.append(table_name)
                
                # Populate parent_registry for FK resolution using schema_graph primary key
                pk_field = None
                if table_name in schema_graph:
                    pk_field = schema_graph[table_name].get('primary_key')
                
                # Handle composite primary keys - use first field for FK resolution
                if isinstance(pk_field, list) and len(pk_field) > 0:
                    pk_field = pk_field[0]
                
                if pk_field and rows:
                    registry_key = table_name.lower().strip()
                    pk_values = [row.get(pk_field) for row in rows]
                    self.parent_registry[registry_key] = {
                        'pk_field': pk_field,
                        'values': pk_values
                    }
                    logger.info(f"Populated parent_registry['{registry_key}'] with {len(pk_values)} {pk_field} values")
            
            # Write CSV files
            self._write_csv_files()
            
            # Build manifest with only generated tables in row_counts
            status = 'success' if not self.warnings else 'partial'
            if self.errors:
                status = 'failed'
            
            # Only include row counts for generated tables
            generated_row_counts = {
                table_name: self.row_counts.get(table_name, 0)
                for table_name in self.tables_generated
            }
            
            manifest = {
                'run_id': str(uuid.uuid4()),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'random_seed': self.random_seed,
                'distribution_spec_hash': self._compute_spec_hash(),
                'tables_generated': self.tables_generated,
                'tables_skipped': self.tables_skipped,
                'row_counts': generated_row_counts,
                'warnings': self.warnings,
                'errors': self.errors,
                'status': status,
            }
            
            return manifest
        
        except Exception as e:
            logger.error("Pilot generator failed", exc_info=True)
            self.errors.append(str(e))
            
            # Only include row counts for generated tables
            generated_row_counts = {
                table_name: self.row_counts.get(table_name, 0)
                for table_name in self.tables_generated
            }
            
            return {
                'run_id': str(uuid.uuid4()),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'random_seed': self.random_seed,
                'distribution_spec_hash': self._compute_spec_hash(),
                'tables_generated': self.tables_generated,
                'tables_skipped': self.tables_skipped,
                'row_counts': generated_row_counts,
                'warnings': self.warnings,
                'errors': self.errors,
                'status': 'failed',
            }

    def _compute_spec_hash(self) -> str:
        """Compute SHA256 hash of distribution spec."""
        spec_json = json.dumps(self.spec, sort_keys=True)
        return hashlib.sha256(spec_json.encode()).hexdigest()

    def _calculate_row_counts(self, table_map: dict) -> None:
        """Calculate row counts based on base_counts and row_count_distributions."""
        # Start with base counts
        for table_name, count in self.base_counts.items():
            self.row_counts[table_name] = count
        
        # For tables not in base_counts, calculate from parent
        for table_name in self.spec.get('generation_order', []):
            if table_name in self.row_counts:
                continue
            
            table = table_map.get(table_name)
            if not table:
                continue
            
            # Check if dependent (has foreign keys)
            if table.get('classification') == 'dependent':
                # Find parent table
                parent_name = self._find_parent_table(table, table_map)
                if parent_name and parent_name in self.row_counts:
                    parent_count = self.row_counts[parent_name]
                    rcd = table.get('row_count_distribution')
                    
                    if rcd and isinstance(rcd, list) and len(rcd) > 0:
                        # Use first entry's mean or expected value
                        entry = rcd[0]
                        dist_type = entry.get('distribution', 'uniform')
                        params = entry.get('params', {})
                        
                        if dist_type == 'normal':
                            mean = params.get('mean', 1.0)
                            self.row_counts[table_name] = max(1, int(parent_count * mean))
                        elif dist_type == 'poisson':
                            lambda_param = params.get('lambda', 1.0)
                            self.row_counts[table_name] = max(1, int(parent_count * lambda_param))
                        else:
                            self.row_counts[table_name] = parent_count
                    else:
                        self.warnings.append(
                            f"row_count_distribution missing for {table_name} — using 1 per parent row"
                        )
                        self.row_counts[table_name] = parent_count
                else:
                    self.row_counts[table_name] = 1
            else:
                # Independent table — use default
                self.row_counts[table_name] = self.base_counts.get(table_name, 1)

    def _find_parent_table(self, table: dict, table_map: dict) -> Optional[str]:
        """Find parent table for a dependent table by inferring from FK fields."""
        # Look for FK fields and infer parent table from field names
        for field in table.get('fields', []):
            if field.get('strategy') == 'foreign_key':
                parent_name = self._infer_parent_table_from_field(field['name'], table_map)
                if parent_name:
                    return parent_name
        return None

    def _infer_parent_table_from_field(self, field_name: str, table_map: dict) -> Optional[str]:
        """Infer parent table from FK field name (e.g., account_id -> account, primary_owner_party_id -> party)."""
        # Try removing common suffixes
        for suffix in ['_id', '_key', '_ref']:
            if field_name.endswith(suffix):
                potential_parent = field_name[:-len(suffix)]
                if potential_parent in table_map:
                    return potential_parent
        
        # Try matching against table names directly (e.g., primary_owner_party_id contains 'party')
        for table_name in table_map.keys():
            if table_name in field_name:
                return table_name
        
        return None

    def _generate_table(self, table: dict, table_map: dict, row_count: int) -> List[dict]:
        """Generate rows for a table."""
        rows = []
        table_name = table['name']
        
        # Check FK and computed fields and log warnings once
        for field in table.get('fields', []):
            field_name = field['name']
            strategy = field.get('strategy')
            
            if strategy == 'foreign_key':
                parent_name = self._infer_parent_table_from_field(field_name, table_map)
                
                if parent_name and parent_name not in self.parent_registry:
                    self.warnings.append(
                        f"FK field {table_name}.{field_name} references {parent_name} which was not generated"
                    )
                elif not parent_name:
                    self.warnings.append(
                        f"FK field {table_name}.{field_name} could not infer parent table"
                    )
            
            elif strategy == 'computed':
                self.warnings.append(
                    f"Computed strategy not implemented for {table_name}.{field_name}"
                )
        
        # Generate rows
        for i in range(row_count):
            row = {}
            for field in table.get('fields', []):
                field_name = field['name']
                value = self._generate_field_value(
                    field, table, row, table_name
                )
                row[field_name] = value
            rows.append(row)
        
        return rows

    def _generate_field_value(
        self,
        field: dict,
        table: dict,
        current_row: dict,
        table_name: str,
    ) -> Any:
        """Generate a value for a field."""
        strategy = field.get('strategy')
        
        # Check condition first
        if field.get('condition'):
            if not self._evaluate_condition(field['condition'], current_row):
                return None
        
        # Generate based on strategy
        if strategy == 'sequence':
            return str(uuid.uuid4())
        
        elif strategy == 'foreign_key':
            # Infer parent table from field name
            field_name = field['name']
            table_map = {t['name']: t for t in self.spec.get('tables', [])}
            parent_name = self._infer_parent_table_from_field(field_name, table_map)
            
            if parent_name:
                # Normalize lookup key
                lookup_key = parent_name.lower().strip()
                
                if lookup_key in self.parent_registry:
                    parent_info = self.parent_registry[lookup_key]
                    values = parent_info['values']
                    if values:
                        return random.choice(values)
            
            # FK field but no parent data available — set to null (don't log per row)
            return None
        
        elif strategy == 'enum':
            values = field.get('values')
            weights = field.get('weights')
            if values:
                # Handle both dict and list formats
                if isinstance(values, dict):
                    value_list = list(values.keys())
                    if weights:
                        weight_list = list(weights.values()) if isinstance(weights, dict) else weights
                        return random.choices(value_list, weights=weight_list)[0]
                    else:
                        return random.choice(value_list)
                elif isinstance(values, list):
                    if weights:
                        weight_list = weights if isinstance(weights, list) else list(weights.values())
                        return random.choices(values, weights=weight_list)[0]
                    else:
                        return random.choice(values)
            return None
        
        elif strategy == 'constant':
            return field.get('params', {}).get('value')
        
        elif strategy == 'distribution':
            dist_type = field.get('distribution')
            params = field.get('params', {})
            return self._generate_from_distribution(dist_type, params)
        
        elif strategy == 'date_range':
            min_date = field.get('min')
            max_date = field.get('max')
            if min_date and max_date:
                return self._generate_date_in_range(min_date, max_date)
            return None
        
        elif strategy == 'regex':
            pattern = field.get('pattern')
            if pattern:
                return self._generate_from_regex(pattern)
            return None
        
        elif strategy == 'computed':
            return None
        
        elif strategy is None:
            return None
        
        else:
            return None
        
        # Apply nullable_rate
        if field.get('nullable_rate', 0) > 0:
            if random.random() < field['nullable_rate']:
                return None
        
        return None

    def _evaluate_condition(self, condition: dict, row: dict) -> bool:
        """Evaluate a condition against a row."""
        if 'all' in condition:
            return all(self._evaluate_condition(c, row) for c in condition['all'])
        
        if 'any' in condition:
            return any(self._evaluate_condition(c, row) for c in condition['any'])
        
        field = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')
        
        if field not in row:
            return False
        
        row_value = row[field]
        
        if operator == '==':
            return row_value == value
        elif operator == '!=':
            return row_value != value
        elif operator == 'in':
            return row_value in value
        elif operator == 'not_in':
            return row_value not in value
        elif operator == 'is_null':
            return row_value is None
        elif operator == 'is_not_null':
            return row_value is not None
        
        return False

    def _generate_from_distribution(self, dist_type: str, params: dict) -> Any:
        """Generate a value from a distribution."""
        if not np:
            self.warnings.append("NumPy not available — using uniform fallback")
            return random.uniform(params.get('min', 0), params.get('max', 1))
        
        if dist_type == 'normal':
            mean = params.get('mean', 0)
            std_dev = params.get('std_dev', 1)
            return np.random.normal(mean, std_dev)
        
        elif dist_type == 'lognormal':
            mean = params.get('mean', 0)
            sigma = params.get('sigma', 1)
            return np.random.lognormal(mean, sigma)
        
        elif dist_type == 'uniform':
            min_val = params.get('min', 0)
            max_val = params.get('max', 1)
            return random.uniform(min_val, max_val)
        
        elif dist_type == 'poisson':
            lambda_param = params.get('lambda', 1)
            return np.random.poisson(lambda_param)
        
        elif dist_type == 'bernoulli':
            p = params.get('p', 0.5)
            return 1 if random.random() < p else 0
        
        return None

    def _generate_date_in_range(self, min_date: str, max_date: str) -> str:
        """Generate a random date between min and max."""
        try:
            min_dt = datetime.fromisoformat(min_date.replace('Z', '+00:00'))
            max_dt = datetime.fromisoformat(max_date.replace('Z', '+00:00'))
            
            time_delta = max_dt - min_dt
            random_seconds = random.randint(0, int(time_delta.total_seconds()))
            random_date = min_dt + timedelta(seconds=random_seconds)
            
            return random_date.isoformat()
        except Exception as e:
            logger.warning(f"Failed to generate date: {e}")
            return min_date

    def _generate_from_regex(self, pattern: str) -> str:
        """Generate a string matching a regex pattern."""
        if not rstr:
            logger.warning("rstr not available — using placeholder")
            return "generated_value"
        
        try:
            return rstr.xeger(pattern)
        except Exception as e:
            logger.warning(f"Failed to generate from regex {pattern}: {e}")
            return "generated_value"

    def _write_csv_files(self) -> None:
        """Write generated data to CSV files."""
        for table_name, rows in self.generated_data.items():
            if not rows:
                continue
            
            csv_path = self.output_dir / f"{table_name}.csv"
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = list(rows[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for row in rows:
                    # Convert None to empty string
                    row_str = {k: (str(v) if v is not None else '') for k, v in row.items()}
                    writer.writerow(row_str)
            
            logger.info(f"Wrote {csv_path}")


def run_pilot(distribution_spec: dict, pilot_config: dict) -> dict:
    """Generate pilot data and return manifest."""
    generator = PilotGenerator(distribution_spec, pilot_config)
    manifest = generator.run()
    
    # Write manifest
    manifest_path = generator.output_dir / "pilot_run_manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    logger.info(f"Manifest written to {manifest_path}")
    
    return manifest


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Pilot Generator')
    parser.add_argument('distribution_spec', help='Path to distribution_spec.json')
    parser.add_argument('pilot_config', help='Path to pilot_config.json')
    parser.add_argument('--output-dir', help='Output directory')
    
    args = parser.parse_args()
    
    # Load inputs
    with open(args.distribution_spec, 'r', encoding='utf-8') as f:
        spec = json.load(f)
    
    with open(args.pilot_config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Override output_dir if provided
    if args.output_dir:
        config['output_dir'] = args.output_dir
    
    # Run generator
    manifest = run_pilot(spec, config)
    
    # Print summary
    print("\n" + "=" * 60)
    print("Pilot Generator Summary")
    print("=" * 60)
    print(f"Status: {manifest['status']}")
    print(f"Tables generated: {len(manifest['tables_generated'])}")
    print(f"Tables skipped: {len(manifest['tables_skipped'])}")
    print(f"Row counts:")
    for table, count in manifest['row_counts'].items():
        print(f"  {table}: {count}")
    print(f"Warnings: {len(manifest['warnings'])}")
    if manifest['warnings']:
        for warning in manifest['warnings']:
            print(f"  - {warning}")
    print(f"Errors: {len(manifest['errors'])}")
    if manifest['errors']:
        for error in manifest['errors']:
            print(f"  - {error}")
    print("=" * 60)


if __name__ == '__main__':
    main()
