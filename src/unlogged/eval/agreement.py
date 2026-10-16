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


def alpha_over_units(units: list[list[str]]) -> float:
    """Nominal Krippendorff's alpha for any number of ratings per unit.

    The two-rater form is the special case. This one is what the corpus actually needs: a
    panel of readers where not everyone reads everything, which is the normal shape of an
    annotation effort and the reason alpha is preferred to kappa in the first place.

    Units rated fewer than twice carry no information about agreement and are dropped, which
    is alpha's own convention rather than a choice made here.
    """
    coincidence: Counter[tuple[str, str]] = Counter()
    for ratings in units:
        m = len(ratings)
        if m < 2:
            continue
        for i, a in enumerate(ratings):
            for j, b in enumerate(ratings):
                if i != j:
                    coincidence[(a, b)] += 1 / (m - 1)

    totals: Counter[str] = Counter()
    for (a, _), weight in coincidence.items():
        totals[a] += weight
    n = sum(totals.values())
    if n < 2:
        return 1.0

    disagreeing = sum(v for (a, b), v in coincidence.items() if a != b)
    expected = sum(totals[a] * totals[b] for a in totals for b in totals if a != b)
    if expected == 0:
        return 1.0
    return 1.0 - (n - 1) * disagreeing / expected


def krippendorff_alpha(pairs: list[tuple[str, str]]) -> float:
    """Nominal alpha for two ratings per unit.

    The coefficient the reliability literature asks for when the number of raters per item
    varies, which is the case across a corpus where different people read different threads.
    With two raters and complete data it coincides with kappa on a two-category problem — the
    textbook 2x2 example gives 0.40 for both — and the two come apart as categories multiply.
    """
    return alpha_over_units([[a, b] for a, b in pairs])


@dataclass
class Panel:
    """Several readers over one set of events."""

    readers: list[str]
    n: int
    alpha: float
    unanimous: int
    ceiling: float
    model: float | None = None
    split: dict[str, int] = field(default_factory=dict)

    def table(self) -> str:
        lines = [
            "| measure | value |",
            "|---|---|",
            f"| readers | {len(self.readers)} |",
            f"| events at least two readers labelled | {self.n} |",
            f"| Krippendorff's alpha across the panel | {self.alpha:.3f} |",
            f"| events all of them called the same way | {self.unanimous} of {self.n} |",
            f"| one reader against the rest (the ceiling) | {self.ceiling:.1%} |",
        ]
        if self.model is not None:
            lines.append(f"| the model against the same majority | {self.model:.1%} |")
        return "\n".join(lines)


def panel(readings: dict[str, dict[str, str]], model: dict[str, str] | None = None) -> Panel:
    """Agreement across a panel, and the ceiling a model should be measured against.

    The ceiling is leave-one-out: for each reader, how often they match the majority of the
    others. That is the right comparison for a model, because it is the same question asked of
    a human — not "is the model right", which needs a truth nobody has, but "does the model
    agree with a panel as well as a member of that panel does".
    """
    names = sorted(readings)
    # Every event any reader labelled, not only the ones all of them did. Intersecting down to
    # the common subset is exactly what alpha exists to avoid — a panel where not everyone
    # reads everything is the normal shape of an annotation effort, and discarding the ragged
    # part silently reports a coefficient computed over data the reader was not told about.
    # It happens to change nothing here, because all four readers labelled all 31 events.
    covered = sorted({e for r in readings.values() for e in r})
    units = [[r[e] for r in readings.values() if e in r] for e in covered]
    shared = [e for e, u in zip(covered, units, strict=True) if len(u) >= 2]
    units = [u for u in units if len(u) >= 2]

    def majority(calls: list[str]) -> str | None:
        counts = Counter(calls)
        top, n_top = counts.most_common(1)[0]
        return top if list(counts.values()).count(n_top) == 1 else None

    hits = total = 0
    for e in shared:
        for held_out in names:
            if e not in readings[held_out]:
                continue
            rest = [readings[n][e] for n in names if n != held_out and e in readings[n]]
            winner = majority(rest) if rest else None
            if winner is not None:
                total += 1
                hits += readings[held_out][e] == winner

    model_hits = model_total = 0
    if model:
        for e in shared:
            if e not in model:
                continue
            winner = majority([readings[n][e] for n in names if e in readings[n]])
            if winner is not None:
                model_total += 1
                model_hits += model[e] == winner

    return Panel(
        readers=names,
        n=len(shared),
        alpha=alpha_over_units(units),
        unanimous=sum(1 for u in units if len(set(u)) == 1),
        ceiling=hits / total if total else 0.0,
        model=(model_hits / model_total) if model_total else None,
        split=dict(Counter(c for u in units for c in u)),
    )


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
