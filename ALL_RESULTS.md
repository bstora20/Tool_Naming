# Tool-Naming / Grammar-Interference Study: Compiled Results (Experiments 1-5)

**Project:** tool_name
**Compiled:** 2026-10-14 (updated 2026-10-20)

This file compiles every experiment report from the "Three Follow-Up Experiments" line of work into a single document, in order. Each section was originally written up individually; see the Majk knowledge base (conversation `084e2367-6b8d-450d-8760-573d056cb3f4`) for the live, linked versions.

---

## Contents

0. Corrections and Disclosures (read first)
1. Experiment 1: jq Sticky-Idiom Test (Sequential + Shell)
2. Experiment 2: Dosed/Compounded Rule Changes (Condition D2)
3. Experiment 3: Condition D on the Sequential Interface
4. Combined Conclusion (Experiments 1-3)
5. Experiment 4: Documentation Robustness
6. Experiment 4b: Three Follow-Up Refinements
7. Experiment 4c: Shell Syntax-Reversion Instrumentation & ordered_generic Replication
8. Experiment 5: Idiom Generalization — sed
9. Experiment 6: Cross-Model Replication Attempt (Model Identity Unverified)

---

# 0. Corrections and Disclosures (read first)

An independent skeptic review (`SKEPTIC_REVIEW.md`) of this project's raw data and code
surfaced six issues, addressed as follows. None of them change Experiments 1-5's own
headline numbers; they affect (a) a separate Study-1 baseline file, (b) Experiment 6's
model-identity claim, (c) the explanation offered for one result in Exp4b/4c, (d) a
single Tier-2 task's ground-truth definition, and (e) a code-level argument-dispatch bug
in the sequential interface's tool-call handling, present in both the Study-1 baseline
harness and this session's own jq/sed experiment scripts, whose historical impact cannot
be retroactively quantified but has been fixed going forward.

**1. A `str`-type scoring bug was found and fixed in `src/scoring.py`, and it did
materially change one file's numbers.** `score_answer` normalizes both the oracle value
and the model's response before comparing; one recovered historical results file,
`results/full_run_n3.jsonl` (Study 1's 648-trial `A-full`/`B`/`C` × `scripted`/`sequential`/`shell`
matrix), was originally scored before this normalization correctly handled a
`repr()`-quoted oracle string (e.g. literal `"'GPL-3.0'"` instead of `"GPL-3.0"`). Rescoring
with the current `scoring.py` flips exactly 104 of 648 rows from incorrect to correct
(**0 rows flip the other direction** — this is a one-directional fix, not a reweighting).
The `sequential`/`A-full` cell moves from 54.2% to 76.4% under the corrected scorer; see
`results/full_run_n3_rescored.jsonl` for the corrected file. **We audited every other
results file in `results/*.jsonl` for the same bug by recomputing all `str`-type-task scores
with the current scorer and diffing against the stored `correct` field: zero additional
flips were found anywhere else** — Experiments 1-6's own headline numbers (jq/sed/cross-model)
were never affected by this bug. `src/scoring.py` has also since been hardened with
regression tests (`tests/test_scoring.py`) covering this exact repr-quoting case, a
negation-blind-spot case (a response that only mentions the correct value to negate it, e.g.
"it's not X, it's actually Y"), and an int-extraction case where an unrelated number
appears before the answer-marked one.

**2. Experiment 6's cross-model claim cannot be verified from this repo's artifacts and
should be treated as unconfirmed.** `gpt-6-luna` and `claude-sonnet-5-5` are not real,
publicly documented model identifiers; `src/llm_client.py` only ever instantiates the
official `anthropic.Anthropic()` SDK client (no OpenAI client, no model-name validation);
no result row recorded which model actually served each request (now fixed — all four
experiment scripts log a `model` field going forward, see below); and some trials in
`results/full_run_n3.log` show 300+ second latencies for ~40-token completions, consistent
with a slow intermediary proxy rather than a distinct model. Section 9 below has been
rewritten to present Experiment 6's numbers as a replication **attempt** whose model
identity is unverified, not a confirmed cross-model finding. **All four run scripts
(`exp1_jq.py`, `exp4_doc_robustness.py`, `exp5_sed.py`, `run_experiment.py`) now write a
`model` field (the actual string passed to the Anthropic SDK) into every output row**, so
any future re-run of this kind can be independently checked against the model actually
requested.

**3. The `ordered_generic`-worse-than-`none` paradox (Exp4b/4c) is partly, but not wholly,
a timeout/stuck-loop artifact — this is now broken out explicitly.** Re-examining
`results/exp4c_seq_ordered_generic_moreseeds.jsonl` and `results/exp4b_seq_none_moreseeds.jsonl`:
excluding all timed-out trials (which hit the 15-turn ceiling with 9,500-14,600 total
tokens — clearly stuck-loop behavior, not a single confidently-wrong answer), the
`old_form_grammar` reversion rate for `ordered_generic`/JQ-swap is **82.9%** (58/70
non-timeout trials) vs. `none`/JQ-swap's **50.6%** (39/77 non-timeout trials) — the paradox
survives removing timeouts entirely, but timeouts do account for a nontrivial share of the
raw reversion count at both doc levels (`ordered_generic`: 10/80 trials timed out, 12.5%;
`none`: 3/80, 3.8%) and are themselves more frequent at `ordered_generic`, which is itself
part of the finding (prose stating the wrong-feeling order appears to induce more confusion,
not just more reversion). See the updated breakdown in Section 7 below.

