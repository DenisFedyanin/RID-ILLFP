"""
Explainable model checking.

`explain(model, world, phi)` returns a structured Step tree mirroring the
semantic definitions of L_SPQ. Each step records:

    - the formula being checked
    - the world it is checked at
    - the result (True / False)
    - the reasoning (text + arithmetic shown)
    - children for sub-evaluations

The result can be rendered as plain text (see `render_text`). LaTeX and JSON
renderers can be added without touching the trace structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import FrozenSet, List, Optional

from .language import (
    And,
    Atom,
    C,
    E,
    Formula,
    Implies,
    K,
    LinIneq,
    Neg,
    Or,
    PropFormula,
    Query,
)
from .model import Model
from .semantics import (
    bcs,
    evaluate,
    min_cost,
    p_eval,
    reachable,
    share,
    term_value,
    update,
)


@dataclass
class Step:
    """One node in an explanation tree."""

    headline: str
    world: Optional[str]
    formula: Optional[Formula]
    result: bool
    detail: List[str] = field(default_factory=list)
    children: List["Step"] = field(default_factory=list)


def explain(model: Model, world: str, phi: Formula) -> Step:
    """Build an explanation tree for `M, world |= phi`."""
    return _explain(model, world, phi)


# =============================================================================
# Core recursion
# =============================================================================


def _explain(model: Model, world: str, phi: Formula) -> Step:
    if isinstance(phi, Atom):
        result = world in model.val.get(phi.name, set())
        return Step(
            headline=_eq(model, world, phi, result),
            world=world,
            formula=phi,
            result=result,
            detail=[
                f"V({phi.name}) = {{{', '.join(sorted(model.val.get(phi.name, set())))}}}",
                f"{world} {'∈' if result else '∉'} V({phi.name})",
            ],
        )

    if isinstance(phi, Neg):
        child = _explain(model, world, phi.inner)
        return Step(
            headline=_eq(model, world, phi, not child.result),
            world=world,
            formula=phi,
            result=not child.result,
            detail=["negation"],
            children=[child],
        )

    if isinstance(phi, And):
        lc = _explain(model, world, phi.left)
        result = lc.result
        children = [lc]
        if lc.result:
            rc = _explain(model, world, phi.right)
            result = lc.result and rc.result
            children.append(rc)
        else:
            children.append(
                Step(
                    headline="(right branch short-circuited)",
                    world=world,
                    formula=phi.right,
                    result=False,
                    detail=["left conjunct is False; right branch not evaluated"],
                )
            )
        return Step(
            headline=_eq(model, world, phi, result),
            world=world,
            formula=phi,
            result=result,
            detail=["conjunction"],
            children=children,
        )

    if isinstance(phi, Or):
        lc = _explain(model, world, phi.left)
        result = lc.result
        children = [lc]
        if not lc.result:
            rc = _explain(model, world, phi.right)
            result = lc.result or rc.result
            children.append(rc)
        return Step(
            headline=_eq(model, world, phi, result),
            world=world,
            formula=phi,
            result=result,
            detail=["disjunction"],
            children=children,
        )

    if isinstance(phi, Implies):
        # phi.left -> phi.right
        lc = _explain(model, world, phi.left)
        if not lc.result:
            return Step(
                headline=_eq(model, world, phi, True),
                world=world,
                formula=phi,
                result=True,
                detail=["implication: antecedent is False, so vacuously True"],
                children=[lc],
            )
        rc = _explain(model, world, phi.right)
        return Step(
            headline=_eq(model, world, phi, rc.result),
            world=world,
            formula=phi,
            result=rc.result,
            detail=["implication: antecedent True, follow consequent"],
            children=[lc, rc],
        )

    if isinstance(phi, K):
        succs = sorted(model.successors(world, phi.agent))
        children: List[Step] = []
        result = True
        for v in succs:
            sub = _explain(model, v, phi.inner)
            children.append(sub)
            if not sub.result:
                result = False
                break  # one counterexample suffices
        return Step(
            headline=_eq(model, world, phi, result),
            world=world,
            formula=phi,
            result=result,
            detail=[
                f"~_{phi.agent}-successors of {world}: {{{', '.join(succs)}}}",
                "K_i phi holds iff phi holds at every ~_i-successor",
            ],
            children=children,
        )

    if isinstance(phi, E):
        children = []
        result = True
        for i in sorted(phi.group):
            sub = _explain(model, world, K(i, phi.inner))
            children.append(sub)
            if not sub.result:
                result = False
        return Step(
            headline=_eq(model, world, phi, result),
            world=world,
            formula=phi,
            result=result,
            detail=[f"E_G phi := /\\_{{i in G}} K_i phi for G = {{{','.join(sorted(phi.group))}}}"],
            children=children,
        )

    if isinstance(phi, C):
        reach = sorted(reachable(model, world, phi.group))
        children = []
        result = True
        for v in reach:
            sub = _explain(model, v, phi.inner)
            children.append(sub)
            if not sub.result:
                result = False
                break
        return Step(
            headline=_eq(model, world, phi, result),
            world=world,
            formula=phi,
            result=result,
            detail=[
                f"G = {{{','.join(sorted(phi.group))}}}",
                f"G-reachable from {world}: {{{', '.join(reach)}}}",
                "C_G phi holds iff phi holds at every G-reachable world",
            ],
            children=children,
        )

    if isinstance(phi, LinIneq):
        # Show the arithmetic explicitly.
        parts = []
        total = Fraction(0)
        for c, t in phi.coeffs:
            v = term_value(model, world, t)
            total += c * v
            parts.append(f"{_coef(c)}{t} = {_coef(c)}({v})")
        detail = [
            f"LHS = {' + '.join(parts)} = {total}",
            f"compare LHS ({total}) >= bound ({phi.bound}) -> {total >= phi.bound}",
        ]
        result = total >= phi.bound
        return Step(
            headline=_eq(model, world, phi, result),
            world=world,
            formula=phi,
            result=result,
            detail=detail,
        )

    if isinstance(phi, Query):
        return _explain_query(model, world, phi)

    raise TypeError(f"Cannot explain: {phi!r}")


# =============================================================================
# The interesting case: query
# =============================================================================


def _explain_query(model: Model, world: str, phi: Query) -> Step:
    A = phi.A
    G = phi.group

    children: List[Step] = []

    # Step 1: BCS check.
    bcs_step = _explain_bcs(model, world, G, A)
    children.append(bcs_step)

    if not bcs_step.result:
        return Step(
            headline=_eq(model, world, phi, True),
            world=world,
            formula=phi,
            result=True,
            detail=["BCS fails at this world; [?A_G]phi is vacuously True"],
            children=children,
        )

    # Step 2: describe the update.
    M_upd = update(model, G, A)
    detail = _describe_update(model, M_upd, G, A)
    update_step = Step(
        headline=f"compute M^{{?{A}_{{{','.join(sorted(G))}}}}}",
        world=None,
        formula=None,
        result=True,
        detail=detail,
    )
    children.append(update_step)

    # Step 3: evaluate inner in updated model.
    inner_step = _explain(M_upd, world, phi.inner)
    children.append(inner_step)

    result = inner_step.result
    return Step(
        headline=_eq(model, world, phi, result),
        world=world,
        formula=phi,
        result=result,
        children=children,
    )


def _explain_bcs(model: Model, world: str, G: FrozenSet[str], A: PropFormula) -> Step:
    detail: List[str] = []
    # min cost
    costs = [(j, model.cost_of(j, world, A)) for j in sorted(G)]
    min_j, min_c = min(costs, key=lambda kv: kv[1])
    s = min_c / Fraction(len(G))
    detail.append(
        "min_{j∈G} c_j(A) = "
        + " ; ".join(f"c_{j}({A})={c}" for j, c in costs)
        + f"  ->  min = c_{min_j}({A}) = {min_c}"
    )
    detail.append(f"share = {min_c} / |G|({len(G)}) = {s}")
    ok = True
    for i in sorted(G):
        bi = model.bdg_of(i, world)
        cmp = "≥" if bi >= s else "<"
        ok_i = bi >= s
        detail.append(f"b_{i}({world}) = {bi}  {cmp}  {s}  {'✓' if ok_i else '✗'}")
        ok = ok and ok_i
    return Step(
        headline=f"BCS({{{','.join(sorted(G))}}}, {A}) at {world}: {ok}",
        world=world,
        formula=None,
        result=ok,
        detail=detail,
    )


def _describe_update(
    M: Model, Mu: Model, G: FrozenSet[str], A: PropFormula
) -> List[str]:
    surv = set(Mu.worlds)
    dropped = [w for w in M.worlds if w not in surv]
    detail = [
        f"surviving worlds: {{{', '.join(Mu.worlds)}}}"
        + (f"   (dropped: {{{', '.join(dropped)}}} — BCS failed)" if dropped else ""),
        "for j ∈ G: ~_j now distinguishes A-worlds from ¬A-worlds",
        "for j ∉ G: ~_j unchanged (semi-public: outsiders see the query, not the answer)",
    ]
    # Budget changes
    for w in Mu.worlds:
        s = share(M, w, G, A)
        if s != 0:
            changes = []
            for i in sorted(G):
                before = M.bdg_of(i, w)
                after = Mu.bdg_of(i, w)
                changes.append(f"b_{i}({w}): {before} → {after}  (−{s})")
            detail.append("; ".join(changes))
    return detail


# =============================================================================
# Rendering
# =============================================================================


def _eq(model: Model, world: str, phi: Formula, result: bool) -> str:
    mark = "⊨" if result else "⊭"
    return f"M, {world} {mark} {phi}"


def _coef(c: Fraction) -> str:
    if c == 1:
        return ""
    if c == -1:
        return "-"
    return f"{c}*"


def render_text(step: Step, indent: int = 0) -> str:
    """Render a Step tree as a Unicode tree string."""
    return _render(step, prefix="", is_last=True, is_root=True)


def _render(step: Step, prefix: str, is_last: bool, is_root: bool) -> str:
    if is_root:
        head = step.headline
    else:
        connector = "└── " if is_last else "├── "
        head = prefix + connector + step.headline
    lines = [head]

    new_prefix = "" if is_root else prefix + ("    " if is_last else "│   ")
    for d in step.detail:
        lines.append(new_prefix + "· " + d)
    for i, ch in enumerate(step.children):
        last = i == len(step.children) - 1
        lines.append(_render(ch, new_prefix, last, False))
    return "\n".join(lines)
