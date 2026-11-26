"""M/M/c/K ручной модерации: баланс, переходный режим и согласованный DES."""
import argparse
import json
from pathlib import Path
from random import Random
import sys

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.des import ROOT, baseline
from experiments.capacity import save_csv


def generator(rate, mu, channels, capacity):
    if not 0 <= rate or mu <= 0 or not 1 <= channels <= capacity:
        raise ValueError("Нужны λ ≥ 0, μ > 0 и 1 ≤ c ≤ K")
    g = np.zeros((capacity + 1, capacity + 1))
    for n in range(capacity + 1):
        if n < capacity:
            g[n, n + 1] = rate
        if n > 0:
            g[n, n - 1] = min(n, channels) * mu
        g[n, n] = -g[n].sum()
    return g


def stationary(rate, mu, c, k):
    if rate == 0:
        return np.eye(1, k + 1)[0]
    logs = np.cumsum([0] + [np.log(rate) - np.log(min(n, c) * mu) for n in range(1, k + 1)])
    weights = np.exp(logs - max(logs))
    return weights / weights.sum()


def indicators(p, rate, c):
    n = np.arange(len(p))
    return dict(block=p[-1], has_queue=p[c + 1:].sum(), all_busy=p[c:].sum(),
                mean_system=p @ n, mean_queue=p @ np.maximum(n - c, 0),
                utilization=p @ np.minimum(n, c) / c, effective_rate=rate * (1 - p[-1]))


def des(rate, mu, c, k, horizon, seed):
    rng = Random(seed)
    n = 0
    t = 0
    areas = np.zeros(k + 1)
    offered = rejected = 0
    while t < horizon:
        death = min(n, c) * mu
        if not rate + death:
            areas[n] += horizon - t
            break
        delay = rng.expovariate(rate + death)
        areas[n] += min(delay, horizon - t)
        t += delay
        if t > horizon:
            break
        if rng.random() < rate / (rate + death):
            offered += 1
            if n == k:
                rejected += 1
            else:
                n += 1
        else:
            n -= 1
    return areas / horizon, rejected, offered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "results/raw/des_baseline.json")
    options = parser.parse_args()
    base = json.loads(options.source.read_text(encoding="utf-8"))
    r3 = base["resources"]["R3"]
    c, q, mean, _ = baseline()["resources"]["R3"]
    k = c + q
    rate = r3["offered"] / base["observation_window"][-1]
    mu = 1 / mean
    g = generator(rate, mu, c, k)
    p0 = np.eye(1, k + 1)[0]
    times = np.linspace(0, 240, 241)
    answer = solve_ivp(lambda t, p: g.T @ p, (0, times[-1]), p0, t_eval=times,
                       rtol=1e-10, atol=1e-12)
    assert answer.success
    p = answer.y.T
    assert np.max(abs(p.sum(axis=1) - 1)) < 1e-9 and p.min() > -1e-10
    assert np.max(abs(p[-1] - p0 @ expm(times[-1] * g))) < 1e-8
    equilibrium = stationary(rate, mu, c, k)
    assert np.max(abs(equilibrium @ g)) < 1e-12
    assert np.max(abs(equilibrium[:-1] * rate - equilibrium[1:] * np.tril(g, -1).sum(axis=1)[1:])) < 1e-12
    raw = ROOT / "results/raw"
    np.savetxt(raw / "markov_generator.csv", g, delimiter=",")
    save_csv(raw / "markov_transient.csv", [dict(hour=t, **indicators(row, rate, c),
                  **{f"p{i}": value for i, value in enumerate(row)}) for t, row in zip(times, p)])
    experiments = []
    for seed in range(5801, 5811):
        occupation, rejected, offered = des(rate, mu, c, k, 100_000, seed)
        experiments.append(dict(seed=seed, horizon=100_000, **indicators(occupation, rate, c),
                                observed_rejected=rejected, offered=offered))
    save_csv(raw / "markov_des.csv", experiments)
    save_csv(ROOT / "results/processed/markov_capacity.csv", [
        dict(channels=channels, capacity=channels + q,
             **indicators(stationary(rate, mu, channels, channels + q), rate, channels))
        for channels in range(1, 7)
    ])
    result = dict(lambda_offered=rate, mu=mu, channels=c, capacity=k,
                  analytical=indicators(equilibrium, rate, c), final=indicators(p[-1], rate, c),
                  probability_error=float(np.max(abs(p.sum(axis=1) - 1))),
                  platform=dict(block=r3["rejected"] / r3["offered"],
                                mean_queue=r3["average_queue"], utilization=r3["utilization"]))
    (raw / "markov.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
