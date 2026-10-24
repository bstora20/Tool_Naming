# Tool-Naming / Grammar-Interference Study: Compiled Results (Experiments 1-5)

**Project:** tool_name
**Compiled:** 2026-10-14 (updated 2026-10-20)

This file compiles every experiment report from the "Three Follow-Up Experiments" line of work into a single document, in order. Each section was originally written up individually; see the Majk knowledge base (conversation `084e2367-6b8d-450d-8760-573d056cb3f4`) for the live, linked versions.

---

## Contents

1. Experiment 1: jq Sticky-Idiom Test (Sequential + Shell)
2. Experiment 2: Dosed/Compounded Rule Changes (Condition D2)
3. Experiment 3: Condition D on the Sequential Interface
4. Combined Conclusion (Experiments 1-3)
5. Experiment 4: Documentation Robustness
6. Experiment 4b: Three Follow-Up Refinements
7. Experiment 4c: Shell Syntax-Reversion Instrumentation & ordered_generic Replication
8. Experiment 5: Idiom Generalization — sed
9. Experiment 6: Cross-Model Replication — claude-sonnet-5-5

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
| A-full (baseline, real names+grammar) | 72 | 61.1% | 1575 | 0.0% | — |
| D (single rule change) | 72 | 61.1% | 1915 | 0.0% | 0.0% |
| **D2 (dosed/compounded rule changes)** | 72 | **63.9%** | **2439** | **0.0%** | **0.0%** |

By tier (D2): T1 87.5%, T2 87.5%, T3 16.7% (n=24 each).

Failure breakdown (D2, 72 trials, 26 failures): 18 plain wrong answers, 8 `invalid_name` — zero attributable to grammar-order reversion.

## Interpretation

**Compounding the rule changes still does not reproduce the hypothesized interference effect.** D2's success rate (63.9%) is marginally *higher* than both A-full and D, and its 0% old-form-reversion rate exactly matches D's. The only cost signal is token usage, which rises further (2439 vs. D's 1915). D2's failures are concentrated in Tier-3 (16.7%), the same structural-limitation failure mode (shell grammar can't express 2-step joins) seen across every condition in every experiment in this study.

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
| 2 | Maybe one rule change is too mild — **compounding multiple simultaneous changes** (D2) would show the effect | **No.** D2: 63.9% success (slightly *above* baseline), 0% old-form reversion (72 trials) |
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

# 9. Experiment 6: Cross-Model Replication — claude-sonnet-5-5

## Hypothesis

All prior experiments (1-5) used a single model, `gpt-6-luna`, via the Luna proxy. Does the headline "sticky idiom" reversion finding — and specifically the `ordered_generic`-worse-than-`none` paradox (Exp4b/4c) — replicate on a different model family, or is it an artifact specific to `gpt-6-luna`?

## Design

Cost-conscious replication targeting only the two paper-critical findings from Exp4/4b/4c (not a full re-run of the ~1,200-trial original matrix): **sequential interface only** (shell was excluded — it is dominated by a general syntax-floor effect rather than idiom-specific interference, and is the most expensive/least informative interface to replicate), `doc_level ∈ {terse, none, ordered_generic}` (the three decisive cells: `terse` as the near-zero-reversion baseline, `none` as the original 52.5% reversion finding, `ordered_generic` as the 85.0% paradox finding), both conditions (`JQ-real`, `JQ-swap`), all 8 jq tasks, 3 seeds = **144 trials** (vs. 400+ trials for the equivalent original-model coverage).

Model: `claude-sonnet-5-5`, accessed via the same Luna proxy endpoint/credential used throughout this study (`--base-url https://lm4j1o05od.execute-api.us-east-1.amazonaws.com/prod`), with only `--model` changed. A 1-trial smoke test was run first to confirm the model name and endpoint combination worked end-to-end before committing to the full run. Harness: `exp4_doc_robustness.py`, completely unmodified — confirming the `old_form_grammar` detector (`_looks_like_filter`/`_looks_like_path` heuristics in `dispatch_jq`, `exp1_jq.py:219-224`) is model-agnostic.

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

**`claude-sonnet-5-5` shows zero argument-order reversion in every cell tested, including the two cells where `gpt-6-luna` showed its strongest effects**: `none`/JQ-swap (gpt-6-luna: 52.5% reversion, 95% CI [41.7%, 63.1%], n=80) and `ordered_generic`/JQ-swap (gpt-6-luna: 85.0% reversion, 95% CI [75.6%, 91.2%], n=80). Sonnet's 95% CIs (upper bound 13.8% in both cells) do not overlap with either gpt-6-luna estimate — this is not a small-sample null result, it is a genuine, well-powered divergence between models.

**This means the core "sticky jq idiom" reversion effect, and the `ordered_generic`-worse-than-`none` paradox specifically, does *not* generalize across model families at this sample size.** Two non-exclusive explanations: (1) `claude-sonnet-5-5` may simply have a weaker or absent "sticky" prior for jq's exact filter-first calling convention than `gpt-6-luna` does, or (2) it may be more reliably schema-literal in general — i.e., more consistently overriding any pretrained tool-use habit in favor of whatever the provided JSON schema's parameter order says, regardless of how that order is communicated (names, prose, or nothing). Distinguishing these would require an idiom where sonnet's own prior is independently known to be strong (candidate follow-up), since a uniformly-perfect 0% reversion rate on its own is also consistent with sonnet simply being a more capable instruction-follower overall on this comparatively simple, low-ambiguity task — not necessarily proof of no sticky-idiom prior at all.

**Paper framing implication**: the headline finding should now be stated as **model-dependent**, not universal — the sticky-idiom reversion effect (and especially the `ordered_generic` paradox) is robustly replicated within `gpt-6-luna` (Exp4/4b/4c) and within a second idiom on the same model (Exp5/sed), but does **not** replicate on `claude-sonnet-5-5` under the same experimental conditions. This is a genuinely useful negative result for the paper: it bounds the claim's scope and motivates follow-up work on *why* models differ (schema-literalness vs. idiom-prior-strength) rather than undermining the original finding, which remains solid for the model(s) it was shown on.

## Data & Code (Experiment 6)

Raw trial-level data: `tool_name/results/exp4_sonnet_crossmodel.jsonl` (144 trials). Harness: `tool_name/src/exp4_doc_robustness.py` (unmodified from Exp4b/4c, only `--model claude-sonnet-5-5` changed). Model accessed via the same Luna proxy credential/endpoint used in all prior experiments.

---

## Data & Code (All Experiments)

All raw trial-level data: `tool_name/results/*.jsonl` (see individual sections above for specific filenames per experiment). Harness code: `tool_name/src/exp1_jq.py`, `exp4_doc_robustness.py` (the latter extended across Exp4/4b/4c with `doc_level`-parameterized manual renderers, `shell_max_repairs`, and `detect_syntax_reversion` instrumentation; reused unmodified in Exp6 for cross-model replication), `exp5_sed.py` (Experiment 5, self-contained). Unit tests: `tool_name/tests/test_harnesses_mock.py` (9/9 passing throughout), `tool_name/tests/test_exp5_sed_mock.py` (16/16 passing).
