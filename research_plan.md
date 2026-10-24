# Tool Naming & Action-Language Familiarity: Two-Paper Research Plan

**Prepared for:** Blanche
**Context:** Follow-on to Jules White's "Agent Action Language" research program (Sept 2026)
**Status:** Draft for discussion

---

## 0. How this plan relates to Jules's program

Jules's document frames tool sets as *action languages* and proposes a broad research program (RQ1–RQ9, Papers 1–4). This plan does **not** replace that program — it proposes a **fast, self-contained first study** that pilots one specific piece of it (the naming ablation implied in his §7 ablation list and RQ5), and a **second study** that is essentially an expanded, better-informed version of his own §10 "Recommended first study."

Mapping:

| This plan | Jules's doc |
|---|---|
| **Study 1 (Paper A)** — naming × interface crossed design | Operationalizes the §7 ablation "replace familiar command names with novel names while holding semantics constant," crossed with RQ5 ("does a familiar ecosystem over a recast representation outperform a novel API") |
| **Study 2 (Paper B)** — full multi-layout, multi-interface study | Directly implements §10's "Recommended first study," parameterized using Study 1's effect sizes |

Both studies are designed to be **independently publishable**. Study 2 does not require Study 1 to exist as a paper — but Study 1 makes Study 2 better-designed, faster to justify, and easier to power correctly (sample sizes, task counts, which naming conditions are worth carrying forward).

---

## 1. Study 1 (Paper A): Naming × Interface-Familiarity Interaction

### 1.1 Core research question

Does the effect of tool/command **naming** (exact-Unix vs. sensible-novel vs. random) on agent success rate and token cost **depend on** the interaction mechanism — specifically, on (a) whether results are exposed turn-by-turn vs. hidden inside a single-shot script, and (b) whether that single-shot script is written in a familiar *compositional grammar* (shell pipes, flags, redirection) versus a plain scripting call convention with no such grammar?

This is a genuine two-factor interaction test, not a single ablation. Separating **turn-structure** (sequential vs. single-shot) from **grammar-familiarity** (shell-like vs. plain-script) requires a third interface condition — *scripted function calls* — in addition to sequential function-calling and shell-over-VFS. Including it from the start avoids a design where the "interface axis" secretly bundles two different mechanisms:

- If the naming effect is similar across all three interfaces → naming carries a general, structure-independent prior-knowledge benefit.
- If the naming effect is present in both single-shot conditions (scripted calls and shell) but not sequential → the benefit comes from **hiding intermediate results**, not from naming or grammar per se.
- If the naming effect is present in shell but not scripted-calls (despite both being single-shot) → it's specifically the **combination** of familiar names *and* familiar composition rules (pipes, flags) that unlocks the benefit — supporting Jules's stronger "recast the whole problem" thesis.
- If the naming effect is similarly large in sequential function-calling → naming carries value even without script-mediation or rich grammar, which is more surprising and more broadly applicable (most production agents today use plain function-calling, not shells).

### 1.2 Design overview

**3 (Interface) × 3 (Naming) = 9 cells**, one task family, one shared capability layer.

| | Exact Unix names | Sensible non-Unix names | Random names |
|---|---|---|---|
| **Sequential function-calling** | Cell 1 | Cell 2 | Cell 3 |
| **Scripted function calls** | Cell 4 | Cell 5 | Cell 6 |
| **Shell over virtual file system** | Cell 7 | Cell 8 | Cell 9 |

