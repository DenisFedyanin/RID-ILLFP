"""
Abstract syntax for L_PL (propositional fragment) and L_SPQ
(epistemic logic of semi-public queries).

Notation follows Dolgorukov, Galimullin, Gladyshev, "Dynamic Epistemic
Logic of Resource Bounded Information Mining Agents" (AAMAS 2024).

All AST nodes are frozen dataclasses so they hash and equate structurally.
Their __repr__ produces ASCII the parser can round-trip.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import FrozenSet, Tuple, Union


# =============================================================================
# L_PL — propositional formulas
# =============================================================================


class PropFormula:
    """Base class for propositional formulas A in L_PL."""

    __slots__ = ()


@dataclass(frozen=True)
class PVar(PropFormula):
    name: str

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class PNot(PropFormula):
    inner: PropFormula

    def __repr__(self) -> str:
        return f"~{self.inner}"


@dataclass(frozen=True)
class PAnd(PropFormula):
    left: PropFormula
    right: PropFormula

    def __repr__(self) -> str:
        return f"({self.left} & {self.right})"


@dataclass(frozen=True)
class POr(PropFormula):
    left: PropFormula
    right: PropFormula

    def __repr__(self) -> str:
        return f"({self.left} | {self.right})"


class _Top(PropFormula):
    """Propositional truth constant."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "top"

    def __hash__(self) -> int:
        return hash("PL_TOP")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Top)


TOP = _Top()


def p_similar(A: PropFormula, B: PropFormula) -> bool:
    """A ≈ B per Definition C2: A ≡ B or A ≡ ¬B (classical equivalence).

    Sound (but incomplete) syntactic approximation: handles identity,
    a single layer of outer negation, and double-negation.
    """
    if A == B:
        return True
    if isinstance(A, PNot) and A.inner == B:
        return True
    if isinstance(B, PNot) and B.inner == A:
        return True
    if isinstance(A, PNot) and isinstance(B, PNot):
        return p_similar(A.inner, B.inner)
    return False


# =============================================================================
# Terms (occur inside linear inequalities)
# =============================================================================


@dataclass(frozen=True)
class BudgetTerm:
    """b_i — budget of agent i."""

    agent: str

    def __repr__(self) -> str:
        return f"b_{self.agent}"


@dataclass(frozen=True)
class CostTerm:
    """c_i(A) — cost of querying A for agent i."""

    agent: str
    formula: PropFormula

    def __repr__(self) -> str:
        return f"c_{self.agent}({self.formula})"


Term = Union[BudgetTerm, CostTerm]


# =============================================================================
# L_SPQ — the main language
# =============================================================================


class Formula:
    """Base class for L_SPQ formulas."""

    __slots__ = ()


@dataclass(frozen=True)
class Atom(Formula):
    name: str

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Neg(Formula):
    inner: Formula

    def __repr__(self) -> str:
        return f"~{self.inner}"


@dataclass(frozen=True)
class And(Formula):
    left: Formula
    right: Formula

    def __repr__(self) -> str:
        return f"({self.left} & {self.right})"


@dataclass(frozen=True)
class Or(Formula):
    left: Formula
    right: Formula

    def __repr__(self) -> str:
        return f"({self.left} | {self.right})"


@dataclass(frozen=True)
class Implies(Formula):
    left: Formula
    right: Formula

    def __repr__(self) -> str:
        return f"({self.left} -> {self.right})"


@dataclass(frozen=True)
class K(Formula):
    """K_i phi — agent i knows phi."""

    agent: str
    inner: Formula

    def __repr__(self) -> str:
        return f"K_{self.agent} {self.inner}"


@dataclass(frozen=True)
class E(Formula):
    """E_G phi := /\\ K_i phi for i in G."""

    group: FrozenSet[str]
    inner: Formula

    def __repr__(self) -> str:
        return f"E_{{{','.join(sorted(self.group))}}} {self.inner}"


@dataclass(frozen=True)
class C(Formula):
    """C_G phi — common knowledge of phi among group G."""

    group: FrozenSet[str]
    inner: Formula

    def __repr__(self) -> str:
        return f"C_{{{','.join(sorted(self.group))}}} {self.inner}"


@dataclass(frozen=True)
class Query(Formula):
    """[?A_G] phi — after G's semi-public query whether A, phi holds.

    A must be a propositional formula (L_PL) per the paper.
    """

    A: PropFormula
    group: FrozenSet[str]
    inner: Formula

    def __repr__(self) -> str:
        g = ",".join(sorted(self.group))
        return f"[?{self.A}_{{{g}}}] {self.inner}"


@dataclass(frozen=True)
class LinIneq(Formula):
    """Sum_k (coeff_k * term_k) >= bound  (linear inequality over Terms)."""

    coeffs: Tuple[Tuple[Fraction, Term], ...]
    bound: Fraction

    def __repr__(self) -> str:
        parts = []
        for c, t in self.coeffs:
            if c == 1:
                parts.append(f"{t}")
            elif c == -1:
                parts.append(f"-{t}")
            else:
                parts.append(f"{c}*{t}")
        lhs = " + ".join(parts).replace("+ -", "- ")
        return f"({lhs} >= {self.bound})"


# ---- Convenience builders -------------------------------------------------


def geq(t: Term, z) -> Formula:
    return LinIneq(((Fraction(1), t),), Fraction(z))


def leq(t: Term, z) -> Formula:
    return LinIneq(((Fraction(-1), t),), Fraction(-z))


def eq(t: Term, z) -> Formula:
    return And(geq(t, z), leq(t, z))
