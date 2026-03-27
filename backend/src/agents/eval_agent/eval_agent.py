import os
import json
import csv
import logging
import hashlib
import argparse
import uuid
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict
import statistics

try:
    import numpy as np
except ImportError:
    np = None

try:
    import anthropic
except ImportError:
    anthropic = None

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are a data quality expert evaluating synthetic data.
You will receive sample rows from a generated table and its field spec.
Your job is to assess whether the data looks realistic and semantically correct.

You are NOT re-checking constraint rules — focus only on:
1. Realism: do values look like real-world data for this domain?
2. Anomalies: impossible values, nonsensical combinations, suspicious patterns
3. Conditional correctness: are conditional fields populated appropriately?
4. Overall quality score: integer 0-10

Return ONLY valid JSON with these exact keys:
{"quality_score": <integer 0-10>, "realism": <integer 0-10>, "anomalies": [...], "conditional_correctness": <integer 0-10>}
No markdown fences, no commentary."""


class EvalAgent:
    """Data quality evaluation agent with programmatic checks and LLM judge."""

    def __init__(self, csv_dir: str, distribution_spec: dict, eval_config: dict):
        self.csv_dir = Path(csv_dir)
        self.spec = distribution_spec
        self.config = eval_config
        
        # Parse thresholds
        self.pass_threshold = eval_config.get('pass_threshold', {})
        self.llm_judge_config = eval_config.get('llm_judge', {})
        self.skip_tables = set(eval_config.get('skip_tables', []))
        
        # Output directory
        self.output_dir = Path(
            eval_config.get('output_dir') or 
            os.getenv('EVAL_AGENT_OUTPUT_DIR', 'backend/data/outputs/eval')
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize report structure
        self.report = {
            'run_id': str(uuid.uuid4()),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'distribution_spec_hash': self._compute_spec_hash(),
            'status': 'pass',
            'pass_signal': False,
            'stages': {
                'referential_integrity': {
                    'pass_rate': 0.0,
                    'passed': False,
                    'violations': []
                },
                'cross_field_rules': {
                    'pass_rate': 0.0,
                    'passed': False,
                    'results': []
                },
                'distribution_similarity': {
                    'pass_rate': 0.0,
                    'passed': False,
                    'results': []
                },
                'llm_judge': {
                    'enabled': self.llm_judge_config.get('enabled', False),
                    'average_quality_score': 0.0,
                    'llm_quality_warning': False,
                    'table_results': []
                }
            },
            'summary': {
                'tables_evaluated': 0,
                'total_rows_evaluated': 0,
                'rules_evaluated': 0,
                'rules_passed': 0,
                'fk_violations': 0,
                'distribution_flags': 0,
                'llm_quality_warning': False
            }
        }
        
        # Load CSV data
        self.csv_data = {}
        self._load_csv_files()
        
        # Build table lookup
        self.table_map = {t['name']: t for t in self.spec.get('tables', [])}

    def _compute_spec_hash(self) -> str:
        """Compute SHA256 hash of distribution spec."""
        spec_json = json.dumps(self.spec, sort_keys=True)
        return hashlib.sha256(spec_json.encode()).hexdigest()

    def _load_csv_files(self) -> None:
        """Load all CSV files from csv_dir."""
        if not self.csv_dir.exists():
            logger.warning(f"CSV directory not found: {self.csv_dir}")
            return
        
        for csv_file in self.csv_dir.glob('*.csv'):
            table_name = csv_file.stem
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    self.csv_data[table_name] = rows
                    logger.info(f"Loaded {table_name}: {len(rows)} rows")
            except Exception as e:
                logger.warning(f"Failed to load {csv_file}: {e}")

    def run(self) -> dict:
        """Run all evaluation stages and return report."""
        try:
            logger.info("Starting Eval Agent")
            
            # Stage 1: Programmatic checks
            logger.info("Stage 1: Running programmatic checks")
            self._stage_1_referential_integrity()
            self._stage_1_cross_field_rules()
            self._stage_1_distribution_similarity()
            
            # Stage 2: LLM Judge (if enabled)
            if self.llm_judge_config.get('enabled', False):
                logger.info("Stage 2: Running LLM Judge")
                self._stage_2_llm_judge()
            
            # Aggregate summary counts across all stages
            self._aggregate_summary_counts()

            # Stage 3: Pass/Fail signal
            logger.info("Stage 3: Computing pass/fail signal")
            self._stage_3_pass_fail_signal()

            # Write report
            self._write_report()
            
            logger.info(f"Eval Agent complete. Status: {self.report['status']}")
            return self.report
        
        except Exception as e:
            logger.error("Eval Agent failed", exc_info=True)
            self.report['status'] = 'failed'
            self.report['pass_signal'] = False
            return self.report

    def _stage_1_referential_integrity(self) -> None:
        """Check referential integrity for all FK relationships."""
        logger.info("Checking referential integrity")
        
        violations = []
        total_fk_checks = 0
        total_fk_valid = 0
        
        # Iterate through tables and their FK fields
        for table_name, table in self.table_map.items():
            if table_name in self.skip_tables:
                continue
            
            # Find FK fields
            for field in table.get('fields', []):
                if field.get('strategy') != 'foreign_key':
                    continue
                
                field_name = field['name']
                
                # Infer parent table from field name
                parent_name = self._infer_parent_table(field_name)
                if not parent_name:
                    logger.warning(f"Could not infer parent table for {table_name}.{field_name}")
                    continue
                
                # Check if both tables have data
                if table_name not in self.csv_data:
                    logger.warning(f"Table {table_name} not found in CSV data")
                    continue
                
                if parent_name not in self.csv_data:
                    logger.warning(f"Parent table {parent_name} not found in CSV data")
                    continue
                
                # Get parent PK field
                parent_table = self.table_map.get(parent_name)
                if not parent_table:
                    logger.warning(f"Parent table {parent_name} not found in spec")
                    continue
                
                parent_pk = parent_table.get('primary_key')
                if not parent_pk:
                    logger.warning(f"Parent table {parent_name} has no primary_key in spec")
                    continue
                
                # Collect parent PK values
                parent_pk_values = set()
                for row in self.csv_data[parent_name]:
                    pk_val = row.get(parent_pk)
                    if pk_val:
                        parent_pk_values.add(pk_val)
                
                # Check FK values
                child_rows = self.csv_data[table_name]
                invalid_count = 0
                for row in child_rows:
                    fk_val = row.get(field_name)
                    total_fk_checks += 1
                    
                    if fk_val and fk_val not in parent_pk_values:
                        invalid_count += 1
                    elif fk_val:
                        total_fk_valid += 1
                
                if invalid_count > 0:
                    violations.append({
                        'child_table': table_name,
                        'child_field': field_name,
                        'parent_table': parent_name,
                        'parent_field': parent_pk,
                        'violation_count': invalid_count,
                        'total_count': len(child_rows)
                    })
                    self.report['summary']['fk_violations'] += invalid_count
        
        # Compute pass rate
        pass_rate = 1.0 if total_fk_checks == 0 else (total_fk_valid / total_fk_checks)
        self.report['stages']['referential_integrity']['pass_rate'] = pass_rate
        self.report['stages']['referential_integrity']['violations'] = violations
        self.report['stages']['referential_integrity']['passed'] = (
            pass_rate >= self.pass_threshold.get('referential_integrity_pass_rate', 1.0)
        )
        
        logger.info(f"Referential integrity: {pass_rate:.2%} pass rate, {len(violations)} violations")

    def _infer_parent_table(self, field_name: str) -> Optional[str]:
        """Infer parent table from FK field name."""
        # Try removing common suffixes
        for suffix in ['_id', '_key', '_ref']:
            if field_name.endswith(suffix):
                potential_parent = field_name[:-len(suffix)]
                if potential_parent in self.table_map:
                    return potential_parent
        
        # Try matching against table names directly
        for table_name in self.table_map.keys():
            if table_name in field_name:
                return table_name
        
        return None

    def _stage_1_cross_field_rules(self) -> None:
        """Evaluate cross-field rules with enforcement: validator."""
        logger.info("Checking cross-field rules")
        
        results = []
        rules_evaluated = 0
        rules_passed = 0
        
        # Debug: count rules with enforcement == validator
        validator_rules_count = 0
        all_rules_count = 0
        for table_name, table in self.table_map.items():
            for rule in table.get('cross_field_rules', []):
                all_rules_count += 1
                if rule.get('enforcement') == 'validator':
                    validator_rules_count += 1
        
        logger.info(f"Cross-field rules debug: {validator_rules_count} validator rules, {all_rules_count} total rules")
        
        # Fallback: if no validator rules found, evaluate all rules and log warning
        evaluate_all_rules = validator_rules_count == 0 and all_rules_count > 0
        if evaluate_all_rules:
            logger.warning("No enforcement tags found on cross-field rules. Evaluating ALL rules as fallback.")
        
        for table_name, table in self.table_map.items():
            if table_name in self.skip_tables or table_name not in self.csv_data:
                continue
            
            rows = self.csv_data[table_name]
            
            # Evaluate cross-field rules
            for rule in table.get('cross_field_rules', []):
                # Skip non-validator rules only if validator rules exist
                if not evaluate_all_rules and rule.get('enforcement') != 'validator':
                    continue
                
                rules_evaluated += 1
                rule_type = rule.get('type')
                violations = []
                
                if rule_type == 'temporal_ordering':
                    violations = self._check_temporal_ordering(rows, rule)
                elif rule_type == 'sum_constraint':
                    violations = self._check_sum_constraint(rows, rule)
                elif rule_type == 'balance_equation':
                    violations = self._check_balance_equation(rows, rule)
                elif rule_type == 'consistency':
                    violations = self._check_consistency(rows, rule)
                elif rule_type == 'conditional_population':
                    violations = self._check_conditional_population(rows, rule)
                elif rule_type == 'mutual_exclusion':
                    violations = self._check_mutual_exclusion(rows, rule)
                elif rule_type == 'referential_alignment':
                    violations = self._check_referential_alignment(rows, rule, table_name)
                
                passed = len(violations) == 0
                if passed:
                    rules_passed += 1
                
                results.append({
                    'table': table_name,
                    'rule_type': rule_type,
                    'rule': json.dumps(rule),
                    'passed': passed,
                    'violation_count': len(violations),
                    'total_checked': len(rows),
                    'sample_violations': violations[:5]
                })
        
        # Compute pass rate
        pass_rate = 1.0 if rules_evaluated == 0 else (rules_passed / rules_evaluated)
        self.report['stages']['cross_field_rules']['pass_rate'] = pass_rate
        self.report['stages']['cross_field_rules']['results'] = results
        self.report['stages']['cross_field_rules']['passed'] = (
            pass_rate >= self.pass_threshold.get('cross_field_rule_pass_rate', 0.95)
        )
        self.report['summary']['rules_evaluated'] = rules_evaluated
        self.report['summary']['rules_passed'] = rules_passed
        
        logger.info(f"Cross-field rules: {pass_rate:.2%} pass rate, {rules_evaluated} rules evaluated")

    def _check_temporal_ordering(self, rows: List[dict], rule: dict) -> List[str]:
        """Check temporal_ordering rule: field_a < field_b."""
        violations = []
        field_a = rule.get('field_a')
        field_b = rule.get('field_b')
        
        for i, row in enumerate(rows[:100]):  # Sample first 100 rows
            val_a = row.get(field_a)
            val_b = row.get(field_b)
            
            if val_a and val_b and val_a >= val_b:
                violations.append(f"Row {i}: {field_a}={val_a} >= {field_b}={val_b}")
        
        return violations

    def _check_sum_constraint(self, rows: List[dict], rule: dict) -> List[str]:
        """Check sum_constraint rule: grouped sum equals target."""
        violations = []
        group_by = rule.get('group_by')
        fields = rule.get('fields', [])
        target = rule.get('target')
        
        groups = defaultdict(list)
        for row in rows:
            group_key = row.get(group_by)
            if group_key:
                groups[group_key].append(row)
        
        for group_key, group_rows in groups.items():
            total = 0
            for row in group_rows:
                for field in fields:
                    try:
                        total += float(row.get(field, 0) or 0)
                    except (ValueError, TypeError):
                        pass
            
            if abs(total - target) > 0.01:
                violations.append(f"Group {group_key}: sum={total}, expected={target}")
        
        return violations[:5]

    def _check_balance_equation(self, rows: List[dict], rule: dict) -> List[str]:
        """Check balance_equation rule: LHS sum equals RHS field."""
        violations = []
        lhs_fields = rule.get('lhs_fields', [])
        rhs_field = rule.get('rhs_field')
        
        for i, row in enumerate(rows[:100]):
            lhs_sum = 0
            for field in lhs_fields:
                try:
                    lhs_sum += float(row.get(field, 0) or 0)
                except (ValueError, TypeError):
                    pass
            
            try:
                rhs_val = float(row.get(rhs_field, 0) or 0)
            except (ValueError, TypeError):
                continue
            
            if abs(lhs_sum - rhs_val) > 0.01:
                violations.append(f"Row {i}: LHS sum={lhs_sum}, RHS={rhs_val}")
        
        return violations

    def _check_consistency(self, rows: List[dict], rule: dict) -> List[str]:
        """Check consistency rule: derived boolean flags match source."""
        violations = []
        source_field = rule.get('source_field')
        derived_field = rule.get('derived_field')
        
        for i, row in enumerate(rows[:100]):
            source_val = row.get(source_field)
            derived_val = row.get(derived_field)
            
            if source_val and derived_val and str(source_val).lower() != str(derived_val).lower():
                violations.append(f"Row {i}: {source_field}={source_val}, {derived_field}={derived_val}")
        
        return violations

    def _check_conditional_population(self, rows: List[dict], rule: dict) -> List[str]:
        """Check conditional_population: field null when condition false."""
        violations = []
        field = rule.get('field')
        condition = rule.get('condition')
        
        for i, row in enumerate(rows[:100]):
            # Evaluate condition (simplified)
            cond_field = condition.get('field')
            cond_value = condition.get('value')
            row_cond_val = row.get(cond_field)
            
            field_val = row.get(field)
            
            if row_cond_val == cond_value and not field_val:
                violations.append(f"Row {i}: condition true but {field} is null")
            elif row_cond_val != cond_value and field_val:
                violations.append(f"Row {i}: condition false but {field} is non-null")
        
        return violations

    def _check_mutual_exclusion(self, rows: List[dict], rule: dict) -> List[str]:
        """Check mutual_exclusion: only one of N fields is non-null."""
        violations = []
        fields = rule.get('fields', [])
        
        for i, row in enumerate(rows[:100]):
            non_null_count = sum(1 for f in fields if row.get(f))
            
            if non_null_count > 1:
                violations.append(f"Row {i}: {non_null_count} fields non-null, expected 1")
        
        return violations

    def _check_referential_alignment(self, rows: List[dict], rule: dict, table_name: str) -> List[str]:
        """Check referential_alignment: cross-table value match."""
        violations = []
        local_field = rule.get('local_field')
        ref_table = rule.get('ref_table')
        ref_field = rule.get('ref_field')
        
        if ref_table not in self.csv_data:
            logger.warning(f"Reference table {ref_table} not found for alignment check")
            return violations
        
        # Build reference values
        ref_values = {}
        for row in self.csv_data[ref_table]:
            ref_values[row.get(ref_field)] = row
        
        for i, row in enumerate(rows[:100]):
            local_val = row.get(local_field)
            if local_val and local_val not in ref_values:
                violations.append(f"Row {i}: {local_field}={local_val} not found in {ref_table}.{ref_field}")
        
        return violations

    def _stage_1_distribution_similarity(self) -> None:
        """Check distribution similarity for numeric and enum fields.
        
        Issue 2 — Lognormal Parameterization:
        - numpy.random.lognormal(mean, sigma) expects LOG-SPACE mean (μ)
        - If spec param is named "mean" treat it as log-space μ
        - If spec param is named "actual_mean" convert: μ = log(actual_mean)
        """
        logger.info("Checking distribution similarity")
        
        results = []
        flags = 0
        
        for table_name, table in self.table_map.items():
            if table_name in self.skip_tables or table_name not in self.csv_data:
                continue
            
            rows = self.csv_data[table_name]
            
            for field in table.get('fields', []):
                strategy = field.get('strategy')
                field_name = field['name']
                
                if strategy == 'distribution':
                    # Numeric distribution check
                    dist_type = field.get('distribution')
                    params = field.get('params', {})

                    values = []
                    null_count = 0
                    for row in rows:
                        val = row.get(field_name)
                        if val:
                            try:
                                values.append(float(val))
                            except (ValueError, TypeError):
                                pass
                        else:
                            null_count += 1

                    if values:
                        actual_mean = statistics.mean(values)
                        actual_std = statistics.stdev(values) if len(values) > 1 else 0
                        actual_min = min(values)
                        actual_max = max(values)

                        if dist_type == 'lognormal':
                            # Lognormal: compare in log-space
                            # Spec should have mu/sigma (log-space). Fall back to mean/std_dev for old specs.
                            expected_mu = params.get('mu', params.get('mean', 0))
                            expected_sigma = params.get('sigma', params.get('std_dev', 1))

                            # Compute actual log-space statistics
                            positive_values = [v for v in values if v > 0]
                            if positive_values and np:
                                log_values = [np.log(v) for v in positive_values]
                                actual_log_mean = statistics.mean(log_values)
                                actual_log_std = statistics.stdev(log_values) if len(log_values) > 1 else 0

                                mean_deviation = abs(actual_log_mean - expected_mu) / abs(expected_mu) if expected_mu != 0 else 0
                                flagged = mean_deviation > 0.20

                                logger.info(
                                    f"Lognormal {table_name}.{field_name}: "
                                    f"spec mu={expected_mu} sigma={expected_sigma}, "
                                    f"actual log-mean={actual_log_mean:.3f} log-std={actual_log_std:.3f}, "
                                    f"deviation={mean_deviation:.3f}"
                                )
                            else:
                                mean_deviation = 0.0
                                flagged = False
                                actual_log_mean = None
                                actual_log_std = None

                            if flagged:
                                flags += 1

                            results.append({
                                'table': table_name,
                                'field': field_name,
                                'strategy': strategy,
                                'distribution_type': dist_type,
                                'expected': {
                                    'distribution': dist_type,
                                    'mu': expected_mu,
                                    'sigma': expected_sigma,
                                    'params': params
                                },
                                'actual': {
                                    'mean': actual_mean,
                                    'std': actual_std,
                                    'log_mean': actual_log_mean,
                                    'log_std': actual_log_std,
                                    'min': actual_min,
                                    'max': actual_max,
                                    'null_count': null_count
                                },
                                'deviation': mean_deviation,
                                'flagged': flagged
                            })
                        else:
                            # Non-lognormal distributions: compare actual-space mean
                            expected_mean = params.get('mean', 0)

                            mean_deviation = abs(actual_mean - expected_mean) / abs(expected_mean) if expected_mean != 0 else 0
                            flagged = mean_deviation > 0.20

                            if flagged:
                                flags += 1

                            results.append({
                                'table': table_name,
                                'field': field_name,
                                'strategy': strategy,
                                'distribution_type': dist_type,
                                'expected': {
                                    'distribution': dist_type,
                                    'mean': expected_mean,
                                    'params': params
                                },
                                'actual': {
                                    'mean': actual_mean,
                                    'std': actual_std,
                                    'min': actual_min,
                                    'max': actual_max,
                                    'null_count': null_count
                                },
                                'deviation': mean_deviation,
                                'flagged': flagged
                            })
                
                elif strategy == 'enum':
                    # Enum distribution check
                    values = field.get('values', [])
                    weights = field.get('weights')

                    if not values:
                        continue

                    # If weights is null/None, skip flagging entirely
                    if weights is None:
                        results.append({
                            'table': table_name,
                            'field': field_name,
                            'strategy': strategy,
                            'distribution_type': 'enum',
                            'expected': {'values': values, 'weights': None},
                            'actual': {},
                            'deviation': None,
                            'flagged': False,
                            'note': 'weights not specified in spec'
                        })
                        continue

                    # Count actual values
                    value_counts = defaultdict(int)
                    for row in rows:
                        val = row.get(field_name)
                        if val:
                            value_counts[val] += 1

                    total = sum(value_counts.values())
                    if total == 0:
                        continue

                    # Compare against expected weights
                    flagged = False
                    for val in values:
                        expected_weight = weights.get(val, 1.0 / len(values)) if isinstance(weights, dict) else 1.0 / len(values)
                        actual_weight = value_counts.get(val, 0) / total

                        if abs(actual_weight - expected_weight) > 0.15:
                            flagged = True
                            break

                    if flagged:
                        flags += 1

                    results.append({
                        'table': table_name,
                        'field': field_name,
                        'strategy': strategy,
                        'distribution_type': 'enum',
                        'expected': {'values': values, 'weights': weights},
                        'actual': dict(value_counts),
                        'deviation': 0.0,
                        'flagged': flagged
                    })
        
        # Compute pass rate
        pass_rate = 1.0 - (flags / len(results)) if results else 1.0
        self.report['stages']['distribution_similarity']['pass_rate'] = pass_rate
        self.report['stages']['distribution_similarity']['results'] = results
        self.report['stages']['distribution_similarity']['passed'] = (
            pass_rate >= self.pass_threshold.get('distribution_similarity_threshold', 0.80)
        )
        self.report['summary']['distribution_flags'] = flags
        
        logger.info(f"Distribution similarity: {pass_rate:.2%} pass rate, {flags} flags, {len(results)} fields evaluated")

    def _stage_2_llm_judge(self) -> None:
        """Run LLM judge evaluation on sampled rows."""
        if not anthropic:
            logger.error("anthropic library not available, skipping LLM judge")
            self.report['stages']['llm_judge']['table_results'].append({
                'error': 'anthropic library not installed',
                'warning': 'LLM judge skipped entirely — install anthropic package'
            })
            return

        logger.info("Running LLM Judge")

        try:
            client = anthropic.Anthropic()
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}", exc_info=True)
            self.report['stages']['llm_judge']['table_results'].append({
                'error': f'Anthropic client init failed: {e}',
                'warning': 'LLM judge skipped — check ANTHROPIC_API_KEY'
            })
            return

        model = os.getenv('ANTHROPIC_MODEL', self.llm_judge_config.get('model', 'claude-sonnet-4-20250514'))
        sample_size = self.llm_judge_config.get('sample_size_per_table', 20)

        table_results = []
        quality_scores = []
        tables_attempted = 0
        tables_failed = 0

        for table_name, table in self.table_map.items():
            if table_name in self.skip_tables or table_name not in self.csv_data:
                continue

            rows = self.csv_data[table_name]
            if not rows:
                continue

            tables_attempted += 1

            # Sample rows
            sample_rows = random.sample(rows, min(sample_size, len(rows)))

            # Build prompt
            field_descriptions = []
            for field in table.get('fields', []):
                nullable_rate = field.get('nullable_rate', 0)
                nullable = (nullable_rate or 0) > 0
                field_descriptions.append({
                    'name': field['name'],
                    'strategy': field.get('strategy'),
                    'nullable': nullable
                })

            user_prompt = f"""