- **Interface axis** manipulates the *mechanism*, isolating turn-structure from grammar-familiarity:
  - **Sequential function-calling**: multi-turn ReAct-style loop; every tool result returns to the model context.
  - **Scripted function calls**: single-shot — the model writes one Python script that calls the same named functions programmatically (e.g., `result = grep("license:MIT", "/projects/*/meta.json")`); executed in a sandbox; only the final printed/returned output is shown to the model. This is single-shot like the shell row, but uses a plain call convention with no Unix-style compositional grammar (no pipes, flags, globs-as-syntax, redirection).
  - **Shell over virtual file system**: single-shot shell command/pipeline executed in a sandbox against the mocked VFS; only stdout/stderr returned (script-mediated, per Jules's §2).
- **Naming axis** manipulates only the **name string** (and, where applicable, description length) attached to each underlying capability. Arguments, return values, and behavior are held perfectly constant across the three naming conditions within a row.

This 3×3 structure cleanly decomposes what might otherwise be a single "interface" contrast into two orthogonal mechanisms — **turn-structure** (row 1 vs. rows 2–3) and **grammar-familiarity** (row 2 vs. row 3, both single-shot) — each crossed with naming.

### 1.3 Task family: project/dependency analysis

Chosen because it is the exact example Jules uses in his §10 recommendation, and it naturally supports both representations (a small function-calling API *and* a Unix-like virtual file system) without distortion.

**Synthetic data:** A generated dependency graph of N projects (~30–60) and M packages (~100–200), each with:
- `project` → list of `(package, version)` direct dependencies
- `package` → metadata (`license`, `owner`, `last_updated`, `deprecated: bool`)
- Some intentional version conflicts and one or two cycles, for harder tasks

Data is fully synthetic/mocked (no real package registry data), generated by a small script with a fixed seed for reproducibility.

**Virtual file system rendering** (for the shell row):
```
/projects/<name>/deps.txt          # one "package==version" per line
/projects/<name>/meta.json
/packages/<name>/dependents.txt    # reverse index: which projects use it
/packages/<name>/meta.json
```
One layout only for Study 1 (entity-oriented). Layout comparison is explicitly deferred to Study 2 — introducing it here would reintroduce the confound Study 1 is designed to avoid.

### 1.4 Shared capability primitives

Five primitives, each chosen because it has a **natural, non-forced** mapping to a real Unix tool — this avoids the risk of implausible name/semantics pairings undermining the naming manipulation.

| Primitive (fixed semantics) | Args | Unix analogue | Behavior |
|---|---|---|---|
| P1: list entries at a path | `path` | `ls` | `/` → all projects; `/projects/X` → X's direct deps |
| P2: recursively find entries matching a pattern | `root, pattern` | `find` | e.g., find all projects whose deps.txt references package Y |
| P3: search file contents for a pattern | `pattern, path` | `grep` | e.g., filter meta.json files by `license:MIT` |
| P4: read full contents of a record | `path` | `cat` | dump a project's or package's full metadata |
| P5: count matching lines/entries | `path or list` | `wc` | e.g., count how many projects depend on package Y |

### 1.5 Naming conditions (applied identically to both interface rows)

| Primitive | Condition A: Exact Unix | Condition B: Sensible non-Unix | Condition C: Random |
|---|---|---|---|
| P1 | `ls` | `list_entries` | `zeplin` |
| P2 | `find` | `search_by_name` | `kordu` |
| P3 | `grep` | `search_content` | `brivex` |
| P4 | `cat` | `read_file` | `tannle` |
| P5 | `wc` | `count_items` | `ovax` |

**Description-length control (critical):** Conditions B and C receive **identical-length, identical-information manuals** describing each command's syntax and behavior — the only difference between B and C is the name token itself. Condition A is tested twice:
- **A-full**: same manual length as B/C (isolates pure name effect, description held constant)
- **A-zero** *(key test of the prior-knowledge hypothesis)*: no manual at all, just the bare name — testing whether the model's pretrained knowledge of `ls`/`grep`/`find`/`cat`/`wc` lets it skip the description cost entirely (this directly operationalizes Jules's "tool-description cost" argument in §3)

This gives **4 naming variants × 3 interfaces = 12 cells** if A-zero is included from the start, or 9 core cells with A-zero added as a fast follow-up once the harness works. Given A-zero is cheap to add (it only removes text, no new mechanism) and is likely the single most compelling result in the paper, recommend building the harness to support it from day one even if the first full run uses the 9-cell core.

### 1.6 Task set (~20–30 tasks, held identical across all cells)

Three difficulty tiers, each with an automatically checkable oracle answer:

1. **Single-hop lookup** (~8 tasks): "List X's direct dependencies," "What is package Y's license?"
2. **Reverse/aggregate** (~8 tasks): "Which projects depend on package Y?", "How many projects depend on Y?"
3. **Composed/multi-step** (~8–10 tasks): "List all MIT-licensed projects that depend on package Y," "Find any version conflicts for package Z," "Find a dependency cycle if one exists." These are the tasks most likely to show the interface-axis effect (script-mediation advantage) and are where naming × interface interaction is expected to be sharpest.

### 1.7 Evaluation protocol

