"""The objects the adjudication turns on.

A WorkEvent is something that happened on the real work surface — a Slack message, a
commit, a PR review, a calendar entry. A Verdict places it against the engagement's own
scope clauses. The only interesting question in this product is which side of a prose
line a sentence falls on, so the Verdict must carry the clause it relied on.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class Call(StrEnum):
    INCLUDED = "included"          # inside the agreed scope; bill nothing
    BILLABLE_EXTRA = "billable_extra"  # real work, outside scope; becomes a line item
    NOISE = "noise"                # not work at all


class Source(StrEnum):
    SLACK = "slack"
    DISCORD = "discord"
    GITHUB = "github"
    CALENDAR = "calendar"
    EMAIL = "email"


class ScopeClause(BaseModel):
    """One sentence of the agreement. The id is quoted back in every verdict."""

    id: str
    text: str
    kind: str = Field(default="scope", description="scope | rate | exclusion | approval")


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
    category: str | None = None
    hours: Decimal | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    def is_billable(self) -> bool:
        return self.call is Call.BILLABLE_EXTRA and self.hours is not None


class Engagement(BaseModel):
    id: str
    client_name: str
    client_email: str | None = None
    invoicer_name: str
    currency: str = "USD"
    cap: Decimal | None = Field(default=None, description="Agreed ceiling, stated to the payer")
    clauses: list[ScopeClause] = Field(default_factory=list)
    rate_card: RateCard

    def clause(self, clause_id: str | None) -> ScopeClause | None:
        return next((c for c in self.clauses if c.id == clause_id), None)

    def payer_note(self) -> str:
        """Rendered by PayPal as 'Note from seller' on the client's own page."""
        scope = next((c.text for c in self.clauses if c.kind == "scope"), "")
        cap = f" Agreed cap {self.currency} {self.cap:,.2f}." if self.cap is not None else ""
        return f"Agreed scope: {scope}{cap} Extra work is itemised with its source."