Evaluate the quality of these {len(sample_rows)} sampled rows from table '{table_name}'.

Field specifications:
{json.dumps(field_descriptions, indent=2)}

Sample rows:
{json.dumps(sample_rows, indent=2)}

Assess:
1. Realism: do values look like real-world data?
2. Anomalies: impossible values, nonsensical combinations?
3. Conditional correctness: are conditional fields populated appropriately?
4. Quality score: 0-10

Return JSON only.
"""

            try:
                logger.info(f"LLM Judge: calling API for table '{table_name}' ({len(sample_rows)} sample rows)")
                response = client.messages.create(
                    model=model,
                    max_tokens=4000,
                    system=JUDGE_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}]
                )

                # Parse response — strip markdown fences if present
                response_text = response.content[0].text.strip()
                if response_text.startswith('```'):
                    # Remove ```json ... ``` wrapper
                    lines = response_text.split('\n')
                    if lines[0].startswith('```'):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == '```':
                        lines = lines[:-1]
                    response_text = '\n'.join(lines)
                logger.info(f"LLM Judge: raw response for {table_name} ({len(response_text)} chars)")

                try:
                    judge_result = json.loads(response_text)
                except json.JSONDecodeError as parse_err:
                    logger.error(f"LLM Judge: JSON parse failed for {table_name}: {parse_err}\nRaw response: {response_text[:500]}")
                    tables_failed += 1
                    table_results.append({
                        'table': table_name,
                        'error': f'JSON parse failed: {parse_err}',
                        'raw_response_preview': response_text[:500],
                        'quality_score': None
                    })
                    continue

                judge_result['table'] = table_name
                table_results.append(judge_result)

                # Extract quality score — LLM may use different key names
                quality_score = (
                    judge_result.get('quality_score')
                    or judge_result.get('overall_quality_score')
                    or judge_result.get('overall_quality')
                    or judge_result.get('overall_score')
                )
                if quality_score is not None:
                    try:
                        quality_scores.append(int(quality_score))
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid quality_score for {table_name}: {quality_score}")

                logger.info(f"LLM Judge for {table_name}: quality_score={quality_score}")

            except Exception as e:
                tables_failed += 1
                logger.error(f"LLM Judge API call failed for {table_name}: {e}", exc_info=True)
                table_results.append({
                    'table': table_name,
                    'error': str(e),
                    'quality_score': None,
                    'warning': f'LLM judge call failed for {table_name} — results incomplete'
                })

        # Warn if no tables were successfully judged
        if tables_attempted > 0 and len(quality_scores) == 0:
            logger.error(f"LLM Judge: all {tables_attempted} table calls failed — no quality scores produced")
        elif tables_failed > 0:
            logger.warning(f"LLM Judge: {tables_failed}/{tables_attempted} tables failed")

        logger.info(f"LLM Judge: {tables_attempted} attempted, {len(quality_scores)} scored, {tables_failed} failed")

        # Compute average quality score
        avg_quality = statistics.mean(quality_scores) if quality_scores else 0.0

        self.report['stages']['llm_judge']['table_results'] = table_results
        self.report['stages']['llm_judge']['average_quality_score'] = avg_quality
        self.report['stages']['llm_judge']['tables_attempted'] = tables_attempted
        self.report['stages']['llm_judge']['tables_failed'] = tables_failed
        self.report['stages']['llm_judge']['llm_quality_warning'] = (
            avg_quality < 6.0 if quality_scores else tables_attempted > 0
        )
        self.report['summary']['llm_quality_warning'] = (
            avg_quality < 6.0 if quality_scores else tables_attempted > 0
        )

        logger.info(f"LLM Judge complete: average quality score = {avg_quality:.1f}")

    def _aggregate_summary_counts(self) -> None:
        """Aggregate tables_evaluated and total_rows_evaluated across all stages."""
        tables_seen = set()
        total_rows = 0

        # From referential integrity: any table that was checked
        for table_name in self.table_map:
            if table_name in self.skip_tables:
                continue
            if table_name in self.csv_data:
                tables_seen.add(table_name)
                total_rows += len(self.csv_data[table_name])

        self.report['summary']['tables_evaluated'] = len(tables_seen)
        self.report['summary']['total_rows_evaluated'] = total_rows

        logger.info(f"Summary: {len(tables_seen)} tables evaluated, {total_rows} total rows")

    def _stage_3_pass_fail_signal(self) -> None:
        """Compute overall pass/fail signal from thresholds."""
        ri_passed = self.report['stages']['referential_integrity']['passed']
        cf_passed = self.report['stages']['cross_field_rules']['passed']
        ds_passed = self.report['stages']['distribution_similarity']['passed']
        
        self.report['pass_signal'] = ri_passed and cf_passed and ds_passed
        self.report['status'] = 'pass' if self.report['pass_signal'] else 'fail'
        
        logger.info(f"Pass/Fail signal: {self.report['pass_signal']}")

    def _write_report(self) -> None:
        """Write evaluation report to JSON file."""
        report_path = self.output_dir / 'eval_report.json'

        class NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                if np and isinstance(obj, (np.bool_, np.integer)):
                    return int(obj)
                if np and isinstance(obj, np.floating):
                    return float(obj)
                if np and isinstance(obj, np.ndarray):
                    return obj.tolist()
                return super().default(obj)

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2, cls=NumpyEncoder)
        logger.info(f"Report written to {report_path}")


def run_eval(csv_dir: str, distribution_spec: dict, eval_config: dict) -> dict:
    """Run evaluation and return report."""
    agent = EvalAgent(csv_dir, distribution_spec, eval_config)
    return agent.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Eval Agent for data quality evaluation')
    parser.add_argument('csv_dir', help='Directory containing generated CSV files')
    parser.add_argument('distribution_spec_path', help='Path to distribution_spec.json')
    parser.add_argument('--config', help='Path to eval_config.json')
    parser.add_argument('--output', help='Path to output report')
    
    args = parser.parse_args()
    
    # Load distribution spec
    with open(args.distribution_spec_path, 'r', encoding='utf-8') as f:
        distribution_spec = json.load(f)
    
    # Load eval config
    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            eval_config = json.load(f)
    else:
        eval_config = {
            'pass_threshold': {
                'referential_integrity_pass_rate': 1.0,
                'cross_field_rule_pass_rate': 0.95,
                'distribution_similarity_threshold': 0.80
            },
            'llm_judge': {'enabled': False},
            'skip_tables': []
        }
    
    # Run evaluation
    report = run_eval(args.csv_dir, distribution_spec, eval_config)
    
    # Output report
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f"Report written to {args.output}")
    else:
        print(json.dumps(report, indent=2))
