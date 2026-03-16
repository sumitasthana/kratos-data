import re
import json
import argparse
import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict

from dotenv import load_dotenv
import anthropic

# Load environment variables from .env file
load_dotenv()


@dataclass
class Column:
    name: str
    type: str
    enum_name: Optional[str] = None
    nullable: bool = True
    default: Optional[str] = None


@dataclass
class ForeignKey:
    from_field: str
    to_table: str
    to_field: str
    nullable: bool = True


@dataclass
class CheckConstraint:
    name: str
    expression: str


@dataclass
class UniqueConstraint:
    fields: List[str]
    condition: Optional[str] = None


@dataclass
class ConditionalGroup:
    condition_field: str
    condition_value: str
    fields: List[str]


@dataclass
class Table:
    name: str
    primary_key: str | List[str]
    pk_type: str
    columns: List[Column] = field(default_factory=list)
    conditional_groups: List[ConditionalGroup] = field(default_factory=list)
    check_constraints: List[CheckConstraint] = field(default_factory=list)
    unique_constraints: List[UniqueConstraint] = field(default_factory=list)
    foreign_keys: List[ForeignKey] = field(default_factory=list)
    referenced_by: List[str] = field(default_factory=list)


class DDLParser:
    """Deterministic DDL parser for PostgreSQL DDL files."""

    def __init__(self):
        self.tables: Dict[str, Table] = {}
        self.enums: Dict[str, List[str]] = {}
        self.all_fks: List[Dict[str, Any]] = []
        self.warnings: List[str] = []

    def parse_file(self, ddl_path: str) -> None:
        """Parse a DDL file and extract schema information."""
        with open(ddl_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self._extract_enums(content)
        self._extract_tables(content)
        self._build_referenced_by()

    def _extract_enums(self, content: str) -> None:
        """Extract all CREATE TYPE ... AS ENUM statements."""
        enum_pattern = r'CREATE\s+TYPE\s+(\w+)\s+AS\s+ENUM\s*\((.*?)\);'
        matches = re.finditer(enum_pattern, content, re.DOTALL | re.IGNORECASE)

        for match in matches:
            enum_name = match.group(1)
            values_str = match.group(2)
            values = [v.strip().strip("'\"") for v in values_str.split(',')]
            values = [v for v in values if v]
            self.enums[enum_name] = values

    def _extract_tables(self, content: str) -> None:
        """Extract all CREATE TABLE statements."""
        # Split by CREATE TABLE to find all table definitions
        parts = re.split(r'CREATE\s+TABLE\s+', content, flags=re.IGNORECASE)
        
        for part in parts[1:]:  # Skip the first part (before any CREATE TABLE)
            # Extract table name and body
            match = re.match(r'(\w+)\s*\((.*)\);', part, re.DOTALL)
            if match:
                table_name = match.group(1)
                table_body = match.group(2)
                self._parse_table(table_name, table_body)

    def _parse_table(self, table_name: str, table_body: str) -> None:
        """Parse a single table definition."""
        table = Table(
            name=table_name,
            primary_key="",
            pk_type="",
            columns=[],
            conditional_groups=[],
            check_constraints=[],
            unique_constraints=[],
            foreign_keys=[],
            referenced_by=[]
        )

        lines = table_body.split('\n')
        pk_fields = []
        composite_pk = False
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            i += 1

            if not line or line.startswith('--'):
                continue

            # Strip inline comments
            if '--' in line:
                line = line[:line.index('--')].strip()

            # Parse PRIMARY KEY constraint (standalone)
            if line.upper().startswith('PRIMARY KEY'):
                pk_match = re.search(r'PRIMARY\s+KEY\s*\((.*?)\)', line, re.IGNORECASE)
                if pk_match:
                    pk_fields = [f.strip() for f in pk_match.group(1).split(',')]
                    composite_pk = len(pk_fields) > 1
                continue

            # Parse UNIQUE constraint
            if line.upper().startswith('UNIQUE'):
                unique_match = re.search(r'UNIQUE\s*\((.*?)\)', line, re.IGNORECASE)
                if unique_match:
                    fields = [f.strip() for f in unique_match.group(1).split(',')]
                    condition = None
                    if 'WHERE' in line.upper():
                        where_match = re.search(r'WHERE\s+(.*?)(?:,|$)', line, re.IGNORECASE)
                        if where_match:
                            condition = where_match.group(1).strip()
                    table.unique_constraints.append(UniqueConstraint(fields=fields, condition=condition))
                continue

            # Parse CHECK constraint (stop at CONSTRAINT keyword)
            if 'CONSTRAINT' in line.upper() and 'CHECK' in line.upper():
                check_match = re.search(r'CONSTRAINT\s+(\w+)\s+CHECK\s*\((.*?)(?:\)|,)', line, re.IGNORECASE | re.DOTALL)
                if check_match:
                    constraint_name = check_match.group(1)
                    expression = check_match.group(2).strip()
                    table.check_constraints.append(CheckConstraint(name=constraint_name, expression=expression))
                continue

            # Skip constraint/index lines that are not columns
            if any(kw in line.upper() for kw in ['CONSTRAINT', 'INDEX', 'FOREIGN']):
                continue

            # Parse column definition
            col = self._parse_column(line, table_name)
            if col:
                table.columns.append(col)
                # Check if this column has PRIMARY KEY inline
                if 'PRIMARY KEY' in line.upper() and not pk_fields:
                    pk_fields = [col.name]
                    composite_pk = False

        # Set primary key
        if pk_fields:
            table.primary_key = pk_fields[0] if len(pk_fields) == 1 else pk_fields
            table.pk_type = "composite" if composite_pk else "simple"
        else:
            # Try to find _id column as fallback
            for col in table.columns:
                if col.name.endswith('_id'):
                    table.primary_key = col.name
                    table.pk_type = "simple"
                    break

        self.tables[table_name] = table

    def _parse_column(self, line: str, table_name: str) -> Optional[Column]:
        """Parse a single column definition."""
        # Skip standalone constraint lines (not column definitions with constraints)
        line_upper = line.upper()
        if line_upper.startswith(('CONSTRAINT', 'UNIQUE', 'FOREIGN', 'INDEX', 'PRIMARY KEY')):
            return None

        # Remove trailing comma
        line = line.rstrip(',').strip()
        if not line:
            return None

        # Strip inline comments (everything after --)
        if '--' in line:
            line = line[:line.index('--')].strip()

        parts = line.split()
        if len(parts) < 2:
            return None

        col_name = parts[0]
        
        # Extract type (everything after column name until a keyword)
        type_start = len(col_name)
        type_end = len(line)
        
        # Find where the type ends (before keywords like NOT, DEFAULT, REFERENCES, etc.)
        keywords = ['NOT', 'DEFAULT', 'REFERENCES', 'CHECK', 'CONSTRAINT']
        for kw in keywords:
            idx = line.upper().find(' ' + kw + ' ')
            if idx > type_start and idx < type_end:
                type_end = idx
        
        col_type = line[type_start:type_end].strip()
        
        # Clean up type (remove extra whitespace, handle parentheses)
        col_type = re.sub(r'\s+', ' ', col_type).strip()

        nullable = True
        default = None
        enum_name = None

        # Check for NOT NULL
        if 'NOT NULL' in line.upper():
            nullable = False

        # Check for DEFAULT
        default_match = re.search(r'DEFAULT\s+([^\s,]+)', line, re.IGNORECASE)
        if default_match:
            default = default_match.group(1)

        # Check if type is an enum
        if col_type in self.enums:
            enum_name = col_type

        # Parse REFERENCES (foreign key)
        if 'REFERENCES' in line.upper():
            fk_match = re.search(r'REFERENCES\s+(\w+)\s*\(\s*(\w+)\s*\)', line, re.IGNORECASE)
            if fk_match:
                to_table = fk_match.group(1)
                to_field = fk_match.group(2)
                self.all_fks.append({
                    'from_table': table_name,
                    'from_field': col_name,
                    'to_table': to_table,
                    'to_field': to_field,
                    'nullable': nullable
                })

        return Column(
            name=col_name,
            type=col_type,
            enum_name=enum_name,
            nullable=nullable,
            default=default
        )

    def _build_referenced_by(self) -> None:
        """Build referenced_by lists for each table."""
        for fk_info in self.all_fks:
            to_table = fk_info['to_table']
            from_table = fk_info['from_table']
            if to_table in self.tables and from_table not in self.tables[to_table].referenced_by:
                self.tables[to_table].referenced_by.append(from_table)

        # Assign foreign keys to tables
        for fk_info in self.all_fks:
            from_table = fk_info['from_table']
            if from_table in self.tables:
                fk = ForeignKey(
                    from_field=fk_info['from_field'],
                    to_table=fk_info['to_table'],
                    to_field=fk_info['to_field'],
                    nullable=fk_info['nullable']
                )
                self.tables[from_table].foreign_keys.append(fk)


class OntologyAgent:
    """Agent for extracting schema graph from DDL and detecting conditional groups."""

    def __init__(self, bedrock_model: str = "anthropic.claude-sonnet-4-20250514"):
        self.bedrock_model = bedrock_model
        self.parser = DDLParser()

    async def process_ddl(self, ddl_path: str, output_path: str) -> None:
        """Process a DDL file and generate schema_graph.json."""
        # Parse DDL
        self.parser.parse_file(ddl_path)

        # Detect conditional groups using LLM
        await self._detect_conditional_groups()

        # Compute generation order
        generation_order, generation_rationale = self._compute_generation_order()

        # Validate schema
        self._validate_schema(generation_order)

        # Build output
        output = self._build_output(generation_order, generation_rationale)

        # Write output
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        print(f"Schema graph written to {output_path}")

    async def _detect_conditional_groups(self) -> None:
        """Use LLM to detect conditional groups in tables."""
        # Hardcode conditional groups for party table (most critical)
        # These are documented in the DDL and data dictionary
        party_groups = [
            ConditionalGroup(
                condition_field="party_type",
                condition_value="Individual",
                fields=[
                    "individual_name_given",
                    "individual_name_middle",
                    "individual_name_family",
                    "individual_name_suffix",
                    "individual_date_of_birth",
                    "individual_ssn",
                    "individual_country_of_birth",
                    "individual_gender"
                ]
            ),
            ConditionalGroup(
                condition_field="party_type",
                condition_value="Organization",
                fields=[
                    "organization_legal_name",
                    "organization_tax_id",
                    "organization_type",
                    "organization_country_of_inc",
                    "organization_state_of_inc"
                ]
            ),
            ConditionalGroup(
                condition_field="party_type",
                condition_value="Government",
                fields=[
                    "government_entity_name",
                    "government_entity_type",
                    "government_jurisdiction"
                ]
            )
        ]
        
        if "party" in self.parser.tables:
            self.parser.tables["party"].conditional_groups = party_groups

        # Try LLM for other tables if credentials available
        try:
            # Build a summary of tables for the LLM (excluding party which we already handled)
            table_summaries = []
            for table_name, table in self.parser.tables.items():
                if table_name == "party":
                    continue
                col_names = [col.name for col in table.columns]
                table_summaries.append(f"{table_name}: {', '.join(col_names)}")

            if not table_summaries:
                return

            prompt = f"""Analyze the following database tables and identify any conditional groups.
A conditional group is a set of columns that only apply when another column has a specific value.

Tables:
{chr(10).join(table_summaries)}

For each table, identify conditional groups in this JSON format:
{{
  "table_name": {{
    "groups": [
      {{
        "condition_field": "field_name",
        "condition_value": "value",
        "fields": ["field1", "field2"]
      }}
    ]
  }}
}}

Only include tables with conditional groups. Return valid JSON only."""

            response = await self._call_bedrock(prompt)
            conditional_data = self._parse_json_response(response)

            # Apply conditional groups to tables
            if conditional_data:
                for table_name, data in conditional_data.items():
                    if table_name in self.parser.tables and 'groups' in data:
                        for group in data['groups']:
                            self.parser.tables[table_name].conditional_groups.append(
                                ConditionalGroup(
                                    condition_field=group['condition_field'],
                                    condition_value=group['condition_value'],
                                    fields=group['fields']
                                )
                            )
        except Exception as e:
            # Graceful fallback - party table already has conditional groups
            self.parser.warnings.append(f"LLM conditional group detection unavailable: {str(e)}")

    async def _call_bedrock(self, prompt: str) -> str:
        """Call Anthropic API with the given prompt."""
        try:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            model = os.getenv('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')
            
            if not api_key:
                raise Exception("ANTHROPIC_API_KEY not set in environment")
            
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response."""
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
        return None

    def _compute_generation_order(self) -> Tuple[List[str], Dict[str, str]]:
        """Compute topological sort of tables based on FK dependencies."""
        # Build dependency graph - account to party mapping
        in_degree = {table: 0 for table in self.parser.tables}
        graph = defaultdict(list)
        rationale = {}
        self_refs = set()

        for table_name, table in self.parser.tables.items():
            for fk in table.foreign_keys:
                if fk.to_table not in in_degree:
                    continue
                # Self-referencing FKs don't create dependencies
                if fk.to_table == table_name:
                    self_refs.add(table_name)
                    continue
                # Add edge: to_table -> table_name (to_table must come before table_name)
                graph[fk.to_table].append(table_name)
                in_degree[table_name] += 1

        # Topological sort (Kahn's algorithm)
        queue = [table for table in in_degree if in_degree[table] == 0]
        order = []

        while queue:
            # Sort queue for deterministic ordering
            queue.sort()
            node = queue.pop(0)
            order.append(node)

            for neighbor in sorted(graph[node]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles (excluding self-references)
        if len(order) != len(self.parser.tables):
            # Return tables in order, with problematic ones at end
            remaining = [t for t in sorted(self.parser.tables.keys()) if t not in order]
            order.extend(remaining)
            # Identify actual circular dependencies (not self-refs)
            circular_tables = [t for t in remaining if t not in self_refs]
            if circular_tables:
                self.parser.warnings.append(f"Circular FK dependency detected in: {', '.join(circular_tables)}")

        # Build rationale
        for table in order:
            table_obj = self.parser.tables[table]
            deps = [fk.to_table for fk in table_obj.foreign_keys if fk.to_table != table]
            self_ref_fks = [fk.from_field for fk in table_obj.foreign_keys if fk.to_table == table]
            
            if deps and self_ref_fks:
                rationale[table] = f"Depends on: {', '.join(deps)}; Self-referencing: {', '.join(self_ref_fks)}"
            elif deps:
                rationale[table] = f"Depends on: {', '.join(deps)}"
            elif self_ref_fks:
                rationale[table] = f"Self-referencing: {', '.join(self_ref_fks)}"
            elif table_obj.referenced_by:
                rationale[table] = f"Referenced by: {', '.join(table_obj.referenced_by)}"
            else:
                rationale[table] = "No FK dependencies"

        return order, rationale

    def _validate_schema(self, generation_order: List[str]) -> None:
        """Validate the schema for consistency."""
        # Check all FK targets exist
        for table_name, table in self.parser.tables.items():
            for fk in table.foreign_keys:
                if fk.to_table not in self.parser.tables:
                    self.parser.warnings.append(
                        f"Table {table_name}.{fk.from_field} references non-existent table {fk.to_table}"
                    )

        # Check generation order contains all tables
        if set(generation_order) != set(self.parser.tables.keys()):
            missing = set(self.parser.tables.keys()) - set(generation_order)
            extra = set(generation_order) - set(self.parser.tables.keys())
            if missing:
                self.parser.warnings.append(f"Missing tables in generation order: {missing}")
            if extra:
                self.parser.warnings.append(f"Extra tables in generation order: {extra}")

        # Check generation order respects FK dependencies
        table_index = {table: idx for idx, table in enumerate(generation_order)}
        for table_name, table in self.parser.tables.items():
            for fk in table.foreign_keys:
                if fk.to_table in table_index:
                    if table_index[table_name] < table_index[fk.to_table]:
                        self.parser.warnings.append(
                            f"Generation order violation: {table_name} before its FK dependency {fk.to_table}"
                        )

    def _build_output(self, generation_order: List[str], generation_rationale: Dict[str, str]) -> Dict[str, Any]:
        """Build the final output structure."""
        tables_output = []
        for table_name in generation_order:
            table = self.parser.tables[table_name]
            tables_output.append({
                'name': table.name,
                'primary_key': table.primary_key,
                'pk_type': table.pk_type,
                'columns': [
                    {
                        'name': col.name,
                        'type': col.type,
                        'enum_name': col.enum_name,
                        'nullable': col.nullable,
                        'default': col.default
                    }
                    for col in table.columns
                ],
                'conditional_groups': [
                    {
                        'condition_field': cg.condition_field,
                        'condition_value': cg.condition_value,
                        'fields': cg.fields
                    }
                    for cg in table.conditional_groups
                ],
                'check_constraints': [
                    {
                        'name': cc.name,
                        'expression': cc.expression
                    }
                    for cc in table.check_constraints
                ],
                'unique_constraints': [
                    {
                        'fields': uc.fields,
                        'condition': uc.condition
                    }
                    for uc in table.unique_constraints
                ],
                'foreign_keys': [
                    {
                        'from_field': fk.from_field,
                        'to_table': fk.to_table,
                        'to_field': fk.to_field,
                        'nullable': fk.nullable
                    }
                    for fk in table.foreign_keys
                ],
                'referenced_by': table.referenced_by
            })

        return {
            'tables': tables_output,
            'enums': self.parser.enums,
            'foreign_keys': self.parser.all_fks,
            'generation_order': generation_order,
            'generation_order_rationale': generation_rationale,
            'warnings': self.parser.warnings
        }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Extract schema graph from PostgreSQL DDL')
    parser.add_argument('--ddl', required=True, help='Path to DDL file')
    parser.add_argument('--output', required=True, help='Path to output schema_graph.json')
    parser.add_argument('--model', default='anthropic.claude-sonnet-4-20250514', help='Bedrock model ID')

    args = parser.parse_args()

    agent = OntologyAgent(bedrock_model=args.model)
    await agent.process_ddl(args.ddl, args.output)


if __name__ == '__main__':
    asyncio.run(main())
