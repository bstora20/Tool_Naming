# Paper Outline: Learned Grammars as Compression for LLM Tool Interfaces

**Project:** tool_name
**Drafted:** 2026-10-22

This document synthesizes all experiments conducted under this project into a single
paper abstract and outline. Sources: `ALL_RESULTS.md` (this session's Experiments 1-6,
jq/sed/cross-model sticky-idiom line), the Majk knowledge base (original Study 1
naming×interface experiment, Condition D/D2), and `experiments.txt`/`prelim_results.txt`
(Jules White's theoretical framework and Experiments A-H/0/8).

**Correspondence note:** `prelim_results.txt` is the theoretical paper draft proposing a
formal model (S + R ≥ G) and a numbered Experiment 0-9 program. `experiments.txt`'s
Experiments A-H/0/8 are the results for that program: A/B→Exp1/5, C→Exp2, D→Exp3,
E→Exp4, F→Exp6, G→Exp9, H→Exp7. This session's own Exp1-6 (jq/sed/cross-model, in
`ALL_RESULTS.md`) is an independent, more rigorous causal follow-up to exactly one node
of that program — Experiment C's "familiar name is worse when rules change" jq finding —
adding multi-turn repair, a documentation-degradation ladder, and the cross-model test
the theory paper explicitly flags as missing.

---

## Abstract

When a large language model is given a tool, how it is named, documented, and
composed determines how much of its calling convention the model must be
explicitly taught versus how much it already "knows" from pretraining. We
study this tradeoff through a program of controlled experiments that
manipulate tool names, argument grammars, documentation detail, host-language
realism, and recovery budgets while holding underlying task semantics fixed.

We find that familiar names function as free, pretrained grammar: a single
real command name (e.g. grep) recovers ~80% first-call argument correctness
with no description at all, while a random name requires roughly one usage
line (~145 tokens) to match it (Exp A/B). This familiarity is not
unconditionally beneficial. When a familiar command's rules are deliberately
changed, a familiar name becomes *harder* to correct than an unfamiliar one
taught the same rules — but only in single-shot calling; once multi-turn
repair is available, the accuracy penalty collapses to near zero and
resurfaces only as extra tokens (Exp C; confirmed independently in Exp 1-3).
We show this "sticky idiom" effect is real but brittle: it requires near-total
documentation removal to appear, is non-monotonically suppressed by
information (a prose statement of argument order performs *worse* than no
information at all once real parameter names are absent — the
"ordered_generic paradox," Exp 4b/4c), generalizes to a second idiom (sed,
Exp 5), and fails to replicate on a newer model family (claude-sonnet-5-5,
Exp 6) under conditions where it is large and robust on gpt-6-luna — making
the effect's severity both documentation- and model-dependent.

We further show that interfaces which merely resemble a familiar language
(restricted JavaScript, restricted shell) induce "grammar completion": models
spontaneously emit unsupported-but-valid constructs from the full language
unless explicitly told what is unsupported, a single sentence that suppresses
borrowing almost entirely (Exp D, Exp 0). Wholly novel grammars can be taught
in-context, but only a grammar description plus one example reaches high
reliability; examples alone teach exactly what they show and do not
generalize (Exp E). Finally, we decompose interface token cost: repeated tool
definitions dominate cost over call length or composition ability at
short task depths (Exp 8), but script-style composition saves increasingly
more tokens (not accuracy) as dependency depth grows (Exp H), and error cost
is dominated by resent context rather than error position, mostly absorbed by
prompt caching (Exp F), while attempt budget and error-message quality jointly
determine whether a grammar mismatch costs a task or only tokens (Exp G).

Together these results support a unifying account — Grammar Compression —
in which familiar interface cues let models substitute pretrained knowledge
for explicit specification, at a price that scales with how much behavior is
delegated to that knowledge and how faithfully it matches the implemented
interface. We formalize this as S + R ≥ G and derive practical design rules:
borrow a grammar wholly or not at all, keep each source of grammar in one
place, and measure interfaces by total cost per successful task rather than
call length or error rate alone.

---

## Outline

### 1. Introduction
1.1 Tool interfaces as learned grammars, not interchangeable syntaxes
1.2 Three hypotheses: Retrieval-Cue, Grammar-Compression, Grammar-Completion
1.3 Contributions and roadmap

