"""
Command-line interface for `spq`.

    spq check   <formula>           -- evaluate at the actual world of the telescope example
    spq explain <formula>           -- same, but print the proof trace
    spq global  <formula>           -- list all worlds where the formula holds

For now CLI uses the built-in `telescope` example as the model. A YAML model
loader is on the roadmap; until then, use the Python API for custom models:

    from spq import Model, parse_formula, evaluate
    M = Model(...)
    evaluate(M, "w1", parse_formula("..."))
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .examples import telescope
from .parser import parse_formula, ParseError
from .semantics import evaluate, global_check
from .trace import explain, render_text


def _cmd_check(args: argparse.Namespace) -> int:
    M, _ = telescope()
    world = args.world or M.actual or M.worlds[0]
    try:
        phi = parse_formula(args.formula)
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 2
    result = evaluate(M, world, phi)
    mark = "⊨" if result else "⊭"
    print(f"M (telescope), {world} {mark} {phi}")
    print(f"  result: {result}")
    return 0 if result else 1


def _cmd_global(args: argparse.Namespace) -> int:
    M, _ = telescope()
    try:
        phi = parse_formula(args.formula)
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 2
    ws = global_check(M, phi)
    if ws:
        print(f"Worlds satisfying {phi}:")
        for w in ws:
            print(f"  {w}")
    else:
        print(f"No world satisfies {phi}.")
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    M, _ = telescope()
    world = args.world or M.actual or M.worlds[0]
    try:
        phi = parse_formula(args.formula)
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 2
    step = explain(M, world, phi)
    print(render_text(step))
    return 0 if step.result else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="spq",
        description="Model checker for the SPQ logic (Dolgorukov et al., AAMAS 2024)",
    )
    p.add_argument("--version", action="version", version=f"spq {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="evaluate a formula at the actual world")
    pc.add_argument("formula")
    pc.add_argument("--world", help="world to evaluate at (default: M.actual)")
    pc.set_defaults(func=_cmd_check)

    pg = sub.add_parser("global", help="list worlds satisfying a formula")
    pg.add_argument("formula")
    pg.set_defaults(func=_cmd_global)

    pe = sub.add_parser("explain", help="print a proof trace")
    pe.add_argument("formula")
    pe.add_argument("--world", help="world to evaluate at (default: M.actual)")
    pe.set_defaults(func=_cmd_explain)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
