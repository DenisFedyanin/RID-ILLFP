"""
Recursive-descent parser for L_SPQ formulas in paper-style notation.

Examples that parse:

    p
    ~p
    K_n p
    K_l (C_{n,m} p | C_{n,m} ~p)
    [?p_{n,m}] C_{n,m} p
    [?p_{n,m}] K_l (C_{n,m} p | C_{n,m} ~p)
    b_n + b_m >= 20
    c_n(p) <= 30
    2*b_n - b_m = 10

Grammar (lowest precedence first):

    phi      := impl
    impl     := or_expr ( "->" impl )?              right-associative
    or_expr  := and_expr ( "|" and_expr )*
    and_expr := unary    ( "&" unary )*
    unary    := "~" unary
              | modal_prefix unary
              | primary
    primary  := "(" phi ")"
              | lin_ineq
              | atom

    modal_prefix := "K_" agent
                  | "C_" group
                  | "E_" group
                  | "[?" prop_formula "_" group "]"

    lin_ineq := lin_expr CMP NUMBER
    lin_expr := lin_term ( ("+" | "-") lin_term )*
    lin_term := [ NUMBER "*" ] term
    term     := "b_" agent | "c_" agent "(" prop_formula ")"
    CMP      := ">=" | "<=" | "=" | ">" | "<"

    group        := "{" agent ("," agent)* "}" | agent
    agent        := IDENT

    prop_formula := pf_or
    pf_or        := pf_and ( "|" pf_and )*
    pf_and       := pf_un  ( "&" pf_un )*
    pf_un        := "~" pf_un | pf_atom | "(" prop_formula ")"
    pf_atom      := IDENT | "top"

Naming conventions: agents and atom names are identifiers without underscores
(letters and digits only). The single-letter prefixes K, C, E, b, c are reserved
when followed by "_".
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import FrozenSet, List, Optional, Tuple

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
    PAnd,
    PNot,
    POr,
    PVar,
    PropFormula,
    Query,
    TOP,
    Term,
)


# =============================================================================
# Tokenizer
# =============================================================================


@dataclass
class Token:
    kind: str
    value: str
    pos: int

    def __repr__(self) -> str:
        return f"<{self.kind}:{self.value!r}@{self.pos}>"


_TWO_CHAR = {"->": "ARROW", "<->": "IFF", ">=": "GEQ", "<=": "LEQ"}
_SINGLE = {
    "(": "LP", ")": "RP",
    "{": "LB", "}": "RB",
    "[": "LBR", "]": "RBR",
    ",": "COMMA",
    "_": "UNDER",
    "?": "QMARK",
    "+": "PLUS", "-": "MINUS", "*": "STAR",
    "&": "AND", "|": "OR", "~": "NOT",
    "=": "EQ", "<": "LT", ">": "GT",
}


def tokenize(src: str) -> List[Token]:
    toks: List[Token] = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        if ch.isspace():
            i += 1
            continue
        # Three-char "<->"
        if src[i:i + 3] == "<->":
            toks.append(Token("IFF", "<->", i))
            i += 3
            continue
        # Two-char operators
        two = src[i:i + 2]
        if two in _TWO_CHAR:
            toks.append(Token(_TWO_CHAR[two], two, i))
            i += 2
            continue
        # Single-char punctuation/operators
        if ch in _SINGLE:
            toks.append(Token(_SINGLE[ch], ch, i))
            i += 1
            continue
        # Number (integer or rational with /)
        if ch.isdigit():
            j = i
            while j < n and src[j].isdigit():
                j += 1
            if j < n and src[j] == "/":
                j += 1
                while j < n and src[j].isdigit():
                    j += 1
            toks.append(Token("NUM", src[i:j], i))
            i = j
            continue
        # Identifier (letters + digits; no underscores — underscore is a token)
        if ch.isalpha():
            j = i
            while j < n and (src[j].isalnum()):
                j += 1
            toks.append(Token("IDENT", src[i:j], i))
            i = j
            continue
        raise ParseError(f"Unexpected character {ch!r} at position {i}")
    toks.append(Token("EOF", "", n))
    return toks


# =============================================================================
# Parser
# =============================================================================


class ParseError(ValueError):
    pass


class _Parser:
    def __init__(self, src: str) -> None:
        self.src = src
        self.toks = tokenize(src)
        self.i = 0

    # ---- token helpers ------------------------------------------------------

    def peek(self, offset: int = 0) -> Token:
        return self.toks[self.i + offset]

    def consume(self) -> Token:
        t = self.toks[self.i]
        self.i += 1
        return t

    def accept(self, kind: str) -> Optional[Token]:
        if self.peek().kind == kind:
            return self.consume()
        return None

    def expect(self, kind: str) -> Token:
        if self.peek().kind != kind:
            raise ParseError(
                f"Expected {kind}, got {self.peek().kind} ({self.peek().value!r}) "
                f"near `...{self.src[max(0, self.peek().pos - 10):self.peek().pos + 10]}...`"
            )
        return self.consume()

    # ---- groups / agents ----------------------------------------------------

    def parse_agent(self) -> str:
        t = self.expect("IDENT")
        return t.value

    def parse_group(self) -> FrozenSet[str]:
        # Either a single agent or {a, b, c}
        if self.peek().kind == "LB":
            self.consume()
            agents = [self.parse_agent()]
            while self.accept("COMMA"):
                agents.append(self.parse_agent())
            self.expect("RB")
            return frozenset(agents)
        return frozenset({self.parse_agent()})

    # ---- propositional sub-grammar -----------------------------------------

    def parse_prop(self) -> PropFormula:
        return self._pf_or()

    def _pf_or(self) -> PropFormula:
        left = self._pf_and()
        while self.accept("OR"):
            right = self._pf_and()
            left = POr(left, right)
        return left

    def _pf_and(self) -> PropFormula:
        left = self._pf_un()
        while self.accept("AND"):
            right = self._pf_un()
            left = PAnd(left, right)
        return left

    def _pf_un(self) -> PropFormula:
        if self.accept("NOT"):
            return PNot(self._pf_un())
        if self.accept("LP"):
            inner = self.parse_prop()
            self.expect("RP")
            return inner
        t = self.expect("IDENT")
        if t.value == "top":
            return TOP
        return PVar(t.value)

    # ---- terms and linear inequalities -------------------------------------

    def _at_term(self) -> bool:
        t = self.peek()
        return t.kind == "IDENT" and t.value in ("b", "c") and self.peek(1).kind == "UNDER"

    def _at_lin_expr(self) -> bool:
        # NUMBER, b_, c_, +, -  all start a linear expression
        t = self.peek()
        return t.kind in ("NUM", "PLUS", "MINUS") or self._at_term()

    def parse_term(self) -> Term:
        prefix = self.expect("IDENT").value
        self.expect("UNDER")
        agent = self.parse_agent()
        if prefix == "b":
            return BudgetTerm(agent)
        if prefix == "c":
            self.expect("LP")
            A = self.parse_prop()
            self.expect("RP")
            return CostTerm(agent, A)
        raise ParseError(f"Unknown term prefix {prefix!r}")

    def parse_lin_term(self, sign: int) -> Tuple[Fraction, Term]:
        coeff = Fraction(sign)
        if self.peek().kind == "NUM":
            n = self.consume().value
            coeff = coeff * _parse_number(n)
            self.expect("STAR")
        elif not self._at_term():
            # Plain number followed by no term: bare constant — not valid here.
            raise ParseError(
                f"Expected term (b_… or c_…) at position {self.peek().pos}"
            )
        term = self.parse_term()
        return (coeff, term)

    def parse_lin_expr(self) -> Tuple[Tuple[Fraction, Term], ...]:
        # First term may be preceded by a sign
        sign = 1
        if self.accept("MINUS"):
            sign = -1
        elif self.accept("PLUS"):
            sign = 1
        parts = [self.parse_lin_term(sign)]
        while True:
            if self.accept("PLUS"):
                parts.append(self.parse_lin_term(1))
            elif self.accept("MINUS"):
                parts.append(self.parse_lin_term(-1))
            else:
                break
        return tuple(parts)

    def parse_lin_ineq(self) -> Formula:
        coeffs = self.parse_lin_expr()
        cmp_tok = self.consume()
        if cmp_tok.kind not in ("GEQ", "LEQ", "EQ", "GT", "LT"):
            raise ParseError(
                f"Expected comparator (>=, <=, =, >, <), got {cmp_tok.value!r}"
            )
        rhs_neg = False
        if self.accept("MINUS"):
            rhs_neg = True
        bound_tok = self.expect("NUM")
        bound = _parse_number(bound_tok.value)
        if rhs_neg:
            bound = -bound

        # Normalize all comparators to LinIneq (which is >=).
        if cmp_tok.kind == "GEQ":
            return LinIneq(coeffs, bound)
        if cmp_tok.kind == "LEQ":
            # t <= z  iff  -t >= -z
            neg = tuple((-c, t) for (c, t) in coeffs)
            return LinIneq(neg, -bound)
        if cmp_tok.kind == "EQ":
            # t = z  iff  t >= z  &  t <= z
            return And(LinIneq(coeffs, bound),
                       LinIneq(tuple((-c, t) for (c, t) in coeffs), -bound))
        if cmp_tok.kind == "GT":
            # t > z  iff  ¬(t <= z)  iff  ¬(-t >= -z)
            neg = tuple((-c, t) for (c, t) in coeffs)
            return Neg(LinIneq(neg, -bound))
        if cmp_tok.kind == "LT":
            # t < z  iff  ¬(t >= z)
            return Neg(LinIneq(coeffs, bound))
        raise ParseError(f"Unexpected comparator {cmp_tok.value!r}")

    # ---- main formula grammar ----------------------------------------------

    def parse(self) -> Formula:
        phi = self._impl()
        if self.peek().kind != "EOF":
            raise ParseError(
                f"Trailing input at position {self.peek().pos}: {self.peek().value!r}"
            )
        return phi

    def _impl(self) -> Formula:
        left = self._or()
        if self.accept("ARROW"):
            right = self._impl()  # right-assoc
            return Implies(left, right)
        return left

    def _or(self) -> Formula:
        left = self._and()
        while self.accept("OR"):
            right = self._and()
            left = Or(left, right)
        return left

    def _and(self) -> Formula:
        left = self._unary()
        while self.accept("AND"):
            right = self._unary()
            left = And(left, right)
        return left

    def _unary(self) -> Formula:
        if self.accept("NOT"):
            return Neg(self._unary())
        # Modal prefix: K_ / C_ / E_
        if self.peek().kind == "IDENT" and self.peek(1).kind == "UNDER":
            head = self.peek().value
            if head == "K":
                self.consume()  # 'K'
                self.consume()  # '_'
                agent = self.parse_agent()
                inner = self._unary()
                return K(agent, inner)
            if head == "C":
                self.consume()  # 'C'
                self.consume()  # '_'
                group = self.parse_group()
                inner = self._unary()
                return C(group, inner)
            if head == "E":
                self.consume()  # 'E'
                self.consume()  # '_'
                group = self.parse_group()
                inner = self._unary()
                return E(group, inner)
            # Otherwise fall through (it's a term like b_ / c_)
        # Query: [?A_G] phi
        if self.peek().kind == "LBR":
            return self._query()
        return self._primary()

    def _query(self) -> Formula:
        self.expect("LBR")
        self.expect("QMARK")
        A = self.parse_prop()
        self.expect("UNDER")
        group = self.parse_group()
        self.expect("RBR")
        inner = self._unary()
        return Query(A, group, inner)

    def _primary(self) -> Formula:
        if self.accept("LP"):
            inner = self._impl()
            self.expect("RP")
            return inner
        if self._at_lin_expr():
            return self.parse_lin_ineq()
        t = self.expect("IDENT")
        return Atom(t.value)


def _parse_number(s: str) -> Fraction:
    if "/" in s:
        a, b = s.split("/")
        return Fraction(int(a), int(b))
    return Fraction(int(s))


# =============================================================================
# Public API
# =============================================================================


def parse_formula(src: str) -> Formula:
    """Parse a string into an L_SPQ formula AST."""
    return _Parser(src).parse()


def parse_prop(src: str) -> PropFormula:
    """Parse a string into an L_PL propositional formula AST."""
    p = _Parser(src)
    result = p.parse_prop()
    if p.peek().kind != "EOF":
        raise ParseError(
            f"Trailing input after propositional formula at position {p.peek().pos}"
        )
    return result
