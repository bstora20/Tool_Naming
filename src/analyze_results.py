"""
Summarize a results JSONL file (as produced by run_experiment.py) into a
per-cell success-rate / token-cost table, plus an overall error-tag
breakdown (research_plan.md S1.8).

Usage: python3 src/analyze_results.py results/full_run.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python3 src/analyze_results.py <results.jsonl>")
        sys.exit(1)

    path = Path(sys.argv[1])
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    if not rows:
        print("no rows found")
        return

    by_cell = defaultdict(list)
    for r in rows:
        by_cell[(r["interface"], r["condition"])].append(r)

    has_old_form = any("old_form_grammar" in r for r in rows)
    has_delim = any("delimiter_rule_violated" in r for r in rows)
    header = f"{'interface':10s} {'condition':8s} {'n':>4s} {'success%':>9s} {'avg_tok':>8s} {'avg_turns':>10s}"
    if has_old_form:
        header += f" {'old_form%':>10s}"
    if has_delim:
        header += f" {'delim_viol%':>12s}"
    print(header)
    for (interface, condition), cell_rows in sorted(by_cell.items()):
        n = len(cell_rows)
        success = sum(1 for r in cell_rows if r["correct"]) / n * 100
        avg_tok = sum(r["total_tokens"] for r in cell_rows) / n
        avg_turns = sum(r["turns_used"] for r in cell_rows) / n
        line = f"{interface:10s} {condition:8s} {n:4d} {success:8.1f}% {avg_tok:8.1f} {avg_turns:10.2f}"
        if has_old_form:
            old_form_rate = sum(1 for r in cell_rows if r.get("old_form_grammar")) / n * 100
            line += f" {old_form_rate:9.1f}%"
        if has_delim:
            delim_rate = sum(1 for r in cell_rows if r.get("delimiter_rule_violated")) / n * 100
            line += f" {delim_rate:11.1f}%"
        print(line)

    print("\nError-tag breakdown (incorrect/timed-out runs only):")
    error_counts = defaultdict(int)
    for r in rows:
        if not r["correct"]:
            error_counts[r.get("error_tag") or "(none/wrong_answer)"] += 1
    for tag, count in sorted(error_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {tag:20s} {count}")

    print(f"\nTotal runs: {len(rows)}")


if __name__ == "__main__":
    main()
