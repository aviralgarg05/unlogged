"""Measuring whether the model earns its place.

The claim this project has to survive is "the AI is deletable" — that a keyword filter over
a thread would do the same job. That is not answered by asserting it. It is answered by
running both arms over the same labelled events and printing the difference.

Two things make the measurement honest rather than self-serving:

1. The baseline is real practice, not a strawman. Keyword triage over a thread is what
   people actually fall back on today.
2. The errors are asymmetric and are reported separately. Billing a client for work that was
   inside scope, or for a message that contained no work at all, is a different and worse
   failure than missing an extra — one damages a relationship, the other costs money. A
   single accuracy number hides exactly the error that matters, so this never reports one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from unlogged.scope.models import Call, Engagement, Verdict, WorkEvent


class Gold(BaseModel):
    """A hand label. `why` is for the reader of the eval report, not the model."""

    event_id: str
    call: Call
    hours: Decimal | None = None
    why: str = ""


class Adjudicates(Protocol):
    name: str

    def adjudicate(self, events: list[WorkEvent]) -> list[Verdict]: ...


@dataclass
class Result:
    arm: str
    n: int = 0
    # Correct calls, by class.
    correct: int = 0
    # The expensive mistake: billing for something that was not a billable extra.
    overbilled: list[str] = field(default_factory=list)
    # The cheap-but-the-whole-point mistake: real extra work left off the bill.
    missed: list[str] = field(default_factory=list)
    # Right call, wrong class (e.g. called it included when it was noise). Harmless.
    misclassified: list[str] = field(default_factory=list)
    uncited: list[str] = field(default_factory=list)
    money_overbilled: Decimal = Decimal(0)
    money_missed: Decimal = Decimal(0)

    @property
    def accuracy(self) -> float:
        return self.correct / self.n if self.n else 0.0

    @property
    def precision(self) -> float:
        """Of the things it billed, how many should have been billed."""
        billed = self.correct_billable + len(self.overbilled)
        return self.correct_billable / billed if billed else 0.0

    @property
    def recall(self) -> float:
        """Of the things it should have billed, how many did it find."""
        should = self.correct_billable + len(self.missed)
        return self.correct_billable / should if should else 0.0

    correct_billable: int = 0

    def table_row(self) -> str:
        return (
            f"| {self.arm} | {self.accuracy:.0%} | {self.precision:.0%} | {self.recall:.0%} "
            f"| {len(self.overbilled)} | {len(self.missed)} | {len(self.uncited)} "
            f"| ${self.money_overbilled} | ${self.money_missed} |"
        )


def score(
    arm: Adjudicates, events: list[WorkEvent], gold: list[Gold], engagement: Engagement
) -> Result:
    g = {x.event_id: x for x in gold}
    verdicts = {v.event_id: v for v in arm.adjudicate(events)}
    r = Result(arm=arm.name, n=len(gold))

    for ev in events:
        want, got = g.get(ev.id), verdicts.get(ev.id)
        if want is None or got is None:
            continue
        rate = engagement.rate_card.rate_for(got.category)

        if got.call is want.call:
            r.correct += 1
            if want.call is Call.BILLABLE_EXTRA:
                r.correct_billable += 1
                # A verdict that cannot cite the clause it relied on is not auditable,
                # even when the call itself is right.
                if not got.clause_id or not got.quoted_span:
                    r.uncited.append(ev.id)
            continue

        if got.call is Call.BILLABLE_EXTRA:
            r.overbilled.append(ev.id)
            r.money_overbilled += (got.hours or Decimal(0)) * rate
        elif want.call is Call.BILLABLE_EXTRA:
            r.missed.append(ev.id)
            r.money_missed += (want.hours or Decimal(0)) * engagement.rate_card.rate_for(None)
        else:
            r.misclassified.append(ev.id)

    r.money_overbilled = r.money_overbilled.quantize(Decimal("0.01"))
    r.money_missed = r.money_missed.quantize(Decimal("0.01"))
    return r


def report(results: list[Result], engagement: Engagement, gold: list[Gold]) -> str:
    billable = sum(1 for x in gold if x.call is Call.BILLABLE_EXTRA)
    lines = [
        f"# Evaluation — {engagement.id}",
        "",
        f"{len(gold)} hand-labelled work events, of which {billable} are genuine billable extras.",
        "",
        "Accuracy alone is not reported as a headline because the two error classes are not",
        "comparable: **overbilled** means a client was charged for work that was inside scope or",
        "for a message containing no work, and **missed** means real work never reached the bill.",
        "",
        "| arm | accuracy | precision | recall | overbilled | missed | uncited "
        "| $ overbilled | $ missed |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    lines += [r.table_row() for r in results]
    lines += ["", "## Where each arm went wrong", ""]
    for r in results:
        lines.append(f"**{r.arm}**")
        lines.append(f"- overbilled: {', '.join(r.overbilled) or 'none'}")
        lines.append(f"- missed: {', '.join(r.missed) or 'none'}")
        lines.append(f"- billed without citing a clause: {', '.join(r.uncited) or 'none'}")
        lines.append("")
    return "\n".join(lines)


def write_junit(results: list[Result], path: Path) -> None:
    """JUnit XML so CI can gate on the eval rather than only on unit tests."""
    cases = []
    for r in results:
        for eid in r.overbilled:
            cases.append(
                f'<testcase classname="{r.arm}" name="no_overbill_{eid}">'
                f'<failure message="billed a non-extra"/></testcase>'
            )
        for eid in r.missed:
            cases.append(
                f'<testcase classname="{r.arm}" name="no_miss_{eid}">'
                f'<failure message="missed a billable extra"/></testcase>'
            )
        cases.append(f'<testcase classname="{r.arm}" name="scored"/>')
    failures = sum(len(r.overbilled) + len(r.missed) for r in results)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="unlogged-eval" tests="{len(cases)}" failures="{failures}">\n'
        + "\n".join("  " + c for c in cases)
        + "\n</testsuite>\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml)
