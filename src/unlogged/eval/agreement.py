"""How much two readers of the same thread actually agree.

This project tried to build a ground-truth set out of a real repository's issue briefs and
pull-request threads, and reported the attempt as a narrative failure: every engagement came
back from an independent reader with a defect. That is true and it is also not a measurement.
"Fourteen attempts failed" tells a reader nothing about whether the task is hard, whether the
labellers were careless, or whether the disagreements were concentrated in one judgement.

So the two passes are scored against each other here. Both statistics are reported, for a
reason:

* **Cohen's kappa** corrects raw agreement for the agreement expected by chance. It is the
  conventional number and a reader will look for it.
* **Gwet's AC1** exists because kappa has a known failure, the "kappa paradox": when one
  category dominates, the chance-correction term grows and kappa collapses even though the
  raters agree on nearly everything. The categories here are badly skewed — about half of
  every thread is noise — so reporting kappa alone would understate agreement in exactly the
  way that failure predicts.

Reporting both, with the marginals beside them, lets a reader see the skew rather than take
either number on faith. The disagreements are listed individually for the same reason: six
disagreements that are all the same judgement mean something different from six scattered
ones, and only the list shows which.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Agreement:
    n: int
    raw: float
    kappa: float
    ac1: float
    marginals: dict[str, tuple[int, int]] = field(default_factory=dict)
    disagreements: list[tuple[str, str, str]] = field(default_factory=list)

    def table(self) -> str:
        lines = [
            "| measure | value |",
            "|---|---|",
            f"| events labelled by both | {self.n} |",
            f"| raw agreement | {self.raw:.1%} |",
            f"| Cohen's kappa | {self.kappa:.3f} |",
            f"| Gwet's AC1 | {self.ac1:.3f} |",
            "",
            "| call | first pass | second pass |",
            "|---|---|---|",
        ]
        for call, (a, b) in sorted(self.marginals.items()):
            lines.append(f"| {call} | {a} | {b} |")
        return "\n".join(lines)


def score(first: dict[str, str], second: dict[str, str]) -> Agreement:
    """Compare two label sets over whatever events they both cover.

    Events only one pass labelled are excluded rather than counted as disagreement: a reader
    who did not look at an event has not disagreed about it, and treating silence as a verdict
    would make the number depend on how much each pass chose to cover.
    """
    shared = sorted(set(first) & set(second))
    n = len(shared)
    if n == 0:
        raise ValueError("the two passes label no event in common")

    pairs = [(first[e], second[e]) for e in shared]
    categories = sorted({c for pair in pairs for c in pair})
    agreed = sum(1 for a, b in pairs if a == b)
    raw = agreed / n

    m1, m2 = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)

    # Cohen: chance agreement from each rater's own marginal distribution.
    pe = sum((m1[c] / n) * (m2[c] / n) for c in categories)
    kappa = 1.0 if pe == 1 else (raw - pe) / (1 - pe)

    # Gwet: chance agreement from how evenly the categories are used overall, which is what
    # stops a dominant category from inflating the correction.
    k = len(categories)
    if k < 2:
        ac1 = 1.0
    else:
        shares = [(m1[c] + m2[c]) / (2 * n) for c in categories]
        pe_g = sum(p * (1 - p) for p in shares) / (k - 1)
        ac1 = 1.0 if pe_g == 1 else (raw - pe_g) / (1 - pe_g)

    return Agreement(
        n=n,
        raw=raw,
        kappa=kappa,
        ac1=ac1,
        marginals={c: (m1[c], m2[c]) for c in categories},
        disagreements=[(e, first[e], second[e]) for e in shared if first[e] != second[e]],
    )
