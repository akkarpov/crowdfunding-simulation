"""Сверка выгрузок непрерывных экспериментов AnyLogic с эталонными рядами."""
import argparse
import csv
from pathlib import Path
import shutil
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SD_CASES = ("base", "demand", "shock", "shock_buffer", "growth")


def rows(path):
    with path.open(encoding="utf8", newline="") as stream:
        return list(csv.DictReader(stream))


def array(records, keys):
    return np.asarray([[float(r[k]) for k in keys] for r in records])


def compare_native(native, reference, native_names, reference_names, horizon):
    times = array(native, ["hour"]).ravel()
    assert len(times) >= horizon and np.all(np.diff(times) > 0), "Неполная или немонотонная трасса"
    assert 0 <= times[0] < 0.001 and abs(times[-1] - horizon) < 0.001
    ref_times = array(reference, ["hour"]).ravel()
    target = array(reference, reference_names)
    interpolated = np.column_stack([np.interp(times, ref_times, col) for col in target.T])
    measured = array(native, native_names)
    assert np.isfinite(measured).all()
    return measured, np.max(np.abs(interpolated - measured), axis=0)


def markov(source):
    trace = source / "crowdfunding-series-manualqueuemarkov-markov.csv"
    native = rows(trace)
    numeric = rows(ROOT / "results/raw/markov_transient.csv")
    columns = [f"p{i}" for i in range(27)]
    measured, errors = compare_native(native, numeric, columns, columns, 240)
    assert np.max(np.abs(measured.sum(axis=1) - 1)) < 1e-9
    assert measured.min() >= -1e-10
    assert errors.max() < 0.003, errors
    optimization = source / "crowdfunding-markov-optimization.csv"
    choices = rows(optimization)
    assert {int(r["channels"]) for r in choices} == {1, 2, 3}
    best = min(choices, key=lambda r: float(r["blocking"]))
    assert int(best["channels"]) == 3 and int(best["cost"]) <= 15
    archive("markov", [(trace, "series.csv"), (optimization, "optimization.csv")])
    print(f"Markov · 240 ч · max ошибка P = {errors.max():.3g} · лучший вариант c = {best['channels']}")


def sd(source, scenario):
    trace = source / f"crowdfunding-series-platformdynamics-{scenario}.csv"
    native = rows(trace)
    assert all(int(r["scenario"]) == scenario for r in native)
    case = SD_CASES[scenario]
    numeric = [r for r in rows(ROOT / "results/raw/sd_series.csv") if r["scenario"] == case]
    native_names = ("manual", "campaigns", "capacity", "desired", "trust", "usersIndex",
                    "arrivals", "paid", "other", "published")
    reference_names = ("manual_pipeline", "campaigns", "capacity", "desired", "trust", "users",
                       "arrived", "paid", "other", "published")
    measured, errors = compare_native(native, numeric, native_names, reference_names, 480)
    manual, campaigns, _, _, _, _, arrived, paid, other, _ = measured.T
    balance = np.max(np.abs(manual + campaigns + paid + other - arrived))
    assert balance < 1e-6, balance
    assert (measured >= -1e-9).all()
    tolerances = np.array([.5, .5, .03, .03, .015, .015, 1, 1, 1, 1])
    if np.any(errors > tolerances):
        raise AssertionError(dict(zip(native_names, errors, strict=True)))
    archive(f"sd-{case}", [(trace, "series.csv")])
    print(f"SD {case} · 480 ч · ошибка баланса {balance:.3g} · выплат {paid[-1]:.2f}")


def archive(case, paths):
    folder = ROOT / "results/native" / case
    folder.mkdir(parents=True, exist_ok=True)
    for source, name in paths:
        shutil.copyfile(source, folder / name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=("markov", "sd"))
    parser.add_argument("--source", type=Path, default=Path(tempfile.gettempdir()))
    parser.add_argument("--scenario", type=int, choices=range(len(SD_CASES)), default=0)
    args = parser.parse_args()
    if args.model == "markov":
        markov(args.source)
    else:
        sd(args.source, args.scenario)
