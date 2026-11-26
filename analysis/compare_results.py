"""Графики и проверки для факторного плана, поиска, ABM, M/M/c/K и SD."""
import argparse
from collections import defaultdict
from itertools import combinations
import csv
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.capacity_results import (COLORS, FIGURES, PROCESSED, RAW, METRICS,
                                       interval, rows, save_figure, series, summaries)
from experiments.capacity import save_csv
from experiments.optimization import MAX_REJECTED, MAX_SLA, MIN_PAYOUT


def optimization():
    data = series("factorial.jsonl")
    col = ["Интенсивность", "R2", "R3", "R4"]

    def factor(r):
        c = r["config"]
        return (1 if c["rate"] > 5 else -1, 1 if c["caps"]["R2"] > 1 else -1,
                1 if c["caps"]["R3"] > 2 else -1, 1 if c["caps"]["R4"] > 3 else -1)

    results = []
    for order in [1, 2]:
        for ix in combinations(range(4), order):
            label = " × ".join(col[i] for i in ix)
            for metric in ("throughput", "payout_throughput", "sla", "r3_wait", "utilization", "p95"):
                batches = defaultdict(list)
                for trial in data:
                    value = METRICS[metric](trial)
                    if value is not None:
                        batches[trial["seed"]].append(value * np.prod([factor(trial)[i] for i in ix]))
                results.append(dict(factor=label, metric=metric,
                                    **interval(2 * np.mean(v) for v in batches.values())))
    save_csv(PROCESSED / "factor_effects.csv", results)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, metric, xlabel in zip(axes, ["sla", "payout_throughput"],
                                   ["Нарушения SLA, п.п.", "Успешные выплаты, проектов/ч"]):
        v = [r for r in results if r["metric"] == metric]
        v.sort(key=lambda r: abs(r["mean"]))
        scale = 100 if metric == "sla" else 1
        ax.barh([r["factor"] for r in v], [scale*r["mean"] for r in v], color=COLORS[0])
        ax.errorbar([scale*r["mean"] for r in v], np.arange(len(v)),
                    xerr=[scale*(r["hi"]-r["mean"]) for r in v], fmt="none", color="#334155", capsize=2)
        ax.set_xlabel(xlabel)
    fig.suptitle("Факторный план · эффект верхнего уровня и 95% интервал")
    save_figure(fig, "factorial")

    table = list(csv.DictReader((PROCESSED / "search.csv").open(encoding="utf-8")))
    fig, axes = plt.subplots(1, 2, figsize=(10.5,4.5))
    grid = np.empty((5, 5))
    for r in table:
        if r["R2"] == "1":
            grid[int(r["R3"])-2, int(r["R4"])-3] = float(r["failure"])*100
    im = axes[0].imshow(grid, origin="lower", extent=[2.5,7.5,1.5,6.5], cmap="YlOrRd", aspect="auto")
    axes[0].set(title="Доля нарушений SLA, % · R2 = 1", xlabel="Каналы R4", ylabel="Каналы R3")
    fig.colorbar(im, ax=axes[0], shrink=.8)
    best = np.inf
    steps = []
    for step, r in enumerate(table, 1):
        if r["feasible"] == "True":
            best = min(best, float(r["cost"]))
        steps.append(best if np.isfinite(best) else np.nan)
    axes[1].step(np.arange(1, len(steps)+1), steps, where="post", label="Лучший допустимый")
    axes[1].set(title="Минимум стоимости по ходу перебора", xlabel="Оценённые конфигурации",
                ylabel="Стоимость, у.е.")
    save_figure(fig, "search")

    groups, metrics = summaries("validation.jsonl")
    save_csv(PROCESSED / "validation_summary.csv", metrics)
    status = []
    for name, group in groups.items():
        by_key = {v["metric"]:v for v in metrics if v["scenario"] == name}
        status.append(dict(scenario=name, cost=group[0]["cost"], **group[0]["config"]["caps"],
                           meets_sla=by_key["sla"]["hi"] <= MAX_SLA,
                           meets_payout=by_key["payout_throughput"]["lo"] >= MIN_PAYOUT,
                           meets_rejected=by_key["technical"]["hi"] <= MAX_REJECTED))
    save_csv(PROCESSED / "validation_acceptance.csv", status)