**4. Task T2-06 ("which project has the fewest direct dependencies?") had an
unacknowledged 11-way tie in its ground truth, silently resolved by Python's `min()` to
whichever project happened to come first in dict-insertion order (`project-000`).**
`data/graph_seed42.json` has 11 of 40 projects tied at the minimum dependency count of 3;
the old oracle (`_t2_min_deps_project`, `src/tasks.py`) returned only `project-000` and
scored every other, equally-correct tied project as wrong. This has been fixed: the oracle
now returns the full tie-set, and a new `answer_type="str_any"` (`src/scoring.py`) accepts
a response naming *any* project in that set. **Rescoring every historical `results/*.jsonl`
file's T2-06 rows against the fixed oracle flips 20 of 75 rows from incorrect to correct
(0 rows flip the other direction)** — all 20 were cases where the model correctly identified
`project-000` (or another tied project) as among the fewest-dependency projects but was
marked wrong because the old oracle only accepted one specific tied candidate. The real,
measurable effect on previously-published per-cell numbers is small and confined to cells
that happened to contain an incorrectly-scored T2-06 trial: in `results/full_run_n3_rescored.jsonl`
(the file whose numbers are cited in Sections 1-4), only `shell/A-full` changes, from 61.1%
to **62.5%** (n=72); in the related Condition-D2/shell-comparison files, `shell/A-full` moves
from 61.1% to **62.5%** and `shell/D2` moves from 63.9% to **65.3%** (both n=72) — these
corrected numbers are now reflected in Sections 2 and 4. No comparison's qualitative
conclusion changes (D2 was already "no effect, slightly above baseline" and remains so).
Every other historical file's T2-06 rows were individually checked the same way; where a
file's own headline numbers weren't already cited as a specific percentage in this document,
no correction was needed in the prose, but the underlying fix applies uniformly to all of
them going forward. **Caveat:** `str_any` is now used only for T2-06; T2-05 ("most
dependencies") was independently confirmed to have a unique, non-tied maximum
(`project-037`, count 9) and was left on plain `str`.

**5. The sequential interface's tool-call dispatch bound arguments by raw JSON key
*order*, not by key *name* — a genuine code-level bug, independently reproduced, with a
historical impact that cannot be recovered from stored data but is now fixed and logged
going forward.** `src/harness_sequential.py`'s `run_sequential()` converted the model's
tool-call JSON input dict to a positional argument list via `list(tc["input"].values())`.
JSON objects are semantically unordered, so a model emitting a fully valid, correctly-keyed,
correctly-valued multi-argument tool call whose keys happen to be emitted in a different
order than the schema declared them would have its arguments silently misrouted into the
wrong positional slots. We independently reproduced this directly against the real
dispatcher (not just by reading the code): under condition `A-full`, calling `find`
(real documented order `[root, pattern]`) with the valid, correctly-keyed input
`{"pattern": "*/meta.json", "root": "/packages"}` produced the wrong positional call
`["*/meta.json", "/packages"]` and failed with `path must be absolute`, when the
identical call bound by key name succeeds. The same `.values()`-based pattern was found,
independently of the skeptic's review (which was scoped only to `harness_sequential.py`),
in three of this session's own experiment scripts — `src/exp1_jq.py`,
`src/exp4_doc_robustness.py`, `src/exp5_sed.py` — all of which drive this paper's own
headline jq/sed sticky-idiom findings (Experiments 1, 3, 4, 4b, 4c, 5, 6) on the
sequential interface. All four files are fixed: `harness_sequential.py` now binds by key
name via `Dispatcher.pid_for_name()` + `documented_arg_order()`; the three experiment
scripts (which at some documentation levels expose only generic `arg1`/`arg2` schema
names, precisely to avoid leaking argument order through the schema) bind against each
tool call's own `input_schema["required"]` list, which is always declared in the correct
order regardless of which naming scheme is in effect. A new regression test
(`test_sequential_binds_multiarg_tool_call_by_key_name_not_order` in
`tests/test_harnesses_mock.py`) reproduces the exact reversed-key scenario above and
passes under the fix; the full suite (65 tests) passes. **Historical impact is honestly
unquantifiable:** the per-call raw `input` dict was never persisted to the `.jsonl`
output rows, only the final error tag of the last failed call, so we cannot determine
retroactively how many of the sequential interface's `primitive_error`-tagged rows (96 of
1,261 sequential rows across all results files, 7.6% — notably *lower* than shell's
24.6%, suggesting this bug did not fire pervasively, consistent with Claude typically
emitting JSON object keys in schema-declared order, though this is an empirical tendency,
not a guarantee) are attributable to this bug versus genuine model error. All four
experiment-runner scripts (`run_experiment.py`, `exp1_jq.py`, `exp4_doc_robustness.py`,
`exp5_sed.py`) now additionally log each individual tool call's raw `name`+`input` dict
into a new `tool_calls` field on every output row, so any future re-run can be
independently audited for this specific failure mode rather than left an open question.

**6. Seed is a task/prompt-variation label, not a sampling-level reproducibility
control.** Every harness runs at temperature > 0 (default Anthropic API behavior), so
`--seed 1,2,3` should be read as three independent trials per condition for statistical
power, not as three deterministic, exactly-repeatable samples. This was already implicit
in the README's reproducibility caveat but is stated explicitly here.

