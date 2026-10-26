# Tool-Naming / Grammar-Interference Study

Does an LLM agent's prior knowledge of a tool's name interfere with its
ability to follow *documented* (but different) calling conventions for that
tool? This repo contains the harness, primitives, and raw trial data for a
series of controlled experiments testing this question, run against models
accessed through the Anthropic API.

**Start here for results:** [`ALL_RESULTS.md`](ALL_RESULTS.md) (compiled
write-up of Experiments 1-6) and [`PAPER_OUTLINE.md`](PAPER_OUTLINE.md)
(paper abstract + outline synthesizing this work).

## Repository layout

```
src/            Harness code, task primitives, scoring, LLM client wrapper
tests/          Mock-client unit tests (no API calls, no cost)
results/        Raw trial-level output (.jsonl), one row per trial
data/           Fixed synthetic filesystem/dependency graph used by Study 1
ALL_RESULTS.md  Compiled write-up of Experiments 1-6 (jq/sed/cross-model)
PAPER_OUTLINE.md  Paper abstract + outline synthesizing all experiment lines
```

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You will need an Anthropic API key (`ANTHROPIC_API_KEY`-style credential;
get one at https://console.anthropic.com/). No other provider or proxy is
required — every harness defaults to the plain Anthropic API and the public
model `claude-sonnet-4-5-20250929` (see `src/llm_client.py:DEFAULT_MODEL`).

**The API key is never read from the environment automatically** — every
script takes it explicitly via `--api-key`, to keep key-handling obvious and
auditable. Pass it on the command line, e.g.:

```bash
python3 src/exp1_jq.py --api-key "$ANTHROPIC_API_KEY" --pilot
```

(or export it into a shell variable first and reference that, as above, so
it never appears in shell history in plaintext if you prefer — use your
shell's history-exclusion mechanism, e.g. prefixing the `export` line with a
space under `HISTCONTROL=ignorespace`).

## Running the test suite (no API calls, no cost)

```bash
python3 -m pytest tests/ -v
```

All 60 tests should pass in under a second. These use a scripted mock LLM
client and validate harness control flow, dispatch, and scoring logic
independent of any live model.

## Running experiments

Every experiment script follows the same pattern: a small, cheap `--pilot`
subset to sanity-check the harness against the live API before spending
budget on a full run, then the full matrix via comma-separated filter flags.

**Always run the `--pilot` subset first** when pointing at a new model or
provider — this is standard practice throughout this project and catches
prompt/schema issues cheaply (a handful of trials instead of hundreds).

### Experiment 1 — jq sticky-idiom test (Exp 1 in ALL_RESULTS.md)

```bash
# Pilot (cheap sanity check)
python3 src/exp1_jq.py --api-key "$KEY" --pilot --out results/pilot_exp1_jq.jsonl

# Full run: both conditions x 8 tasks x 3 seeds x each interface = 48 trials/interface
python3 src/exp1_jq.py --api-key "$KEY" --interface sequential --seeds 1,2,3 \
  --out results/exp1_jq.jsonl
python3 src/exp1_jq.py --api-key "$KEY" --interface shell --seeds 1,2,3 \
  --out results/exp1_jq_shell.jsonl
```

### Experiment 4/4b/4c — documentation-robustness matrix

```bash
python3 src/exp4_doc_robustness.py --api-key "$KEY" --pilot \
  --out results/pilot_exp4_doc_robustness.jsonl

# Full matrix: doc_levels x interfaces x conditions x 8 tasks x 3 seeds
python3 src/exp4_doc_robustness.py --api-key "$KEY" \
  --doc-levels terse,none,named,ordered_generic \
  --interfaces sequential,shell \
  --seeds 1,2,3 \
  --out results/exp4_doc_robustness.jsonl
```

### Experiment 5 — idiom generalization (sed)

```bash
python3 src/exp5_sed.py --api-key "$KEY" --pilot --out results/pilot_exp5_sed.jsonl

python3 src/exp5_sed.py --api-key "$KEY" \
  --doc-levels terse,none \
  --interfaces sequential,shell \
  --seeds 1,2,3 \
  --out results/exp5_sed.jsonl
```

### Experiment 6 — cross-model replication

Identical harness to Experiment 4, only `--model` changes:

```bash
python3 src/exp4_doc_robustness.py --api-key "$KEY" \
  --model claude-sonnet-4-5-20250929 \
  --doc-levels terse,none,ordered_generic \
  --interfaces sequential \
  --seeds 1,2,3 \
  --out results/exp4_crossmodel_<your-model-name>.jsonl
```

Swap `--model` to any Anthropic model you want to test against (e.g. an
Opus/Haiku variant, or a future model release) to extend the cross-model
comparison. **Exact point estimates will not reproduce byte-for-byte** —
model updates, provider-side sampling, and inherent trial-to-trial
stochasticity (temperature > 0 in all harnesses) mean replication should be
judged by whether confidence intervals and qualitative directions match, not
exact percentages. See `ALL_RESULTS.md` Experiment 6 for how we report this.

### Study 1 — naming x interface (`run_experiment.py`)

```bash
python3 src/run_experiment.py --api-key "$KEY" --pilot --out results/pilot.jsonl

python3 src/run_experiment.py --api-key "$KEY" \
  --conditions A-full,B,C \
  --interfaces sequential,scripted,shell \
  --seeds 1,2,3 \
  --out results/full_run.jsonl
```

### Analyzing results

```bash
python3 src/analyze_results.py results/<your_output>.jsonl
```

## A note on cost and reproducibility

- Every full experiment run here is on the order of tens to a few hundred
  trials at a few hundred to a few thousand tokens each — expect low
  single-digit dollars per full matrix on current Anthropic pricing, but
  **always run `--pilot` first** to confirm before committing to a full run.
- Use `--base-url` only if you are routing through your own proxy; omit it
  entirely to hit the standard Anthropic API directly.
- Trial-level `.jsonl` outputs in `results/` are the exact raw data behind
  every table in `ALL_RESULTS.md`. Each row includes success/failure,
  token counts, turn counts, and the specific error tags described in the
  write-up, so published aggregates can be independently recomputed from
  these files without re-running the API calls.

