"""
Regression tests verifying every claim about the telescope example
(Dolgorukov-Galimullin-Gladyshev, AAMAS 2024, §2.2 and Figure 1).
"""

from fractions import Fraction

import pytest

from spq import (
    Atom, C, K, Neg, Or, Query,
    bcs, evaluate, examples, global_check, parse_formula, update,
)
from spq.language import BudgetTerm
from spq.language import geq


@pytest.fixture
def telescope():
    M, p = examples.telescope()
    return M, p


def test_actual_world_satisfies_p(telescope):
    M, _ = telescope
    assert evaluate(M, "w1", Atom("p"))
    assert not evaluate(M, "w2", Atom("p"))


def test_n_does_not_know_p_before_query(telescope):
    M, _ = telescope
    assert not evaluate(M, "w1", K("n", Atom("p")))


def test_l_unaware_of_b_m(telescope):
    M, _ = telescope
    # l does not know whether b_m >= 10.
    assert not evaluate(M, "w1", K("l", geq(BudgetTerm("m"), 10)))


def test_bcs_at_each_world(telescope):
    M, p = telescope
    nm = frozenset({"n", "m"})
    assert bcs(M, "w1", nm, p)
    assert bcs(M, "w2", nm, p)
    assert not bcs(M, "w3", nm, p)
    assert not bcs(M, "w4", nm, p)


def test_update_drops_unrealisable_worlds(telescope):
    M, p = telescope
    nm = frozenset({"n", "m"})
    Mu = update(M, nm, p)
    assert Mu.worlds == ["w1", "w2"]


def test_common_knowledge_after_query(telescope):
    M, p = telescope
    nm = frozenset({"n", "m"})
    Mu = update(M, nm, p)
    assert evaluate(Mu, "w1", K("n", Atom("p")))
    assert evaluate(Mu, "w1", K("m", Atom("p")))
    assert evaluate(Mu, "w1", C(nm, Atom("p")))


def test_l_still_does_not_know_p(telescope):
    M, p = telescope
    nm = frozenset({"n", "m"})
    Mu = update(M, nm, p)
    assert not evaluate(Mu, "w1", K("l", Atom("p")))


def test_semi_public_property(telescope):
    """The defining property: outsiders know that the group has settled the question."""
    M, p = telescope
    nm = frozenset({"n", "m"})
    Mu = update(M, nm, p)
    semi_public = Or(C(nm, Atom("p")), C(nm, Neg(Atom("p"))))
    assert evaluate(Mu, "w1", K("l", semi_public))


def test_budget_bookkeeping(telescope):
    M, p = telescope
    nm = frozenset({"n", "m"})
    Mu = update(M, nm, p)
    # min-cost share is c_m(p)/|G| = 20/2 = 10
    assert Mu.bdg_of("n", "w1") == Fraction(5)    # 15 - 10
    assert Mu.bdg_of("m", "w1") == Fraction(0)    # 10 - 10
    assert Mu.bdg_of("l", "w1") == Fraction(5)    # unchanged (l is outside G)


def test_dynamic_operator_directly(telescope):
    M, p = telescope
    nm = frozenset({"n", "m"})
    assert evaluate(M, "w1", Query(p, nm, C(nm, Atom("p"))))


def test_dynamic_semi_public_directly(telescope):
    M, p = telescope
    nm = frozenset({"n", "m"})
    semi_public = Or(C(nm, Atom("p")), C(nm, Neg(Atom("p"))))
    assert evaluate(M, "w1", Query(p, nm, K("l", semi_public)))


def test_query_vacuously_true_where_bcs_fails(telescope):
    """In w3, w4 the query is unrealisable, so [?p_{n,m}] phi is True for any phi."""
    M, p = telescope
    nm = frozenset({"n", "m"})
    worlds = global_check(M, Query(p, nm, C(nm, Atom("p"))))
    assert worlds == ["w1", "w3", "w4"]


# ---------------------------------------------------------------------------
# Same set of facts, but exercising the DSL parser.
# ---------------------------------------------------------------------------


def _eval_dsl(M, world, src):
    return evaluate(M, world, parse_formula(src))


def test_dsl_basic_atoms(telescope):
    M, _ = telescope
    assert _eval_dsl(M, "w1", "p")
    assert not _eval_dsl(M, "w2", "p")


def test_dsl_knowledge(telescope):
    M, _ = telescope
    assert not _eval_dsl(M, "w1", "K_n p")


def test_dsl_query_common_knowledge(telescope):
    M, _ = telescope
    assert _eval_dsl(M, "w1", "[?p_{n,m}] C_{n,m} p")


def test_dsl_semi_public(telescope):
    M, _ = telescope
    assert _eval_dsl(M, "w1", "[?p_{n,m}] K_l (C_{n,m} p | C_{n,m} ~p)")


def test_dsl_linear_inequality(telescope):
    M, _ = telescope
    # Joint budget of n and m at w1 is 15 + 10 = 25 >= 20.
    assert _eval_dsl(M, "w1", "b_n + b_m >= 20")
    # ...but at w3 it is 15 + 9 = 24, still >= 20.
    assert _eval_dsl(M, "w3", "b_n + b_m >= 20")
    # cost equality
    assert _eval_dsl(M, "w1", "c_m(p) = 20")
    # strict
    assert _eval_dsl(M, "w1", "c_m(p) < 21")
    assert not _eval_dsl(M, "w1", "c_m(p) > 21")


def test_dsl_singleton_group_braces_optional(telescope):
    M, _ = telescope
    # Singleton group: K_n vs C_n vs C_{n} should all behave the same way.
    assert _eval_dsl(M, "w1", "C_n p") == _eval_dsl(M, "w1", "C_{n} p")
