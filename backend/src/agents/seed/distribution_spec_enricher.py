import json
import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import anthropic


SYSTEM_PROMPT = """You are a data modeling expert specializing in relational database systems.
Your job is to complete unresolved fields in a distribution specification.

For each unresolved field, determine:
1. strategy: enum, distribution, date_range, regex, constant, or computed
2. For enums: values array and weights array (must sum to 1.0)
3. For distributions: distribution type (normal, uniform, poisson, etc.) with params
4. For date_range: min and max dates
5. For regex: pattern string
6. For all: rationale explaining the choice
7. nullable_rate: probability of null (0.0-1.0) if applicable

Return ONLY valid JSON. No markdown, no commentary."""


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

    def build_user_prompt(self) -> str:
        """Build user prompt with unresolved fields - simplified for better JSON generation."""
        unresolved = self.get_unresolved_fields()
        
        # Group by table
        by_table = {}
        for item in unresolved:
            table = item['table']
            if table not in by_table:
                by_table[table] = []
            by_table[table].append(item)

        # Limit data dictionary to first 5000 chars to reduce token usage
        dd_excerpt = self.data_dictionary[:5000]

        prompt = f"""Complete distribution specs for {len(unresolved)} unresolved fields.

DATA DICTIONARY (excerpt):
{dd_excerpt}

UNRESOLVED FIELDS BY TABLE:
"""
        
        for table, fields in sorted(by_table.items()):
            prompt += f"\n{table}:\n"
            for item in fields:
                field = item['field_spec']
                prompt += f"  {item['field_name']}: {field.get('type', 'unknown')}\n"

        prompt += """
Return valid JSON with this exact structure (no markdown, no extra text):
{
  "delta_fields": [
    {"table": "name", "field": "name", "updates": {"strategy": "enum|distribution|date_range|regex|constant|computed", "values": [], "weights": [], "weight_rationale": "text", "distribution": null, "params": {}, "min": null, "max": null, "pattern": null, "nullable_rate": 0.0, "rationale": "text"}}
  ],
  "row_count_distributions": [
    {"table": "name", "distribution": "normal|uniform|poisson", "params": {}, "rationale": "text"}
  ],
  "cross_field_rules": [
    {"table": "name", "type": "sum_constraint|temporal_ordering|conditional_population", "rule": "text", "fields_involved": [], "rationale": "text"}
  ]
}

REQUIREMENTS:
- Enum weights must sum to 1.0
- Every field must have a rationale
- Use realistic distributions based on data dictionary
- Return ONLY valid JSON"""

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
        """Parse delta JSON from Claude response."""
        text = raw_text.strip()
        
        # Strip markdown fences
        if text.startswith('```json'):
            text = text[7:]
        elif text.startswith('```'):
            text = text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

        # Find JSON boundaries
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

        # 4. No delta field has strategy: null
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
        print(f"Cross-field rules added: {cross_field_rules_count}")
        print(f"Row count distributions: {row_count_count}")
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


def main():
    parser = argparse.ArgumentParser(description='Distribution Spec Enricher (Seed Agent Phase B)')
    parser.add_argument('skeleton', help='Path to distribution_spec_skeleton.json')
    parser.add_argument('data_dictionary', help='Path to data dictionary file')
    parser.add_argument('--output', default='outputs/distribution_spec_delta.json',
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
