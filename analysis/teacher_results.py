"""Приёмочные таблицы и графики по исходному заданию преподавателя."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
from statistics import mean
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.capacity_results import COLORS, METRICS, PROCESSED, interval, rows, save_figure, series
from experiments.capacity import run_series, save_csv
import matplotlib.pyplot as plt


def series_groups(filename):
    groups = defaultdict(list)
    for row in series(filename):
        groups[row["scenario"]].append(row)
    return groups


def metrics(row):
    return {
        "throughput": row["throughput"],
        "payouts": row["payout_throughput"],
        "mean_queue": sum(r["average_queue"] for r in row["resources"].values()),
        "avg_utilization": row["utilization"],
        "sum_utilization": sum(r["utilization"] for r in row["resources"].values()),
        "sla_failure": row["sla"]["failure"],
        "technical": row["outcomes"].get("technical", 0) / row["arrived"],
    }


def summarize(group):
    values = [metrics(r) for r in group]
    return {key: mean(v[key] for v in values) for key in values[0]}


def score(row):
    return .65 * row["throughput"] / 5 - .35 * row["sum_utilization"] / 8


def allowed(row):
    from experiments.optimization import MAX_REJECTED, MAX_SLA, MIN_PAYOUT

    return (row["sla_failure"] <= MAX_SLA and row["payouts"] >= MIN_PAYOUT
            and row["technical"] <= MAX_REJECTED and row["cost"] <= 74)


def factorial_response(design, figure_name='factorial_response'):
    factors = (("arrival_rate", "Поток"), ("R2", "R2"), ("R3", "R3"), ("R4", "R4"))
    responses = (("throughput", "Завершения, проект/ч", 1),
                 ("payouts", "Выплаты, проект/ч", 1),
                 ("mean_queue", "Сумма очередей, заявок", 1),
                 ("sla_failure", "Нарушения SLA, %", 100))
    fig, axes = plt.subplots(4, 4, sharey="row", figsize=(12.8, 9.2))
    for i, (field, label, scale) in enumerate(responses):
        for j, (key, factor) in enumerate(factors):
            axis = axes[i, j]
            levels = sorted({row[key] for row in design})
            values = [scale * mean(row[field] for row in design if row[key] == level) for level in levels]
            axis.plot(levels, values, marker="o", color=COLORS[j])
            axis.set_xticks(levels, [str(level).replace(".", ",") for level in levels])
            axis.grid(axis="y", alpha=.25)
            if i == 0:
                axis.set_title(factor)
            if j == 0:
                axis.set_ylabel(label)
    fig.suptitle("Факторный план · средние отклики на крайних уровнях")
    save_figure(fig, figure_name)


def section_four():
    controls = []
    for name, group in series_groups("capacity.jsonl").items():
        if name in {"base", "r3_1", "r3_4"} or (group[0]["config"]["rate"] in (2.5, 10)
                                                and group[0]["config"]["caps"]["R3"] == 2):
            config = group[0]["config"]
            controls.append(dict(scenario=name, arrival_rate=config["rate"], r3=config["caps"]["R3"],
                                 repetitions=len(group), **summarize(group)))
    assert {(r["arrival_rate"],r["r3"]) for r in controls} == {(5,1),(5,2),(5,4),(2.5,2),(10,2)}
    save_csv(PROCESSED / "controls_before_after.csv", controls)
    for label, filename in [("factorial_design", "factorial.jsonl"), ("multiobjective_screen", "search.jsonl")]:
        results = []
        for scenario, group in series_groups(filename).items():
            config = group[0]["config"]
            values = dict(scenario=scenario, arrival_rate=config["rate"],
                          **{r:config["caps"][r] for r in ("R2","R3","R4")},
                          cost=group[0]["cost"], repetitions=len(group), **summarize(group))
            values["feasible"] = allowed(values)
            values["objective"] = score(values)
            results.append(values)
        feasible = [row for row in results if row["feasible"]]
        if filename == "factorial.jsonl":
            factorial_response(results)
        else:
            for r in results:
                r["pareto"] = r["feasible"] and not any(
                    o["throughput"] >= r["throughput"] and o["sum_utilization"] <= r["sum_utilization"]
                    and (o["throughput"],o["sum_utilization"]) != (r["throughput"],r["sum_utilization"])
                    for o in feasible)
            results.sort(key=lambda r: (-int(r["feasible"]), -r["objective"], r["cost"]))
        save_csv(PROCESSED / (label+".csv"), results)

    assert feasible
    best = results[0]
    low_cost = min(feasible, key=lambda r: (r["cost"], -r["objective"]))
    fig, ax = plt.subplots(figsize=(9.4, 5.4))
    for tag, label, color in [(False,"Вне ограничений","#94A3B8"), (True,"Допустимые",COLORS[0])]:
        subset = [r for r in results if r["feasible"] == tag]
        ax.scatter([r["sum_utilization"] for r in subset], [r["throughput"] for r in subset],
                   label=label, color=color, s=36, alpha=.8)
    frontier = sorted([r for r in results if r["pareto"]], key=lambda r: r["sum_utilization"])
    ax.plot([r["sum_utilization"] for r in frontier], [r["throughput"] for r in frontier], lw=1,
            color=COLORS[0], alpha=.7, label="Граница Парето")
    ax.scatter(best["sum_utilization"],best["throughput"],s=140,marker="*",color=COLORS[3],
               zorder=4,label="Максимум взвешенной цели")
    ax.set(xlabel="Сумма коэффициентов загрузки (0–8)",ylabel="Завершения, проектов/ч",
           title="Многокритериальная постановка · эталонная сетка из 100 конфигураций")
    ax.legend()
    save_figure(fig,"weighted_objective")
    configs = [("weighted",best), ("capacity",low_cost)]
    jobs = [(name,seed,5,{k:result[k] for k in ("R2","R3","R4")},2160,True,{})
            for name,result in configs for seed in range(5501,5511)]
    trials = run_series("multiobjective_validation.jsonl",jobs)
    output=[]
    for name,result in configs:
        cases=[r for r in trials if r["scenario"]==name]
        metrics_by_case=[metrics(r) for r in cases]
        for key in ("throughput","payouts","sum_utilization","sla_failure","technical","objective"):
            obs=[score(r) if key=="objective" else r[key] for r in metrics_by_case]
            output.append(dict(scenario=name, R2=result["R2"],R3=result["R3"],R4=result["R4"],
                               cost=result["cost"],metric=key,**interval(obs)))
    save_csv(PROCESSED / "multiobjective_validation.csv",output)


def section_five(native=False):
    figure_name = "markov_all_states"
    if native:
        path = PROCESSED.parent / "native/markov/series.csv"
        with path.open(encoding="utf8", newline="") as stream:
            data = list(csv.DictReader(stream))
        figure_name = "markov_native_probabilities"
    else:
        data = rows("markov_transient.csv")
    labels=[k for k in data[0] if k.startswith("p") and k[1:].isdigit()]
    assert len(labels)==27
    fig, axes=plt.subplots(3,1,figsize=(11,10),sharex=True,layout=None)
    t=[float(r["hour"]) for r in data]
    palette=plt.get_cmap("tab10")
    for block,ax in enumerate(axes):
        selected=labels[9*block:9*(block+1)]
        for i,key in enumerate(selected):
            ax.plot(t,[float(r[key]) for r in data],lw=1.5,label=f"n={key[1:]}",color=palette(i))
        ax.set_ylabel("Вероятность")
        ax.legend(loc="center left",bbox_to_anchor=(1.02,.5),fontsize=9,ncol=2)
    axes[-1].set_xlabel("Модельное время, ч")
    fig.suptitle("M/M/2/26 · переходные вероятности для всех 27 состояний")
    save_figure(fig,figure_name)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",type=int,choices=(4,5))
    parser.add_argument("--native",action="store_true",help="График по нативному ряду Markov")
    args = parser.parse_args()
    if args.native and args.stage != 5:
        parser.error("--native требует этап 5")
    if args.stage == 4:
        section_four()
    else:
        section_five(args.native)