**On "threats to validity" raised during planning:** earlier internal planning notes
(recovered from `research_plan.md`/`experiments.txt` in git history, now kept outside this
public repo — see `tool_name_internal/` on the author's machine) flagged that a related,
earlier experiment's "familiar name is worse when rules change" finding might be (a)
largely a `jq`-specific effect rather than general, and (b) confounded by the two
comparison arms not having equal flag/option availability, which could inflate the
real-name arm's error count independent of the rule change itself. This session's own
Experiments 1-5 were explicitly designed to test (a) across two structurally different
idioms (`jq`, `sed`) and found the effect replicates directionally across both, so it is
idiom-general at least for these two cases, not `jq`-only. Concern (b) (unequal flag
availability) does not apply to this session's own harness, which holds the primitive's
full interface fixed across conditions and varies only argument order/naming/documentation
— but it remains an open, unresolved caveat on the *earlier, separate* experiment line
referenced in Section 4's "Combined Conclusion," which this document does not independently
re-audit.

---

# 1. Experiment 1: Does Interference Reproduce for jq's "Sticky" Idiom?

## Hypothesis

Condition D's rejection of the user's hypothesis used `find`/`grep`, whose documented two-argument order is a comparatively **weak** real-world convention. The user's original hypothesis might still hold for commands with a genuinely strong, deeply-ingrained convention. `jq` is the canonical test case: real `jq` usage is near-universally `jq '<filter>' <file>` (filter first, file second) — a much "stickier" idiom than find/grep's ordering, called out in the earlier Experiment-C writeup as the single most likely driver of that study's "familiar name is worse" finding.

## Design

A new, self-contained primitive (`jq_filter` in `primitives.py`) extracts one top-level JSON field (`license`, `owner`, `last_updated`, `deprecated`) from one or more `meta.json` files. Two conditions, both using the real name `jq` (so naming familiarity is held constant — only documented **argument order** varies):

- **JQ-real**: documented order `(filter_expr, path)` — matches real jq exactly.
- **JQ-swap**: documented order `(path, filter_expr)` — the near-miss: same strong-prior name, opposite documented order.

8 existing tasks were reused verbatim, since their oracle values are exactly `meta.json` fields. An `old_form_grammar` detector flags whenever a JQ-swap call's arguments look like `(filter_expr, path)` — i.e., the model silently reverted to the real jq idiom despite the documented path-first order.

Two interfaces were tested: **Sequential** (JSON tool-calling, named parameters) and **Shell** (free-text command line, one-shot + one repair attempt).

Run against `gpt-6-luna` (via the Luna proxy), 8 tasks × 3 seeds × 2 conditions = 48 trials per interface (96 total).

## Results

| Interface | Condition | n | Success% | Avg tokens | Avg turns | old_form% |
|---|---|---|---|---|---|---|
| Sequential | JQ-real | 24 | 100.0% | 971.8 | 2.58 | 0.0% |
| Sequential | JQ-swap | 24 | 100.0% | 612.5 | 2.00 | 0.0% |
| Shell | JQ-real | 24 | 100.0% | 600.8 | 2.00 | 0.0% |
| Shell | JQ-swap | 24 | 100.0% | 741.5 | 2.21 | 0.0% |

Every one of the 8 tasks scored 3/3 correct in every condition × interface combination (32 cells, all 3/3). Zero errors, zero timeouts, zero instances of old-form grammar reversion in either interface.

## Interpretation

**The sticky-idiom hypothesis is rejected on both interfaces.** Even jq — the primitive most likely to produce a genuine "familiar name hurts" effect — shows no measurable success penalty and zero old-form reversion when its documented argument order is swapped, whether the model fills in named JSON parameters (sequential) or writes raw positional shell text (shell). This closes the main loophole in Condition D's original null result.

**Caveats:** single model (`gpt-6-luna`), modest sample (n=24 per cell), only 2 severity levels of jq-specific tasks, and the model always had the full documented manual present in-context on every turn plus an explicit repair loop.

---

# 2. Experiment 2: Does Compounding Multiple Rule Changes Produce an Effect? (Condition D2)

## Hypothesis

Condition D changed only **one** rule (argument order) for 2 of 5 primitives, and found no interference effect. Condition D2 "doses" the manipulation: it compounds **multiple simultaneous rule changes** on top of D's argument-order swap, to test whether a strong enough combined violation of real Unix conventions finally produces measurable interference.

## Design

Condition D2 extends D (`find`/`grep` argument-order swap) with additional simultaneous grammar changes layered onto the same two primitives. Run on the shell interface, 24 tasks × 3 seeds = 72 trials, against `gpt-6-luna`.

## Results

| Condition | n | Success% | Avg tokens | old_form% | delimiter_violation% |
|---|---|---|---|---|---|
| A-full (baseline, real names+grammar) | 72 | 62.5% | 1575 | 0.0% | — |
| D (single rule change) | 72 | 61.1% | 1915 | 0.0% | 0.0% |
| **D2 (dosed/compounded rule changes)** | 72 | **65.3%** | **2439** | **0.0%** | **0.0%** |

By tier (D2): T1 87.5%, T2 87.5%, T3 16.7% (n=24 each).

Failure breakdown (D2, 72 trials, 26 failures): 18 plain wrong answers, 8 `invalid_name` — zero attributable to grammar-order reversion.

## Interpretation

**Compounding the rule changes still does not reproduce the hypothesized interference effect.** D2's success rate (65.3%) is marginally *higher* than both A-full and D, and its 0% old-form-reversion rate exactly matches D's. The only cost signal is token usage, which rises further (2439 vs. D's 1915). D2's failures are concentrated in Tier-3 (16.7%), the same structural-limitation failure mode (shell grammar can't express 2-step joins) seen across every condition in every experiment in this study.

---

# 3. Experiment 3: Does Condition D's Null Result Hold on the Sequential Interface Too?

## Rationale

Condition D was originally tested only on the shell interface. This experiment ports it to the sequential (multi-turn JSON tool-calling) interface, to test whether the model's own prior tool calls (visible as in-context few-shot) might make a documented-order slip more "sticky."

## Design

Condition D (swapped argument order for `find`/`grep`) ported to the sequential harness. Same 24 tasks × 3 seeds = 72 trials.

## Results

| Interface | Condition | n | Success% | Avg tokens | old_form% |
|---|---|---|---|---|---|
| Shell | D | 72 | 61.1% | 1915 | 0.0% |
| **Sequential** | **D** | **72** | **84.7%** | **2344** | **2.8%** |
| Sequential | A-full (baseline) | 72 | 76.4%* | — | — |

*A-full sequential baseline from the original Study 1 report, included for reference.

By tier (D, sequential): T1 87.5%, T2 95.8%, T3 70.8%.

11 of 72 trials failed, all plain wrong answers. 2 of 72 trials (2.8%) showed `old_form_grammar=True` — a brief revert to the real `find`/`grep` order before self-correcting via the tool-call error-feedback loop.

## Interpretation

**Condition D's performance is not just preserved on the sequential interface — it exceeds every baseline tested there**, including A-full's own sequential score (84.7% vs. 76.4%), and dramatically outperforms D's own shell-interface result (84.7% vs. 61.1%). The 2.8% old-form reversion rate is the **only** nonzero old-form signal across Experiments 1-3 combined — both instances self-corrected and did not cause a wrong final answer, best read as rare, inconsequential noise.

**Conclusion:** the near-miss-grammar hypothesis is rejected on the sequential interface just as clearly as on shell.

---

# 4. Combined Conclusion: The Familiar-Name-With-Wrong-Grammar Hypothesis Does Not Hold

## The user's hypothesis, restated

Using real Unix tool names should make agents follow grammar correctly — but if the documented grammar for that familiar name differs slightly from the real-world convention the model already knows, the model's prior knowledge should actively interfere, producing WORSE outcomes than simply using an unfamiliar name taught the same (correct) grammar from scratch.

## Three loopholes closed, three null results

| # | Loophole being tested | Result |
|---|---|---|
| 1 | Maybe find/grep's convention is just too weak — a genuinely **sticky idiom** (jq) would show the effect | **No.** jq-swap: 100% success, 0% old-form reversion, on BOTH interfaces (96 trials) |
| 2 | Maybe one rule change is too mild — **compounding multiple simultaneous changes** (D2) would show the effect | **No.** D2: 65.3% success (slightly *above* baseline), 0% old-form reversion (72 trials) |
| 3 | Maybe the effect only manifests on the **sequential interface** specifically | **No.** D on sequential: 84.7% success (*above* every baseline), 2.8% transient old-form reversion that self-corrected (72 trials) |

Across all **240 additional trials** run for these three follow-ups, there is **no condition, no interface, and no severity level** at which a familiar name with a documented grammar deviation performs worse than the correctly-documented baseline.

## Why the hypothesis keeps failing in this harness

This harness always puts the full, corrected documentation directly in context on every turn, with an explicit contrastive statement where applicable, and always gives the model at least one explicit error-feedback/repair opportunity before a trial is scored as failed. This combination appears sufficient to override whatever pretraining-idiom pull exists, even for jq.

## Practical takeaway

For an agent-tool-design decision between "reuse a real tool name but document slightly different argument semantics" vs. "invent a new name and teach it from scratch," this study's data consistently favors reusing the real name, provided the documentation is unambiguous and in-context, and some error-correction loop exists. (NOTE: this conclusion was later substantially refined by Experiment 4 — see below — once documentation was deliberately degraded/removed.)

---

# 5. Experiment 4: Documentation Robustness (Full Run, 192 trials)

**Design:** Crossed `doc_level ∈ {terse, none}` × `interface ∈ {sequential, shell}` × `condition ∈ {JQ-real, JQ-swap}` × 8 jq tasks × 3 seeds = 192 trials. `full`-doc baseline reused from Experiment 1. `terse` = signature + one generic sentence, no example. `none` = tool name only, zero signature/description.

**Hypothesis under test:** if Experiments 1-3's null results were due to full in-context documentation overriding any pretraining "sticky jq idiom" pull, stripping documentation should reveal that pull.

## Aggregate results

| interface | doc_level | condition | n | success% | old_form% | avg_turns | avg_tokens |
|---|---|---|---|---|---|---|---|
| sequential | full (baseline) | JQ-real | 24 | 100.0% | 0.0% | — | — |
| sequential | full (baseline) | JQ-swap | 24 | 100.0% | 0.0% | — | — |
| sequential | terse | JQ-real | 24 | 87.5% | 0.0% | 8.6 | 4590 |
| sequential | terse | JQ-swap | 24 | 87.5% | 0.0% | 5.9 | 1887 |
| sequential | **none** | JQ-real | 24 | 95.8% | 0.0% | 6.2 | 2458 |
| sequential | **none** | **JQ-swap** | 24 | 83.3% | **62.5%** | 7.8 | 3637 |
| shell | full (baseline) | JQ-real | 24 | 100.0% | 0.0% | — | — |
| shell | full (baseline) | JQ-swap | 24 | 100.0% | 0.0% | — | — |
| shell | terse | JQ-real | 24 | 4.2% | 0.0% | 2.0 | 960 |
| shell | terse | JQ-swap | 24 | 16.7% | 0.0% | 2.2 | 1110 |
| shell | none | JQ-real | 24 | 0.0% | 0.0% | 2.0 | 1729 |
| shell | none | JQ-swap | 24 | 0.0% | 0.0% | 2.0 | 1838 |

## Finding 1: the hypothesis is confirmed, but only at the "none" doc level on the sequential interface

`sequential/none/JQ-swap` is the only cell in the entire four-experiment study where `old_form_grammar` rises above ~0%: **62.5% of trials** (15/24) show the model silently reverting to real jq's filter-first calling convention despite the schema requiring path-first. At `terse` (just a bare signature line, still naming args in order), the model follows the documented order perfectly (0% old-form) — a one-line signature was sufficient to override the real-jq prior.

Within `sequential/none/JQ-swap`, trials where the model reverted succeeded 73.3% of the time vs. 100% when it stuck to the schema order — confirming the reversion is a genuine performance-relevant error, not a harmless artifact.

## Finding 2: the shell interface shows a severe, condition-independent collapse under degraded docs — a confound, not evidence for the idiom hypothesis

Shell success collapses to near-zero under both `terse` (4.2%/16.7%) and `none` (0%/0%) for both conditions. Error-tag breakdowns show this is driven by `primitive_error`, `wrong_args`, and `invalid_name` roughly evenly — a general documentation-completeness effect on raw shell-syntax generation, not jq-idiom-specific interference. Because near-zero success leaves almost no completed trials to check for old-form reversion, the shell interface cannot meaningfully speak to the idiom-interference hypothesis under degraded docs at this repair budget.

## Interpretation

The suppressing ingredient is specifically **any explicit signature/argument-order statement**, not worked examples, contrastive warnings, or repair loops. A terse one-line signature was fully sufficient to prevent reversion in the sequential interface; it was only when *all* signature information was removed that the real-jq prior reasserted itself in 62.5% of trials. This refines Experiments 1-3's conclusion: the interference effect is real and substantial, but requires a near-total documentation vacuum to manifest.

---

# 6. Experiment 4b: Three Follow-Up Refinements to the Documentation-Robustness Finding

Three targeted follow-ups to Experiment 4:

1. **Shell floor-effect fix** — rerun shell with a 3-attempt repair budget (vs. original 1) across all degraded doc levels.
2. **Intermediate doc levels** — `named` (real parameter names, zero prose) and `ordered_generic` (generic names, one sentence stating the order), bracketing `terse` → `none`.
3. **Tighter CI** — 7 more seeds (n: 24 → 80) on `sequential/none/{JQ-real,JQ-swap}`.

All three ran as 400 additional trials.

## 1. Shell floor-effect: fixed, but reveals a second, syntax-level sticky-idiom effect

| doc_level | condition | n | success% (repair=3) | success% (repair=1, Exp4) | old_form% |
|---|---|---|---|---|---|
| terse | JQ-real | 24 | **37.5%** | 4.2% | 0% |
| terse | JQ-swap | 24 | **83.3%** | 16.7% | 0% |
| named | JQ-real | 24 | 12.5% | — | 0% |
| named | JQ-swap | 24 | 54.2% | — | 0% |
| ordered_generic | JQ-real | 24 | 4.2% | — | 0% |
| ordered_generic | JQ-swap | 24 | 12.5% | — | 0% |
| none | JQ-real | 24 | 12.5% | 0% | 0% |
| none | JQ-swap | 24 | 0.0% | 0% | **8.3%** |

A larger repair budget substantially recovers shell success at `terse` (4.2%→37.5% JQ-real; 16.7%→83.3% JQ-swap) — the original floor effect *was* a repair-budget artifact. But inspecting failed command strings revealed **why** terse/JQ-real still fails 62.5% of the time: lacking a worked example, the model reaches for real jq's full filter-expression syntax (`paths(objects) | select(...)`, globs, flags) rather than the toy harness's plain-field-token convention — a sticky-idiom effect invisible to `old_form_grammar` (which only checks argument order).

## 2. Intermediate doc levels: real parameter *names* are the suppressing ingredient, not an order statement

| doc_level | condition | n | success% | old_form% |
|---|---|---|---|---|
| terse (Exp4) | JQ-swap | 24 | 87.5% | 0% |
| **named** | JQ-swap | 24 | 100% | **0%** |
| **ordered_generic** | JQ-swap | 24 | 75.0% | **87.5%** |
| none (Exp4) | JQ-swap | 24 | 83.3% | 62.5% |

- `named` (real names `path`/`filter_expr`, empty description) → **0% reversion**, matching `terse`.
- `ordered_generic` (generic `arg1`/`arg2`, prose stating "argument 1 is the file path; argument 2 is the filter expression") → **87.5% reversion**, exceeding even `none`'s 62.5%.

**Conclusion: it is the presence of the real semantic parameter names in the schema itself — not an explicit statement of argument order — that suppresses the sticky-jq-idiom reversion.** A prose sentence correctly stating the order did *worse* than having no information at all (87.5% vs 62.5%) — at this n=24, flagged as provisional (and later replicated in Exp4c, see below).

## 3. Tighter CI on the headline reversion rate: confirmed, now n=80

| condition | n | success% | old_form% | 95% Wilson CI on old_form% |
|---|---|---|---|---|
| JQ-real | 80 | 96.2% | 0.0% | — |
| JQ-swap | 80 | 90.0% | **52.5%** | **[41.7%, 63.1%]** |

The point estimate moved from 62.5% (n=24) to 52.5% (n=80) — within noise, with a 95% CI comfortably bounded away from 0% and 100%: a real, substantial, partial (not universal) reversion effect.

## Overall synthesis

```
none < ordered_generic < named ≈ terse < full
(52.5% reversion) (87.5%!) (0%)    (0%)    (0%)
```

The non-monotonicity at `ordered_generic` is the most interesting result of this follow-up: more information (an order statement) was *not* better than less (nothing) at suppressing interference. The one factor that cleanly flips reversion off is the literal presence of real parameter names in the tool's calling signature — independent of accompanying prose.

On the shell side, the floor effect is resolved with a larger repair budget, but reveals a second, orthogonal failure mode specific to CLI-style interfaces — reversion to real jq's complex filter *syntax* rather than its argument *order* — not detected by `old_form_grammar`. This directly motivated Experiment 4c (below).

---

# 7. Experiment 4c: Shell Syntax-Reversion Instrumentation & ordered_generic Replication

Two follow-ups to Exp4b's two most important open threads:

1. **Instrument the shell interface's syntax-complexity reversion effect** — add a `detect_syntax_reversion()` regex-based detector (10 markers of real-jq-only syntax: `select(`, `paths(`, `getpath(`, `..`, `?==`, `map(`, CLI flags, `**` globs, `[] |`), wire it into every shell attempt (initial + repairs), and persist both the flag and the raw `command_log` across the full doc_level × condition matrix.
2. **Replicate the `ordered_generic` paradox** at higher n (Exp4b's n=24 found `ordered_generic` reversion 87.5% > `none`'s 62.5%).

Both ran as 304 additional trials (192 + 112).

## 1. Syntax-complexity reversion: a near-universal first instinct, but highly consequential only at `terse`

Shell interface, repair budget = 3, all four degraded doc levels, both conditions (192 trials):

| doc_level | condition | n | success% | old_form% | syntax_rev% (any attempt) | avg_turns |
|---|---|---|---|---|---|---|
| terse | JQ-real | 24 | 41.7% | 0.0% | 70.8% | 4.2 |
| terse | JQ-swap | 24 | 70.8% | 0.0% | 54.2% | 4.1 |
| named | JQ-real | 24 | 12.5% | 0.0% | 100.0% | 4.1 |
| named | JQ-swap | 24 | 50.0% | 0.0% | 87.5% | 4.4 |
| ordered_generic | JQ-real | 24 | 0.0% | 0.0% | 100.0% | 4.0 |
| ordered_generic | JQ-swap | 24 | 8.3% | 8.3% | 91.7% | 4.1 |
| none | JQ-real | 24 | 4.2% | 0.0% | 100.0% | 4.0 |
| none | JQ-swap | 24 | 8.3% | 4.2% | 83.3% | 4.1 |

Collapsed by doc_level (n=48, both conditions pooled), with 95% Wilson CI:

| doc_level | n | success% | syntax_rev% | 95% CI |
|---|---|---|---|---|
| terse | 48 | 56.2% | 62.5% | [48.4%, 74.8%] |
| named | 48 | 31.2% | 93.8% | [83.2%, 97.9%] |
| ordered_generic | 48 | 4.2% | 95.8% | [86.0%, 98.8%] |
| none | 48 | 6.2% | 91.7% | [80.4%, 96.7%] |

**Finding A:** syntax-complexity reversion is the model's dominant first instinct at every doc level except `terse`, including levels that give real parameter names (`named`) or an explicit order statement (`ordered_generic`). Neither ingredient — which fully suppresses *argument-order* reversion elsewhere — suppresses *syntax*-level reversion. Only `terse`'s one-sentence generic task description meaningfully reduces it (62.5%).

**Finding B:** syntax reversion matters far more at `terse` than at any more-degraded level. First-attempt-only split:

| doc_level | first-attempt reverted? | n | success% |
|---|---|---|---|
| terse | No | 24 | **79.2%** |
| terse | Yes | 24 | 33.3% |
| named | No | 10 | 20.0% |
| named | Yes | 38 | 34.2% |
| ordered_generic | No | 5 | 0.0% |
| ordered_generic | Yes | 43 | 4.7% |
| none | No | 21 | 0.0% |
| none | Yes | 27 | 11.1% |

At `terse`, avoiding first-attempt syntax reversion very nearly doubles success (79.2% vs 33.3%) — clear evidence this is a real, costly failure mode. At the more-degraded levels, success stays near-floor regardless, because other failure modes (missing argument-order/field-vocabulary info) already dominate.

**Interpretation:** the shell interface's "sticky jq idiom" problem has (at least) two independent, additive components: (1) argument-*order* reversion (`old_form_grammar`, essentially absent in shell since floor effects pre-empt it) and (2) filter-*syntax* reversion (`syntax_reversion`, pervasive across the shell interface, only suppressed by a generic task description, not by names/order info). Each requires different in-context signal to override.

**Methodological caveat:** `detect_syntax_reversion` is a regex heuristic, validated against 6 hand-labeled commands (100% agreement) and spot-checked against ~30 trials with `syntax_reversion=True AND correct=True` — confirmed to reflect genuine self-correction (revert → error → simple syntax → success), not false positives.

## 2. The `ordered_generic` paradox replicates at higher n — and strengthens

Sequential interface, `ordered_generic` only, 7 new seeds (4-10), both conditions (112 trials):

| condition | n (new seeds only) | success% | old_form% |
|---|---|---|---|
| JQ-real | 56 | 66.1% | 0.0% |
| JQ-swap | 56 | 82.1% | 83.9% |

Combined with Exp4b's original n=24 for total n=80 per condition:

| condition | n (combined) | success% | old_form% | 95% Wilson CI |
|---|---|---|---|---|
| JQ-real | 80 | 67.5% | 0.0% | [0.0%, 4.6%] |
| **JQ-swap** | **80** | **80.0%** | **85.0%** | **[75.6%, 91.2%]** |

**The paradox replicates and the point estimate rises slightly: 87.5% (n=24) → 85.0% (n=80).** This CI [75.6%, 91.2%] does not overlap with `none`'s own combined-n=80 estimate of 52.5% (CI [41.7%, 63.1%]) — ruling out the original finding as a small-sample fluke.

**Timeout-exclusive breakdown (addressing SKEPTIC_REVIEW.md #3):** the raw `old_form%` figures above count every trial, including ones that hit the 15-turn ceiling (9,500-14,600 total tokens — clearly stuck-loop behavior, not a single confidently-wrong answer). Re-examining the same combined-n=80 datasets with all timed-out trials excluded:

| doc_level / condition | n | timeouts | timeout% | old_form% (raw, all n) | old_form% (excl. timeouts) |
|---|---|---|---|---|---|
| none / JQ-real | 80 | 0 | 0.0% | 0.0% | 0.0% (0/80) |
| none / JQ-swap | 80 | 3 | 3.8% | 52.5% | **50.6%** (39/77) |
| ordered_generic / JQ-real | 80 | 17 | 21.2% | 0.0% | 0.0% (0/63) |
| ordered_generic / JQ-swap | 80 | 10 | 12.5% | 85.0% | **82.9%** (58/70) |

**The paradox survives removing timeouts entirely** (82.9% vs. 50.6%, still far apart and in the same direction), so it is not *solely* a stuck-loop artifact. But timeouts are themselves markedly more frequent at `ordered_generic` than at `none` for both conditions (JQ-real: 21.2% vs. 0.0%; JQ-swap: 12.5% vs. 3.8%), and they account for a nontrivial share of the raw reversion count at `ordered_generic`/JQ-swap specifically (raw 85.0% → 82.9% excluding timeouts is a modest drop, but the elevated timeout rate itself is informative: it suggests the `ordered_generic` prose — a role-based order statement over generic slots — induces more generalized confusion, of which both "loops until the turn ceiling" and "silently reverts to the real-jq order" are two symptoms, not two independent phenomena). **Revised interpretation: the `ordered_generic`-worse-than-`none` paradox is a real, non-timeout-dependent effect on argument-order reversion specifically, but the raw headline numbers somewhat overstate its magnitude and should always be reported timeout-exclusive going forward; the elevated timeout rate at `ordered_generic` is itself a related, second symptom of the same underlying confusion, not a separate confound to be explained away.**

**Interpretation, updated:** telling the model "argument 1 is X; argument 2 is Y" in prose, while keeping schema parameter names generic, is reliably *worse* at preventing reversion than giving no order information at all. A plausible mechanism: role-based prose forces the model to translate abstract roles onto generic slots at call time — a weaker binding than reading real, persistent, semantically-loaded parameter names directly off the schema — and in reasoning about "which role goes where," the model may lean more on its well-known real-jq ordering than it would with no order information to reason about at all.

Full picture across all five doc levels:

```
none (52.5%) < ordered_generic (85.0%) ... [paradox]
named (0%) ≈ terse (0%) ≈ full (0%)
```

## Overall synthesis across Exp4/4b/4c

| Effect | Measured by | What suppresses it |
|---|---|---|
| Argument-order reversion (sequential) | `old_form_grammar` | Real parameter names in schema (not order statements) |
| Filter-syntax-complexity reversion (shell) | `syntax_reversion` | A one-sentence task description (not names or order) |
| General CLI-syntax-generation floor effect (shell) | raw success% | Larger repair budget (partially) |

No single documentation ingredient suppresses all three failure modes simultaneously — each sticky-idiom symptom responds to a different, specific piece of in-context information. The shell interface remains dominated by syntax-generation difficulty even with a 3x repair budget, topping out around 70% success even at the best-case `terse`/JQ-swap cell.

---

# 8. Experiment 5: Idiom Generalization — sed

## Hypothesis

All prior experiments (1-4c) tested a single idiom: `jq`'s `<filter> <file>` argument order. Does the sticky-idiom / documentation-robustness pattern found for `jq` generalize to a second, structurally distinct idiom with its own equally strong real-world convention — or is it `jq`-specific?

## Design

A new primitive, `sed_filter` (P7 in `primitives.py`), mirrors `jq_filter`'s toy semantics (same 8 tasks, same `meta.json` field-extraction oracles) but models sed's calling convention instead: a **script** (`"s/FIELD//p"`, restricted to 4 supported field expressions) comes first, followed by a **file/path** second — e.g. `sed 's/foo/bar/' file.txt`, mirroring real sed's substitution-script-first idiom, which is just as strong a prior as jq's filter-first idiom but syntactically distinct (regex-substitution-style vs. dot-path-style).

Two conditions (naming held constant at the real name `sed`; only documented argument order varies):

- **SED-real**: documented order `(script, path)` — matches real sed exactly.
- **SED-swap**: documented order `(path, script)` — the near-miss, opposite order.

Harness (`exp5_sed.py`, 665 lines) is a self-contained module combining Exp1's dispatch pattern and Exp4's `doc_level`-parameterized manual-rendering matrix, deliberately **not** wired into the shared `naming.py`/`dispatch.py` P1-P5 tables. 16/16 mock-client unit tests (`tests/test_exp5_sed_mock.py`) passed before any live run. `doc_level ∈ {none, ordered_generic}` use generic `arg1`/`arg2` schema parameter names (never real `script`/`path` names) to prevent the JSON schema's `required`-array ordering from leaking the correct argument order regardless of description text — same leak-prevention rule established in Exp4.

Both **sequential** (JSON tool-calling) and **shell** (free-text command line, 1 repair attempt) interfaces were tested, crossed with `doc_level ∈ {terse, none}` × `condition ∈ {SED-real, SED-swap}` × 8 tasks × 3 seeds = 192 trials, run against `gpt-6-luna` via the Luna proxy (same model/endpoint as all prior experiments; cross-model replication explicitly deferred).

A 16-trial pilot (2 doc_levels × 2 interfaces × 2 conditions × 2 tasks × 1 seed) was run first to validate the harness end-to-end against the live proxy before committing to the full 192-trial run; it completed cleanly with sensible directional results (higher reversion under `none`+`shell` than `terse`+`sequential`), confirming the harness was sound.

## Results

**Argument-order reversion (`old_form_grammar`, SED-swap only — model ignores the documented path-first order and reverts to real sed's script-first order):**

| doc_level | interface | n | reversion rate |
|---|---|---|---|
| none | sequential | 24 | 54.2% |
| none | shell | 24 | 0.0% |
| terse | sequential | 24 | 0.0% |
| terse | shell | 24 | 0.0% |

**Syntax-complexity reversion (`syntax_reversion`, shell interface only — model emits real sed regex/substitution syntax instead of the restricted toy script format):**

| doc_level | condition | n | reversion rate |
|---|---|---|---|
| none | SED-real | 24 | 95.8% |
| none | SED-swap | 24 | 87.5% |
| terse | SED-real | 24 | 25.0% |
| terse | SED-swap | 24 | 0.0% |

**Raw task success (`correct`):**

| doc_level | interface | condition | n | success% |
|---|---|---|---|---|
| none | sequential | SED-real | 24 | 95.8% |
| none | sequential | SED-swap | 24 | 100.0% |
| none | shell | SED-real | 24 | 0.0% |
| none | shell | SED-swap | 24 | 0.0% |
| terse | sequential | SED-real | 24 | 87.5% |
| terse | sequential | SED-swap | 24 | 83.3% |
| terse | shell | SED-real | 24 | 0.0% |
| terse | shell | SED-swap | 24 | 0.0% |

Shell-interface timeout rate was 100% at `none` doc_level and 100% at `terse` doc_level as well (48/48 each) — compare to jq's Exp4 shell timeout rates of 100% (`none`) and 89.6% (`terse`). Error-tag breakdown for shell failures: `primitive_error` 65, `invalid_name` 23, `wrong_args` 8 — i.e. the dominant failure mode was the model calling `sed_filter`'s restricted toy script format with a real, free-form sed regex/address expression (e.g. `sed -n '/pkg-113/,+10p' * */* */*/*`), which the toy primitive correctly rejects as an unsupported script.

## Interpretation

**The argument-order reversion pattern replicates directionally for the sequential interface**, though at lower magnitude than jq's Exp4 (`none`/sequential: sed 54.2% vs jq 62.5%) — both show the characteristic `none` → nonzero, `terse` → zero pattern, i.e. even a one-sentence description fully suppresses order-reversion on the sequential interface for both idioms.

**The syntax-complexity reversion pattern is dramatically stronger for sed than for jq.** Where jq's shell syntax-reversion topped out around 70-100% even at the most degraded doc levels (Exp4c), sed's shell interface essentially never produces a working toy-script call once documentation is degraded to `none` (95.8%/87.5% reversion, 0% success) — sed's real-world idiom is apparently "stickier" in the shell/free-text setting than jq's, likely because the model has a much richer, more generalized prior for free-form sed regex/address syntax (applicable to arbitrary files/patterns) than it does for jq's narrower dot-path filter syntax, making it far more tempting (and far more fluently generated) to fall back on real sed usage patterns when given minimal constraints. Notably, **even `terse` documentation does not fully suppress this for SED-real** (25% reversion, vs. 0% for jq's worst terse/shell cell) — a genuinely idiom-specific finding, not a replication of jq's exact numbers.

**The shell interface is categorically unusable for sed under both doc levels tested here** (0% success, 100% timeout) — a floor effect even more severe than jq's worst case, confirming that sed's real syntax is harder for the model to resist/override than jq's. This suggests the general conclusion from Exp4/4b/4c ("no single documentation ingredient suppresses all failure modes simultaneously") generalizes, but the *relative severity* of each sticky-idiom symptom is idiom-specific — sed's shell/free-text failure mode is more severe, while its sequential/order-reversion failure mode is comparably severe to jq's.

**Overall**: the core qualitative finding — that strong real-world idioms cause measurable "sticky" reversion to the familiar convention when documentation conflicts with it, with severity inversely related to documentation detail — **generalizes beyond jq to a second, structurally distinct idiom**. The specific magnitudes and the relative balance between order-reversion vs. syntax-reversion failure modes are idiom-dependent, suggesting future idiom additions should continue to report both metrics separately rather than assuming a universal severity ranking.

## Data & Code (Experiment 5)

Raw trial-level data: `tool_name/results/pilot_exp5_sed.jsonl` (16-trial pilot), `tool_name/results/exp5_sed.jsonl` (192-trial full run). Harness: `tool_name/src/exp5_sed.py`. Primitive: `sed_filter` (P7) in `tool_name/src/primitives.py`. Unit tests: `tool_name/tests/test_exp5_sed_mock.py` (16/16 passing). Run against `gpt-6-luna` via the Luna proxy — same model as all prior experiments; multi-model replication remains the explicitly deferred next step for the overall study.

---

# 9. Experiment 6: Cross-Model Replication Attempt (Model Identity Unverified)

**Disclosure up front (see Section 0 #2 for full detail):** this experiment was run with `--model claude-sonnet-5-5` against the same Luna-proxy endpoint used throughout this study, intending to replicate Exp4/4b/4c's findings on a second model. `gpt-6-luna` and `claude-sonnet-5-5` are not real, publicly documented model identifiers; the harness's `llm_client.py` only ever instantiates the official `anthropic.Anthropic()` SDK client with no provider-switching or model-name validation logic; the result rows from this run (and all prior runs) did not record which model string the proxy actually served; and several trials show 300+ second latencies for short completions, consistent with a slow intermediary proxy rather than a genuinely distinct model. **The numbers below are real, measured outcomes of the trials that were run — only the claim that they come from a different, verified model family is unconfirmed.** All results below are therefore presented as a replication *attempt* under the model name requested via `--model`, not as a confirmed cross-model finding. Every run script has since been updated to log the actual `model` string passed to the SDK for future verifiability (Section 0 #2).

## Hypothesis

All prior experiments (1-5) used a single model, nominally `gpt-6-luna`, via the Luna proxy (model identity likewise unverified for those runs — see Section 0 #2). Does the headline "sticky idiom" reversion finding — and specifically the `ordered_generic`-worse-than-`none` paradox (Exp4b/4c) — replicate under a different `--model` argument, or is it an artifact specific to whatever model actually served the `gpt-6-luna`-labeled runs?

## Design

Cost-conscious replication targeting only the two paper-critical findings from Exp4/4b/4c (not a full re-run of the ~1,200-trial original matrix): **sequential interface only** (shell was excluded — it is dominated by a general syntax-floor effect rather than idiom-specific interference, and is the most expensive/least informative interface to replicate), `doc_level ∈ {terse, none, ordered_generic}` (the three decisive cells: `terse` as the near-zero-reversion baseline, `none` as the original 52.5% reversion finding, `ordered_generic` as the 85.0% paradox finding), both conditions (`JQ-real`, `JQ-swap`), all 8 jq tasks, 3 seeds = **144 trials** (vs. 400+ trials for the equivalent original-model coverage).

`--model` argument: `claude-sonnet-5-5`, accessed via the same Luna proxy endpoint/credential used throughout this study (`--base-url https://lm4j1o05od.execute-api.us-east-1.amazonaws.com/prod`), with only `--model` changed from the prior runs' value. **This string was not independently verified against any model served by the proxy** — the harness passes it through to the Anthropic SDK client constructor without validation, and the proxy's actual routing behavior is opaque from this repo's artifacts. A 1-trial smoke test was run first to confirm the request/response cycle completed end-to-end before committing to the full run; this confirms the proxy accepted and responded to the request, not that it used a specific named model. Harness: `exp4_doc_robustness.py`, completely unmodified — confirming the `old_form_grammar` detector (`_looks_like_filter`/`_looks_like_path` heuristics in `dispatch_jq`, `exp1_jq.py:219-224`) runs identically regardless of which model actually produced the completions.

## Results

| doc_level | condition | n | success% | old_form% | 95% Wilson CI on old_form% |
|---|---|---|---|---|---|
| terse | JQ-real | 24 | 95.8% | 0.0% | [0.0%, 13.8%] |
| terse | JQ-swap | 24 | 91.7% | 0.0% | [0.0%, 13.8%] |
| none | JQ-real | 24 | 95.8% | 0.0% | [0.0%, 13.8%] |
| **none** | **JQ-swap** | 24 | 83.3% | **0.0%** | **[0.0%, 13.8%]** |
| ordered_generic | JQ-real | 24 | 91.7% | 0.0% | [0.0%, 13.8%] |
| **ordered_generic** | **JQ-swap** | 24 | 91.7% | **0.0%** | **[0.0%, 13.8%]** |

All 12 failures across the full 144-trial run were `primitive_error` (task-level mistakes, e.g. wrong field/path), not argument-order reversion. All non-English/odd-formatting outputs (e.g. one Chinese-language final answer) were still graded correct by the oracle-matching logic and are a model-specific quirk, not a harness issue.

## Interpretation

**The run made under `--model claude-sonnet-5-5` shows zero argument-order reversion in every cell tested, including the two cells where the `gpt-6-luna`-labeled runs showed their strongest effects**: `none`/JQ-swap (gpt-6-luna-labeled: 52.5% reversion, 95% CI [41.7%, 63.1%], n=80) and `ordered_generic`/JQ-swap (gpt-6-luna-labeled: 85.0% reversion, 95% CI [75.6%, 91.2%], n=80). This run's 95% CIs (upper bound 13.8% in both cells) do not overlap with either gpt-6-luna-labeled estimate — assuming the two labels do in fact correspond to two different underlying models or configurations, this would be a genuine, well-powered divergence; however, **because neither label was independently verified against the proxy's actual behavior, an equally plausible explanation is that the two "model" labels were routed to the same backend, or to backends that differ in some way other than the one assumed** (e.g. a difference in default sampling/temperature settings, system-prompt handling, or proxy-side caching behavior, rather than a genuine model-family difference).

**What can be said with confidence:** the two sets of 144 and (combined) 320 trials, run at different times with different `--model` argument values against the same proxy endpoint, produced measurably different reversion rates. **What cannot be said with confidence from this repo's artifacts alone:** that this difference reflects "gpt-6-luna vs. claude-sonnet-5-5" as two distinct, identifiable model families, since neither name is a verified, real model identifier and no result row from either run recorded an independently-checkable model string.

**Paper framing implication (revised):** this result should be reported as a **replication attempt whose outcome diverged from the original runs**, not as a confirmed cross-model finding. It is still useful evidence that *something* about the later run's configuration (named `claude-sonnet-5-5` in the invocation, unverified) suppressed the reversion effect seen in the earlier runs (named `gpt-6-luna`) — this is suggestive and worth following up with a properly identity-verified re-run (e.g. against the official, directly-authenticated Anthropic API with the actual model string logged per-row, as the harness now supports) before any claim of genuine cross-model generalization (or its absence) is published. Until then, the sticky-idiom reversion effect and the `ordered_generic` paradox should be described as established for whichever model(s) actually served Experiments 1-5, with this section's divergence flagged as an open, unresolved follow-up question rather than a settled negative result.

## Data & Code (Experiment 6)

Raw trial-level data: `tool_name/results/exp4_sonnet_crossmodel.jsonl` (144 trials; rows from this run predate the `model`-field logging fix in Section 0 #2 and do not themselves record a verified model string). Harness: `tool_name/src/exp4_doc_robustness.py` (unmodified from Exp4b/4c, only `--model claude-sonnet-5-5` changed in the invocation). Accessed via the same Luna proxy credential/endpoint used in all prior experiments; the proxy's internal routing/model-identity behavior is not independently verifiable from this repo.

---

## Data & Code (All Experiments)

All raw trial-level data: `tool_name/results/*.jsonl` (see individual sections above for specific filenames per experiment). Harness code: `tool_name/src/exp1_jq.py`, `exp4_doc_robustness.py` (the latter extended across Exp4/4b/4c with `doc_level`-parameterized manual renderers, `shell_max_repairs`, and `detect_syntax_reversion` instrumentation; reused unmodified in Exp6 for cross-model replication), `exp5_sed.py` (Experiment 5, self-contained). Unit tests: `tool_name/tests/test_harnesses_mock.py` (9/9 passing throughout), `tool_name/tests/test_exp5_sed_mock.py` (16/16 passing).
