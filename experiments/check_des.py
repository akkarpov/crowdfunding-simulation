"""Сценарии приёмки эталонного DES."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.des import Simulation, baseline, sla

cases = {}


def run(name, modify=lambda c: None):
    config = baseline()
    config.update(horizon_hours=12, arrivals_per_hour=1, campaign_hours=1,
                  donations_per_hour=6, target_kopecks_min=900, target_kopecks_max=900)
    modify(config)
    sim = Simulation(config, 231, name, trace=True)
    cases[name] = sim.run()
    return sim


def no_load(c):
    c["arrivals_per_hour"] = 0


assert run("Нулевая нагрузка", no_load).finished == 0

small = run("Малая нагрузка")
assert small.outcomes["paid"] > 0
for p in small.projects:
    if p.outcome == "paid":
        assert [r for r, _, _ in p.visits][:2] in (["R1", "R2"], ["R1", "R3"])
        assert p.confirmed >= p.target
        events = [e["event"] for e in small.trace if e["project"] == p.id]
        assert events.count("paid") == 1
        assert events.index("публикация") < events.index("зачисление") < events.index("paid")


def stress(c):
    c["arrivals_per_hour"] = 30
    c["route_probabilities"] = {"B": 1}
    c["resources"]["R3"][:2] = [1, 2]


overload = run("Перегрузка и ручная проверка", stress)
assert overload.resources["R3"].rejected > 0
assert overload.resources["R3"].max_queue == 2


def disputed(c):
    c["route_probabilities"] = {"D": 1}
    c["dispute_upheld_probability"] = 1


arbitration = run("Спор с возвратом", disputed)
assert arbitration.resources["R7"].served > 0 and arbitration.refunds > 0
assert not arbitration.paid


def failures(c):
    c["payment_error_probability"] = 1


payment = run("Ошибка платежа и поддержка", failures)
assert payment.payments["retries"] > 0 and payment.payments["failed"] > 0
assert payment.confirmed == 0


def impossible(c):
    c["target_kopecks_min"] = c["target_kopecks_max"] = 10 ** 12


assert run("Недостижимая цель", impossible).outcomes["expired"] > 0
count = run("Остановка по счётчику", lambda c: c.update(terminal_limit=2))
assert count.finished == 2 and cases["Остановка по счётчику"]["stop_reason"] == "terminal_limit"
assert cases["Нулевая нагрузка"]["stop_reason"] == "horizon"
assert cases["Малая нагрузка"] | {"scenario": "Повтор"} == run("Повтор").metrics("horizon")
assert sla([(0, None, False), (6, None, False), (0, 2, True)], 10, 5) == {
    "n": 3, "on_time": 1, "late": 1, "unknown": 1, "mature": 2, "mature_late": 1,
    "failure": .5, "lower": 1 / 3, "upper": 2 / 3,
}
out = Path(__file__).resolve().parents[1] / "results/raw/des_checks.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"cases": cases, "trace": small.trace}, ensure_ascii=False, indent=2) + "\n",
               encoding="utf-8")
print(f"Проверено сценариев: {len(cases)}")