def agents():
    grouped = defaultdict(list)
    for record in series("abm.jsonl"):
        grouped[record["scenario"]].append(record)
    table = []
    for name, batch in grouped.items():
        config = batch[0]["config"]
        for kind in ("light", "heavy"):
            for metric, extract in {
                "p95": lambda g: g["waiting"]["p95"],
                "sla": lambda g: g["sla"]["failure"],
                "mature": lambda g: g["sla"]["mature"],
                "n_wait": lambda g: g["waiting"]["n"],
            }.items():
                table.append(dict(scenario=name, heavy_share=config["heavy_share"], priority=config["priorities"],
                                  group=kind, metric=metric, **interval(extract(r["groups"][kind]) for r in batch)))
        for metric, extract in {"utilization": METRICS["r3_util"], "technical": METRICS["technical"]}.items():
            table.append(dict(scenario=name, heavy_share=config["heavy_share"], priority=config["priorities"],
                              group="all", metric=metric, **interval(extract(r) for r in batch)))
    save_csv(PROCESSED / "abm_summary.csv", table)

    fig, axes = plt.subplots(1,2,figsize=(10, 4.5))
    for ax, metric, groups in zip(axes, ["p95", "sla"], [("light",), ("light", "heavy")]):
        for color, kind in zip(COLORS, groups):
            for priority, style in [(False,"-"),(True,"--")]:
                v = sorted((r for r in table if r["group"] == kind and r["metric"] == metric
                            and r["priority"] == priority and r["mean"] is not None),
                           key=lambda r: r["heavy_share"])
                weight = 100 if metric == "sla" else 1
                ax.errorbar([100*r["heavy_share"] for r in v], [weight*r["mean"] for r in v],
                    yerr=[weight*(r["hi"]-r["mean"]) for r in v],
                    linestyle=style, marker=".", capsize=2, color=color,
                    label=("Лёгкие" if kind == "light" else "Тяжёлые") +
                          (" · приоритет" if priority else " · FIFO"))
        ax.set(xlabel="Доля тяжёлых проектов, %")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("P95 ожидания начавших обслуживание, ч")
    axes[1].set_ylabel("Доля нарушений зрелой когорты, %")
    fig.suptitle("Агентная модель · средние и 95% интервалы")
    save_figure(fig, "abm")


def continuous():
    m = json.loads((RAW / "markov.json").read_text())
    transient = rows("markov_transient.csv")
    agreed = rows("markov_des.csv")
    compare = [dict(metric=metric, stationary=value,
                    **interval(float(r[metric]) for r in agreed)) for metric, value in m["analytical"].items()]
    save_csv(PROCESSED / "markov_comparison.csv", compare)
    fig, axes = plt.subplots(1,2,figsize=(10,4.2))
    h = [float(x["hour"]) for x in transient]
    for ax, key, title in zip(axes, ["block","mean_queue"], ["Блокировка, %", "Средняя очередь, проект"]):
        scale = 100 if key == "block" else 1
        ax.plot(h, [scale*float(r[key]) for r in transient], color=COLORS[0], label="Переходный режим")
        ax.axhline(scale*m["analytical"][key], color=COLORS[1], linestyle="--", label="Стационарный расчёт")
        v = next(r for r in compare if r["metric"] == key)
        ax.axhspan(scale*v["lo"], scale*v["hi"], alpha=.3, color=COLORS[2], label="DES, 95% интервал")
        ax.set(xlabel="Модельное время, ч", ylabel=title)
        ax.legend(fontsize=8)
    fig.suptitle("Ручная модерация · M/M/2/26 из пустой системы")
    save_figure(fig, "markov")

    fig, axes = plt.subplots(1,2,figsize=(11,4.6))
    comparative = rows("sd_des_comparison.csv")
    sd = rows("sd_series.csv")
    labels = {"base":"База","demand":"Спрос 6,5 проекта/ч","shock":"Шок мощности",
              "shock_buffer":"Шок и масштабирование","growth":"Эндогенный рост"}
    for color, name in zip(COLORS, labels):
        x = [r for r in sd if r["scenario"] == name]
        axes[0].plot([int(r["hour"]) for r in x], [float(r["queue"]) for r in x], color=color,
                     label=labels[name])
    shock = [r for r in comparative if r["scenario"] == "shock"]
    for col, color, label in [("sd_queue",COLORS[0],"SD"),("des_queue",COLORS[1],"DES · 6 повторений")]:
        axes[1].plot([int(r["hour"]) for r in shock], [float(r[col]) for r in shock], color=color, label=label)
    for ax in axes:
        ax.axvspan(168, 240, color="#E2E8F0", alpha=.5, label="Снижение R3 · 72 ч")
        ax.set(xlabel="Модельное время, ч", ylabel="Очередь R3, проектов")
        ax.legend(fontsize=8)
    axes[0].set_title("Сценарии SD")
    axes[1].set_title("Сценарий шока · SD и DES")
    save_figure(fig, "sd")


if __name__ == "__main__":
    sections = {"optimization": optimization, "agents": agents, "continuous": continuous}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=(*sections, "all"), default="all")
    name = parser.parse_args().section
    for section in sections.values() if name == "all" else (sections[name],):
        section()
