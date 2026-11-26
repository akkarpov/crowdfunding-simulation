"""Парные эксперименты мощности на эталонном DES."""
from concurrent.futures import ProcessPoolExecutor
import csv
import itertools
import json
import os
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.des import ROOT, Simulation, baseline, distribution, sla

SEEDS = list(range(2501, 2511))
SCENARIOS = {
    "base": (5, {}),
    "r3_3": (5, {"R3": 3}),
    "r3_4": (5, {"R3": 4}),
    "r2_3": (5, {"R2": 3}),
    "r4_5": (5, {"R4": 5}),
    "redistribute": (5, {"R2": 1, "R3": 3}),
    "r3_1": (5, {"R3": 1}),
    "load_half": (2.5, {}),
    "load_2x": (10, {}),
    "load_1_2x": (6, {"R3": 3}),
    "load_1_4x": (7, {"R3": 3}),
    "r3_3_r4_5": (5, {"R3": 3, "R4": 5}),
}
RAW = ROOT / "results/raw"


def segment(p, cutoff, threshold):
    return (p.arrival, p.decision if p.decision is not None else p.terminal,
            p.decision is not None)


def run_job(job):
    name, seed, rate, caps, hours, fixed, options = job
    cfg = baseline()
    cfg.update(arrivals_per_hour=rate, horizon_hours=hours)
    for key, value in caps.items():
        cfg["resources"][key][0] = value
    samples = name == "base" and seed == SEEDS[0] and hours == 2160
    sim_type = Simulation
    run_options = options.copy()
    if run_options.pop('agent_based', False):
        from analysis.abm import AgentSimulation
        sim_type = AgentSimulation
    sim = sim_type(cfg, seed, name, fixed=fixed, samples=samples, **run_options)
    start = perf_counter()
    result = sim.run()
    result["wall_seconds"] = perf_counter() - start
    result["config"] = dict(rate=rate, caps={k: x[0] for k, x in cfg["resources"].items()},
                            fixed=fixed, hours=hours, **options)
    if samples:
        save_csv(RAW / "base_queue_trace.csv", sim.snapshots)
        records = [dict(project=p.id, category=p.category, reputation=p.reputation,
                        target_kopecks=p.target, manual=int(p.manual), track=p.route,
                        disputed=int(p.disputed), arrival=p.arrival, decision=p.decision,
                        outcome=p.outcome, terminal=p.terminal) for p in sim.projects]
        save_csv(RAW / "base_projects.csv", records)
    if "heavy_share" in options:
        result["groups"] = {}
        for label, group in [(key, [p for p in sim.projects if p.heavy == flag])
                             for key, flag in [("light", False), ("heavy", True)]]:
            result["groups"][label] = dict(
                waiting=distribution(w for p in group for w in p.manual_waits),
                sla=sla((segment(p, sim.t, cfg["sla_hours"]["moderation"]) for p in group),
                        sim.t, cfg["sla_hours"]["moderation"]))
    return result


def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_series(filename, jobs):
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / filename
    path_pending = path.with_suffix(".part")
    metrics_old = {}
    rebuild = os.environ.get("CROWDFUNDING_REBUILD") == "1"
    if path.exists() and not rebuild:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if path_pending.exists() and not rebuild:
        for line in path_pending.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            metrics_old[(r["scenario"], r["seed"])] = r
    jobs = [job for job in jobs if tuple(job[:2]) not in metrics_old]
    workers = max(1, int(os.environ.get("CROWDFUNDING_WORKERS", min(5, os.cpu_count() or 1))))
    with path_pending.open("w" if rebuild else "a", encoding="utf-8", newline="\n") as out:
        def save(results):
            for result in results:
                metrics_old[(result["scenario"], result["seed"])] = result
                out.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
                out.flush()

        try:
            executor = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
        except PermissionError:
            executor = None
        if executor is None:
            save(map(run_job, jobs))
        else:
            with executor:
                save(executor.map(run_job, jobs))
    path_pending.replace(path)
    return list(metrics_old.values())


if __name__ == "__main__":
    jobs = [(name, seed, rate, caps, 2160, True, {})
            for (name, (rate, caps)), seed in itertools.product(SCENARIOS.items(), SEEDS)]
    run_series("capacity.jsonl", jobs)
