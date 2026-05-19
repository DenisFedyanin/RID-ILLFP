"""
Kripke-style model with Cost and Bdg functions (Definition 2.2).

A Model is intentionally mutable as a builder, then frozen at use time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .language import PropFormula, _Top, p_similar


@dataclass
class Model:
    worlds: List[str]
    agents: List[str]
    # rels[agent] = set of (w, v) pairs, must be an equivalence relation.
    rels: Dict[str, Set[Tuple[str, str]]]
    # cost[(agent, world)][A] = c_i(w, A)
    cost: Dict[Tuple[str, str], Dict[PropFormula, Fraction]]
    # bdg[(agent, world)] = b_i(w)
    bdg: Dict[Tuple[str, str], Fraction]
    # val[atom_name] = set of worlds where that atom is true
    val: Dict[str, Set[str]]
    # The "actual" world (optional but useful for examples).
    actual: Optional[str] = None

    # ---- Cost lookup respecting C1 (Cost_i(w, top)=0) and C2 (A~~B) -----

    def cost_of(self, agent: str, world: str, A: PropFormula) -> Fraction:
        if isinstance(A, _Top):
            return Fraction(0)
        table = self.cost.get((agent, world), {})
        if A in table:
            return table[A]
        for B, c in table.items():
            if p_similar(A, B):
                return c
        return Fraction(0)

    def bdg_of(self, agent: str, world: str) -> Fraction:
        return self.bdg.get((agent, world), Fraction(0))

    def atoms_at(self, world: str) -> Set[str]:
        return {p for p, ws in self.val.items() if world in ws}

    def successors(self, world: str, agent: str) -> Set[str]:
        return {v for (w, v) in self.rels.get(agent, set()) if w == world}

    # ---- Builder helpers ------------------------------------------------

    @staticmethod
    def total_relation(worlds: Iterable[str]) -> Set[Tuple[str, str]]:
        ws = list(worlds)
        return {(w, v) for w in ws for v in ws}

    @staticmethod
    def equivalence_from_partition(partition: List[List[str]]) -> Set[Tuple[str, str]]:
        """Build an equivalence relation from a list of equivalence classes.

        Each class is a list of worlds that should all be related to each other.
        Worlds not in any class are only reflexively related to themselves.
        """
        pairs: Set[Tuple[str, str]] = set()
        for cls in partition:
            for w in cls:
                for v in cls:
                    pairs.add((w, v))
        return pairs
