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
    import rstr as _rstr
except ImportError:
    _rstr = None

try:
    from faker import Faker
    _faker = Faker()
except ImportError:
    _faker = None

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ORC code -> boolean flag mapping (fix #3)
# ---------------------------------------------------------------------------
ORC_FLAG_MAP = {
    'Single':                   {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Joint_TenancyByEntirety':  {'is_joint_ownership': True,  'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Joint_TenancyInCommon':    {'is_joint_ownership': True,  'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Joint_JTWROS':             {'is_joint_ownership': True,  'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'IRA_Traditional':          {'is_joint_ownership': False, 'is_ira': True,  'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'IRA_Roth':                 {'is_joint_ownership': False, 'is_ira': True,  'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'IRA_SEP':                  {'is_joint_ownership': False, 'is_ira': True,  'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'IRA_SIMPLE':               {'is_joint_ownership': False, 'is_ira': True,  'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Keogh_DefinedContribution':{'is_joint_ownership': False, 'is_ira': False, 'is_keogh': True,  'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Keogh_DefinedBenefit':     {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': True,  'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Trust_Revocable':          {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': True,  'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Trust_Irrevocable':        {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': True,  'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Trust_Charitable':         {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': True,  'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Trust_Qualified':          {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': True,  'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Escrow_Agent':             {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': True,  'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Government_Federal':       {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': True,  'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Government_State':         {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': True,  'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Government_Local':         {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': True,  'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Business_Corporation':     {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': True,  'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Business_Partnership':     {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': True,  'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Business_LLC':             {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': True,  'is_payable_on_death': False, 'is_transfer_on_death': False},
    'Business_SoleProprietor':  {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': True,  'is_payable_on_death': False, 'is_transfer_on_death': False},
    'POD_PayableOnDeath':       {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': True,  'is_transfer_on_death': False},
    'TOD_TransferOnDeath':      {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': True},
    'FiduciaryOther':           {'is_joint_ownership': False, 'is_ira': False, 'is_keogh': False, 'is_trust': False, 'is_government': False, 'is_business': False, 'is_payable_on_death': False, 'is_transfer_on_death': False},
}

# Party status constraints by party_type (fix #5)
PARTY_STATUS_BY_TYPE = {
    'Individual':   ['Active', 'Inactive', 'Deceased'],
    'Organization': ['Active', 'Inactive', 'Dissolved'],
    'Government':   ['Active', 'Inactive', 'Dissolved'],
}

# Boolean ORC flag field names
ORC_BOOLEAN_FIELDS = {
    'is_joint_ownership', 'is_ira', 'is_keogh', 'is_trust',
    'is_government', 'is_business', 'is_payable_on_death', 'is_transfer_on_death',
}


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
        self.parent_registry = {}

        random.seed(self.random_seed)
        if np:
            np.random.seed(self.random_seed)

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------
    def run(self) -> dict:
        """Generate pilot data and return manifest."""
        try:
            table_map = {t['name']: t for t in self.spec.get('tables', [])}

            # Load schema_graph for primary key information
            schema_graph_path = os.path.join(os.path.dirname(__file__), '../../..', 'outputs', 'schema_graph.json')
            schema_graph = {}
            if os.path.exists(schema_graph_path):
                with open(schema_graph_path, 'r', encoding='utf-8') as f:
                    schema_graph_data = json.load(f)
                    schema_graph = {t['name']: t for t in schema_graph_data.get('tables', [])}
                    logger.info(f"Loaded schema_graph with {len(schema_graph)} tables")

            self._calculate_row_counts(table_map)

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

                # Populate parent_registry
                pk_field = None
                if table_name in schema_graph:
                    pk_field = schema_graph[table_name].get('primary_key')
                if isinstance(pk_field, list) and len(pk_field) > 0:
                    pk_field = pk_field[0]
                if pk_field and rows:
                    registry_key = table_name.lower().strip()
                    pk_values = [row.get(pk_field) for row in rows]
                    self.parent_registry[registry_key] = {
                        'pk_field': pk_field,
                        'values': pk_values,
                    }
                    logger.info(f"Populated parent_registry['{registry_key}'] with {len(pk_values)} {pk_field} values")

            self._write_csv_files()

            status = 'success' if not self.warnings else 'partial'
            if self.errors:
                status = 'failed'

            generated_row_counts = {t: self.row_counts.get(t, 0) for t in self.tables_generated}

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
                'status': status,
            }

        except Exception as e:
            logger.error("Pilot generator failed", exc_info=True)
            self.errors.append(str(e))
            generated_row_counts = {t: self.row_counts.get(t, 0) for t in self.tables_generated}
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
        spec_json = json.dumps(self.spec, sort_keys=True)
        return hashlib.sha256(spec_json.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Row count calculation
    # ------------------------------------------------------------------
    def _calculate_row_counts(self, table_map: dict) -> None:
        for table_name, count in self.base_counts.items():
            self.row_counts[table_name] = count

        for table_name in self.spec.get('generation_order', []):
            if table_name in self.row_counts:
                continue
            table = table_map.get(table_name)
            if not table:
                continue

            if table.get('classification') == 'dependent':
                parent_name = self._find_parent_table(table, table_map)
                if parent_name and parent_name in self.row_counts:
                    parent_count = self.row_counts[parent_name]
                    rcd = table.get('row_count_distribution')
                    if rcd and isinstance(rcd, list) and len(rcd) > 0:
                        entry = rcd[0]
                        dist_type = entry.get('distribution', 'uniform')
                        params = entry.get('params', {})
                        if dist_type == 'normal':
                            self.row_counts[table_name] = max(1, int(parent_count * params.get('mean', 1.0)))
                        elif dist_type == 'poisson':
                            self.row_counts[table_name] = max(1, int(parent_count * params.get('lambda', 1.0)))
                        else:
                            self.row_counts[table_name] = parent_count
                    else:
                        self.row_counts[table_name] = parent_count
                else:
                    self.row_counts[table_name] = 1
            else:
                self.row_counts[table_name] = self.base_counts.get(table_name, 1)

    def _find_parent_table(self, table: dict, table_map: dict) -> Optional[str]:
        for field in table.get('fields', []):
            if field.get('strategy') == 'foreign_key':
                parent_name = self._infer_parent_table_from_field(field['name'], table_map)
                if parent_name:
                    return parent_name
        return None

    def _infer_parent_table_from_field(self, field_name: str, table_map: dict) -> Optional[str]:
        for suffix in ['_id', '_key', '_ref']:
            if field_name.endswith(suffix):
                potential = field_name[:-len(suffix)]
                if potential in table_map:
                    return potential
        for tn in table_map.keys():
            if tn in field_name:
                return tn
        return None

    # ------------------------------------------------------------------
    # Table generation — dispatches to per-table post-processing
    # ------------------------------------------------------------------
    def _generate_table(self, table: dict, table_map: dict, row_count: int) -> List[dict]:
        rows = []
        table_name = table['name']

        for i in range(row_count):
            row = {}
            for field in table.get('fields', []):
                fname = field['name']
                # ORC boolean flags are set in post-processing (fix #3)
                if table_name == 'account_regulatory_classification' and fname in ORC_BOOLEAN_FIELDS:
                    continue
                # balance_closing_amount is computed (fix #6)
                if table_name == 'daily_account_balance' and fname == 'balance_closing_amount':
                    continue
                row[fname] = self._generate_field_value(field, table, row, table_name)
            rows.append(row)

        # Per-table post-processing
        if table_name == 'party':
            self._postprocess_party(rows)
        elif table_name == 'account':
            self._postprocess_account(rows)
        elif table_name == 'account_ownership':
            self._postprocess_account_ownership(rows)
        elif table_name == 'account_regulatory_classification':
            self._postprocess_orc(rows)
        elif table_name == 'daily_account_balance':
            self._postprocess_daily_balance(rows)
        elif table_name == 'transaction':
            self._postprocess_transaction(rows)
        elif table_name == 'kyc_cip_verification':
            self._postprocess_kyc(rows)

        return rows

    # ------------------------------------------------------------------
    # Field value generation
    # ------------------------------------------------------------------
    def _generate_field_value(self, field: dict, table: dict, current_row: dict, table_name: str) -> Any:
        strategy = field.get('strategy')

        # Evaluate condition
        if field.get('condition'):
            if not self._evaluate_condition(field['condition'], current_row):
                return None

        if strategy == 'sequence':
            return str(uuid.uuid4())

        elif strategy == 'foreign_key':
            field_name = field['name']
            table_map = {t['name']: t for t in self.spec.get('tables', [])}
            parent_name = self._infer_parent_table_from_field(field_name, table_map)
            if parent_name:
                lookup_key = parent_name.lower().strip()
                if lookup_key in self.parent_registry:
                    values = self.parent_registry[lookup_key]['values']
                    if values:
                        return random.choice(values)
            return None

        elif strategy == 'enum':
            values = field.get('values')
            weights = field.get('weights')
            if values:
                vlist = list(values.keys()) if isinstance(values, dict) else list(values)
                if weights and isinstance(weights, dict):
                    wlist = [weights.get(str(v), 1.0) for v in vlist]
                    return random.choices(vlist, weights=wlist)[0]
                elif weights and isinstance(weights, list):
                    return random.choices(vlist, weights=weights)[0]
                else:
                    return random.choice(vlist)
            return None

        elif strategy == 'constant':
            raw = field.get('params', {}).get('value')
            # Fix #2: resolve CURRENT_TIMESTAMP to a realistic datetime
            # Use a date near other dates in the row rather than literal "now"
            if isinstance(raw, str) and 'CURRENT_TIMESTAMP' in raw.upper():
                # Find the latest date in the current row to anchor near it
                latest = None
                for v in current_row.values():
                    if isinstance(v, str) and len(v) >= 10:
                        try:
                            d = datetime.strptime(v[:10], '%Y-%m-%d')
                            if latest is None or d > latest:
                                latest = d
                        except (ValueError, TypeError):
                            pass
                if latest:
                    # created/modified shortly after the latest date in row
                    ts = latest + timedelta(seconds=random.randint(0, 86400))
                else:
                    ts = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 365))
                return ts.strftime('%Y-%m-%dT%H:%M:%SZ')
            return raw

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
            field_name = field.get('name', '')
            return self._generate_from_regex(pattern, field_name)

        elif strategy == 'computed':
            return None

        return None

    # ------------------------------------------------------------------
    # Condition evaluator
    # ------------------------------------------------------------------
    def _evaluate_condition(self, condition: dict, row: dict) -> bool:
        if 'all' in condition:
            return all(self._evaluate_condition(c, row) for c in condition['all'])
        if 'any' in condition:
            return any(self._evaluate_condition(c, row) for c in condition['any'])
        field = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')
        if field not in row:
            return False
        rv = row[field]
        if operator == '==':
            return rv == value
        elif operator == '!=':
            return rv != value
        elif operator == 'in':
            return rv in value
        elif operator == 'not_in':
            return rv not in value
        elif operator == 'is_null':
            return rv is None
        elif operator == 'is_not_null':
            return rv is not None
        return False

    # ------------------------------------------------------------------
    # Distribution generator
    # ------------------------------------------------------------------
    def _generate_from_distribution(self, dist_type: str, params: dict) -> Any:
        if not np:
            return random.uniform(params.get('min', 0), params.get('max', 1))
        if dist_type == 'normal':
            return np.random.normal(params.get('mean', 0), params.get('std_dev', 1))
        elif dist_type == 'lognormal':
            mu = params.get('mu', params.get('mean', 0))
            sigma = params.get('sigma', params.get('std_dev', 1))
            return np.random.lognormal(mu, sigma)
        elif dist_type == 'uniform':
            return random.uniform(params.get('min', 0), params.get('max', 1))
        elif dist_type == 'poisson':
            return int(np.random.poisson(params.get('lambda', 1)))
        elif dist_type == 'bernoulli':
            return 1 if random.random() < params.get('p', 0.5) else 0
        return None

    # ------------------------------------------------------------------
    # Date helpers
    # ------------------------------------------------------------------
    def _generate_date_in_range(self, min_date: str, max_date: str) -> str:
        try:
            min_dt = datetime.fromisoformat(min_date.replace('Z', '+00:00'))
            max_dt = datetime.fromisoformat(max_date.replace('Z', '+00:00'))
            delta = max_dt - min_dt
            secs = max(0, int(delta.total_seconds()))
            return (min_dt + timedelta(seconds=random.randint(0, secs))).strftime('%Y-%m-%d')
        except Exception:
            return min_date

    def _random_date_between(self, start: str, end: str) -> str:
        """Generate date string between two YYYY-MM-DD dates."""
        try:
            s = datetime.strptime(start[:10], '%Y-%m-%d')
            e = datetime.strptime(end[:10], '%Y-%m-%d')
            if e <= s:
                e = s + timedelta(days=random.randint(1, 365))
            delta = (e - s).days
            return (s + timedelta(days=random.randint(0, max(delta, 1)))).strftime('%Y-%m-%d')
        except Exception:
            return start

    def _random_date_after(self, after: str, max_days: int = 365) -> str:
        try:
            d = datetime.strptime(after[:10], '%Y-%m-%d')
            return (d + timedelta(days=random.randint(1, max_days))).strftime('%Y-%m-%d')
        except Exception:
            return after

    # ------------------------------------------------------------------
    # Regex generator with faker fallback (fix #1)
    # ------------------------------------------------------------------
    def _generate_from_regex(self, pattern: Optional[str], field_name: str = '') -> str:
        fn = field_name.lower()

        # Known-pattern faker fallback (fix #1) — always use these for quality
        if _faker:
            if 'ssn' in fn:
                return _faker.ssn()
            if fn in ('phone_number_primary', 'phone_number_alternate') or 'phone' in fn:
                return _faker.numerify('###-###-####')
            if 'email' in fn:
                return _faker.email()
            if fn == 'account_number':
                return _faker.numerify('##########')
            if fn == 'transaction_amount_currency' or fn.endswith('_currency'):
                return 'USD'
            if 'address_street' in fn or fn == 'address_street_line1':
                return _faker.street_address()
            if fn == 'address_street_line2':
                return _faker.secondary_address() if random.random() < 0.3 else ''
            if fn == 'address_city':
                return _faker.city()
            if fn == 'address_state_province':
                return _faker.state_abbr()
            if fn == 'address_postal_code' or 'postal' in fn or 'zip' in fn:
                return _faker.zipcode()
            if fn == 'address_country' or fn == 'individual_country_of_birth':
                return 'US'
            if fn in ('organization_country_of_inc',):
                return 'US'
            if fn in ('organization_state_of_inc',):
                return _faker.state_abbr()
            if fn in ('organization_tax_id',):
                return _faker.numerify('##-#######')
            if fn in ('government_jurisdiction',):
                return _faker.state()
            if fn in ('government_entity_name',):
                return f"{_faker.city()} {random.choice(['Department', 'Agency', 'Office', 'Bureau'])}"
            if 'name_given' in fn or fn == 'individual_name_given':
                # Will be overridden in party post-processing for gender consistency
                return _faker.first_name()
            if 'name_family' in fn or fn == 'individual_name_family':
                return _faker.last_name()
            if 'name_middle' in fn:
                return _faker.first_name()[0] if random.random() < 0.7 else ''
            if 'name_suffix' in fn:
                return random.choice(['', '', '', 'Jr.', 'Sr.', 'III', 'IV'])
            if 'organization_legal_name' in fn:
                return _faker.company()
            if fn in ('reference_number', 'confirmation_number'):
                return _faker.bothify('??##??##??##').upper()
            if fn == 'ach_trace_number':
                return _faker.numerify('###############')
            if fn == 'wire_reference':
                return _faker.bothify('WIRE-??########').upper()
            if fn == 'transaction_description':
                return random.choice([
                    'Direct deposit', 'ATM withdrawal', 'Online transfer',
                    'POS purchase', 'Wire transfer', 'Check deposit',
                    'Payroll', 'Bill payment', 'ACH credit', 'ACH debit',
                ])
            if fn == 'transaction_status_reason':
                return random.choice(['Approved', 'Processed', 'Cleared', 'Verified', 'Authorized'])
            if fn == 'reversal_reason':
                return random.choice(['Customer request', 'Duplicate', 'Fraud', 'Error', 'Unauthorized'])
            if fn == 'orc_change_reason':
                return random.choice(['Account restructure', 'Ownership change', 'Regulatory update', 'Customer request'])
            if fn == 'gl_reconciliation_approved_by':
                return _faker.name()
            if fn == 'verification_status_reason':
                return random.choice(['Complete', 'Pending review', 'Documents received', 'Auto-verified'])
            if fn == 'risk_rating_basis':
                return random.choice(['Standard review', 'Enhanced due diligence', 'Low-risk profile', 'Geographic risk'])
            if fn == 'verification_approved_by' or fn == 'verification_reviewed_by':
                return _faker.name()
            if fn == 'address_verification_source':
                return random.choice(['USPS', 'Experian', 'LexisNexis', 'Internal'])
            if fn.startswith('identity_document_1_type') or fn.startswith('identity_document_2_type'):
                return random.choice(['Passport', 'DriversLicense', 'StateID', 'MilitaryID'])
            if fn.startswith('identity_document') and 'number' in fn:
                return _faker.bothify('??########').upper()
            if fn.startswith('identity_document') and 'file_ref' in fn:
                return f"DOC-{_faker.numerify('######')}"
            if fn == 'sanctions_screening_hit_details':
                return 'No hits found'

        # Try rstr for remaining patterns
        if _rstr and pattern:
            try:
                return _rstr.xeger(pattern)
            except Exception:
                pass

        # Last resort
        if _faker:
            return _faker.pystr(min_chars=5, max_chars=20)
        return f"val_{random.randint(1000, 9999)}"

    # ------------------------------------------------------------------
    # Post-processing: account_ownership
    # ------------------------------------------------------------------
    def _postprocess_account_ownership(self, rows: List[dict]) -> None:
        for row in rows:
            # ownership_percentage_amount: compute realistic value
            row['ownership_percentage_amount'] = round(random.uniform(10.0, 100.0), 2)

            # Temporal: effective_date <= verification_date
            eff = row.get('ownership_effective_date')
            ver = row.get('ownership_verification_date')
            if eff and ver and ver < eff:
                row['ownership_verification_date'] = self._random_date_after(eff, 90)

            # ownership_end_date/reason: only set for ended ownership
            is_ended = random.random() < 0.15  # 15% ended
            if is_ended:
                eff_date = row.get('ownership_effective_date', '2020-01-01')
                row['ownership_end_date'] = self._random_date_after(eff_date, 730)
                row['ownership_end_reason'] = random.choice(
                    ['Removal', 'Death', 'Account Closed', 'Voluntary', 'Other'])
            else:
                row['ownership_end_date'] = None
                row['ownership_end_reason'] = None

    # ------------------------------------------------------------------
    # Post-processing: party (fix #5)
    # ------------------------------------------------------------------
    def _postprocess_party(self, rows: List[dict]) -> None:
        for row in rows:
            pt = row.get('party_type')
            valid_statuses = PARTY_STATUS_BY_TYPE.get(pt, ['Active', 'Inactive'])
            current = row.get('party_status')
            if current not in valid_statuses:
                row['party_status'] = random.choice(valid_statuses)

            # address_is_usa must match address_country
            if row.get('address_country') == 'US':
                row['address_is_usa'] = True
            elif row.get('address_is_usa') in (True, 'True') and row.get('address_country') != 'US':
                row['address_country'] = 'US'

            # date_of_birth should be realistic (18-90 years ago)
            if pt == 'Individual':
                dob = row.get('individual_date_of_birth')
                if dob:
                    try:
                        dob_dt = datetime.strptime(dob[:10], '%Y-%m-%d')
                        age = (datetime.now() - dob_dt).days / 365.25
                        if age < 18 or age > 100:
                            years_ago = random.randint(18, 80)
                            new_dob = datetime.now() - timedelta(days=int(years_ago * 365.25))
                            row['individual_date_of_birth'] = new_dob.strftime('%Y-%m-%d')
                    except Exception:
                        pass

                # Gender-name consistency
                if _faker:
                    gender = row.get('individual_gender')
                    if gender == 'M':
                        row['individual_name_given'] = _faker.first_name_male()
                    elif gender == 'F':
                        row['individual_name_given'] = _faker.first_name_female()

    # ------------------------------------------------------------------
    # Post-processing: account (fix #4 temporal + fix #7 conditional)
    # ------------------------------------------------------------------
    def _postprocess_account(self, rows: List[dict]) -> None:
        for row in rows:
            open_date = row.get('account_open_date', '2020-01-01')

            # current_balance_date >= account_open_date
            cbd = row.get('current_balance_date')
            if cbd and cbd < open_date:
                row['current_balance_date'] = self._random_date_after(open_date, 365)

            # Enforce min <= current <= max balance
            mn = row.get('minimum_balance')
            mx = row.get('maximum_balance')
            cur = row.get('current_balance')
            vals = sorted([v for v in [mn, mx, cur] if v is not None])
            if len(vals) == 3:
                row['minimum_balance'] = round(vals[0], 2)
                row['current_balance'] = round(vals[1], 2)
                row['maximum_balance'] = round(vals[2], 2)

            # daily_withdrawal_limit <= monthly_withdrawal_limit
            daily = row.get('transaction_daily_withdrawal_limit')
            monthly = row.get('transaction_monthly_withdrawal_limit')
            if daily is not None and monthly is not None and daily > monthly:
                row['transaction_daily_withdrawal_limit'], row['transaction_monthly_withdrawal_limit'] = monthly, daily

            # interest_rate_percentage: generate as computed
            row['interest_rate_percentage'] = round(random.uniform(0.01, 5.0), 4)

            # Fill interest fields that were empty
            if not row.get('interest_rate_effective_date'):
                row['interest_rate_effective_date'] = self._random_date_after(open_date, 90)
            if not row.get('interest_rate_expiry_date'):
                row['interest_rate_expiry_date'] = self._random_date_after(
                    row['interest_rate_effective_date'], 730)
            if not row.get('interest_last_accrual_date'):
                row['interest_last_accrual_date'] = self._random_date_after(open_date, 365)
            if not row.get('interest_calculation_method'):
                row['interest_calculation_method'] = random.choice(['Simple', 'Compound', 'Daily'])
            if not row.get('interest_compounding_freq'):
                row['interest_compounding_freq'] = random.choice(['Daily', 'Monthly', 'Quarterly'])
            if not row.get('interest_calculation_basis'):
                row['interest_calculation_basis'] = random.choice(['360-Day', '365-Day', 'Actual'])

            # Fix #7: closed account must have close_date after open_date
            status = row.get('account_status')
            if status == 'Closed':
                close_date = self._random_date_after(open_date, 730)
                row['account_close_date'] = close_date
                # current_balance_date must be <= close_date
                row['current_balance_date'] = close_date
            else:
                row['account_close_date'] = None

            # interest dates should be after open_date
            for df in ('interest_rate_effective_date', 'interest_last_accrual_date'):
                v = row.get(df)
                if v and v < open_date:
                    row[df] = self._random_date_after(open_date, 365)
            ied = row.get('interest_rate_effective_date', open_date)
            ixd = row.get('interest_rate_expiry_date')
            if ixd and ixd <= ied:
                row['interest_rate_expiry_date'] = self._random_date_after(ied, 730)

    # ------------------------------------------------------------------
    # Post-processing: ORC flags (fix #3)
    # ------------------------------------------------------------------
    def _postprocess_orc(self, rows: List[dict]) -> None:
        for row in rows:
            orc_code = row.get('orc_code', 'Single')
            flags = ORC_FLAG_MAP.get(orc_code, ORC_FLAG_MAP['Single'])
            for flag_name, flag_value in flags.items():
                row[flag_name] = flag_value

            # Insured amount should be realistic (FDIC limit is $250,000)
            amt = row.get('orc_insured_amount_per_owner')
            if amt is not None:
                row['orc_insured_amount_per_owner'] = round(
                    min(250000, max(1000, float(amt) * 100)), 2)

            # Temporal ordering: determination <= verification <= change
            det = row.get('orc_determination_date')
            ver = row.get('orc_verification_date')
            chg = row.get('orc_change_date')
            if det:
                if ver and ver < det:
                    row['orc_verification_date'] = self._random_date_after(det, 90)
                ver = row.get('orc_verification_date') or det
                if chg and chg < det:
                    row['orc_change_date'] = self._random_date_after(det, 180)

            # determination_method should match ORC type
            orc_prefix = orc_code.split('_')[0] if '_' in orc_code else orc_code
            method_map = {
                'Trust': 'TrustDocument',
                'Government': 'RegistrationForm',
                'Business': 'RegistrationForm',
                'IRA': 'SignedAgreement',
                'Keogh': 'SignedAgreement',
            }
            if orc_prefix in method_map:
                row['orc_determination_method'] = method_map[orc_prefix]

    # ------------------------------------------------------------------
    # Post-processing: daily_account_balance (fix #6)
    # ------------------------------------------------------------------
    def _postprocess_daily_balance(self, rows: List[dict]) -> None:
        for row in rows:
            # Round all component amounts first
            for f in ('balance_opening_amount', 'balance_deposits_amount',
                       'balance_withdrawals_amount', 'balance_interest_amount',
                       'balance_fees_amount', 'balance_corrections_amount'):
                v = row.get(f)
                if v is not None:
                    row[f] = round(float(v), 2)

            # Make fees and interest more realistic relative to opening
            opening = row.get('balance_opening_amount', 0) or 0
            if opening > 0:
                row['balance_interest_amount'] = round(opening * random.uniform(0.0001, 0.005), 2)
                row['balance_fees_amount'] = round(random.uniform(0, min(50.0, opening * 0.01)), 2)
                row['balance_corrections_amount'] = round(random.uniform(-10, 10), 2)

            opening = row.get('balance_opening_amount', 0) or 0
            deposits = row.get('balance_deposits_amount', 0) or 0
            withdrawals = row.get('balance_withdrawals_amount', 0) or 0
            interest = row.get('balance_interest_amount', 0) or 0
            fees = row.get('balance_fees_amount', 0) or 0
            corrections = row.get('balance_corrections_amount', 0) or 0

            # Ensure withdrawals don't exceed available funds to avoid negative closing
            available = opening + deposits + interest + corrections
            if withdrawals + fees > available:
                withdrawals = round(available * random.uniform(0.3, 0.7), 2)
                fees = round(available * random.uniform(0.001, 0.01), 2)
                row['balance_withdrawals_amount'] = withdrawals
                row['balance_fees_amount'] = fees

            # Exact equation: closing = opening + deposits - withdrawals + interest - fees + corrections
            closing = round(opening + deposits - withdrawals + interest - fees + corrections, 2)
            row['balance_closing_amount'] = closing

            # interest_accrual_days should be integer, varying realistically
            row['interest_accrual_days'] = random.choice([28, 29, 30, 31])

            # Temporal: interest_last_accrual_date should be on or before balance_as_of_date
            bao = row.get('balance_as_of_date')
            if bao:
                row['interest_last_accrual_date'] = bao  # Accrue up to balance date
                # gl_reconciliation_approved_date should be on or after balance_as_of_date
                gra = row.get('gl_reconciliation_approved_date')
                if gra and gra < bao:
                    row['gl_reconciliation_approved_date'] = self._random_date_after(bao, 7)

    # ------------------------------------------------------------------
    # Post-processing: transaction (fix #4 + fix #7)
    # ------------------------------------------------------------------
    def _postprocess_transaction(self, rows: List[dict]) -> None:
        # Description templates keyed by full transaction type for precision
        full_desc_map = {
            'Deposit_Cash':      ['Cash deposit at branch', 'Cash deposit', 'Teller cash deposit'],
            'Deposit_Check':     ['Check deposit', 'Mobile check deposit', 'ATM check deposit'],
            'Deposit_ACH':       ['ACH direct deposit', 'Payroll deposit', 'ACH credit'],
            'Deposit_Wire':      ['Wire transfer received', 'Incoming wire', 'Wire deposit'],
            'Withdrawal_Cash':   ['ATM withdrawal', 'Cash withdrawal', 'Teller cash withdrawal'],
            'Withdrawal_Check':  ['Check payment', 'Check issued', 'Cashier check'],
            'Withdrawal_ACH':    ['ACH debit', 'ACH payment', 'Automated payment'],
            'Withdrawal_Wire':   ['Outgoing wire transfer', 'Wire payment', 'Wire remittance'],
            'Transfer_Internal': ['Internal transfer', 'Account transfer', 'Savings transfer'],
            'Transfer_External': ['External transfer', 'Bank-to-bank transfer'],
            'Fee_Service':       ['Monthly service fee', 'Account maintenance fee'],
            'Fee_Overdraft':     ['Overdraft fee', 'NSF fee'],
            'Interest_Credit':   ['Interest payment', 'Interest credit', 'Monthly interest'],
        }
        # Fallback by prefix
        desc_map = {
            'Deposit':     ['Deposit', 'Funds received'],
            'Withdrawal':  ['Withdrawal', 'Funds disbursed'],
            'Transfer':    ['Transfer', 'Funds transfer'],
            'Payment':     ['Payment', 'Bill payment'],
            'Fee':         ['Fee', 'Service charge'],
            'Interest':    ['Interest credit', 'Interest payment'],
            'ACH':         ['ACH transaction'],
            'Wire':        ['Wire transfer'],
            'Check':       ['Check transaction'],
        }
        status_reason_map = {
            'Completed': ['Processed', 'Cleared', 'Settled'],
            'Pending':   ['Awaiting clearance', 'In processing', 'Pending review'],
            'Failed':    ['Insufficient funds', 'Account frozen', 'Limit exceeded', 'Declined'],
            'Reversed':  ['Customer request', 'Duplicate', 'Fraud', 'Error'],
            'Cancelled': ['Customer cancelled', 'Timeout', 'Superseded'],
        }

        for row in rows:
            # Fix #4: transaction_time as HH:MM:SS
            row['transaction_time'] = f"{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}"

            # Fix #4: temporal ordering submitted <= posted <= settled
            base_date = row.get('transaction_date', '2020-01-01')
            submitted = base_date
            posted = self._random_date_after(submitted, 3)
            settled = self._random_date_after(posted, 5)
            row['transaction_date_submitted'] = submitted
            row['transaction_date_posted'] = posted
            row['transaction_date_settled'] = settled

            # Round transaction_amount
            amt = row.get('transaction_amount')
            if amt is not None:
                row['transaction_amount'] = round(float(amt), 2)

            # Match description to transaction_type (exact match first, then prefix)
            txn_type = row.get('transaction_type', '')
            matched_descs = full_desc_map.get(txn_type)
            if not matched_descs:
                for prefix, descs in desc_map.items():
                    if txn_type.startswith(prefix):
                        matched_descs = descs
                        break
            row['transaction_description'] = random.choice(matched_descs or ['Transaction'])

            # Match status_reason to status
            status = row.get('transaction_status', 'Completed')
            reasons = status_reason_map.get(status, ['Processed'])
            row['transaction_status_reason'] = random.choice(reasons)

            # Fix #7: reversed transaction must have reason and date
            if status == 'Reversed':
                if not row.get('reversal_reason'):
                    row['reversal_reason'] = random.choice(['Customer request', 'Duplicate', 'Fraud', 'Error'])
                if not row.get('reversal_date'):
                    row['reversal_date'] = self._random_date_after(posted, 7)
            else:
                row['reversal_reason'] = None
                row['reversal_date'] = None

            # Wire/ACH fields for matching types
            if 'Wire' in txn_type:
                if not row.get('wire_reference'):
                    row['wire_reference'] = f"WIRE-{random.randint(10000000, 99999999)}"
            if 'ACH' in txn_type:
                if not row.get('ach_trace_number'):
                    row['ach_trace_number'] = f"{random.randint(100000000000000, 999999999999999)}"

            # transaction_amount_currency must be a currency code
            row['transaction_amount_currency'] = 'USD'

    # ------------------------------------------------------------------
    # Post-processing: kyc_cip_verification (fix #7)
    # ------------------------------------------------------------------
    def _postprocess_kyc(self, rows: List[dict]) -> None:
        def _is_true(val):
            return str(val).strip().lower() in ('true', '1', 'yes')

        for row in rows:
            ver_date = self._generate_date_in_range('2020-01-01', '2025-06-30')

            # If identity NOT verified, clear doc fields
            if not _is_true(row.get('identity_verified')):
                for f in ('identity_document_1_type', 'identity_document_1_number',
                           'identity_document_1_expiry_date', 'identity_document_1_file_ref',
                           'identity_document_2_type', 'identity_document_2_number',
                           'identity_verification_score'):
                    row[f] = None

            # Fix #7: identity_verified=True -> doc fields must be set
            if _is_true(row.get('identity_verified')):
                if not row.get('identity_verification_date'):
                    row['identity_verification_date'] = ver_date
                if not row.get('identity_verification_score'):
                    row['identity_verification_score'] = round(random.uniform(70, 100), 1)
                if not row.get('identity_document_1_type'):
                    row['identity_document_1_type'] = random.choice(['Passport', 'DriversLicense', 'StateID', 'MilitaryID'])
                if not row.get('identity_document_1_number'):
                    row['identity_document_1_number'] = (_faker.bothify('??########').upper() if _faker
                                                         else f"DOC{random.randint(100000, 999999)}")
                if not row.get('identity_document_1_expiry_date'):
                    row['identity_document_1_expiry_date'] = self._random_date_after(
                        row['identity_verification_date'], 1825)
                if not row.get('identity_document_1_file_ref'):
                    row['identity_document_1_file_ref'] = f"DOC-{random.randint(100000, 999999)}"

            # address_verified=True -> date and method
            if _is_true(row.get('address_verified')):
                if not row.get('address_verification_date'):
                    row['address_verification_date'] = ver_date
                if not row.get('address_verification_method'):
                    row['address_verification_method'] = random.choice(
                        ['DocumentReview', 'DatabaseMatch', 'UtilityBill', 'BankStatement'])
                if not row.get('address_verification_source'):
                    row['address_verification_source'] = random.choice(['USPS', 'Experian', 'LexisNexis'])

            # sanctions_screening_performed=True -> all screening fields
            if _is_true(row.get('sanctions_screening_performed')):
                if not row.get('sanctions_screening_date'):
                    row['sanctions_screening_date'] = ver_date
                if not row.get('sanctions_screening_database'):
                    row['sanctions_screening_database'] = random.choice(['OFAC', 'UN_Sanctions', 'EU_Sanctions'])
                if not row.get('sanctions_screening_result'):
                    row['sanctions_screening_result'] = random.choice(['Clear', 'Clear', 'Clear', 'PotentialMatch'])

            # pep_screening_performed=True -> all fields
            if _is_true(row.get('pep_screening_performed')):
                if not row.get('pep_screening_date'):
                    row['pep_screening_date'] = ver_date
                if not row.get('pep_status'):
                    row['pep_status'] = random.choice(['NotPEP', 'NotPEP', 'NotPEP', 'PEP_Domestic'])

            # adverse_media_screening_performed=True -> all fields
            if _is_true(row.get('adverse_media_screening_performed')):
                if not row.get('adverse_media_screening_date'):
                    row['adverse_media_screening_date'] = ver_date
                if not row.get('adverse_media_screening_result'):
                    row['adverse_media_screening_result'] = random.choice(['Clear', 'Clear', 'Clear', 'FlaggedForReview'])

            # Temporal: identity_verification_date <= identity_document_1_expiry_date
            ivd = row.get('identity_verification_date')
            exp = row.get('identity_document_1_expiry_date')
            if ivd and exp and exp < ivd:
                row['identity_document_1_expiry_date'] = self._random_date_after(ivd, 1825)

            # Approved/reviewed dates must be after verification date
            anchor = ivd or ver_date
            for df in ('verification_approved_date', 'verification_reviewed_date',
                        'verification_status_date', 'risk_rating_date'):
                v = row.get(df)
                if anchor and v and v < anchor:
                    row[df] = self._random_date_after(anchor, 30)

            # risk_rating_basis should match risk_rating
            rr = row.get('risk_rating')
            if rr:
                basis_map = {
                    'Low': 'Low-risk profile',
                    'Medium': 'Standard review',
                    'High': 'Enhanced due diligence',
                    'Critical': 'Enhanced due diligence',
                }
                row['risk_rating_basis'] = basis_map.get(rr, 'Standard review')

            # verification_status must be consistent with identity_verified
            id_verified = _is_true(row.get('identity_verified'))
            vs = row.get('verification_status')
            if id_verified and vs in ('Failed', 'Expired'):
                row['verification_status'] = 'Complete'
            elif not id_verified and vs == 'Complete':
                row['verification_status'] = 'Failed'

            # verification_status_reason must match verification_status
            vs = row.get('verification_status')
            if vs:
                reason_map = {
                    'Complete': 'All checks passed',
                    'Pending': 'Pending review',
                    'Failed': 'Verification failed',
                    'Expired': 'Review period expired',
                    'InProgress': 'Under review',
                }
                row['verification_status_reason'] = reason_map.get(vs, 'Processed')

            # verification_next_review_date should be in the future relative to status_date
            vsd = row.get('verification_status_date')
            if vsd:
                row['verification_next_review_date'] = self._random_date_after(vsd, 365)

    # ------------------------------------------------------------------
    # CSV writer
    # ------------------------------------------------------------------
    def _write_csv_files(self) -> None:
        for table_name, rows in self.generated_data.items():
            if not rows:
                continue
            csv_path = self.output_dir / f"{table_name}.csv"
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = list(rows[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    row_str = {k: (str(v) if v is not None else '') for k, v in row.items()}
                    writer.writerow(row_str)
            logger.info(f"Wrote {csv_path}")


def run_pilot(distribution_spec: dict, pilot_config: dict) -> dict:
    generator = PilotGenerator(distribution_spec, pilot_config)
    manifest = generator.run()
    manifest_path = generator.output_dir / "pilot_run_manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Manifest written to {manifest_path}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description='Pilot Generator')
    parser.add_argument('distribution_spec', help='Path to distribution_spec.json')
    parser.add_argument('pilot_config', help='Path to pilot_config.json')
    parser.add_argument('--output-dir', help='Output directory')
    args = parser.parse_args()

    with open(args.distribution_spec, 'r', encoding='utf-8') as f:
        spec = json.load(f)
    with open(args.pilot_config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    if args.output_dir:
        config['output_dir'] = args.output_dir

    manifest = run_pilot(spec, config)

    print("\n" + "=" * 60)
    print("Pilot Generator Summary")
    print("=" * 60)
    print(f"Status: {manifest['status']}")
    print(f"Tables generated: {len(manifest['tables_generated'])}")
    for table, count in manifest['row_counts'].items():
        print(f"  {table}: {count}")
    if manifest['warnings']:
        print(f"Warnings ({len(manifest['warnings'])}):")
        for w in manifest['warnings']:
            print(f"  - {w}")
    print("=" * 60)


if __name__ == '__main__':
    main()
