"""The adjudicator: does this piece of work fall inside the agreed scope or outside it?

This is the irreducible part. Deciding whether "can you also just add the retry" sits
inside "build the checkout page" is a judgement about two pieces of prose, against a
rate card that is itself prose. There is no column to join on.

Requires OPENAI_API_KEY. Without one the project still runs end to end on the keyword
baseline, which is also the evaluation's ablation arm.
"""

from __future__ import annotations

import json
from decimal import Decimal

import structlog

from unlogged.scope.models import Call, Engagement, Verdict, WorkEvent

log = structlog.get_logger(__name__)

# Function calling is available on the Responses API for this model, not on Chat Completions.
MODEL = "gpt-6.1-sol"

SYSTEM = """You adjudicate whether work found on a project's real work surface falls inside \
an agreed scope of work or outside it.

You are given the engagement's scope clauses verbatim, its rate card, and one work event \
(a message, a commit, a review thread, a calendar entry).

Return exactly one verdict:
- included: covered by the agreement, or explicitly non-billable under it. Cite that clause.
- billable_extra: work that was DONE and that no scope clause covers. Cite the clause it \
falls outside of, estimate hours, and name a rate category.
- scope_request: out-of-scope work was ASKED for here, but not performed here. Cite the \
clause it falls outside of. Do NOT estimate hours — the money attaches to the work, not the ask.
- noise: not work. Scheduling, acknowledgements, thanks, admin chatter.

Rules you must follow:
- Always cite the clause id you relied on, and quote the exact span of the event text that \
decided it. A verdict that cannot quote its own evidence is worthless.
- Being asked politely does not make something billable, and arriving without a request does \
not make it unbillable. Judge the work, not the phrasing.
- A request and the work that answers it are separate events. Bill the work once. If you bill \
the ask as well, the client is charged twice for one thing.
- If two readings are genuinely defensible, return the lower-revenue one and say so in reason. \
This bills a real person.
"""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["call", "clause_id", "quoted_span", "reason", "category", "hours", "confidence"],
    "properties": {
        "call": {
            "type": "string",
            "enum": ["included", "billable_extra", "scope_request", "noise"],
        },
        "clause_id": {"type": ["string", "null"]},
        "quoted_span": {"type": ["string", "null"]},
        "reason": {"type": "string"},
        "category": {"type": ["string", "null"]},
        "hours": {"type": ["number", "null"]},
        "confidence": {"type": "number"},
    },
}


class Adjudicator:
    name = MODEL

    def __init__(self, engagement: Engagement, api_key: str):
        from openai import OpenAI  # imported lazily so the package works without the extra

        self.e = engagement
        self.client = OpenAI(api_key=api_key)

    def _context(self) -> str:
        clauses = "\n".join(f"[{c.id}] ({c.kind}) {c.text}" for c in self.e.clauses)
        rates = ", ".join(
            f"{k} at {self.e.currency} {v}/h" for k, v in self.e.rate_card.by_category.items()
        )
        return (
            f"SCOPE CLAUSES\n{clauses}\n\n"
            f"RATE CARD\ndefault {self.e.currency} {self.e.rate_card.default_rate}/h"
            + (f"; {rates}" if rates else "")
        )

    def adjudicate_one(self, event: WorkEvent) -> Verdict:
        resp = self.client.responses.create(
            model=MODEL,
            input=[
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"{self._context()}\n\n"
                        f"WORK EVENT\nsource: {event.source.value}\n"
                        f"author: {event.author}\nat: {event.occurred_at.isoformat()}\n"
                        f"text: {event.text}"
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "verdict",
                    "strict": True,
                    "schema": SCHEMA,
                }
            },
        )
        data = json.loads(resp.output_text)
        return Verdict(
            event_id=event.id,
            call=Call(data["call"]),
            clause_id=data["clause_id"],
            quoted_span=data["quoted_span"],
            reason=data["reason"],
            category=data["category"],
            hours=Decimal(str(data["hours"])) if data["hours"] is not None else None,
            confidence=float(data["confidence"]),
        )

    def adjudicate(self, events: list[WorkEvent]) -> list[Verdict]:
        return [self.adjudicate_one(e) for e in events]
