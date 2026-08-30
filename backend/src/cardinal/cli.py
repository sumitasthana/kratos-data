"""Cardinal command line. One entry point, not a pile of one-off scripts.

    python -m cardinal.cli validate --spec specs/portfolio.yaml
    python -m cardinal.cli generate --spec specs/portfolio.yaml --out data
    python -m cardinal.cli dag      --spec specs/portfolio.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import emit
from .dag import BuildError, build_order
from .engine import generate
from .invariants import unenforced
from .spec import load_specs


def _validate(args: argparse.Namespace) -> int:
    bundle = load_specs(args.spec)
    try:
        order = build_order(bundle)
    except BuildError as exc:
        print(f"INVALID: {exc}")
        return 1
    print(f"OK: {len(bundle.fields)} fields, {len(bundle.events)} events, "
          f"{len(bundle.invariants)} invariants. lag-0 order resolves ({len(order)} nodes).")
    missing = unenforced(bundle.invariants)
    if missing:
        print(f"NOTE: hard invariants declared but not yet enforced: {', '.join(missing)}")
    return 0


def _dag(args: argparse.Namespace) -> int:
    bundle = load_specs(args.spec)
    try:
        order = build_order(bundle)
    except BuildError as exc:
        print(f"INVALID: {exc}")
        return 1
    print("lag-0 topological order:")
    for i, node in enumerate(order):
        print(f"  {i:2d}. {node}")
    return 0


def _generate(args: argparse.Namespace) -> int:
    bundle = load_specs(args.spec)
    if args.accounts is not None:
        bundle.portfolio.accounts = args.accounts
    if args.seed is not None:
        bundle.portfolio.seed = args.seed

    try:
        build_order(bundle)
    except BuildError as exc:
        print(f"INVALID: {exc}")
        return 1

    result = generate(bundle, ablate=args.ablate)
    spec_root = Path(args.spec).parent
    manifest = emit.write(result, args.out, spec_root)

    s = manifest
    print(f"generated {s['accounts']} accounts x {s['cycles']} cycles -> {args.out}")
    print(f"  cli events:      {s['cli_events']}")
    print(f"  rejection rate:  {s['rejection_rate']:.3%}")
    print(f"  output hash:     {s['output_hash'][:16]}...")
    if s["rejection_rate"] > 0.05:
        print("  WARNING: rejection rate above 5%. The specs contradict each other. "
              "Fix the spec, not the threshold.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cardinal")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--spec", required=True, help="path to portfolio.yaml")

    p_val = sub.add_parser("validate", parents=[common], help="load and check specs")
    p_val.set_defaults(func=_validate)

    p_dag = sub.add_parser("dag", parents=[common], help="print the resolved order")
    p_dag.set_defaults(func=_dag)

    p_gen = sub.add_parser("generate", parents=[common], help="generate a portfolio")
    p_gen.add_argument("--out", default="data", help="output directory")
    p_gen.add_argument("--accounts", type=int, default=None, help="override account count")
    p_gen.add_argument("--seed", type=int, default=None, help="override seed")
    p_gen.add_argument("--ablate", action="store_true",
                       help="disable domain handlers, to prove they do work")
    p_gen.set_defaults(func=_generate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
