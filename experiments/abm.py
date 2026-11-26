"""Сверка агентных состояний с DES и испытание гетерогенности."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.abm import AgentSimulation
from analysis.des import Simulation, baseline
from experiments.capacity import run_series


def main():
    for seed in (6101, 6102, 6103):
        cfg = baseline()
        cfg["horizon_hours"] = 336
        a = AgentSimulation(cfg, seed).run()
        d = Simulation(cfg, seed).run()
        assert a | {"engine": "Python DES"} == d, seed
    jobs = [(f"heavy_{int(share*100)}_{'priority' if priority else 'fifo'}", seed, 5, {}, 504, True,
             dict(heavy_share=share, heavy_multiplier=2.5, priorities=priority, agent_based=True))
            for share in (0, .10, .25, .50, .75) for priority in (False, True)
            for seed in range(6101, 6111) if share or not priority]
    run_series("abm.jsonl", jobs)


if __name__ == "__main__":
    main()
