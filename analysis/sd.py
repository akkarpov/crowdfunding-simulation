"""Агрегированная SD по очереди R3, активным кампаниям и мощности."""
import csv
import json
from pathlib import Path
import sys

import numpy as np
from scipy.integrate import solve_ivp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.des import ROOT, Simulation, baseline
from experiments.capacity import save_csv

NAMES = ("manual_pipeline", "campaigns", "capacity", "desired", "trust", "users",
         "arrived", "paid", "other", "published", "manual_refused")
HORIZON = 480
SHOCK_AT = 168
RESTORE_AT = 240


def load_calibration():
    d = json.loads((ROOT / "results/raw/des_baseline.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((ROOT / "results/raw/base_projects.csv").open(encoding="utf-8")))
    finished = [float(r["terminal"]) - float(r["decision"]) for r in rows
                if r["terminal"] and r["decision"] and r["outcome"] in {"paid", "disputed", "expired"}]
    return dict(manual_offers=d["resources"]["R3"]["offered"] / d["arrived"],
                publish_fraction=d["published"] /
                    (d["arrived"] - d["resources"]["R3"]["rejected"] - d["nonterminal"] + d["active"]),
                campaign_hours=float(np.mean(finished)),
                paid_fraction=d["outcomes"]["paid"] / sum(d["outcomes"].get(x, 0)
                                                           for x in ("paid", "disputed", "expired")),
                service_hours=baseline()["resources"]["R3"][2])


def actual_capacity(t, scenario):
    return 1 if scenario == "shock" and SHOCK_AT <= t < RESTORE_AT else 2


def derivative(levels, calibration, external_rate, capacity_target, scaling, growth):
    manual, active, capacity, desired, trust, users, *_ = levels
    p = calibration
    input_rate = external_rate * (1 + growth * users)
    manual_attempts = p["manual_offers"] * input_rate
    occupied = min(manual, capacity)
    processed = occupied / p["service_hours"]
    spare = max(capacity + 24 - manual, 0)
    accepted = min(manual_attempts, processed + spare / .75)
    overflow = manual_attempts - accepted
    direct = input_rate - manual_attempts
    published = p["publish_fraction"] * (processed + direct)
    closed = active / p["campaign_hours"]
    successes = p["paid_fraction"] * closed
    rejected = input_rate - accepted - direct + (1 - p["publish_fraction"]) * (processed + direct)
    target = capacity_target + scaling * max(manual - capacity - 2, 0)
    return np.array((accepted - processed, published - closed, (desired - capacity) / 16,
                     (target - desired) / 8, (successes / 5 - trust) / 24,
                     (trust - users) / 48, input_rate, successes, rejected + closed - successes,
                     published, overflow))


def sd(name, demand, step, scaling, growth, calibration):
    times = np.arange(HORIZON + 1)
    start = np.array([0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 0], dtype=float)
    pieces = [(0, SHOCK_AT, 2), (SHOCK_AT, RESTORE_AT, 1), (RESTORE_AT, HORIZON, 2)]         if name == "shock" else [(0, HORIZON, 2)]
    points = []
    for i, (a, b, capacity) in enumerate(pieces):
        grid = times[a if i == 0 else a + 1:b + 1]
        result = solve_ivp(lambda t, y: derivative(y, calibration, demand, capacity, scaling, growth),
                           (a, b), start, method="RK45", rtol=2e-8, atol=1e-9,
                           t_eval=grid, max_step=step)
        assert result.success
        start = result.y[:, -1]
        points.extend(result.y.T)
    data = np.array(points)
    assert data.min() >= -1e-7
    balance = data[:, 0] + data[:, 1] + data[:, 7] + data[:, 8] - data[:, 6]
    assert max(abs(balance)) < 1e-6
    rows = [dict(hour=int(t), queue=max(s[0] - s[2], 0), **dict(zip(NAMES, s)))
            for t, s in zip(times, data)]
    return rows, data


def des_replicate(name, demand, seed):
    cfg = baseline()
    cfg.update(arrivals_per_hour=demand, horizon_hours=HORIZON)
    simulation = Simulation(cfg, seed, scenario=name, fixed=True, samples=True)
    r3 = simulation.resources["R3"]
    if name == "shock":
        simulation.schedule(SHOCK_AT, r3.set_capacity, 1)
        simulation.schedule(RESTORE_AT, r3.set_capacity, 2)
    simulation.run()
    return simulation.snapshots[:HORIZON + 1]


def main():
    calibration = load_calibration()
    assert 0 < calibration["publish_fraction"] <= 1
    scenarios = [("base", 5, 0, 0), ("demand", 6.5, 0, 0),
                 ("shock", 5, 0, 0), ("shock_buffer", 5, .20, 0),
                 ("growth", 5, .20, .15)]
    raw = ROOT / "results/raw"
    all_data = []
    comparison = []
    checks = []
    for name, demand, scaling, growth in scenarios:
        scenario = "shock" if name.startswith("shock") else name
        rows, data = sd(scenario, demand, .5, scaling, growth, calibration)
        _, finer = sd(scenario, demand, .25, scaling, growth, calibration)
        error = float(np.max(abs(data - finer)))
        assert error < .1
        checks.append(dict(scenario=name, grid_difference=error, final_arrivals=rows[-1]["arrived"],
                           final_paid=rows[-1]["paid"], peak_queue=max(r["queue"] for r in rows),
                           queue_24h_after_restore=rows[RESTORE_AT + 24]["queue"]))
        all_data.extend(dict(scenario=name, **r) for r in rows)
        if name in {"base", "demand", "shock"}:
            reference = [des_replicate(name, demand, seed) for seed in range(6401, 6407)]
            for row in rows:
                t = row["hour"]
                simulated = [rep[t] for rep in reference]
                comparison.append(dict(scenario=name, hour=t,
                    sd_queue=row["queue"], des_queue=np.mean([r["R3_queue"] for r in simulated]),
                    sd_published=row["published"], des_published=np.mean([r["published"] for r in simulated]),
                    sd_campaigns=row["campaigns"], des_campaigns=np.mean([r["active"] for r in simulated])))
    save_csv(raw / "sd_series.csv", all_data)
    save_csv(raw / "sd_des_comparison.csv", comparison)
    save_csv(ROOT / "results/processed/sd_checks.csv", checks)
    (raw / "sd_calibration.json").write_text(json.dumps(calibration, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
