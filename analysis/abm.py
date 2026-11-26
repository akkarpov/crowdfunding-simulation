"""Эталонная агентная модель с состояниями проекта и отдельных платежей."""
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial

from analysis.des import Donation, Project, Simulation


class Phase(Enum):
    INTAKE = auto()
    AI = auto()
    MANUAL = auto()
    APPEAL = auto()
    PUBLICATION = auto()
    FUNDRAISING = auto()
    DRAINING = auto()
    ARBITRATION = auto()
    PAYOUT = auto()
    TERMINAL = auto()


@dataclass
class AgentProject(Project):
    phase: Phase = Phase.INTAKE

    def enter(self, source, dest):
        if self.phase not in source:
            raise ValueError(f"{self.id}: {self.phase.name} → {dest.name}")
        self.phase = dest


class PaymentPhase(Enum):
    GATEWAY = auto()
    ACCOUNTING = auto()
    HELP = auto()
    DONE = auto()


@dataclass
class AgentDonation(Donation):
    phase: PaymentPhase = PaymentPhase.GATEWAY

    def enter(self, source, dest):
        if self.phase not in source:
            raise ValueError(f"{self.project.id}/{self.id}: {self.phase.name} → {dest.name}")
        self.phase = dest


class AgentSimulation(Simulation):
    project_type = AgentProject
    donation_type = AgentDonation

    def after_intake(self, p):
        if p.route == "B":
            self.manual(p)
        else:
            p.enter({Phase.INTAKE}, Phase.AI)
            self.offer("R2", p, "ai", partial(self.after_ai, p))

    def manual(self, p, attempt=0):
        p.enter({Phase.INTAKE, Phase.AI, Phase.APPEAL}, Phase.MANUAL)
        super().manual(p, attempt)

    def approve(self, p):
        p.enter({Phase.AI, Phase.MANUAL}, Phase.PUBLICATION)
        p.decision = self.t
        self.offer("R5", p, "publish", partial(self.publish, p))

    def publish(self, p):
        p.enter({Phase.PUBLICATION}, Phase.FUNDRAISING)
        super().publish(p)

    def stop_accepting(self, p):
        if p.phase is Phase.FUNDRAISING:
            p.enter({Phase.FUNDRAISING}, Phase.DRAINING)
        super().stop_accepting(p)

    def support(self, p, reason, resume, fail, donation=None):
        if donation:
            donation.enter({PaymentPhase.GATEWAY, PaymentPhase.ACCOUNTING}, PaymentPhase.HELP)
        else:
            p.enter({Phase.MANUAL}, Phase.APPEAL)
        super().support(p, reason, resume, fail, donation)

    def retry(self, d):
        d.enter({PaymentPhase.HELP}, PaymentPhase.GATEWAY)
        super().retry(d)

    def after_gateway(self, d):
        if self.draw(d.project.id, "payment_error", d.attempt, d.id) < self.c["payment_error_probability"]:
            self.payment_problem(d)
        else:
            d.enter({PaymentPhase.GATEWAY}, PaymentPhase.ACCOUNTING)
            self.offer("R5", d.project, "record", partial(self.credit, d),
                       partial(self.payment_problem, d), d.attempt, d.id)

    def finish_donation(self, d):
        d.enter({PaymentPhase.GATEWAY, PaymentPhase.ACCOUNTING, PaymentPhase.HELP}, PaymentPhase.DONE)
        super().finish_donation(d)

    def settle(self, p):
        if p.phase is not Phase.DRAINING or p.pending:
            return
        p.closing = True
        if p.held < p.target:
            self.finish(p, "expired")
        elif self.draw(p.id, "dispute") < self.c["dispute_probability"][p.route]:
            p.disputed = True
            p.enter({Phase.DRAINING}, Phase.ARBITRATION)
            self.offer("R7", p, "arbitrate", partial(self.arbitration, p),
                       partial(self.finish, p, "disputed"))
        else:
            self.payout(p)

    def payout(self, p):
        p.enter({Phase.DRAINING, Phase.ARBITRATION}, Phase.PAYOUT)
        super().payout(p)

    def finish(self, p, outcome):
        allowed = {
            "paid": {Phase.PAYOUT},
            "expired": {Phase.DRAINING},
            "disputed": {Phase.ARBITRATION},
            "rejected": {Phase.MANUAL, Phase.APPEAL},
            "technical": {Phase.INTAKE, Phase.AI, Phase.MANUAL, Phase.PUBLICATION, Phase.PAYOUT},
        }
        p.enter(allowed[outcome], Phase.TERMINAL)
        super().finish(p, outcome)

    def metrics(self, reason):
        result = super().metrics(reason)
        result["engine"] = "Python ABM"
        assert all((p.phase is Phase.TERMINAL) == (p.outcome is not None) for p in self.projects)
        assert all((d.phase is PaymentPhase.DONE) == (d.finish is not None) for d in self.donations)
        return result
