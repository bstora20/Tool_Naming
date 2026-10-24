"""
Experiment runner: iterates the full cell matrix (interface x naming
condition) x task x seed, invokes the right harness, scores the result
against the task oracle, and writes one JSON-lines row per run to
`results/<run_name>.jsonl` (research_plan.md S1.7/S1.8 logging
requirements: success, tokens, turns, error tag).

Usage:
    python3 src/run_experiment.py --api-key KEY [--pilot] [--conditions A-full,B,C]
                                   [--interfaces sequential,scripted,shell]
                                   [--tasks T1-01,T1-02] [--seeds 1,2,3]
                                   [--model claude-sonnet-4-5-20250929]
                                   [--out results/pilot.jsonl]

`--pilot` restricts to a small fixed subset (1 task per tier, 1 seed, all
9 core cells) for the sanity-check run called for in research_plan.md
S3 step 5, before committing to the full matrix.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

from data_gen import Graph  # noqa: E402
from vfs import VirtualFS  # noqa: E402
from dispatch import Dispatcher  # noqa: E402
from tasks import ALL_TASKS, get_task  # noqa: E402
from scoring import score_answer  # noqa: E402
from llm_client import make_client  # noqa: E402
from harness_sequential import run_sequential  # noqa: E402
from harness_scripted import run_scripted  # noqa: E402
from harness_shell import run_shell  # noqa: E402

DATA_PATH = SRC_DIR.parent / "data" / "graph_seed42.json"
RESULTS_DIR = SRC_DIR.parent / "results"

ALL_CONDITIONS = ["A-full", "A-zero", "B", "C"]
CORE_CONDITIONS = ["A-full", "B", "C"]
ALL_INTERFACES = ["sequential", "scripted", "shell"]

_HARNESS_FNS = {
    "sequential": run_sequential,
    "scripted": run_scripted,
    "shell": run_shell,
}

PILOT_TASK_IDS = ["T1-01", "T2-01", "T3-01"]


def load_vfs() -> VirtualFS:
    with open(DATA_PATH) as f:
        d = json.load(f)
    return VirtualFS(Graph.from_dict(d))


def load_graph() -> Graph:
    with open(DATA_PATH) as f:
        return Graph.from_dict(json.load(f))


def run_one_cell(
    client_kwargs: Dict[str, Any],
    interface: str,
    condition: str,
    task_id: str,
    seed: int,
    graph: Graph,
) -> Dict[str, Any]:
    # Fresh client (and session id) per cell: each cell is its own
    # conversation, so it gets its own UUID per the endpoint's caching
    # semantics (reused within a conversation, separate across conversations).
    client = make_client(**client_kwargs)
    vfs = VirtualFS(graph)
    dispatcher = Dispatcher(vfs, condition)
    task = get_task(task_id)
    oracle_value = task.oracle_fn(graph)

    harness_fn = _HARNESS_FNS[interface]
    t0 = time.time()
    try:
        outcome = harness_fn(client, dispatcher, condition, task.prompt)
        error_tag = ""
        if interface == "sequential":
            if outcome.timed_out:
                error_tag = "timeout"
            else:
                failed_calls = [l for l in outcome.turn_log if not l.ok]
                error_tag = failed_calls[-1].error_tag if failed_calls else ""
        else:
            error_tag = outcome.final_error_tag if outcome.timed_out else ""
        correct = (not outcome.timed_out) and score_answer(task, oracle_value, outcome.final_answer)
        old_form_grammar = getattr(outcome, "old_form_grammar", False)
        delimiter_rule_violated = getattr(outcome, "delimiter_rule_violated", False)
    except Exception as e:  # defensive: never let one bad run kill the matrix
        return {
            "interface": interface,
            "condition": condition,
            "task_id": task_id,
            "seed": seed,
            "correct": False,
            "timed_out": True,
            "error_tag": "harness_exception",
            "old_form_grammar": False,
            "delimiter_rule_violated": False,
            "exception": f"{type(e).__name__}: {e}",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "turns_used": 0,
            "wall_clock_s": time.time() - t0,
            "final_answer": "",
            "oracle_value": repr(oracle_value),
        }

    return {
        "interface": interface,
        "condition": condition,
        "task_id": task_id,
        "seed": seed,
        "correct": correct,
        "timed_out": outcome.timed_out,
        "error_tag": error_tag,
        "old_form_grammar": old_form_grammar,
        "delimiter_rule_violated": delimiter_rule_violated,
        "prompt_tokens": outcome.usage.prompt_tokens,
        "completion_tokens": outcome.usage.completion_tokens,
        "total_tokens": outcome.usage.total_tokens,
        "turns_used": outcome.turns_used,
        "wall_clock_s": time.time() - t0,
        "final_answer": outcome.final_answer,
        "oracle_value": repr(oracle_value),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--base-url", default=None, help="custom API base URL, e.g. a Bedrock proxy root (no /v1/messages suffix)")
    ap.add_argument("--application-source", default="tool_name_experiment")
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--conditions", default=None, help="comma-separated, default: core 3 (or all 4 if --with-azero)")
    ap.add_argument("--with-azero", action="store_true")
    ap.add_argument("--interfaces", default=None, help="comma-separated, default: all 3")
    ap.add_argument("--tasks", default=None, help="comma-separated task IDs, default: all")
    ap.add_argument("--seeds", default="1", help="comma-separated seed ints, default: 1")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.pilot:
        conditions = CORE_CONDITIONS
        interfaces = ALL_INTERFACES
        task_ids = PILOT_TASK_IDS
        seeds = [1]
        out_path = Path(args.out) if args.out else RESULTS_DIR / "pilot.jsonl"
    else:
        conditions = (
            args.conditions.split(",") if args.conditions
            else (ALL_CONDITIONS if args.with_azero else CORE_CONDITIONS)
        )
        interfaces = args.interfaces.split(",") if args.interfaces else ALL_INTERFACES
        task_ids = args.tasks.split(",") if args.tasks else [t.id for t in ALL_TASKS]
        seeds = [int(s) for s in args.seeds.split(",")]
        out_path = Path(args.out) if args.out else RESULTS_DIR / "full_run.jsonl"

    RESULTS_DIR.mkdir(exist_ok=True)
    client_kwargs: Dict[str, Any] = {"api_key": args.api_key}
    if args.model:
        client_kwargs["model"] = args.model
    if args.base_url:
        client_kwargs["base_url"] = args.base_url
    if args.application_source:
        client_kwargs["application_source"] = args.application_source

    graph = load_graph()

    total = len(conditions) * len(interfaces) * len(task_ids) * len(seeds)
    done = 0
    print(f"Running {total} cells -> {out_path}")

    with open(out_path, "w") as f:
        for seed in seeds:
            for interface in interfaces:
                for condition in conditions:
                    for task_id in task_ids:
                        row = run_one_cell(client_kwargs, interface, condition, task_id, seed, graph)
                        f.write(json.dumps(row) + "\n")
                        f.flush()
                        done += 1
                        status = "OK " if row["correct"] else ("TIMEOUT" if row["timed_out"] else "WRONG")
                        print(
                            f"[{done}/{total}] {interface:10s} {condition:7s} {task_id:6s} "
                            f"seed={seed} -> {status} ({row['total_tokens']} tok, "
                            f"{row['turns_used']} turns, {row['wall_clock_s']:.1f}s)"
                        )

    print(f"\nDone. Results written to {out_path}")


if __name__ == "__main__":
    main()