### 2. A Model of Grammar, Cost, and Reliability
2.1 S, R, G, F: explicit specification, retrieval, required grammar, fidelity
2.2 Grammar leverage as a token-equivalent quantity (Exp 5/B)
2.3 Turn amplification: why an error costs more than the bad call
    (fixed-definition and growing-history amplification; Exp F, Exp 6/first-round)
2.4 Effective cost per successful task as the evaluation objective

### 3. Naming Gives Away Grammar for Free
3.1 Name-alone accuracy vs. random names (Exp A)
3.2 Dose-response: what a usage line buys an unfamiliar name (Exp B, Exp 5)
3.3 Precursor: the original 3(name)×3(interface) study (648 trials) —
    naming matters in shell, barely in scripted/sequential calling
    (Study 1 / "outside naming study"); structured schemas blunt the
    naming effect further (Exp 1, "structured naming experiment")

### 4. The Almost-Familiar Principle: When Familiarity Backfires
4.1 Dosed rule changes: familiar name ~10pts worse than random name taught
    the same changed rules, driven almost entirely by jq (Exp C)
4.2 Precursor null results: Condition D / D2 (find/grep, shell + sequential)
    found no effect — explained by weaker idiom strength and/or scoring
4.3 This paper's resolution: the effect is single-call-only. Multi-turn
    repair collapses it to ~0% task-level cost, surfacing only as tokens
    (Exp 1-3, this study's jq sticky-idiom line)
4.4 Documentation-robustness ladder: full → terse → named → ordered_generic
    → none (Exp 4/4b/4c)
    - Argument-order reversion requires near-total doc removal (none: 52.5%)
    - The ordered_generic paradox: prose stating the order is *worse* than
      no information (85.0% reversion) — real parameter names, not order
      statements, are the suppressing ingredient
    - A parallel, syntax-level (not just order-level) reversion is endemic
      to shell and suppressed only by a one-sentence task description
4.5 Idiom generalization: sed replicates the order-reversion pattern but
    with a far more severe syntax-reversion failure mode (Exp 5)
4.6 Model dependence: the entire effect fails to replicate on
    claude-sonnet-5-5 under conditions where it is large on gpt-6-luna
    (Exp 6) — severity is documentation- *and* model-dependent

### 5. Grammar Completion: Borrowing What Wasn't Taught
5.1 Restricted-JavaScript vs. relabelled-isomorphic grammar: 5.4x more
    borrowed real-JS constructs unless told what's unsupported (Exp D)
5.2 Post-hoc error classification: most ToolScript failures are valid,
    unsupported JavaScript; most CLI failures are grammar collisions, not
    borrowing (Exp 0)
5.3 Unifying with Section 4's syntax-reversion detector: two independently
    discovered instances of the same underlying phenomenon

### 6. Teaching Novel Grammar In-Context
6.1 Nothing / grammar / example / grammar+example, and placement (Exp E)
6.2 Examples teach exactly what they show; grammar carries generalization
6.3 Feedback-based examples (shown after a failed call) outperform the
    same example given upfront

### 7. The Economics of Interface Design
7.1 Definition size dominates token cost; composition and call length are
    within noise at shallow depth (Exp 8)
7.2 Composition saves cost, not accuracy, and the saving grows with
    dependency depth (Exp H)
7.3 Error cost is driven by resent context, not position; caching absorbs
    most of the dollar cost (Exp F)
7.4 Attempt budget × error-message quality decide whether a mismatch costs
    a task or only tokens (Exp G)

### 8. Discussion
8.1 Reconciling single-shot and multi-turn findings under one framework
8.2 Model-dependence as a first-class variable, not noise
8.3 Design principles: borrow a grammar whole or not at all; keep each
    grammar source in one place; teach new grammar where it's used;
    minimize repeated specification and unnecessary turns
8.4 Threats to validity (consolidated from each experiment's "three
    biggest threats"): single-provider caching assumptions, scorer
    strictness/leakage, single-construct-driven effects, short task depth

### 9. Related Work
9.1 Identifier-name studies in code models
9.2 Zero-shot tool use from documentation
9.3 Positioning relative to prior tool-use benchmarks (schema completeness,
    tool count) vs. this paper's focus on grammar source

### 10. Conclusion and Future Work
10.1 Summary of the ten headline principles and their current support
10.2 Open: Composition Leverage beyond depth-12 synthetic chains;
     isolating recovery as an independent factor; a second model family
     with an independently-known strong idiom prior
