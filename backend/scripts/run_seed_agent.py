#!/usr/bin/env python
"""CLI script to run the Seed Agent Phase A (Distribution Spec Skeleton Builder)."""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.seed.distribution_spec_skeleton_builder import DistributionSpecSkeletonBuilder


def main():
    parser = argparse.ArgumentParser(description='Seed Agent Phase A: Build distribution spec skeleton')
    parser.add_argument('--schema', default='outputs/schema_graph.json',
                        help='Path to schema_graph.json')
    parser.add_argument('--supplements', default=None,
                        help='Path to domain_supplements.json (optional)')
    parser.add_argument('--output', default='outputs/distribution_spec_skeleton.json',
                        help='Output path for distribution_spec_skeleton.json')

    args = parser.parse_args()

    builder = DistributionSpecSkeletonBuilder(args.schema, args.supplements)
    builder.run(args.output)


if __name__ == '__main__':
    main()
