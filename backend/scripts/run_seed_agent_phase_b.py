#!/usr/bin/env python
"""CLI script to run the Seed Agent Phase B (Distribution Spec Enricher)."""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.seed.distribution_spec_enricher import DistributionSpecEnricher


def main():
    parser = argparse.ArgumentParser(description='Seed Agent Phase B: LLM enrichment of distribution spec')
    parser.add_argument('skeleton', help='Path to distribution_spec_skeleton.json')
    parser.add_argument('data_dictionary', help='Path to data dictionary file')
    parser.add_argument('--output', default='outputs/distribution_spec_delta.json',
                        help='Output path for delta JSON')
    parser.add_argument('--model', default=None,
                        help='Anthropic model ID (default: env ANTHROPIC_MODEL or claude-sonnet-4-20250514)')
    parser.add_argument('--max-tokens', type=int, default=16000,
                        help='Max tokens for API call')

    args = parser.parse_args()

    enricher = DistributionSpecEnricher(args.skeleton, args.data_dictionary)
    enricher.run(args.output)


if __name__ == '__main__':
    main()
