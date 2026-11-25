"""Таблицы, доверительные интервалы и графики для серий мощности."""
import csv
from collections import defaultdict
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import t as student

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.des import ROOT, distribution, sla
from experiments.capacity import save_csv

RAW = ROOT / "results/raw"
PROCESSED = ROOT / "results/processed"
FIGURES = ROOT / "figures"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": .22, "figure.dpi": 135})
COLORS = ["#2563EB", "#7C3AED", "#059669", "#DC2626", "#64748B"]


def interval(values):
    values = [x for x in values if x is not None]
    if not values:
        return {"n": 0, "mean": None, "lo": None, "hi": None}
    mean = float(np.mean(values))
    radius = float(student.ppf(.975, len(values) - 1) * np.std(values, ddof=1) / np.sqrt(len(values)))         if len(values) > 1 else None
    return dict(n=len(values), mean=mean, lo=mean - radius if radius is not None else None,
                hi=mean + radius if radius is not None else None)


def series(name):
    return [json.loads(line) for line in (RAW / name).read_text(encoding="utf-8").splitlines()]


def rows(name):
    return list(csv.DictReader((RAW / name).open(encoding="utf-8")))


def save_figure(fig, name):
    fig.tight_layout()
    fig.savefig(FIGURES / (name + ".png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


METRICS = {
    "throughput": lambda r: r["throughput"],
    "payout_throughput": lambda r: r["payout_throughput"],
    "sla": lambda r: r["sla"]["failure"],
    "payment_sla": lambda r: r["payment_sla"]["failure"],
    "support_sla": lambda r: r["support_sla"]["failure"],
    "p95": lambda r: r["moderation"]["p95"],
    "r3_wait": lambda r: r["resources"]["R3"]["waiting"]["mean"],
    "r3_queue": lambda r: r["resources"]["R3"]["average_queue"],
    "r3_util": lambda r: r["resources"]["R3"]["utilization"],
    "utilization": lambda r: r["utilization"],
    "technical": lambda r: r["outcomes"].get("technical", 0) / r["arrived"],
    "r4_refused": lambda r: r["resources"]["R4"]["rejected"] / r["resources"]["R4"]["offered"],
}


def summaries(name):
    data = series(name)
    groups = defaultdict(list)
    for r in data:
        groups[r["scenario"]].append(r)
    results = []
    for group, items in groups.items():
        for key, extract in METRICS.items():
            results.append(dict(scenario=group, cost=items[0]["cost"],
                                metric=key, **interval(extract(r) for r in items)))
    return groups, results


def capacity_tables():
    groups, results = summaries("capacity.jsonl")
    save_csv(PROCESSED / "capacity_summary.csv", results)
    pairs = []
    decisions = []
    base = {row["seed"]: row for row in groups["base"]}
    for name, items in groups.items():
        for metric, extract in METRICS.items():
            pairs.append(dict(scenario=name, metric=metric,
                **interval(extract(row) - extract(base[row["seed"]]) for row in items)))
        m = {row["metric"]: row for row in results if row["scenario"] == name}
        decisions.append(dict(scenario=name, rate=items[0]["config"]["rate"],
            cost=items[0]["cost"], sla_hi=m["sla"]["hi"], payouts_lo=m["payout_throughput"]["lo"],
            technical_hi=m["technical"]["hi"], meets_sla=m["sla"]["hi"] <= .05))
    save_csv(PROCESSED / "capacity_differences.csv", pairs)
    save_csv(PROCESSED / "capacity_acceptance.csv", decisions)
    resource_rows = []
    for scenario, trials in groups.items():
        for name in trials[0]["resources"]:
            for metric, get in {
                "utilization": lambda r: r["utilization"],
                "rejected": lambda r: r["rejected"],
                "average_queue": lambda r: r["average_queue"],
                "p95_wait": lambda r: r["waiting"]["p95"],
            }.items():
                resource_rows.append(dict(scenario=scenario, resource=name, metric=metric,
                    **interval(get(r["resources"][name]) for r in trials)))
    save_csv(PROCESSED / "resource_summary.csv", resource_rows)
    knee = []
    for before, after in [("r3_1", "base"), ("base", "r3_3"), ("r3_3", "r3_4")]:
        by_seed = {r["seed"]: r for r in groups[before]}
        for key in ("throughput", "payout_throughput"):
            stats = interval(r[key] / by_seed[r["seed"]][key] - 1 for r in groups[after])
            knee.append(dict(before=before, after=after, metric=key, **stats))
    save_csv(PROCESSED / "capacity_knee.csv", knee)

    x = np.arange(4)
    scenarios = ["r3_1", "base", "r3_3", "r3_4"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6))
    for ax, key, unit in zip(axes.flat, ["payout_throughput", "sla", "r3_wait", "r3_queue"],
                            ["Выплаты, проектов/ч", "Нарушения SLA, %", "Ожидание R3, ч", "Очередь R3, проектов"]):
        measures = [next(r for r in results if r["scenario"] == s and r["metric"] == key) for s in scenarios]
        scale = 100 if key == "sla" else 1
        means = [scale * r["mean"] for r in measures]
        deviations = [scale * (r["hi"] - r["mean"]) for r in measures]
        ax.errorbar(x, means, yerr=deviations, capsize=4, marker="o", color=COLORS[0])
        if key == "sla":
            ax.axhline(5, color=COLORS[3], linestyle="--", label="Порог 5%")
            ax.legend()
        ax.set(xticks=x, xticklabels=[f"{i + 1} · {groups[s][0]['cost']} у.е." for i,s in enumerate(scenarios)],
               ylabel=unit)
    fig.suptitle("Мощность R3 · 5 проектов/ч · средние и 95% интервалы")
    save_figure(fig, "capacity")


def cohort_tables():
    records = rows("base_projects.csv")
    cut = 2160
    threshold = 8
    cohorts = {
        "Категория": lambda r: {"technology":"Технологии","art":"Искусство","social":"Социальный"}[r["category"]],
        "Репутация": lambda r: "r < 0,5" if float(r["reputation"]) < .5 else "r ≥ 0,5",
        "Цель": lambda r: "< 12 000 коп." if int(r["target_kopecks"]) < 12000 else "≥ 12 000 коп.",
        "Ручная проверка": lambda r: "Посетил R3" if r["manual"] == "1" else "Без R3",
        "Интенсивность": lambda r: "Повышенная" if r["track"] == "C" else "Базовая",
        "Спор": lambda r: "Зарегистрирован" if r["disputed"] == "1" else "Без спора к отсечке",
    }
    segments = []
    manual = {}
    for key, group in cohorts.items():
        cells = defaultdict(list)
        for r in records:
            cells[group(r)].append(r)
        for label, data in cells.items():
            observations = [(float(r["arrival"]),
                float(r["decision"] or r["terminal"]) if r["decision"] or r["terminal"] else None,
                bool(r["decision"])) for r in data]
            observed = [finish - start for start, finish, decision in observations if decision]
            segments.append(dict(segment=key, group=label, **sla(observations, cut, threshold),
                                 **{f"delay_{k}": v for k, v in distribution(observed).items()}))
            if key == "Ручная проверка":
                manual[label] = sorted(observed)
    save_csv(PROCESSED / "cohort_segments.csv", segments)
    fig, axes = plt.subplots(2,2, figsize=(10,7))
    for color, (label, values) in zip(COLORS, manual.items()):
        axes[0,0].hist(values, bins=np.linspace(0, 35, 36), histtype="step", label=label,
                       color=color, density=True)
        axes[0,1].step(values, np.arange(1, len(values)+1)/len(values), label=label, color=color)
        axes[1,1].step(values, (len(values)-np.arange(1, len(values)+1))/len(values),
                       label=label, color=color)
    axes[1,0].boxplot(list(manual.values()), labels=list(manual))
    for ax, title, y in zip(axes.flat, ["Гистограмма", "Эмпирическая функция", "Размах", "Хвост"],
                            ["Плотность, 1/ч", "Доля ≤ t", "Время, ч", "Доля > t"]):
        ax.set_title(title)
        ax.set_ylabel(y)
        if ax is not axes[1,0]:
            ax.axvline(8, linestyle="--", color=COLORS[3], label="SLA 8 ч")
            ax.set_xlabel("Время до решения, ч")
            ax.legend(fontsize=8)
    fig.suptitle("Наблюдаемые решения модерации · база · seed 2501")
    save_figure(fig, "moderation_tail")

    samples = rows("base_queue_trace.csv")
    fig, ax = plt.subplots(figsize=(10,4))
    for rid, color in zip(["R3", "R4", "R6"], COLORS):
        ax.step([float(r["hour"]) for r in samples], [int(r[f"{rid}_queue"]) for r in samples],
                where="post", label=rid, color=color, alpha=.82, lw=.8)
    ax.set(title="Очереди в базовом прогоне · seed 2501 · снимки по часам",
           xlabel="Модельное время, ч", ylabel="Заявок в очереди")
    ax.legend()
    save_figure(fig, "queues")


if __name__ == "__main__":
    capacity_tables()
    cohort_tables()
