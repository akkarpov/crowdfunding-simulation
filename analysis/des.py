"""Эталонная DES. Модельное время в часах, деньги в копейках."""
from collections import Counter
from dataclasses import dataclass, field
from functools import partial
import heapq
import json
import math
from pathlib import Path
from random import Random

ROOT = Path(__file__).resolve().parents[1]


def baseline():
    return json.loads((ROOT / "config/baseline.json").read_text(encoding="utf-8"))


def distribution(values):
    values = sorted(values)
    if not values:
        return dict(n=0, mean=None, median=None, p90=None, p95=None, p99=None, max=None)

    def quantile(p):
        lower, part = divmod((len(values) - 1) * p, 1)
        index = int(lower)
        return values[index] + part * (values[min(index + 1, len(values) - 1)] - values[index])

    return dict(n=len(values), mean=sum(values) / len(values), median=quantile(.5),
                p90=quantile(.9), p95=quantile(.95), p99=quantile(.99), max=values[-1])


@dataclass
class Project:
    id: int
    arrival: float
    route: str
    category: str
    reputation: float
    target: int
    fraud: bool
    heavy: bool = False
    suspicion: bool = False
    manual: bool = False
    disputed: bool = False
    decision: float | None = None
    publication: float | None = None
    terminal: float | None = None
    outcome: str | None = None
    accepting: bool = False
    closing: bool = False
    held: int = 0
    confirmed: int = 0
    pending: int = 0
    donation_count: int = 0
    manual_waits: list = field(default_factory=list)
    visits: list = field(default_factory=list)


@dataclass
class Donation:
    project: Project
    id: int
    amount: int
    arrival: float
    attempt: int = 0
    finish: float | None = None
    credited: bool = False


@dataclass
class SupportRequest:
    project: Project
    arrival: float
    reason: str
    donation: Donation | None = None
    finish: float | None = None
    resolved: bool = False


class Resource:
    def __init__(self, sim, name, settings):
        self.sim, self.name = sim, name
        self.capacity, self.limit, self.mean, self.cost = settings
        self.busy = 0
        self.queue = []
        self.last = self.busy_area = self.capacity_area = self.queue_area = 0.0
        self.max_queue = self.offered = self.rejected = self.served = 0
        self.waits = []
        self.durations = []

    def integrate(self):
        elapsed = self.sim.t - self.last
        self.busy_area += elapsed * self.busy
        self.capacity_area += elapsed * self.capacity
        self.queue_area += elapsed * len(self.queue)
        self.last = self.sim.t

    def set_capacity(self, capacity):
        self.integrate()
        self.capacity = capacity
        self._admit()

    def offer(self, project, operation, on_done, on_reject, attempt=0, donation=0):
        self.integrate()
        self.offered += 1
        project.visits.append((self.name, operation, self.sim.t))
        item = (project, operation, on_done, attempt, donation, self.sim.t)
        if self.busy < self.capacity:
            self._start(item)
        elif len(self.queue) < self.limit:
            priority = int(project.heavy and self.sim.priorities and self.name == "R3")
            heapq.heappush(self.queue, (priority, self.offered, item))
            self.max_queue = max(self.max_queue, len(self.queue))
        else:
            self.rejected += 1
            on_reject()

    def _start(self, item):
        project, operation, done, attempt, donation, entered = item
        self.busy += 1
        wait = self.sim.t - entered
        self.waits.append(wait)
        mean = self.mean
        if self.name == "R3":
            project.manual_waits.append(wait)
            if project.heavy:
                mean *= self.sim.heavy_multiplier
        duration = -math.log1p(-self.sim.draw(project.id, operation, attempt, donation)) * mean
        self.sim.schedule(duration, self._complete, done, duration)

    def _admit(self):
        while self.queue and self.busy < self.capacity:
            self._start(heapq.heappop(self.queue)[2])

    def _complete(self, done, duration):
        self.integrate()
        self.busy -= 1
        self.served += 1
        self.durations.append(duration)
        self._admit()
        done()

    def metrics(self):
        self.integrate()
        assert 0 <= self.busy and len(self.queue) <= self.limit
        assert self.offered == self.served + self.busy + len(self.queue) + self.rejected
        return dict(offered=self.offered, served=self.served, rejected=self.rejected,
                    busy=self.busy, queue=len(self.queue), capacity=self.capacity,
                    utilization=self.busy_area / self.capacity_area if self.capacity_area else None,
                    current_utilization=self.busy / self.capacity if self.capacity else None,
                    average_queue=self.queue_area / self.sim.t if self.sim.t else None,
                    max_queue=self.max_queue, waiting=distribution(self.waits),
                    service=distribution(self.durations))


