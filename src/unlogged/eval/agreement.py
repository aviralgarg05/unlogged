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
from random import Random


@dataclass
class Agreement:
    n: int
    raw: float
    kappa: float
    ac1: float
    alpha: float = 0.0
    alpha_ci: tuple[float, float] = (0.0, 0.0)
    per_category: dict[str, float] = field(default_factory=dict)
    confusion: dict[tuple[str, str], int] = field(default_factory=dict)
    marginals: dict[str, tuple[int, int]] = field(default_factory=dict)
    disagreements: list[tuple[str, str, str]] = field(default_factory=list)

    def table(self) -> str:
        lo, hi = self.alpha_ci
        lines = [
            "| measure | value |",
            "|---|---|",
            f"| events labelled by both | {self.n} |",
            f"| raw agreement | {self.raw:.1%} |",
            f"| Krippendorff's alpha (nominal) | {self.alpha:.3f} ({lo:.3f} to {hi:.3f}) |",
            f"| Cohen's kappa | {self.kappa:.3f} |",
            f"| Gwet's AC1 | {self.ac1:.3f} |",
            "",
            "| call | first pass | second pass | agreed when either said it |",
            "|---|---|---|---|",
        ]
        for call, (a, b) in sorted(self.marginals.items()):
            lines.append(f"| {call} | {a} | {b} | {self.per_category.get(call, 0):.0%} |")
        return "\n".join(lines)

    def confusion_table(self) -> str:
        calls = sorted(self.marginals)
        lines = ["| first \\ second | " + " | ".join(calls) + " |", "|---" * (len(calls) + 1) + "|"]
        for a in calls:
            cells = [str(self.confusion.get((a, b), 0)) for b in calls]
            lines.append(f"| **{a}** | " + " | ".join(cells) + " |")
        return "\n".join(lines)


def krippendorff_alpha(pairs: list[tuple[str, str]]) -> float:
    """Nominal alpha for two ratings per unit.

    The coefficient the reliability literature asks for when the number of raters per item
    varies, which is the case across a corpus where different people read different threads.
    With two raters and complete data it coincides with kappa on a two-category problem — the
    textbook 2x2 example gives 0.40 for both — and the two come apart as categories multiply.
    """
    o: Counter[tuple[str, str]] = Counter()
    for a, b in pairs:
        o[(a, b)] += 1
        o[(b, a)] += 1
    totals: Counter[str] = Counter()
    for (a, _), count in o.items():
        totals[a] += count
    n = sum(totals.values())
    if n < 2:
        return 1.0
    disagreeing = sum(v for (a, b), v in o.items() if a != b)
    expected = sum(totals[a] * totals[b] for a in totals for b in totals if a != b)
    if expected == 0:
        return 1.0
    return 1.0 - (n - 1) * disagreeing / expected


def score(first: dict[str, str], second: dict[str, str], *, bootstrap: int = 2000) -> Agreement:
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

    alpha = krippendorff_alpha(pairs)

    # A percentile bootstrap over the units, seeded so the published figure is the figure
    # anyone re-running this gets. An interval matters more than the point estimate at n=31:
    # a coefficient quoted without one invites a reader to treat 0.72 as precise.
    rng = Random(20261015)
    draws = sorted(
        krippendorff_alpha([pairs[rng.randrange(n)] for _ in range(n)]) for _ in range(bootstrap)
    )
    lo = draws[int(0.025 * bootstrap)]
    hi = draws[min(int(0.975 * bootstrap), bootstrap - 1)]

    # Per category: of the events where either reader used this call, how often both did.
    # The rare classes are where a pooled number hides everything interesting.
    per_category = {}
    for c in categories:
        touched = [p for p in pairs if c in p]
        both = sum(1 for a, b in touched if a == b == c)
        per_category[c] = both / len(touched) if touched else 0.0

    return Agreement(
        n=n,
        raw=raw,
        kappa=kappa,
        ac1=ac1,
        alpha=alpha,
        alpha_ci=(lo, hi),
        per_category=per_category,
        confusion=dict(Counter(pairs)),
        marginals={c: (m1[c], m2[c]) for c in categories},
        disagreements=[(e, first[e], second[e]) for e in shared if first[e] != second[e]],
    )
