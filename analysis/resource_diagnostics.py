"""Диагностика ресурсов и миграции узкого места по исходному заданию."""
from collections import defaultdict
from pathlib import Path
from statistics import mean
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.capacity_results import COLORS, PROCESSED, rows, save_figure, series
from analysis.des import Simulation, baseline
from experiments.capacity import save_csv
import matplotlib.pyplot as plt
import numpy as np


def series_groups(filename):
    groups = defaultdict(list)
    for row in series(filename):
        groups[row["scenario"]].append(row)
    return groups


def section_three():
    data = rows("base_queue_trace.csv")
    resources = baseline()["resources"]
    hours = [float(r["hour"]) for r in data]
    cycle = Simulation(baseline(), 2501, fixed=True)
    cycle.run()
    summary = []
    wait_hist = []
    for plot, title, unit in [("queue", "Очередь", "заявок"),
                              ("busy", "Занятые каналы на снимке", "% мощности"),
                              ("waiting", "Распределение ожидания", "% визитов")]:
        fig, axes = plt.subplots(4, 2, figsize=(13.2, 10.0), layout=None)
        for ax, (resource, settings) in zip(axes.ravel(), resources.items()):
            result = cycle.resources[resource]
            if plot == "waiting":
                waits = np.asarray(result.waits)
                bins = np.array([-1e-12,.000000001,.01,.05,.25,1,2,4,8,16,32,np.inf])
                counts = np.histogram(waits, bins)[0]
                total = counts.sum()
                y = 100 * counts / total if total else counts
                ax.bar(range(len(y)), y, color=COLORS[0], width=.78)
                ax.set_xticks(range(len(y)), ["0","<0,01","0,05","0,25","1","2","4","8","16","32",">32"],
                              fontsize=7)
                ax.set_xlabel("Верхняя граница интервала, ч")
                for left, right, count in zip(bins[:-1], bins[1:], counts):
                    wait_hist.append(dict(resource=resource, lower_h=left, upper_h=right, visits=int(count)))
            else:
                values = [int(r[f"{resource}_{plot}"]) for r in data]
                if plot == "busy":
                    values = [100 * v / settings[0] for v in values]
                    ax.set_ylim(-3, 105)
                ax.step(hours, values, lw=.9, color=COLORS[0], where="post")
                ax.set_xlabel("Модельное время, ч")
            ax.set_title(resource, loc="left", fontweight="bold")
            ax.set_ylabel(unit)
        fig.suptitle(title + " · базовая конфигурация, seed 2501")
        save_figure(fig, f"all_resources_{plot}")
    save_csv(PROCESSED / "resource_wait_histogram.csv", wait_hist)
    datasets = series_groups("capacity.jsonl")
    for scenario in ("base", "r3_3"):
        for resource in resources:
            samples = [r["resources"][resource] for r in datasets[scenario]]
            summary.append(dict(scenario=scenario, resource=resource,
                utilization=mean(x["utilization"] for x in samples),
                avg_queue=mean(x["average_queue"] for x in samples),
                avg_wait_h=mean(x["waiting"]["mean"] for x in samples),
                rejected=mean(x["rejected"] for x in samples)))
    save_csv(PROCESSED / "bottleneck_migration.csv", summary)


if __name__ == "__main__":
    section_three()
