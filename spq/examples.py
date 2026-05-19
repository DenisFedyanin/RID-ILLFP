"""
Worked examples from the paper, as Python factory functions.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Tuple

from .language import PVar
from .model import Model


def telescope() -> Tuple[Model, PVar]:
    """
    Example 2.3 / Figure 1 of Dolgorukov, Galimullin, Gladyshev (AAMAS 2024).

    Three countries (agents) n, m, l want to learn the truth-value of p.
    Telescope (one query about p) costs c_n(p)=30, c_m(p)=20, c_l(p)=30.
    Budgets:  b_n=15, b_l=5 everywhere; b_m ∈ {10, 9}.

    Worlds:
        w1: p,  b_m=10        (actual world)
        w2: ~p, b_m=10
        w3: p,  b_m=9
        w4: ~p, b_m=9

    Epistemic structure:
        n and m know each other's budgets and l's budget   -> relate
            only worlds with the same b_m: {w1,w2} and {w3,w4}.
        l does not know b_m and does not know p            -> relates all
            four worlds (total relation).

    Returns the model and the propositional atom `p` for convenience.
    """
    p = PVar("p")
    worlds = ["w1", "w2", "w3", "w4"]
    agents = ["n", "m", "l"]

    val = {"p": {"w1", "w3"}}

    bdg = {}
    for w in worlds:
        bdg[("n", w)] = Fraction(15)
        bdg[("l", w)] = Fraction(5)
    bdg[("m", "w1")] = Fraction(10)
    bdg[("m", "w2")] = Fraction(10)
    bdg[("m", "w3")] = Fraction(9)
    bdg[("m", "w4")] = Fraction(9)

    cost = {}
    for w in worlds:
        cost[("n", w)] = {p: Fraction(30)}
        cost[("m", w)] = {p: Fraction(20)}
        cost[("l", w)] = {p: Fraction(30)}

    nm_pairs = Model.equivalence_from_partition([["w1", "w2"], ["w3", "w4"]])
    l_pairs = Model.total_relation(worlds)

    rels = {
        "n": set(nm_pairs),
        "m": set(nm_pairs),
        "l": set(l_pairs),
    }

    return (
        Model(
            worlds=worlds,
            agents=agents,
            rels=rels,
            cost=cost,
            bdg=bdg,
            val=val,
            actual="w1",
        ),
        p,
    )
