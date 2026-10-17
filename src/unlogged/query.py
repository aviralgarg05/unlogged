"""Filter, sort and window a list of rows, server-side.

The dashboard's data source declares `capabilities: { pagination, filter, sort }`. AG Studio's
own contract for that declaration is explicit: it forwards the applied filter tree and sort
order and then "trusts that response as-is, with no local re-filtering or re-sorting". So
declaring it is a promise, and this module is the half of the promise that has to be kept.

It was not. `getData` never read `options.sort` at all, and the filter was flattened into bare
`&field=value` query parameters that `read_events` did not declare and FastAPI therefore
dropped — so filtering the Adjudications grid to `call = billable_extra` returned every row
with the filter chip showing, and clicking a column header sorted nothing. On a dashboard whose
subject is money, that is a filtered-looking view of unfiltered money rows.

The rule this module is built on: an operator that cannot be honoured raises. Returning
unfiltered rows to an engine that has been told not to re-filter is how a reader ends up
looking at the wrong money and being given no reason to doubt it.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

#: Everything AG Studio can send that means something over a flat row of JSON.
#: Anything outside this raises rather than being quietly ignored — see the module docstring.
OPERATORS = frozenset(
    {
        "equals",
        "notEqual",
        "greaterThan",
        "lessThan",
        "greaterThanOrEqual",
        "lessThanOrEqual",
        "between",
        "isNull",
        "isNotNull",
        "isUndefined",
        "isNotUndefined",
        "isBlank",
        "isNotBlank",
        "contains",
        "notContains",
        "startsWith",
        "endsWith",
        "isIn",
        "isTrue",
        "isFalse",
    }
)


def _comparable(value: Any) -> Any:
    """A value in a form two of them can be ordered by.

    Money and hours cross the wire as strings, because they are Decimals and a float would
    lose them. Compared as strings, "9.00" sorts after "85.00", so a grid sorted by rate would
    be wrong in a way that looks like data rather than a bug. ISO timestamps are the opposite
    case: they already order correctly as text, and parsing them buys nothing.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return value
    return value


def _order(left: Any, right: Any) -> int:
    """-1, 0 or 1, without raising when the two are not the same kind of thing."""
    a, b = _comparable(left), _comparable(right)
    if a is None or b is None:
        return 0 if a is b else (-1 if a is None else 1)
    if isinstance(a, Decimal) != isinstance(b, Decimal):
        a, b = str(left), str(right)
    try:
        return -1 if a < b else (1 if a > b else 0)
    except TypeError:
        a, b = str(left), str(right)
        return -1 if a < b else (1 if a > b else 0)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _condition(row: dict[str, Any], node: dict[str, Any]) -> bool:
    field = node.get("field")
    operator = node.get("operator")
    if not isinstance(field, str) or not isinstance(operator, str):
        raise ValueError(f"filter condition needs a field and an operator, got {node!r}")
    if operator not in OPERATORS:
        # Loud, because the engine has been told not to re-filter. A reader looking at rows
        # that ignored their filter has no way to know.
        raise ValueError(
            f"filter operator {operator!r} is not supported server-side, and this data source "
            f"has told AG Studio not to filter locally — so returning rows would show you an "
            f"unfiltered view under a filter you set"
        )
    value = node.get("value")
    actual = row.get(field)

    if operator == "equals":
        return _order(actual, value) == 0
    if operator == "notEqual":
        return _order(actual, value) != 0
    if operator == "greaterThan":
        return _order(actual, value) > 0
    if operator == "greaterThanOrEqual":
        return _order(actual, value) >= 0
    if operator == "lessThan":
        return _order(actual, value) < 0
    if operator == "lessThanOrEqual":
        return _order(actual, value) <= 0
    if operator == "between":
        pair = value if isinstance(value, (list, tuple)) else []
        if len(pair) != 2:
            raise ValueError(f"between needs two bounds, got {value!r}")
        return _order(actual, pair[0]) >= 0 and _order(actual, pair[1]) <= 0
    if operator in ("isNull", "isUndefined"):
        return actual is None
    if operator in ("isNotNull", "isNotUndefined"):
        return actual is not None
    if operator == "isBlank":
        return _blank(actual)
    if operator == "isNotBlank":
        return not _blank(actual)
    if operator == "contains":
        return _text(value).casefold() in _text(actual).casefold()
    if operator == "notContains":
        return _text(value).casefold() not in _text(actual).casefold()
    if operator == "startsWith":
        return _text(actual).casefold().startswith(_text(value).casefold())
    if operator == "endsWith":
        return _text(actual).casefold().endswith(_text(value).casefold())
    if operator == "isIn":
        options = value if isinstance(value, (list, tuple)) else [value]
        return any(_order(actual, option) == 0 for option in options)
    if operator == "isTrue":
        return actual is True
    return actual is False  # isFalse


def matches(row: dict[str, Any], node: Any) -> bool:
    """Whether a row satisfies a filter tree. A missing tree matches everything."""
    if node is None:
        return True
    if not isinstance(node, dict):
        raise ValueError(f"filter node must be an object, got {node!r}")
    if "conditions" in node:
        operator = node.get("operator")
        children = node.get("conditions")
        if not isinstance(children, list):
            raise ValueError(f"{operator!r} needs a list of conditions")
        if operator == "AND":
            return all(matches(row, child) for child in children)
        if operator == "OR":
            return any(matches(row, child) for child in children)
        if operator == "NOT":
            return not any(matches(row, child) for child in children)
        raise ValueError(f"unknown logical operator {operator!r}")
    return _condition(row, node)


def parse_filter(raw: str | None) -> Any:
    """The filter tree as the data source sends it: one JSON parameter, not flattened pairs.

    It was flattened into `&field=value`, which could carry neither the operator nor the shape
    of the tree — and the endpoint it was sent to did not declare those parameters, so FastAPI
    dropped them without a word.
    """
    if raw is None or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"filter is not valid JSON: {exc}") from exc


def parse_sort(raw: str | None) -> list[tuple[str, bool]]:
    """`field:asc,other:desc` → [(field, descending), …], in priority order."""
    if raw is None or not raw.strip():
        return []
    out: list[tuple[str, bool]] = []
    for part in raw.split(","):
        field, _, direction = part.strip().partition(":")
        if not field:
            continue
        direction = direction.strip().lower() or "asc"
        if direction not in ("asc", "desc"):
            raise ValueError(f"sort direction must be asc or desc, got {direction!r}")
        out.append((field.strip(), direction == "desc"))
    return out


def apply_sort(rows: list[dict[str, Any]], order: list[tuple[str, bool]]) -> list[dict[str, Any]]:
    """Sort by each key in turn, least significant first, which is what makes it stable."""
    import functools

    out = list(rows)
    for field, descending in reversed(order):
        out.sort(
            key=functools.cmp_to_key(
                lambda a, b, f=field: _order(a.get(f), b.get(f))  # type: ignore[misc]
            ),
            reverse=descending,
        )
    return out


def window(
    rows: list[dict[str, Any]],
    *,
    filter_tree: Any = None,
    sort: list[tuple[str, bool]] | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Filter, then sort, then cut the window — and report the total before the cut.

    The order matters: sorting before filtering wastes work, and paging before either returns
    a window of the wrong set. `total` is after filtering, because that is the number a reader
    is shown next to a filter.
    """
    kept = [r for r in rows if matches(r, filter_tree)]
    kept = apply_sort(kept, sort or [])
    start = max(page - 1, 0) * page_size
    return {
        "total": len(kept),
        "page": page,
        "page_size": page_size,
        "rows": kept[start : start + page_size],
    }