1. Give the model the interface description (schema or manual, per condition) and one task.
2. **Function-calling row:** run a standard tool loop; every tool result returns to context; stop at final answer or a fixed turn cap.
3. **Scripted function-calls row:** model writes a single Python script calling the named functions directly; execute in a sandbox; return only the script's final printed/returned output and, if it errors, allow exactly **one repair turn**.
4. **Shell row:** model writes a single command/pipeline; execute in a sandbox against the mocked VFS; return only stdout/stderr and, if it errors, allow exactly **one repair turn**.
4. Score correctness automatically against the oracle.
6. Record: success (first-pass and after-repair), total tokens (prompt+completion, cumulative), number of model turns, command/script length, wall-clock latency, and an error-type tag (invalid name, wrong args, wrong path, semantic misread, empty/wrong result, timeout).
7. Repeat across all tasks × cells × ≥3 seeds. Run on at least one model; ideally 2–3 model families to check the effect isn't idiosyncratic to one model (no budget constraint assumed, so this is recommended, not required).

### 1.8 Analysis plan

- Primary outcome: success rate per cell (mixed-effects logistic regression, task and seed as random effects, naming and interface as fixed effects + interaction term; interface treated as a 3-level factor, with planned orthogonal contrasts: sequential-vs-single-shot, and — within single-shot — scripted-calls-vs-shell).
- Secondary: total token cost per successful task (the doc's "minimum total representational cost to reach a target success rate," §8) — plot cost-success frontiers per condition rather than relying on raw averages.
- Error-taxonomy breakdown by cell — this is often more persuasive than aggregate success rates, since it shows *why* naming helps or doesn't (e.g., random names produce more "invalid tool name" errors, but sensible names produce more "semantic misread" errors when they imply behavior slightly different from the real one).

### 1.9 Design rationale: why three interface rows instead of two

A two-row design (sequential vs. shell) would confound **turn-structure** (sequential multi-turn vs. single-shot) with **grammar-familiarity** (plain calls vs. Unix-style composition), since shell is both single-shot *and* grammar-familiar while sequential function-calling is neither. Adding the **scripted function-calls** row — single-shot but without shell/VFS grammar — turns this into a clean design where:

- **Row 1 vs. Row 2** isolates the effect of hiding intermediate results (turn-structure), holding naming and call convention constant.
- **Row 2 vs. Row 3** isolates the effect of familiar compositional grammar, holding turn-structure and naming constant.

This is included as a core condition from the start rather than an optional follow-up, since the added engineering cost (one more sandboxed executor for single-shot Python scripts) is small relative to the interpretability gained — without it, any "interface" effect found in a 2-row version would be inherently ambiguous between these two mechanisms.

### 1.10 Novelty and venue fit

No existing public work cleanly isolates *tool-name familiarity* as a variable crossed with *turn-structure* and *grammar-familiarity*, holding underlying capability fixed. Most existing tool-use literature studies schema completeness or number of tools, not naming per se, and rarely decomposes "script-mediated" interfaces into their turn-structure and grammar components separately. This 3×3 design, plus the A-zero condition, gives an unusually crisp and complete account of *where* familiarity effects come from — a highly citable, easy-to-explain result.

**Target venues:** LLM-agent-focused workshops at NeurIPS/ICLR/ACL (agent evaluation, tool use, language-and-code), or a short/workshop paper at COLM. Framing as a standalone contribution: *"Decomposing Familiarity Effects in Agent Tool Use: Naming, Turn-Structure, and Compositional Grammar."*

---

## 2. Study 2 (Paper B): Full Action-Language Cost-Success Study

This is Jules's §10 "Recommended first study," expanded and parameterized using Study 1's results.

### 2.1 What carries over from Study 1

- The project/dependency task family (reused, and extended with a second family per Jules's §10 — e.g., document/record retrieval — for a generalization claim).
- The primitive-to-Unix-tool mapping (P1–P5), extended as needed for the second task family.
- **Whichever naming condition(s) Study 1 shows to matter most** — if Study 1 finds no meaningful difference between "sensible" and "random" names but a large gap for "exact Unix + zero description," Study 2 can drop the sensible/random distinction and instead treat naming as a binary "familiar ecosystem vs. not" factor, saving a large number of experimental cells for the dimensions Study 2 actually wants to explore (VFS layout, interface type).
- Calibrated effect sizes from Study 1, used to properly power Study 2's sample sizes (number of tasks/seeds needed per cell to detect effects of the observed magnitude) rather than guessing.

### 2.2 What Study 2 adds (per Jules's §10 and §7)

- **Second task family**: document/record retrieval, to test generalization across task types.
- **Three VFS layouts** for the same data: entity-oriented, relation-oriented (few large relational files, e.g. `projects.csv` / `dependencies.csv`), and hybrid-with-indexes — testing RQ6 (which representation properties drive success/program size/robustness).
- **Interface conditions expanded beyond the 3-row core**: Study 1's three rows (sequential function-calling, scripted function-calls, Unix-over-VFS) carry over directly, extended with generic `call_tool(name, args)`, a restricted purpose-built scripting language over the same primitives, and — if a recastable sub-task exists — a SQL/spreadsheet condition per RQ5/Paper 3.
- **Multiple models and context-budget conditions** (generous vs. constrained), testing RQ9 (stability of optimal interface across models/budgets).
- **Full ablation battery** from Jules's §7: examples removed vs. present, upfront-description vs. on-demand discovery, intermediate results exposed vs. hidden, program-length/description-budget caps.

### 2.3 How Study 1 leads into Study 2 (the narrative link)

Study 1 answers necessary precursor questions before Study 2's larger investment makes sense: *is there even a naming effect, and if so, does it depend on turn-structure, on grammar-familiarity, or both — before committing to three VFS layouts and four-plus interface types?* Concretely:

1. If Study 1 finds a **large, robust** naming effect that is consistent across all three interface rows → Study 2 is justified in treating "familiar naming" as a first-class, interface-independent factor, and can cite Study 1's effect size to argue the follow-up is worth the added engineering (3 layouts × 4+ interfaces × 2 task families × multiple models is a large compute/engineering investment; Study 1 provides the evidence that justifies it).
2. If Study 1 finds the naming effect **concentrated specifically in the shell row** (i.e., naming only matters when paired with familiar compositional grammar, per the Row 2 vs. Row 3 contrast) → Study 2 should prioritize the Unix-over-VFS and SQL/spreadsheet conditions and their layout variants, since that is where the effect actually lives, rather than spreading naming variants evenly across all interface types.
3. If Study 1 finds the naming effect **driven by turn-structure** (present in both single-shot rows but not sequential, per the Row 1 vs. Row 2 contrast) → Study 2 should prioritize the exposed-vs-hidden-intermediate-results ablation (already in Jules's §7 list) as the primary lens, treating naming as a secondary factor.
4. If Study 1 finds a **null or small** effect throughout → that is *also* a valuable, publishable result on its own (contradicts a plausible-sounding intuition), and it tells you to simplify Study 2's design by not spending cells on naming variants, freeing budget for layout/interface breadth instead.
5. Either way, Study 1's error-taxonomy analysis (which specific failure modes naming causes/prevents, and in which interface row) directly informs what Study 2's ablation battery should prioritize (e.g., if Study 1 shows random names mostly fail via "invalid tool name" rather than "semantic misread," Study 2's discovery-vs-upfront-description ablation becomes more clearly motivated).

Both papers stand alone: Study 1 as a tight, mechanism-focused interaction study; Study 2 as the broad, Jules-program-defining benchmark paper (directly instantiating his Papers 1 and 3). Study 1 is explicitly positioned in its own writeup as a "motivating pilot" for the larger program, which gives you a natural, evidence-backed way to propose Study 2 as joint work with Jules once Study 1's results are in hand.

---

## 3. Practical next steps

1. Build the synthetic data generator + VFS renderer for the dependency-graph task family (Study 1, §1.3–1.4).
2. Implement the 5 primitives once, with a name-swapping layer (a simple lookup table mapping "logical primitive" → "active name string" per condition) so all 6–8 cells share one implementation.
3. Write the 20–30 tasks + oracle-checking functions.
4. Build the three harness loops (sequential function-calling; single-shot scripted function-calls/sandbox; single-shot shell/sandbox), each with one repair turn on error.
5. Pilot on a handful of tasks/cells to sanity-check all three harnesses before running the full matrix.
6. Run full matrix (9 core cells, ≥3 seeds per cell, 1–3 models; add A-zero for 12 cells once validated).
7. Analyze, then decide (per §2.3 above) how to scope Study 2.
