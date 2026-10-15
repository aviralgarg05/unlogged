"""The ablation arm.

This is what the product looks like with the model deleted: match a handful of phrases
that sound like a new request. It runs with no API key, so the repo is useful before a
key exists, and it is the column the evaluation has to beat rather than a strawman —
keyword triage over a thread is what people actually fall back on today.

It is expected to be bad in three specific, measurable ways: it fires on polite phrasing
that carries no work ("could you also send me last month's invoice"), it misses work that
arrives with no request at all (a commit, a review thread, a call that overran), and it
cannot tell a request apart from the work that answers it, so where it does fire it bills
the ask and then has nothing left to attach to the delivery.
"""

from __future__ import annotations

import re
from decimal import Decimal

from unlogged.scope.models import Call, Engagement, Verdict, WorkEvent

ASK_PATTERNS = [
    r"\bcan you (also|just)\b",
    r"\bcould you (also|just)\b",
    r"\bwould you mind\b",
    r"\bone more thing\b",
    r"\bwhile you'?re (at it|in there)\b",
    r"\bquick (favou?r|one|ask)\b",
    r"\balso (add|need|want)\b",
]
_ASK = re.compile("|".join(ASK_PATTERNS), re.IGNORECASE)

# A fixed guess, because the baseline has no way to read duration out of prose.
BASELINE_HOURS = Decimal("1.0")


class KeywordBaseline:
    name = "keyword-baseline"

    def __init__(self, engagement: Engagement):
        self.e = engagement

    def adjudicate(self, events: list[WorkEvent]) -> list[Verdict]:
        out: list[Verdict] = []
        for ev in events:
            if _ASK.search(ev.text):
                out.append(
                    Verdict(
                        event_id=ev.id,
                        call=Call.BILLABLE_EXTRA,
                        reason="matched a request-shaped phrase",
                        # Left unset on purpose: matching a phrase tells you nothing about what
                        # the work was, and the fallback below makes that visible on the invoice
                        # rather than papering over it.
                        work_description=None,
                        hours=BASELINE_HOURS,
                        confidence=0.5,
                    )
                )
            else:
                out.append(
                    Verdict(
                        event_id=ev.id,
                        call=Call.NOISE,
                        reason="no request-shaped phrase",
                        confidence=0.5,
                    )
                )
        return out
