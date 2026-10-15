"""The adjudicator: does this piece of work fall inside the agreed scope or outside it?

This is the irreducible part. Deciding whether "can you also just add the retry" sits
inside "build the checkout page" is a judgement about two pieces of prose, against a
rate card that is itself prose. There is no column to join on.

Requires OPENAI_API_KEY. Without one the project still runs end to end on the keyword
baseline, which is also the evaluation's ablation arm.
"""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path

import structlog

from unlogged.scope.models import Call, Engagement, Verdict, WorkEvent

log = structlog.get_logger(__name__)

# Function calling is available on the Responses API for this model, not on Chat Completions.
MODEL = "gpt-6.1-sol"

CASSETTES = Path(__file__).resolve().parents[3] / "cassettes"

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
- For billable_extra, write work_description as the client will read it on their invoice: what \
was done, in their words, under 60 characters. "Retry handling on card decline", not "matched a \
request" and not a restatement of your reasoning.
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
    "required": [
        "call",
        "clause_id",
        "quoted_span",
        "reason",
        "work_description",
        "category",
        "hours",
        "confidence",
    ],
    "properties": {
        "call": {
            "type": "string",
            "enum": ["included", "billable_extra", "scope_request", "noise"],
        },
        "clause_id": {"type": ["string", "null"]},
        "quoted_span": {"type": ["string", "null"]},
        "reason": {"type": "string"},
        "work_description": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"]},
        "hours": {"type": ["number", "null"]},
        "confidence": {"type": "number"},
    },
}


class Adjudicator:
    name = MODEL

    def __init__(self, engagement: Engagement, api_key: str | None = None):
        self.e = engagement
        # No key is needed to replay recorded verdicts, which is the point of recording them:
        # a judge with no OpenAI account still sees this arm. The client is only constructed
        # when a live call is actually going to happen.
        self._api_key = api_key
        self._client = None
        # Recorded verdicts, keyed on everything that determines one. A judge with no key
        # replays these and sees the model arm beat the baseline; nobody pays for the same
        # eight calls twice. Same contract as the PayPal cassettes in paypal/client.py.
        self.cassettes = CASSETTES
        self.replay = os.environ.get("UNLOGGED_REPLAY", "1") not in ("0", "false", "False", "")

    def _context(self, event: WorkEvent | None = None) -> str:
        when = event.occurred_at if event else None
        clauses = "\n".join(f"[{c.id}] ({c.kind}) {c.text}" for c in self.e.clauses_at(when))
        rates = ", ".join(
            f"{k} at {self.e.currency} {v}/h" for k, v in self.e.rate_card.by_category.items()
        )
        return (
            f"SCOPE CLAUSES\n{clauses}\n\n"
            f"RATE CARD\ndefault {self.e.currency} {self.e.rate_card.default_rate}/h"
            + (f"; {rates}" if rates else "")
        )

    @property
    def client(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "a live call needs OPENAI_API_KEY; set UNLOGGED_REPLAY=1 to replay"
                )
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key)
        return self._client

    @classmethod
    def recorded_for(cls, engagement: Engagement, events: list[WorkEvent]) -> bool:
        """Whether every one of these events already has a recorded verdict."""
        probe = cls(engagement)
        return all((probe.cassettes / f"verdict-{probe._key(e)}.json").exists() for e in events)

    def _key(self, event: WorkEvent) -> str:
        """Everything that changes the answer: the model, the agreement, and the event."""
        # The agreement AS IT STOOD when this event happened. For an engagement whose
        # clauses carry no dates this is every clause, so recordings made before the
        # amendment machinery existed still replay under the same key.
        clauses = "|".join(f"{c.id}:{c.text}" for c in self.e.clauses_at(event.occurred_at))
        blob = f"{MODEL}\x00{clauses}\x00{event.id}\x00{event.text}"
        return hashlib.sha256(blob.encode()).hexdigest()[:20]

    def adjudicate_one(self, event: WorkEvent) -> Verdict:
        cassette = self.cassettes / f"verdict-{self._key(event)}.json"
        if cassette.exists():
            return Verdict.model_validate_json(cassette.read_text())
        if self.replay:
            raise RuntimeError(
                f"No recorded verdict for {event.id} ({cassette.name}). Set UNLOGGED_REPLAY=0 "
                f"with an OPENAI_API_KEY to record one."
            )
        resp = self.client.responses.create(
            model=MODEL,
            input=[
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"{self._context(event)}\n\n"
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
        verdict = Verdict(
            event_id=event.id,
            call=Call(data["call"]),
            clause_id=data["clause_id"],
            quoted_span=data["quoted_span"],
            reason=data["reason"],
            work_description=data.get("work_description"),
            category=data["category"],
            hours=Decimal(str(data["hours"])) if data["hours"] is not None else None,
            confidence=float(data["confidence"]),
        )
        self.cassettes.mkdir(parents=True, exist_ok=True)
        cassette.write_text(verdict.model_dump_json(indent=1))
        return verdict

    def adjudicate(self, events: list[WorkEvent]) -> list[Verdict]:
        return [self.adjudicate_one(e) for e in events]
