import json
import argparse
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

import anthropic


SYSTEM_PROMPT = """You are a data modeling expert specializing in relational database systems.
You are part of an automated synthetic data generation pipeline.
Your job is to define HOW data should be generated — not to generate data.

You will receive:
1. A partially-resolved distribution spec skeleton (fields with strategy: null need your input)
2. A data dictionary describing the domain
3. Optional domain supplements (row count hints, generation profiles, cross-field rule hints)

Return a JSON delta containing ONLY the fields you are completing.
Do not return fields already resolved by phase_a.

CRITICAL: Return ONLY valid JSON. No markdown fences, no commentary, no extra text.
Start with { and end with }. Ensure all strings are properly quoted. Ensure all arrays and objects are properly closed.

RULES:
- All conditions use the DSL: {"field":"<n>","operator":"<op>","value":"<v>"}
  Operators: ==, !=, in, not_in, >, <, >=, <=, is_null, is_not_null
  Compound: {"all":[...]} for AND, {"any":[...]} for OR
- Enum weights must sum to 1.0
- Every weight, distribution, and nullable_rate must include a rationale
- Computed fields get strategy:"computed" with formula string — never a distribution
- nullable_rate is for random missingness only — not for conditional nulls
- composite_pk_component fields: assign strategy based on their semantic role
  (e.g. a DATE component of a PK is likely date_range, not nullable)
- Fields with schema_default in params: use the default as a hint for strategy
- Derive realistic distributions from the data dictionary context
- If domain supplements include row_count_hints or generation_profiles, use them as guidance

VALIDATION: Before returning, validate that your JSON is valid by checking:
1. All strings are enclosed in double quotes
2. All arrays are properly closed with ]
3. All objects are properly closed with }
4. No trailing commas
5. No unescaped special characters in strings"""


