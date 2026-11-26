"""Проверка контрольных выгрузок AnyLogic и построение графиков DES."""
from collections import defaultdict
import argparse
import csv
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.capacity_results import COLORS, save_figure
from analysis.des import ROOT
import matplotlib.pyplot as plt
import numpy as np


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def value(text,key):
    m=re.search(rf"(?:^|\s){key}=(\d+)(?:\s|$)",text)
    assert m is not None,key
    return int(m[1])


ABM_CASES = ("abm_sim", "abm_base", "abm_mixed", "abm_mixedpriority")


def full_stop(log, hours):
    return (("reason=project_limit" in log and value(log, "terminal") == 10000)
            or ("reason=horizon" in log and 2159.999 < hours <= 2160))


def accept_des(case,seed,source):
    log=source/f"crowdfunding-platform-{case}-{seed}.txt"
    prefix=f"crowdfunding-native-{case}-{seed}-"
    outputs={name:source/f"{prefix}{name}.csv" for name in ("metrics","resources","trace","waits")}
    text=log.read_text(encoding="utf-8")
    metrics,*extra=read_csv(outputs["metrics"])
    assert not extra
    h=float(metrics["window_h"])
    trace=read_csv(outputs["trace"])
    stats=read_csv(outputs["resources"])
    waits=read_csv(outputs["waits"])
    assert len(stats)==8 and {x["resource"] for x in stats}=={f"R{i}" for i in range(1,9)}
    assert value(text,"arrivals")==value(text,"terminal")+value(text,"unfinished")
    assert value(text,"confirmed")==value(text,"paid")+value(text,"held")+value(text,"refunded")
    for key in ("arrived","terminal","unfinished","payouts","technical","records","retries"):
        assert int(metrics[key])>=0
    assert int(metrics["sla_mature"])>=int(metrics["sla_missed"])>=0
    if case == "research" or case in ABM_CASES[1:]:
        assert sum(int(r["served"]) for r in stats) > 50000
    for resource in stats:
        selector=[r for r in trace if r["resource"]==resource["resource"]]
        assert np.all(np.diff([float(r["hour"]) for r in selector])>=0)
        assert all(0<=int(r["busy"])<=int(r["capacity"]) and int(r["queue"])>=0 for r in selector)
        last=selector[-1]
        assert int(resource["offered"])==int(last["queue"])+int(last["busy"])+int(resource["served"])+int(resource["refused"])
        assert 0<=float(resource["utilization"])<=1
    cases={
        "simulation": lambda: 4.499<h<=4.5 and value(text,"payouts")==3 and all(int(r["served"])>0 for r in stats),
        "count": lambda: "reason=project_limit" in text and value(text,"terminal")==2 and h<4.5,
        "zero": lambda: "reason=horizon" in text and value(text,"arrivals")==0 and 9.999<h<=10,
        "congestion": lambda: any(int(r["refused"])>0 for r in stats),
        "research": lambda: full_stop(text, h),
        **{name: lambda: full_stop(text, h) for name in ABM_CASES[1:]},
        "abm_sim": lambda: (4.499 < h <= 4.5 and value(text, "payouts") == 3
                            and all(int(r["served"]) > 0 for r in stats)),
    }
    assert cases[case](),(case,text)
    extra_class=source/f"{prefix}classes.csv"
    if case in ABM_CASES:
        classes = {row["class"]: row for row in read_csv(extra_class)}
        assert set(classes) == {"light", "heavy"}
        assert sum(int(row["projects"]) for row in classes.values()) == int(metrics["arrived"])
        for row in classes.values():
            if int(row["visits_r3"]) > 0:
                assert np.isfinite(float(row["p95_wait_h"])) and float(row["p95_wait_h"]) >= 0
        if case == "abm_base":
            assert int(classes["heavy"]["projects"]) == 0
        elif case in ABM_CASES[2:]:
            assert all(int(row["projects"]) > 0 and int(row["visits_r3"]) > 0
                       for row in classes.values())
    dest=ROOT/"results/native"/case
    dest.mkdir(parents=True,exist_ok=True)
    for name,path in {"audit":log,**outputs}.items():
        shutil.copyfile(path,dest/(name+path.suffix))
    if case in ABM_CASES:
        shutil.copyfile(extra_class, dest / "classes.csv")
    if case=="research":
        graphs(trace, waits, stats)
    print(f"{case}: окно {h:.6f} ч, инварианты подтверждены")


