"""Tests for the DSL parser."""

from fractions import Fraction

import pytest

from spq import (
    And, Atom, BudgetTerm, C, CostTerm, E, Implies, K, LinIneq, Neg, Or,
    PVar, Query, parse_formula, parse_prop,
)
from spq.parser import ParseError


def test_atom():
    assert parse_formula("p") == Atom("p")


def test_negation():
    assert parse_formula("~p") == Neg(Atom("p"))
    assert parse_formula("~~p") == Neg(Neg(Atom("p")))


def test_and_or_precedence():
    # & binds tighter than |
    assert parse_formula("p & q | r") == Or(And(Atom("p"), Atom("q")), Atom("r"))
    # explicit parens
    assert parse_formula("p & (q | r)") == And(Atom("p"), Or(Atom("q"), Atom("r")))


def test_implies_right_assoc():
    # p -> q -> r  ===  p -> (q -> r)
    parsed = parse_formula("p -> q -> r")
    assert parsed == Implies(Atom("p"), Implies(Atom("q"), Atom("r")))


def test_K_operator():
    assert parse_formula("K_n p") == K("n", Atom("p"))
    # K binds tighter than &
    assert parse_formula("K_n p & q") == And(K("n", Atom("p")), Atom("q"))
    # parenthesised
    assert parse_formula("K_n (p & q)") == K("n", And(Atom("p"), Atom("q")))
    # nested K
    assert parse_formula("K_n K_m p") == K("n", K("m", Atom("p")))


def test_C_group():
    assert parse_formula("C_{n,m} p") == C(frozenset({"n", "m"}), Atom("p"))
    # singleton group, braces optional
    assert parse_formula("C_n p") == C(frozenset({"n"}), Atom("p"))
    assert parse_formula("C_{n} p") == C(frozenset({"n"}), Atom("p"))


def test_E_group():
    assert parse_formula("E_{n,m} p") == E(frozenset({"n", "m"}), Atom("p"))


def test_query():
    expected = Query(PVar("p"), frozenset({"n", "m"}), C(frozenset({"n", "m"}), Atom("p")))
    assert parse_formula("[?p_{n,m}] C_{n,m} p") == expected


def test_query_with_compound_prop():
    expected = Query(
        PVar("p"),
        frozenset({"n", "m"}),
        K("l", Or(C(frozenset({"n", "m"}), Atom("p")),
                  C(frozenset({"n", "m"}), Neg(Atom("p"))))),
    )
    assert parse_formula("[?p_{n,m}] K_l (C_{n,m} p | C_{n,m} ~p)") == expected


def test_linear_inequality_geq():
    parsed = parse_formula("b_n >= 10")
    assert parsed == LinIneq(((Fraction(1), BudgetTerm("n")),), Fraction(10))


def test_linear_inequality_sum():
    parsed = parse_formula("b_n + b_m >= 20")
    assert parsed == LinIneq(
        ((Fraction(1), BudgetTerm("n")), (Fraction(1), BudgetTerm("m"))),
        Fraction(20),
    )


def test_linear_inequality_with_coefficient():
    parsed = parse_formula("2*b_n - b_m = 10")
    # equality expands to (>= /\ <=)
    lhs = ((Fraction(2), BudgetTerm("n")), (Fraction(-1), BudgetTerm("m")))
    lhs_neg = ((Fraction(-2), BudgetTerm("n")), (Fraction(1), BudgetTerm("m")))
    expected = And(LinIneq(lhs, Fraction(10)), LinIneq(lhs_neg, Fraction(-10)))
    assert parsed == expected


def test_linear_inequality_cost():
    parsed = parse_formula("c_m(p) <= 20")
    # t <= z  iff  -t >= -z
    expected = LinIneq(((Fraction(-1), CostTerm("m", PVar("p"))),), Fraction(-20))
    assert parsed == expected


def test_linear_inequality_strict():
    parsed = parse_formula("b_n < 10")
    # < is ¬(>=)
    expected = Neg(LinIneq(((Fraction(1), BudgetTerm("n")),), Fraction(10)))
    assert parsed == expected


def test_prop_formula_parsing():
    assert parse_prop("p") == PVar("p")
    assert parse_prop("p & q").__class__.__name__ == "PAnd"
    assert parse_prop("~p").__class__.__name__ == "PNot"


def test_parse_errors():
    with pytest.raises(ParseError):
        parse_formula("K_")
    with pytest.raises(ParseError):
        parse_formula("p &")
    with pytest.raises(ParseError):
        parse_formula("[?p] phi")  # missing _G


def test_round_trip_through_repr():
    """If we parse, then repr, then parse again, semantics should be preserved.
    Repr round-tripping is approximate; here we just check evaluation equivalence
    on the telescope model."""
    from spq import evaluate, examples
    M, _ = examples.telescope()
    cases = [
        "K_n p",
        "[?p_{n,m}] C_{n,m} p",
        "b_n + b_m >= 20",
        "K_l (C_{n,m} p | C_{n,m} ~p)",
    ]
    for src in cases:
        phi = parse_formula(src)
        # repr produces ASCII; re-parse and compare evaluation
        for w in M.worlds:
            assert evaluate(M, w, phi) == evaluate(M, w, parse_formula(repr(phi))), \
                f"round-trip failed for: {src} -> {repr(phi)}"