class DistributionSpecEnricher:
    """LLM-assisted enrichment of distribution spec skeleton (Phase B)."""

    def __init__(self, skeleton_path: str, data_dictionary_path: str):
        self.skeleton_path = skeleton_path
        self.data_dictionary_path = data_dictionary_path
        self.skeleton = None
        self.data_dictionary = None
        self.delta = None
        self.client = anthropic.Anthropic()

    def load_inputs(self) -> None:
        """Load skeleton and data dictionary."""
        with open(self.skeleton_path, 'r', encoding='utf-8') as f:
            self.skeleton = json.load(f)

        with open(self.data_dictionary_path, 'r', encoding='utf-8') as f:
            self.data_dictionary = f.read()

    def build_unresolved_skeleton(self) -> Dict[str, Any]:
        """Build skeleton with only unresolved fields, stripping phase_a fields."""
        unresolved = {
            'tables': []
        }

        for table in self.skeleton.get('tables', []):
            table_copy = {
                'name': table['name'],
                'classification': table['classification'],
                'cross_field_rules': table.get('cross_field_rules', []),
                'fields': []
            }

            # Include domain hints if present
            if 'domain_row_count_hints' in table:
                table_copy['domain_row_count_hints'] = table['domain_row_count_hints']
            if 'domain_generation_profiles' in table:
                table_copy['domain_generation_profiles'] = table['domain_generation_profiles']
            if 'domain_cross_field_rule_hints' in table:
                table_copy['domain_cross_field_rule_hints'] = table['domain_cross_field_rule_hints']

            # Only include unresolved fields
            for field in table.get('fields', []):
                if field.get('resolved_by') != 'phase_a':
                    table_copy['fields'].append(field)

            unresolved['tables'].append(table_copy)

        return unresolved

    def count_unresolved_fields(self) -> Tuple[int, int]:
        """Count resolved and unresolved fields."""
        resolved = 0
        unresolved = 0

        for table in self.skeleton.get('tables', []):
            for field in table.get('fields', []):
                if field.get('resolved_by') == 'phase_a':
                    resolved += 1
                else:
                    unresolved += 1

        return resolved, unresolved

    def get_required_cross_field_rules(self) -> List[str]:
        """Extract required cross-field rule types from domain supplements."""
        rules = set()

        # Check domain_cross_field_rule_hints in skeleton
        for table in self.skeleton.get('tables', []):
            hints = table.get('domain_cross_field_rule_hints', [])
            for hint in hints:
                if isinstance(hint, dict) and 'type' in hint:
                    rules.add(hint['type'])

        # If no hints found, use generic rules
        if not rules:
            rules = {
                'temporal_ordering',
                'sum_constraint',
                'conditional_population',
                'balance_equation',
                'consistency'
            }

        return sorted(list(rules))

    def build_user_prompt(self) -> str:
        """Build the user prompt for Claude."""
        unresolved_skeleton = self.build_unresolved_skeleton()
        resolved_count, unresolved_count = self.count_unresolved_fields()
        required_rules = self.get_required_cross_field_rules()
        supplements_provided = bool(self.skeleton.get('reference_lookups') or 
                                   self.skeleton.get('domain_row_count_hints') or
                                   self.skeleton.get('domain_generation_profiles'))

        delta_schema = """{
  "delta_fields": [
    {
      "table": "str",
      "field": "str",
      "updates": {
        "strategy": "enum|distribution|date_range|regex|conditional|computed|constant",
        "values": [],
        "weights": [],
        "weight_rationale": "str",
        "distribution": "lognormal|normal|uniform|poisson|bernoulli|discrete_uniform",
        "params": {},
        "min": null,
        "max": null,
        "pattern": "str",
        "nullable_rate": 0.0,
        "rationale": "str",
        "condition": null
      }
    }
  ],
  "row_count_distributions": [
    {
      "table": "str",
      "entries": [
        {
          "distribution": "str",
          "params": {},
          "unit": "per_parent_row",
          "bounds": [0, 100],
          "condition": null,
          "rationale": "str"
        }
      ]
    }
  ],
  "cross_field_rules": [
    {
      "table": "str",
      "rules": [
        {
          "type": "conditional_population|sum_constraint|balance_equation|consistency|mutual_exclusion|temporal_ordering|referential_alignment|computed_formula",
          "rule": "str",
          "fields_involved": [],
          "enforcement": "generator|validator",
          "source": "str"
        }
      ]
    }
  ]
}"""

        prompt = f"""<task>
Complete the distribution spec for the following unresolved fields.
Return a delta JSON per the schema below.
</task>

<skeleton_summary>
Tables: {len(self.skeleton.get('tables', []))}
Phase A resolved: {resolved_count} fields
Unresolved (your task): {unresolved_count} fields
Supplements provided: {supplements_provided}
</skeleton_summary>

<unresolved_skeleton>
{json.dumps(unresolved_skeleton, indent=2)}
</unresolved_skeleton>

<data_dictionary>
{self.data_dictionary}
</data_dictionary>

<delta_schema>
{delta_schema}
</delta_schema>

<required_cross_field_rules>
{', '.join(required_rules)}
</required_cross_field_rules>"""

        return prompt

    def call_claude(self, model_id: str = "claude-sonnet-4-20250514", max_tokens: int = 16000) -> str:
        """Call Claude API and return raw response text."""
        user_prompt = self.build_user_prompt()

        try:
            response = self.client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            )

            raw_text = response.content[0].text
            return raw_text

        except Exception as e:
            error_msg = f"Anthropic API error: {str(e)}"
            raise RuntimeError(error_msg)

    def parse_delta_json(self, raw_text: str) -> Dict[str, Any]:
        """Parse delta JSON from Claude response, stripping markdown fences."""
        # Strip markdown fences
        text = raw_text.strip()
        if text.startswith('```json'):
            text = text[7:]
        elif text.startswith('```'):
            text = text[3:]

        if text.endswith('```'):
            text = text[:-3]

        text = text.strip()

        # Try to find JSON object boundaries
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx:end_idx+1]

        try:
            delta = json.loads(text)
            return delta
        except json.JSONDecodeError as e:
            error_snippet = text[:500]
            raise ValueError(
                f"Failed to parse delta JSON: {str(e)}\n"
                f"First 500 chars: {error_snippet}"
            )

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

        # 3. All enum weights sum to ~1.0 (±0.01)
        for delta_field in delta_fields:
            if delta_field.get('updates', {}).get('strategy') == 'enum':
                weights = delta_field.get('updates', {}).get('weights', [])
                if weights:
                    total = sum(weights)
                    if not (0.99 <= total <= 1.01):
                        errors.append(
                            f"Enum weights for {delta_field.get('table')}.{delta_field.get('field')} "
                            f"sum to {total}, not ~1.0"
                        )

        # 4. cross_field_rules present and non-empty
        cross_field_rules = self.delta.get('cross_field_rules', [])
        if not cross_field_rules:
            errors.append("cross_field_rules is empty")

        # 5. row_count_distributions covers all non-derived/non-computed tables
        row_count_tables = {r.get('table') for r in self.delta.get('row_count_distributions', [])}
        for table in self.skeleton.get('tables', []):
            if table['classification'] not in ['derived', 'computed']:
                if table['name'] not in row_count_tables:
                    errors.append(f"row_count_distributions missing for table {table['name']}")

        # 6. No delta field has strategy: null
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

        cross_field_rules_count = sum(
            len(r.get('rules', []))
            for r in self.delta.get('cross_field_rules', [])
        )

        print(f"\n{'='*60}")
        print(f"Seed Agent Phase B Summary")
        print(f"{'='*60}")
        print(f"Delta fields completed: {delta_field_count}")
        print(f"Tables covered: {len(tables_covered)}")
        print(f"Cross-field rules added: {cross_field_rules_count}")
        print(f"{'='*60}\n")

    def run(self, output_path: str) -> None:
        """Execute the full pipeline."""
        self.load_inputs()

        # Call Claude
        raw_response = self.call_claude()

        # Parse delta
        self.delta = self.parse_delta_json(raw_response)

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


def enrich_skeleton(
    skeleton: dict,
    data_dictionary_path: str,
    model_id: str = "claude-sonnet-4-20250514",
    max_tokens: int = 16000
) -> dict:
    """Returns delta dict. Caller (Phase C) handles merge."""
    # Create temporary skeleton file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(skeleton, f)
        skeleton_path = f.name

    try:
        enricher = DistributionSpecEnricher(skeleton_path, data_dictionary_path)
        enricher.load_inputs()
        raw_response = enricher.call_claude(model_id, max_tokens)
        delta = enricher.parse_delta_json(raw_response)

        errors = enricher.validate_delta()
        if errors:
            raise ValueError(f"Delta validation failed: {errors}")

        return delta
    finally:
        os.unlink(skeleton_path)


def main():
    parser = argparse.ArgumentParser(description='Distribution Spec Enricher (Seed Agent Phase B)')
    parser.add_argument('skeleton', help='Path to distribution_spec_skeleton.json')
    parser.add_argument('data_dictionary', help='Path to data dictionary file')
    parser.add_argument('--output', default='distribution_spec_delta.json',
                        help='Output path for delta JSON')
    parser.add_argument('--model', default=None,
                        help='Anthropic model ID (default: env ANTHROPIC_MODEL or claude-sonnet-4-20250514)')
    parser.add_argument('--max-tokens', type=int, default=16000,
                        help='Max tokens for API call')

    args = parser.parse_args()

    model_id = args.model or os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')

    enricher = DistributionSpecEnricher(args.skeleton, args.data_dictionary)
    enricher.run(args.output)


if __name__ == '__main__':
    main()
