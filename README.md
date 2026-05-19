# spq

**Model checker for the Dynamic Epistemic Logic of Semi-Public Queries (SPQ).**

A faithful, dependency-free Python reference implementation of the logic
introduced in:

> Vitaliy Dolgorukov, Rustam Galimullin, Maksim Gladyshev.
> *Dynamic Epistemic Logic of Resource Bounded Information Mining Agents.*
> AAMAS 2024. [arXiv:2401.13369](https://arxiv.org/abs/2401.13369).

Developed at the [International Laboratory for Logic, Linguistics and Formal
Philosophy, HSE University](https://llfp.hse.ru).

---

## What SPQ is in one paragraph

Agents are perfect reasoners with budgets `b_i`. Every propositional formula
`A` has a cost `c_i(A)` that can differ between agents. A group `G` can
perform a *semi-public query* `[?A_G]`: they pool resources, the member with
the lowest cost asks the question, and every member learns the answer; the
answer is private to `G`, but the fact that the query was made is public.
The logic combines this dynamic operator with `K_i`, `C_G`, and linear
inequalities over budgets and costs, so you can express claims like
“after `{n,m}` ask whether `p`, it is common knowledge among them whether
`p`, and `l` knows that”.

## Install

```bash
pip install -e .
```

No runtime dependencies. Python ≥ 3.10.

## Quickstart

```python
from spq import parse_formula, evaluate, examples

M, p = examples.telescope()
phi  = parse_formula("[?p_{n,m}] C_{n,m} p")
print(evaluate(M, "w1", phi))   # True
```

Or from the shell:

```bash
spq check   "[?p_{n,m}] C_{n,m} p"
spq global  "[?p_{n,m}] C_{n,m} p"
spq explain "[?p_{n,m}] K_l (C_{n,m} p | C_{n,m} ~p)"
```

`spq explain` prints a proof tree showing every BCS check, what the update
operator did to the model (which worlds it dropped, how budgets changed,
which relations were refined), and the inner evaluation in the updated model.

## DSL syntax (cheat sheet)

| Paper notation              | DSL                          |
|-----------------------------|------------------------------|
| `p`                         | `p`                          |
| `¬φ`                        | `~phi`                       |
| `φ ∧ ψ`                     | `phi & psi`                  |
| `φ ∨ ψ`                     | `phi \| psi`                 |
| `φ → ψ`                     | `phi -> psi`                 |
| `K_i φ`                     | `K_i phi`                    |
| `E_G φ`                     | `E_{i,j,k} phi`              |
| `C_G φ`                     | `C_{i,j,k} phi`              |
| `[?A_G] φ`                  | `[?A_{i,j,k}] phi`           |
| `b_i ≥ z`                   | `b_i >= z`                   |
| `c_i(A) ≤ z`                | `c_i(A) <= z`                |
| `2b_i − b_j = z`            | `2*b_i - b_j = z`            |
| `b_i + b_j ≥ c_i(p ∨ q)`    | `b_i + b_j >= c_i(p \| q)`   |

Singleton groups can drop the braces: `C_n p` is `C_{n} p`.

## Project layout

```
spq/
├── language.py    # AST: PropFormula, Formula, terms
├── model.py       # Model (worlds, relations, Cost, Bdg, V)
├── semantics.py   # evaluate, BCS, share, update, reachable
├── trace.py       # explain() — structured, renderable proof trees
├── parser.py      # recursive-descent parser for the DSL above
├── examples.py    # telescope (Example 2.3 of the paper)
└── cli.py         # `spq check / global / explain`
tests/             # pytest suite, regression tests on paper claims
```

The implementation maps to the paper section-by-section. The semantics file
mirrors Definitions 2.2 (Model), 2.4 (Updated Model), and 2.5 (Truth) of the
AAMAS 2024 paper line-for-line.

## Reproducing the telescope example

`examples.telescope()` returns the four-world model of Figure 1. Running
`pytest tests/test_telescope.py` verifies every claim about it that appears
in §2.2 of the paper — pre-update facts, BCS behaviour, common knowledge
after `[?p_{n,m}]`, the semi-public property `K_l(C_{n,m}p ∨ C_{n,m}¬p)`,
and the budget bookkeeping (`b_n: 15 → 5`, `b_m: 10 → 0`, `b_l: 5 → 5`).

## Roadmap

Already on the list for the next iterations:

- LaTeX renderer for `Step` trees (drop-in proof snippets for papers)
- TikZ exporter for `Model` (re-draw Figure 1 from your own scenarios)
- YAML model loader (define models without writing Python)
- Jupyter notebooks: telescope, Wise-men, Mastermind
- Benchmark suite for empirical complexity (`|W| × |AG| × |φ|`)
- Multiple resources (vector budgets and costs), as discussed in §6 of the paper
- Quantified queries in the spirit of APAL / GAL / CAL

## License

MIT — see [`LICENSE`](LICENSE).

## Citing

If you use this software in academic work, please cite both the paper
([`CITATION.cff`](CITATION.cff)) and this repository.
