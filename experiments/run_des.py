"""Запуск эталонного DES с выводом измерений и опциональной трассы."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.des import Simulation, baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2501)
    parser.add_argument("--rate", type=float)
    parser.add_argument("--r3", type=int)
    parser.add_argument("--hours", type=float)
    parser.add_argument("--fixed", action="store_true")
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cfg = baseline()
    for attr, key in [("rate", "arrivals_per_hour"), ("hours", "horizon_hours")]:
        value = getattr(args, attr)
        if value is not None:
            cfg[key] = value
    if args.r3 is not None:
        cfg["resources"]["R3"][0] = args.r3
    if cfg["arrivals_per_hour"] < 0 or cfg["horizon_hours"] <= 0 or cfg["resources"]["R3"][0] <= 0:
        parser.error("интенсивность должна быть ≥0, часы и число каналов — >0")
    sim = Simulation(cfg, args.seed, fixed=args.fixed, trace=args.trace)
    result = sim.run()
    if args.trace:
        result["trace"] = sim.trace
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
