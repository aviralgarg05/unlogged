"""The objects the adjudication turns on.

A WorkEvent is something that happened on the real work surface — a Slack message, a
commit, a PR review, a calendar entry. A Verdict places it against the engagement's own
scope clauses. The only interesting question in this product is which side of a prose
line a sentence falls on, so the Verdict must carry the clause it relied on.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Call(StrEnum):
    """What this event is.

    SCOPE_REQUEST exists because a request and the work that answers it are two separate
    events on the thread, and billing both double-charges the client. The obligation is
    created when the client asks; the money attaches when the work is done. Keeping them
    apart is the single most common way a naive pass gets this wrong.
    """

    INCLUDED = "included"  # covered by the agreement; bill nothing
    BILLABLE_EXTRA = "billable_extra"  # work done outside scope; becomes a line item
    SCOPE_REQUEST = "scope_request"  # out-of-scope work ASKED for; bill the work, not the ask
    NOISE = "noise"  # not work at all


class Source(StrEnum):
    SLACK = "slack"
    DISCORD = "discord"
    GITHUB = "github"
    CALENDAR = "calendar"
    EMAIL = "email"


class ScopeClause(BaseModel):
    """One sentence of the agreement. The id is quoted back in every verdict.

    `in_force_from` is when this sentence became part of the agreement. Agreements get
    amended, and a sentence added in February cannot govern work done in December — that is
    true of a contract and it is true of a CONTRIBUTING.md. Leaving it unset means the clause
    was in force from the beginning, which is the normal case.

    This exists because of a real mistake made while building this project's own evaluation
    corpus: two rules were read from the current file and cited against pull requests from two
    months earlier. An adversarial reader caught it and named it exactly — not fabricated
    text, but fabricated authority. The code now makes that error structurally impossible
    rather than relying on whoever writes the engagement to remember.
    """

    id: str
    text: str
    kind: str = Field(default="scope", description="scope | rate | exclusion | approval")
    in_force_from: datetime | None = None


class RateCard(BaseModel):
    """Rates live in prose in the real world; this is the parsed form."""

    default_rate: Decimal
    currency: str = "USD"
    by_category: dict[str, Decimal] = Field(default_factory=dict)
    unit_of_measure: str = "HOURS"

    def rate_for(self, category: str | None) -> Decimal:
        if category and category in self.by_category:
            return self.by_category[category]
        return self.default_rate


class WorkEvent(BaseModel):
    id: str
    source: Source
    author: str
    occurred_at: datetime
    text: str
    permalink: str | None = None

    @property
    def provenance(self) -> str:
        """What the client reads on PayPal's page beside the line item."""
        return f"{self.source.value} {self.occurred_at:%d %b}"


class Verdict(BaseModel):
    event_id: str
    call: Call
    # The clause this decision rests on. Required for BILLABLE_EXTRA and INCLUDED —
    # a verdict that cannot cite the sentence it relied on is not auditable.
    clause_id: str | None = None
    quoted_span: str | None = None
    reason: str
    # What the client sees on their invoice. Deliberately separate from `reason`, which is why
    # this was billable — a client reading "matched a request-shaped phrase" on a line item is
    # being shown our internal justification instead of their own work.
    work_description: str | None = None
    category: str | None = None
    # Bounded, because this number is multiplied by a rate and written onto a real invoice on
    # the strength of text a client wrote. Negative hours issue a credit; four hundred issue a
    # bill nobody agreed to. A single work event that genuinely took more than a working week
    # is not one event, and a model that says otherwise has been talked into it.
    hours: Decimal | None = Field(default=None, ge=0, le=40)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    def is_billable(self) -> bool:
        return self.call is Call.BILLABLE_EXTRA and self.hours is not None

    def is_citable(self) -> bool:
        """Whether this verdict can be defended to the person being charged for it.

        The claim this product makes is that every billed line names the clause it rests on
        and quotes the words that decided it. A verdict with neither is not a weaker version
        of that; it is the thing the product exists instead of. The keyword baseline produces
        exactly this — "Unspecified work (no description produced)", citing nothing — and it
        was allowed to write it onto a real invoice.
        """
        return bool(self.clause_id and self.quoted_span and (self.work_description or "").strip())


class OpeningItem(BaseModel):
    """The agreed work, as it appears on the invoice from day one."""

    name: str
    quantity: Decimal
    unit_price: Decimal
    unit_of_measure: str = "HOURS"


