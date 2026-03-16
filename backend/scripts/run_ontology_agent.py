#!/usr/bin/env python
"""CLI script to run the Ontology Agent."""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.ontology.ontology_agent import OntologyAgent


def main():
    parser = argparse.ArgumentParser(description='Ontology Agent: Extract schema structure from DDL')
    parser.add_argument('--ddl', default='data/schemas/01_ATOMIC_DEPOSIT_SYSTEM_DDL.sql',
                        help='Path to DDL file')
    parser.add_argument('--output', default='outputs/schema_graph.json',
                        help='Output path for schema_graph.json')

    args = parser.parse_args()

    agent = OntologyAgent()
    agent.process_ddl(args.ddl, args.output)


if __name__ == '__main__':
    main()
