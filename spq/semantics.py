"""
Semantics of L_SPQ.

Implements Definition 2.4 (updated model) and Definition 2.5 (truth) from
Dolgorukov, Galimullin, Gladyshev (AAMAS 2024). Every claim in the paper's
Example 2.3 (the telescope example) is reproduced by these definitions —
see tests/test_telescope.py.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Dict, FrozenSet, List, Set, Tuple

from .language import (
    And,
    Atom,
    BudgetTerm,
    C,
    CostTerm,
    E,
    Formula,
    Implies,
    K,
    LinIneq,
    Neg,
    Or,
    PropFormula,
    Query,
    Term,
)
from .model import Model


# =============================================================================
# Propositional evaluation
# =============================================================================


def p_eval(A: PropFormula, atoms_true: Set[str]) -> bool:
    """Evaluate a propositional formula A given the set of atoms true at a world."""
    from .language import _Top, PAnd, PNot, POr, PVar

    if isinstance(A, _Top):
        return True
    if isinstance(A, PVar):
        return A.name in atoms_true
    if isinstance(A, PNot):
        return not p_eval(A.inner, atoms_true)
    if isinstance(A, PAnd):
        return p_eval(A.left, atoms_true) and p_eval(A.right, atoms_true)
    if isinstance(A, POr):
        return p_eval(A.left, atoms_true) or p_eval(A.right, atoms_true)
    raise TypeError(f"Unknown propositional formula: {A!r}")


# =============================================================================
# Term evaluation
# =============================================================================


def term_value(model: Model, world: str, t: Term) -> Fraction:
    if isinstance(t, BudgetTerm):
        return model.bdg_of(t.agent, world)
    if isinstance(t, CostTerm):
        return model.cost_of(t.agent, world, t.formula)
    raise TypeError(t)


# =============================================================================
# BCS — budget constraint satisfaction (Section 2.2 of the paper)
# =============================================================================


def min_cost(model: Model, world: str, group: FrozenSet[str], A: PropFormula) -> Fraction:
    return min(model.cost_of(j, world, A) for j in group)


def share(model: Model, world: str, group: FrozenSet[str], A: PropFormula) -> Fraction:
    """BC_i(G, A) = min_{j in G} c_j(A) / |G|.

    Same for every i in G — paper's resource-distribution rule.
    """
    return min_cost(model, world, group, A) / Fraction(len(group))


def bcs(model: Model, world: str, group: FrozenSet[str], A: PropFormula) -> bool:
    """BCS(G, A) at w: every member of G can pay the share."""
    s = share(model, world, group, A)
    return all(model.bdg_of(i, world) >= s for i in group)


# =============================================================================
# Update operator (Definition 2.4)
# =============================================================================


def update(model: Model, group: FrozenSet[str], A: PropFormula) -> Model:
    """Compute M^{?A_G}: the model after a semi-public group query of A by G."""
    # 1) Filter worlds where the query is realisable.
    surviving = [w for w in model.worlds if bcs(model, w, group, A)]
    surviving_set = set(surviving)

    # Pre-compute A's truth at each surviving world.
    A_truth = {w: p_eval(A, model.atoms_at(w)) for w in surviving}

    # 2) Update relations: group members distinguish A-worlds from ¬A-worlds.
    new_rels: Dict[str, Set[Tuple[str, str]]] = {}
    for j in model.agents:
        new_pairs: Set[Tuple[str, str]] = set()
        for (w, v) in model.rels.get(j, set()):
            if w not in surviving_set or v not in surviving_set:
                continue
            if j in group:
                if A_truth[w] == A_truth[v]:
                    new_pairs.add((w, v))
            else:
                # Outsiders' relation is preserved (semi-public!).
                new_pairs.add((w, v))
        new_rels[j] = new_pairs

    # 3) Update budgets: each i in G pays the share.
    new_bdg: Dict[Tuple[str, str], Fraction] = {}
    for w in surviving:
        s = share(model, w, group, A)
        for i in model.agents:
            cur = model.bdg_of(i, w)
            new_bdg[(i, w)] = cur - s if i in group else cur

    # 4) Costs unchanged (just filter out removed worlds).
    new_cost: Dict[Tuple[str, str], Dict[PropFormula, Fraction]] = {}
    for (a, w), table in model.cost.items():
        if w in surviving_set:
            new_cost[(a, w)] = dict(table)

    # 5) Valuation restricted.
    new_val = {p: ws & surviving_set for p, ws in model.val.items()}

    actual = model.actual if (model.actual in surviving_set) else None

    return Model(
        worlds=surviving,
        agents=list(model.agents),
        rels=new_rels,
        cost=new_cost,
        bdg=new_bdg,
        val=new_val,
        actual=actual,
    )


# =============================================================================
# Reachability for common knowledge
# =============================================================================


def reachable(model: Model, start: str, group: FrozenSet[str]) -> Set[str]:
    """Reflexive transitive closure of (union over G of ~_i) starting from `start`."""
    visited = {start}
    frontier = [start]
    while frontier:
        nxt: List[str] = []
        for w in frontier:
            for i in group:
                for (x, y) in model.rels.get(i, set()):
                    if x == w and y not in visited:
                        visited.add(y)
                        nxt.append(y)
        frontier = nxt
    return visited


# =============================================================================
# Model checker
# =============================================================================


def evaluate(model: Model, world: str, phi: Formula) -> bool:
    """M, w |= phi."""
    if isinstance(phi, Atom):
        return world in model.val.get(phi.name, set())

    if isinstance(phi, Neg):
        return not evaluate(model, world, phi.inner)

    if isinstance(phi, And):
        return evaluate(model, world, phi.left) and evaluate(model, world, phi.right)

    if isinstance(phi, Or):
        return evaluate(model, world, phi.left) or evaluate(model, world, phi.right)

    if isinstance(phi, Implies):
        return (not evaluate(model, world, phi.left)) or evaluate(model, world, phi.right)

    if isinstance(phi, K):
        return all(evaluate(model, v, phi.inner) for v in model.successors(world, phi.agent))

    if isinstance(phi, E):
        return all(evaluate(model, world, K(i, phi.inner)) for i in phi.group)

    if isinstance(phi, C):
        return all(evaluate(model, v, phi.inner) for v in reachable(model, world, phi.group))

    if isinstance(phi, LinIneq):
        lhs = sum((c * term_value(model, world, t) for c, t in phi.coeffs), Fraction(0))
        return lhs >= phi.bound

    if isinstance(phi, Query):
        if not bcs(model, world, phi.group, phi.A):
            return True  # vacuously true when query is unrealisable
        return evaluate(update(model, phi.group, phi.A), world, phi.inner)

    raise TypeError(f"Unknown formula: {phi!r}")


def global_check(model: Model, phi: Formula) -> List[str]:
    """All worlds w such that M, w |= phi."""
    return [w for w in model.worlds if evaluate(model, w, phi)]
