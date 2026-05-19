"""
SPQ — Dynamic Epistemic Logic of Semi-Public Queries for Resource-Bounded Agents.

Reference implementation accompanying:

    Vitaliy Dolgorukov, Rustam Galimullin, Maksim Gladyshev.
    "Dynamic Epistemic Logic of Resource Bounded Information Mining Agents",
    AAMAS 2024. arXiv:2401.13369.

Public API:

    from spq import (
        Model,
        parse_formula, parse_prop,
        evaluate, global_check,
        explain, render_text,
        examples,
    )

Typical usage:

    >>> from spq import parse_formula, evaluate, examples
    >>> M, p = examples.telescope()
    >>> phi = parse_formula("[?p_{n,m}] C_{n,m} p")
    >>> evaluate(M, "w1", phi)
    True
"""

from . import examples
from .language import (
    And, Atom, BudgetTerm, C, CostTerm, E, Formula, Implies, K, LinIneq, Neg, Or,
    PAnd, PNot, POr, PVar, PropFormula, Query, TOP, Term,
    eq, geq, leq,
)
from .model import Model
from .parser import ParseError, parse_formula, parse_prop
from .semantics import (
    bcs, evaluate, global_check, min_cost, p_eval, reachable, share, update,
)
from .trace import Step, explain, render_text

__version__ = "0.1.0"

__all__ = [
    "Model",
    "parse_formula",
    "parse_prop",
    "ParseError",
    "evaluate",
    "global_check",
    "update",
    "bcs",
    "share",
    "min_cost",
    "reachable",
    "p_eval",
    "explain",
    "render_text",
    "Step",
    "examples",
    # AST nodes
    "Atom", "Neg", "And", "Or", "Implies", "K", "E", "C", "Query", "LinIneq",
    "BudgetTerm", "CostTerm", "Term",
    "PVar", "PNot", "PAnd", "POr", "PropFormula", "TOP",
    "Formula",
    "geq", "leq", "eq",
]