def compare_agents():
    destination = ROOT / "results/processed/abm_native.csv"
    experiments = {"research": "DES", "abm_base": "ABM, база", "abm_mixed": "ABM, 25% тяжёлых",
                   "abm_mixedpriority": "ABM, приоритет лёгких"}
    records = []
    for name, label in experiments.items():
        folder = ROOT / "results/native" / name
        metrics, = read_csv(folder / "metrics.csv")
        resources = read_csv(folder / "resources.csv")
        manual = next(r for r in resources if r["resource"] == "R3")
        hours = float(metrics["window_h"])
        row = dict(case=name, experiment=label, hours=hours,
                   throughput=int(metrics["terminal"]) / hours,
                   payouts=int(metrics["payouts"]) / hours,
                   mean_queue=sum(float(x["mean_queue"]) for x in resources),
                   r3_mean_queue=float(manual["mean_queue"]),
                   sla_failure=int(metrics["sla_missed"]) / int(metrics["sla_mature"]),
                   light_p95_r3_h="", heavy_p95_r3_h="")
        if name != "research":
            for group in read_csv(folder / "classes.csv"):
                if int(group["visits_r3"]) > 0:
                    row[f"{group['class']}_p95_r3_h"] = float(group["p95_wait_h"])
        records.append(row)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0])
        writer.writeheader()
        writer.writerows(records)
    print(f"Сопоставлены четыре нативных опыта: {destination}")


def graphs(trace, waits, stats):
    by_resource=defaultdict(list)
    for row in trace:
        by_resource[row["resource"]].append(row)
    wait_by_resource=defaultdict(list)
    for row in waits:
        wait_by_resource[row["resource"]].append(float(row["wait_h"]))
    fig, ax=plt.subplots(3,1,figsize=(10.8,8.5))
    keys=(("utilization","Загрузка, %",100),("mean_service_h","Обслуживание, ч",1),("refused","Отказов",1))
    for axis,(key,label,scale) in zip(ax,keys):
        axis.bar([r["resource"] for r in stats],[scale*float(r[key]) for r in stats],color=COLORS[0])
        axis.set_ylabel(label)
    fig.suptitle("Ресурсы R1–R8 · полный эксперимент AnyLogic")
    save_figure(fig,"native_resource_metrics")

    fig, axes = plt.subplots(2, 1, figsize=(10.8, 6.4))
    queues = (("mean_queue", "Средняя длина, заявок"), ("mean_wait_h", "Среднее ожидание, ч"))
    for axis, (key, label) in zip(axes, queues):
        axis.bar([r["resource"] for r in stats], [float(r[key]) for r in stats], color=COLORS[1])
        axis.set_ylabel(label)
    fig.suptitle("Средние показатели очередей R1–R8 · AnyLogic")
    save_figure(fig, "native_queue_summary")
    for name,axis_label,fn in [
        ("queue","Длина очереди",lambda r:int(r["queue"])),
        ("utilization","Занято, %",lambda r:100*int(r["busy"])/int(r["capacity"])),
        ("wait","Визиты, %",None),
    ]:
        fig, axes=plt.subplots(4,2,figsize=(13.2,10.0))
        for axis,(r,sequence) in zip(axes.ravel(),by_resource.items()):
            axis.set_title(r,loc="left")
            axis.set_ylabel(axis_label)
            if fn is not None:
                axis.step([float(p["hour"]) for p in sequence],[fn(p) for p in sequence],
                          where="post",color=COLORS[0],lw=.8)
                axis.set_xlabel("Модельное время, ч")
            else:
                x=np.asarray(wait_by_resource[r])
                edges=np.array([-1e-12,1e-9,.01,.05,.25,1,2,4,8,16,32,np.inf])
                bins=np.histogram(x,edges)[0]
                if bins.sum():
                    axis.bar(range(len(bins)),100*bins/bins.sum(),color=COLORS[0])
                axis.set_xticks(range(len(bins)),["0","0,01","0,05","0,25","1","2","4","8","16","32",">32"],fontsize=8)
                axis.set_xlabel("Верхняя граница интервала, ч")
        fig.suptitle("Очереди и ожидание R1–R8 · полный эксперимент AnyLogic")
        save_figure(fig,"native_"+name)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case",choices=("simulation","count","zero","congestion","research", *ABM_CASES,
                                       "abm_comparison"))
    parser.add_argument("--seed",type=int,default=2501)
    parser.add_argument("--source",type=Path,default=Path(tempfile.gettempdir()))
    args=parser.parse_args()
    if args.case == "abm_comparison":
        compare_agents()
    else:
        accept_des(args.case,args.seed,args.source)