def load_events(lines: Iterable[str]) -> list[WorkEvent]:
    """Parse a thread, and refuse one that names the same event twice.

    Event ids are how everything downstream identifies a piece of work: the ledger's guard
    against double-billing, the verdict cassettes, the agreement sets. Nothing checked them,
    so a file listing one event twice — a bad merge, an importer run twice into the same
    output — billed the client twice for it inside a single apply, with the ledger recording
    one row and agreeing.
    """
    events = [WorkEvent.model_validate_json(line) for line in lines if line.strip()]
    seen: set[str] = set()
    repeated = sorted({e.id for e in events if e.id in seen or seen.add(e.id)})
    if repeated:
        raise ValueError(
            f"the event thread names these twice: {', '.join(repeated)}. "
            f"An id identifies one piece of work, and two of them bill it twice."
        )
    return events


class Engagement(BaseModel):
    id: str
    client_name: str
    client_email: str | None = None
    invoicer_name: str
    currency: str = "USD"
    cap: Decimal | None = Field(default=None, description="Agreed ceiling, stated to the payer")
    clauses: list[ScopeClause] = Field(default_factory=list)
    opening: list[OpeningItem] = Field(default_factory=list)
    rate_card: RateCard

    @model_validator(mode="after")
    def _one_currency(self) -> Engagement:
        """The engagement and its rate card have to agree.

        Currency is declared in four places — here, on the rate card, on every line item, and
        on the invoice itself — and nothing compared them. A GBP engagement with a USD rate
        card produced GBP-labelled lines priced from a dollar card, and the client was billed
        the difference without a word appearing anywhere about it.
        """
        if self.rate_card.currency != self.currency:
            raise ValueError(
                f"engagement is in {self.currency} and its rate card is in "
                f"{self.rate_card.currency}. One of them is wrong, and the client pays either way."
            )
        return self

    @property
    def opening_total(self) -> Decimal:
        return sum((i.quantity * i.unit_price for i in self.opening), Decimal(0))

    def clause(self, clause_id: str | None) -> ScopeClause | None:
        return next((c for c in self.clauses if c.id == clause_id), None)

    def clauses_at(self, when: datetime | None = None) -> list[ScopeClause]:
        """The agreement as it stood at `when`. All of it when nothing is dated."""
        if when is None:
            return list(self.clauses)
        return [c for c in self.clauses if c.in_force_from is None or c.in_force_from <= when]

    def payer_note(self) -> str:
        """Rendered by PayPal as 'Note from seller' on the client's own page."""
        scope = next((c.text for c in self.clauses if c.kind == "scope"), "")
        cap = f" Agreed cap {self.currency} {self.cap:,.2f}." if self.cap is not None else ""
        return f"Agreed scope: {scope}{cap} Extra work is itemised with its source."

    def payer_terms(self) -> str:
        """Every clause, verbatim and labelled, for PayPal's `detail.terms_and_conditions`.

        The note above holds one scope clause and the cap, which is all that fits in a line of
        summary. It left the exclusions off the client's page entirely — and the exclusions are
        what the billed lines cite. A client was being charged for work justified by a clause
        they had never been shown, on an invoice built to be auditable. The clause ids here are
        the same ones each verdict cites, so a disputed line can be traced to its sentence.
        """
        kinds = {"scope": "In scope", "exclusion": "Not included", "approval": "Agreed"}
        lines = [f"{kinds.get(c.kind, c.kind.title())} [{c.id}]: {c.text}" for c in self.clauses]
        if self.cap is not None:
            lines.append(f"Agreed cap: {self.currency} {self.cap:,.2f}.")
        # Deliberately NOT clipped. PayPal caps this field at 4000 characters and the client
        # cannot read what is past the cap, so an engagement with more scope than that has a
        # problem the caller must decide about — not one this should hide by silently cutting
        # the clause list at the point where the exclusions usually live. Clipping here also
        # meant the refusal in Invoices.create could never fire, so the check added to stop
        # exactly this was unreachable.
        return "\n".join(lines)


def line_name(verdict: Verdict) -> str:
    """What goes on the client's invoice line.

    The adjudicator's `reason` explains why we billed it; it is not a description of the work
    and must never reach the payer. When no description was produced — the keyword baseline
    never produces one — say so plainly rather than substituting the justification, because an
    invoice line nobody can read is a visible defect and a silently wrong one is not.
    """
    description = (verdict.work_description or "").strip()
    return description[:120] if description else "Unspecified work (no description produced)"
