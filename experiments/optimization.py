"""Поиск по целочисленной сетке и проверка на новых seeds."""
import itertools
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.des import ROOT
from experiments.capacity import run_series, save_csv

SEARCH_SEEDS = [3701, 3702, 3703]
VALIDATION_SEEDS = list(range(4701, 4711))
SEARCH_HOURS = 168
MIN_PAYOUT = 4.4
MAX_REJECTED = .01
MAX_SLA = .05
RANGES = {"R2": range(1, 5), "R3": range(2, 7), "R4": range(3, 8)}


def averages(rows):
    n = len(rows)
    return dict(cost=rows[0]["cost"],
                throughput=sum(r["throughput"] for r in rows) / n,
                payouts=sum(r["payout_throughput"] for r in rows) / n,
                failure=sum(r["sla"]["failure"] for r in rows) / n,
                rejected=sum(r["outcomes"].get("technical", 0) / r["arrived"] for r in rows) / n,
                payment_failure=sum(r["payment_sla"]["failure"] for r in rows) / n,
                p95=sum(r["moderation"]["p95"] for r in rows) / n)


def meets(row):
    return row["failure"] <= MAX_SLA and row["payouts"] >= MIN_PAYOUT and row["rejected"] <= MAX_REJECTED


def main():
    factors = [(rate, r2, r3, r4) for rate, r2, r3, r4 in
               itertools.product((2.5, 7.5), (1, 3), (2, 4), (3, 6))]
    run_series("factorial.jsonl", [
        (f"f_{i}", seed, rate, {"R2": r2, "R3": r3, "R4": r4}, 336, True, {})
        for i, (rate, r2, r3, r4) in enumerate(factors, 1) for seed in SEARCH_SEEDS
    ])
    values = list(itertools.product(*RANGES.values()))
    configs = [(f"opt_{i:03}", dict(zip(RANGES, v))) for i, v in enumerate(values, 1)]
    raw = run_series("search.jsonl", [(name, seed, 5, caps, SEARCH_HOURS, True, {})
                                     for name, caps in configs for seed in SEARCH_SEEDS])
    table = []
    for name, caps in configs:
        row = dict(scenario=name, **caps, **averages([r for r in raw if r["scenario"] == name]))
        row["feasible"] = meets(row)
        table.append(row)
    save_csv(ROOT / "results/processed/search.csv", table)
    feasible = sorted((r for r in table if r["feasible"]),
                      key=lambda r: (r["cost"], r["payment_failure"], r["failure"]))
    valid = feasible[:3]
    if not valid:
        valid = sorted(table, key=lambda r: (r["failure"], -r["payouts"]))[:3]
    names = ["counter_base"] + [r["scenario"] for r in valid]
    caps = [{}] + [{key: row[key] for key in RANGES} for row in valid]
    run_series("validation.jsonl", [(name, seed, 5, c, 2160, True, {})
                                    for name, c in zip(names, caps) for seed in VALIDATION_SEEDS])


if __name__ == "__main__":
    main()
