"""Собирает подтверждения фактически выполненных экспериментов AnyLogic."""
import argparse
from collections import defaultdict
import csv
from itertools import product
from math import isclose, isfinite
from pathlib import Path
from statistics import mean
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.capacity_results import COLORS, save_figure
from analysis.des import ROOT
import matplotlib.pyplot as plt

FACTORS = ("arrival_rate", "r2", "r3", "r4")
MEASURES = ("throughput", "payouts", "mean_queue", "weighted_utilization",
            "sum_utilization", "sla_failure", "technical_failure", "cost", "objective")


def latest_runs(filename, name):
    with filename.open(encoding="utf-8", newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["experiment"] == name]
    assert rows, f"В выгрузке отсутствует эксперимент {name}"
    for row in rows:
        assert isclose(float(row["window_h"]), 168, abs_tol=1e-4)
        for field in (*FACTORS, *MEASURES):
            row[field] = float(row[field])
            assert isfinite(row[field]), (name, field, row[field])
        objective = .65 * row["throughput"] / 5 - .35 * row["sum_utilization"] / 8
        assert isclose(row["objective"], objective, abs_tol=1e-8), row
    return rows


def grouped(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in FACTORS)].append(row)
    return groups


def summary(config, runs):
    return {**dict(zip(FACTORS, config, strict=True)), "replications": len(runs),
            **{key: mean(r[key] for r in runs) for key in MEASURES}}


def unique_seeds(rows, expected):
    assert len({r["trial_seed"] for r in rows}) >= expected, "Повторы должны иметь разные seeds"


def save(filename, rows):
    path = ROOT / "results/native/experiments" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def tuning(rows):
    expected = {(rate, 2, 2, 4) for rate in (2.5, 5, 10)}
    expected |= {(5, 2, r3, 4) for r3 in (1, 4)}
    cases = grouped(rows)
    assert expected <= cases.keys(), "Для двух регуляторов нужны базовое и четыре крайних значения"
    save("tuning.csv", [summary(key, cases[key][-1:]) for key in sorted(expected)])
    return 5


def variation(rows):
    expected = set(product((2.5, 7.5), (1, 3), (2, 4), (3, 6)))
    cases = grouped(rows)
    assert set(cases) == expected, "Требуется полный план из 16 комбинаций"
    for runs in cases.values():
        unique_seeds(runs[-3:], 3)
    design = [summary(key, cases[key][-3:]) for key in sorted(expected)]
    save("variation.csv", design)
    effects = []
    for factor in FACTORS:
        low, high = sorted({r[factor] for r in design})
        for metric in ("throughput", "payouts", "mean_queue", "sla_failure"):
            change = (mean(r[metric] for r in design if r[factor] == high)
                      - mean(r[metric] for r in design if r[factor] == low))
            effects.append(dict(factor=factor, low=low, high=high, metric=metric, effect=change))
    save("variation_effects.csv", effects)
    from analysis.teacher_results import factorial_response
    factorial_response([{**r, **{k.upper(): r[k] for k in FACTORS[1:]}} for r in design],
                       "native_factorial_response")
    return 16


def optquest(rows):
    assert len(rows) >= 300 and len(rows) % 3 == 0, "Нужно минимум 100 итераций с тремя повторами"
    table = []
    best = None
    for start in range(0, len(rows), 3):
        runs = rows[start:start+3]
        cases = grouped(runs)
        assert len(cases) == 1, "Итерация меняет мощности между повторами"
        unique_seeds(runs, 3)
        config, = cases
        _, r2, r3, r4 = config
        assert config[0] == 5 and r2 in range(1, 5) and r3 in range(2, 7) and r4 in range(3, 8)
        item = summary(config, runs)
        feasible = (item["sla_failure"] <= .05 and item["payouts"] >= 4.4
                    and item["technical_failure"] <= .01 and item["cost"] <= 74)
        if feasible:
            best = max(item["objective"], best) if best is not None else item["objective"]
        table.append(dict(iteration=start//3+1, feasible=feasible, best=best, **item))
    candidates = sorted((x for x in table if x["feasible"]), key=lambda x: -x["objective"])
    assert candidates, "OptQuest должен зафиксировать хотя бы одно допустимое решение"
    save("optquest.csv", table)
    save("optquest_best.csv", candidates[:10])

    fig, axis = plt.subplots(figsize=(9.1, 4.8))
    axis.scatter([r["iteration"] for r in table], [r["objective"] for r in table],
                 color="#94A3B8", s=21, label="Среднее по трём репликациям")
    axis.step([r["iteration"] for r in table], [r["best"] for r in table],
              color=COLORS[0], where="post", label="Лучшее допустимое решение")
    axis.set(xlabel="Итерация", ylabel="Взвешенная целевая функция",
             title="Сходимость по журналу выполненного эксперимента OptQuest")
    axis.legend()
    save_figure(fig, "optquest_native")
    return len(table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", choices=("Tuning", "Variation", "OptQuest"))
    parser.add_argument("--source", type=Path, default=Path(tempfile.gettempdir()))
    args = parser.parse_args()
    rows = latest_runs(args.source / f"crowdfunding-native-experiments-{args.experiment}.csv",
                       args.experiment)
    validate = {"Tuning": tuning, "Variation": variation, "OptQuest": optquest}[args.experiment]
    count = validate(rows)
    save(f"{args.experiment.lower()}_replications.csv", rows)
    print(f"{args.experiment}: проверено {count} сценариев или итераций.")