_STREAMS = dict(intake=1, ai=2, manual=3, publish=4, gateway=5, record=6,
                pay_support=7, appeal_support=8, arbitrate=9, payout=10,
                route=11, category=12, reputation=13, target=14, fraud=15,
                ai_check=16, manual_check=17, appeal=18, next_donation=19,
                amount=20, payment_error=21, dispute=22, dispute_upheld=23, heavy=24)
_MASK = (1 << 64) - 1


def sla(observations, cutoff, threshold):
    on_time = late = unknown = mature = mature_late = 0
    for start, finish, service_ok in observations:
        eligible = start <= cutoff - threshold
        mature += eligible
        if finish is None and not eligible:
            unknown += 1
        elif finish is not None and service_ok and finish - start <= threshold:
            on_time += 1
        else:
            late += 1
            mature_late += eligible
    n = on_time + late + unknown
    return dict(n=n, on_time=on_time, late=late, unknown=unknown, mature=mature,
                mature_late=mature_late, failure=mature_late / mature if mature else None,
                lower=late / n if n else None, upper=(late + unknown) / n if n else None)


class Simulation:
    project_type = Project
    donation_type = Donation

    def __init__(self, config, seed, scenario="База", *, fixed=False, heavy_share=0.0,
                 heavy_multiplier=2.5, priorities=False, samples=False, trace=False):
        self.c, self.seed, self.scenario, self.fixed = config, seed, scenario, fixed
        self.heavy_share, self.heavy_multiplier, self.priorities = heavy_share, heavy_multiplier, priorities
        self.t = 0.0
        self.sequence = 0
        self.events = []
        self.projects = []
        self.donations = []
        self.requests = []
        self.outcomes = Counter()
        self.payments = Counter()
        self.finished = 0
        self.confirmed = self.paid = self.refunds = 0
        self.active = self.published = 0
        self.snapshots = [] if samples else None
        self.trace = [] if trace else None
        self.arrival_rng = Random(seed)
        self.resources = {name: Resource(self, name, settings)
                          for name, settings in config["resources"].items()}
        self.cost = sum(r.capacity * r.cost for r in self.resources.values())

    def draw(self, project, stream, attempt=0, donation=0):
        # Ключ проекта и операции сохраняется при изменении порядка событий.
        value = (self.seed * 0x9E3779B97F4A7C15 + project * 0xD1B54A32D192ED03
                 + _STREAMS[stream] * 0x94D049BB133111EB + attempt * 0xBF58476D1CE4E5B9
                 + donation * 0xDB4F0B9175AE2165) & _MASK
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK
        return ((value ^ (value >> 31)) >> 11) * 2 ** -53

    def schedule(self, delay, action, *args):
        assert delay >= 0
        self.sequence += 1
        heapq.heappush(self.events, (self.t + delay, self.sequence, action, args))

    def _schedule_arrival(self):
        rate = self.c["arrivals_per_hour"]
        if rate > 0:
            self.schedule(self.arrival_rng.expovariate(rate), self.arrive)

    def _log(self, event, p, amount=0):
        if self.trace is not None:
            self.trace.append(dict(hour=self.t, project=p.id, event=event, amount_kopecks=amount))

    def sample(self):
        row = dict(hour=self.t, arrived=len(self.projects), terminal=self.finished,
                   paid=self.outcomes["paid"], active=self.active, published=self.published)
        for name, resource in self.resources.items():
            row[f"{name}_queue"] = len(resource.queue)
            row[f"{name}_busy"] = resource.busy
        self.snapshots.append(row)

    def _sample_hour(self):
        self.sample()
        self.schedule(1, self._sample_hour)

    def run(self):
        self._schedule_arrival()
        if self.snapshots is not None:
            self._sample_hour()
        horizon = self.c["horizon_hours"]
        terminal_limit = self.c["terminal_limit"]
        while self.events and self.events[0][0] <= horizon:
            if not self.fixed and self.finished >= terminal_limit:
                break
            self.t, _, action, args = heapq.heappop(self.events)
            action(*args)
        reason = "terminal_limit" if not self.fixed and self.finished >= terminal_limit else "horizon"
        if reason == "horizon":
            self.t = horizon
        if self.snapshots is not None:
            self.sample()
        return self.metrics(reason)

    def arrive(self):
        self._schedule_arrival()
        c = self.c
        pid = len(self.projects) + 1
        u = self.draw(pid, "route")
        cumulative = 0
        route = next(reversed(c["route_probabilities"]))
        for label, probability in c["route_probabilities"].items():
            cumulative += probability
            if u < cumulative:
                route = label
                break
        cats = list(c["categories"])
        category = cats[int(self.draw(pid, "category") * len(cats))]
        reputation = c["reputation_min"] + self.draw(pid, "reputation") * (
            c["reputation_max"] - c["reputation_min"])
        target = c["target_kopecks_min"] + int(self.draw(pid, "target") * (
            1 + c["target_kopecks_max"] - c["target_kopecks_min"]))
        p = self.project_type(pid, self.t, route, category, reputation, target,
                    self.draw(pid, "fraud") < c["fraud_probability"],
                    self.draw(pid, "heavy") < self.heavy_share)
        self.projects.append(p)
        self._log("подача", p)
        self.offer("R1", p, "intake", partial(self.after_intake, p))

    def offer(self, name, p, operation, done, rejected=None, attempt=0, donation=0):
        assert p.terminal is None
        if rejected is None:
            rejected = partial(self.finish, p, "technical")
        self.resources[name].offer(p, operation, done, rejected, attempt, donation)

    def after_intake(self, p):
        if p.route == "B":
            self.manual(p)
        else:
            self.offer("R2", p, "ai", partial(self.after_ai, p))

    def after_ai(self, p):
        sensitivity = self.c["ai_sensitivity"] if p.fraud else self.c["ai_false_positive"]
        p.suspicion = self.draw(p.id, "ai_check") < sensitivity
        if p.suspicion:
            self.manual(p)
        else:
            self.approve(p)

    def manual(self, p, attempt=0):
        p.manual = True
        self.offer("R3", p, "manual", partial(self.after_manual, p, attempt), attempt=attempt)

    def after_manual(self, p, attempt):
        sensitivity = self.c["manual_sensitivity"] if p.fraud else self.c["manual_false_positive"]
        if self.draw(p.id, "manual_check", attempt) >= sensitivity:
            self.approve(p)
        elif attempt < self.c["retry_limit"] and self.draw(p.id, "appeal") < self.c["appeal_probability"]:
            self.support(p, "апелляция", partial(self.manual, p, attempt + 1),
                         partial(self.reject, p))
        else:
            self.reject(p)

    def approve(self, p):
        p.decision = self.t
        self.offer("R5", p, "publish", partial(self.publish, p))

    def reject(self, p):
        p.decision = self.t
        self.finish(p, "rejected")

    def publish(self, p):
        p.publication, p.accepting = self.t, True
        self.active += 1
        self.published += 1
        self._log("публикация", p)
        self.schedule(self.c["campaign_hours"], self.stop_accepting, p)
        self.schedule_donation(p)

    def schedule_donation(self, p):
        c = self.c
        rate = (c["donations_per_hour"] * c["categories"][p.category]
                * (.75 + .5 * p.reputation) * c["transaction_multiplier"][p.route])
        if rate:
            u = self.draw(p.id, "next_donation", donation=p.donation_count + 1)
            self.schedule(-math.log1p(-u) / rate, self.donate, p)

    def donate(self, p):
        if not p.accepting:
            return
        p.donation_count += 1
        p.pending += 1
        u = self.draw(p.id, "amount", donation=p.donation_count)
        amount = int(self.c["pareto_min_kopecks"] / (1 - u) ** (1 / self.c["pareto_shape"]))
        donation = self.donation_type(p, p.donation_count, amount, self.t)
        self.donations.append(donation)
        self._log("пожертвование", p, amount)
        self.gateway(donation)
        self.schedule_donation(p)

    def gateway(self, d):
        self.payments["attempts"] += 1
        self.offer("R4", d.project, "gateway", partial(self.after_gateway, d),
                   partial(self.payment_problem, d), d.attempt, d.id)

    def after_gateway(self, d):
        u = self.draw(d.project.id, "payment_error", d.attempt, d.id)
        if u < self.c["payment_error_probability"]:
            self.payment_problem(d)
        else:
            self.offer("R5", d.project, "record", partial(self.credit, d),
                       partial(self.payment_problem, d), d.attempt, d.id)

    def payment_problem(self, d):
        self.payments["problems"] += 1
        if d.attempt < self.c["retry_limit"]:
            self.support(d.project, "платёж", partial(self.retry, d),
                         partial(self.finish_donation, d), d)
        else:
            self.finish_donation(d)

    def retry(self, d):
        d.attempt += 1
        self.payments["retries"] += 1
        self.gateway(d)

    def support(self, p, reason, resume, fail, donation=None):
        req = SupportRequest(p, self.t, reason, donation)
        self.requests.append(req)

        def complete(callback, resolved):
            req.finish, req.resolved = self.t, resolved
            callback()

        self.offer("R6", p, "pay_support" if donation else "appeal_support",
                   partial(complete, resume, True), partial(complete, fail, False),
                   donation.attempt if donation else 0, donation.id if donation else 0)

    def credit(self, d):
        p = d.project
        assert not d.credited and d.finish is None and p.terminal is None
        d.credited = True
        p.held += d.amount
        p.confirmed += d.amount
        self.confirmed += d.amount
        self._log("зачисление", p, d.amount)
        if p.held >= p.target:
            self.stop_accepting(p)
        self.finish_donation(d)

    def finish_donation(self, d):
        assert d.finish is None
        d.finish = self.t
        d.project.pending -= 1
        self.payments["credited" if d.credited else "failed"] += 1
        self.settle(d.project)

    def stop_accepting(self, p):
        if p.accepting:
            p.accepting = False
            self.active -= 1
            self.settle(p)

    def settle(self, p):
        assert p.pending >= 0
        if p.accepting or p.pending or p.closing:
            return
        p.closing = True
        if p.held < p.target:
            self.finish(p, "expired")
        elif self.draw(p.id, "dispute") < self.c["dispute_probability"][p.route]:
            p.disputed = True
            self.offer("R7", p, "arbitrate", partial(self.arbitration, p),
                       partial(self.finish, p, "disputed"))
        else:
            self.payout(p)

    def arbitration(self, p):
        if self.draw(p.id, "dispute_upheld") < self.c["dispute_upheld_probability"]:
            self.finish(p, "disputed")
        else:
            self.payout(p)

    def payout(self, p):
        assert p.closing and p.held >= p.target and not p.pending and not p.accepting
        self.offer("R8", p, "payout", partial(self.finish, p, "paid"))

    def finish(self, p, outcome):
        assert p.terminal is None and not p.accepting and not p.pending and p.held >= 0
        if outcome == "paid":
            assert p.publication is not None and p.held >= p.target
            self.paid += p.held
        else:
            self.refunds += p.held
        self._log(outcome, p, p.held)
        p.held = 0
        p.terminal, p.outcome = self.t, outcome
        self.outcomes[outcome] += 1
        self.finished += 1

    def metrics(self, reason):
        projects = self.projects
        nonterminal = sum(p.terminal is None for p in projects)
        held = sum(p.held for p in projects)
        assert len(projects) == self.finished + nonterminal
        assert self.finished == sum(self.outcomes.values())
        assert self.active == sum(p.accepting for p in projects)
        assert self.confirmed == self.paid + self.refunds + held
        assert self.confirmed == sum(d.amount for d in self.donations if d.credited)
        assert len(self.donations) == sum(p.pending for p in projects) + self.payments["credited"] + self.payments["failed"]
        assert all(d.attempt <= self.c["retry_limit"] for d in self.donations)
        assert all(p.held >= 0 for p in projects)
        c = self.c["sla_hours"]
        moderation = [(p.arrival, p.decision if p.decision is not None else p.terminal,
                       p.decision is not None) for p in projects]
        resources = {name: r.metrics() for name, r in self.resources.items()}
        capacity_area = sum(r.capacity_area for r in self.resources.values())
        return dict(engine="Python DES", seed=self.seed, scenario=self.scenario, time_unit="hour",
                    observation_window=[0, self.t], stop_reason=reason, arrived=len(projects),
                    terminal=self.finished, nonterminal=nonterminal, active=self.active,
                    published=self.published, outcomes=dict(self.outcomes), cost=self.cost,
                    throughput=self.finished / self.t if self.t else None,
                    payout_throughput=self.outcomes["paid"] / self.t if self.t else None,
                    utilization=sum(r.busy_area for r in self.resources.values()) / capacity_area if capacity_area else None,
                    sla=sla(moderation, self.t, c["moderation"]),
                    payment_sla=sla(((d.arrival, d.finish, d.credited) for d in self.donations), self.t, c["payment"]),
                    support_sla=sla(((r.arrival, r.finish, r.resolved) for r in self.requests), self.t, c["support"]),
                    moderation=distribution(p.decision - p.arrival for p in projects if p.decision is not None),
                    lifecycle=distribution(p.terminal - p.arrival for p in projects if p.terminal is not None),
                    payment_times=distribution(d.finish - d.arrival for d in self.donations if d.finish is not None),
                    payments=dict(self.payments), confirmed=self.confirmed, paid=self.paid, refunded=self.refunds,
                    held=held, resources=resources)
