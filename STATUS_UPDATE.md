# Status Update — Tool-Naming / Grammar-Interference Study

**Date:** 2026-10-20

## 1. Target paper & status

Testing whether reusing familiar tool names (e.g. `jq`) with documentation that deviates from their real-world calling convention causes "sticky idiom" interference in LLM agents — and more broadly, what makes in-context documentation actually override a model's pretraining priors.

**Status:** Core experiments (1-4c, 7 write-ups, ~1,200+ trials total) are complete and show a real, replicated effect. **Not yet paper-ready** — needs multi-model replication and at least one additional idiom before the findings generalize beyond this single model (`gpt-6-luna`) and single tool (`jq`).

## 2. Finished last week

We ran a new round of tests (304 trials) to dig into two things. First, we built a way to automatically detect when the AI writes commands using the complicated "real" syntax instead of the simplified version our test setup actually expects — this had only been spotted by eye before. Second, we re-ran a surprising earlier result with 4x more data to make sure it was real: that explicitly telling the AI the correct order of inputs in plain English actually made it *more* likely to use the wrong order, not less. With the bigger sample, that surprising result held up.

## 3. Working on this week

- Compiling/consolidating all seven experiment write-ups into one results document (`ALL_RESULTS.md`).
- Scoping the next round of experiments — primarily **multi-model replication** of the core paradox finding, since every result so far comes from a single model.
- Planning a second idiom (beyond jq) to test whether the `named`-suppresses / `ordered_generic`-backfires pattern generalizes.

## 4. Current results

When we give an AI a tool name it already knows well (like `jq`) but ask it to use the inputs in a different order than it's used to, it almost always gets it right — as long as we show it the real names of the inputs somewhere in the setup. The only time it starts reverting to the order it already "knows" from training is when we give it *no* information at all about the inputs — and in that case, it reverts about half the time.

Surprisingly, if we instead give it a sentence explaining the correct order in plain English (without showing the real input names), it does *worse* than getting no explanation at all — reverting to its old habit about 85% of the time instead of 52%.

We also found a separate problem specific to one of our test setups: the AI tends to write overly complicated commands (using the real tool's full feature set) instead of the simple version our test expects — but a single plain sentence describing the task mostly fixes that.

## 5. Most interesting finding

The **prose-instruction paradox**: correctly telling the model the argument order performs *worse* than giving it no order information at all. Working theory: a real parameter name requires no recall — the model just reads it off the schema at the point of use — whereas a prose-stated rule has to be actively recalled and reapplied each time, and that recall step is exactly where a strong competing habit (real jq's filter-first order) can intrude and win.

## Files

- Full compiled results: `tool_name/ALL_RESULTS.md`
- Raw data: `tool_name/results/*.jsonl`
- Harness code: `tool_name/src/exp1_jq.py`, `tool_name/src/exp4_doc_robustness.py`
- Tests: `tool_name/tests/test_harnesses_mock.py` (9/9 passing)
