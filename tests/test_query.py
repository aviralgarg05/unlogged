"""The half of the pushdown promise that was missing.

The data source declares `capabilities: { pagination, filter, sort }`, and AG Studio's contract
for that is that it forwards the filter and the sort and then does not re-apply either. The
engine kept its half. `getData` never read `options.sort`, and the filter was flattened into
bare query parameters the endpoint did not declare, so FastAPI dropped them — filtering the
Adjudications grid to `call = billable_extra` returned every row underneath the reader's own
filter chip, and clicking a column header did nothing.
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from unlogged.query import apply_sort, matches, parse_filter, parse_sort, window

os.environ.setdefault("UNLOGGED_REPLAY", "1")

from unlogged.web import app

client = TestClient(app)


ROWS = [
    {"id": "e1", "call": "scope_request", "hours": None, "rate": "85.00", "at": "2026-10-02"},
    {"id": "e2", "call": "noise", "hours": None, "rate": "9.00", "at": "2026-10-03"},
    {"id": "e3", "call": "billable_extra", "hours": "3.0", "rate": "85.00", "at": "2026-10-01"},
    {"id": "e4", "call": "billable_extra", "hours": "1.5", "rate": "120.00", "at": "2026-10-09"},
]


def test_money_sorts_as_money_and_not_as_text():
    """Rates cross the wire as strings because they are Decimals and a float would lose them.

    Sorted as text, "9.00" comes after "85.00" — a rate column that is wrong in a way that
    looks like data rather than a bug.
    """
    ordered = [r["rate"] for r in apply_sort(ROWS, parse_sort("rate:asc"))]
    assert ordered == ["9.00", "85.00", "85.00", "120.00"]


def test_dates_sort_as_dates():
    assert [r["id"] for r in apply_sort(ROWS, parse_sort("at:desc"))] == ["e4", "e2", "e1", "e3"]


def test_a_second_sort_key_breaks_ties_without_disturbing_the_first():
    ordered = apply_sort(ROWS, parse_sort("call:asc,rate:desc"))
    assert [r["id"] for r in ordered] == ["e4", "e3", "e2", "e1"]


@pytest.mark.parametrize(
    ("node", "expected"),
    [
        ({"field": "call", "operator": "equals", "value": "billable_extra"}, ["e3", "e4"]),
        ({"field": "call", "operator": "notEqual", "value": "noise"}, ["e1", "e3", "e4"]),
        ({"field": "rate", "operator": "greaterThan", "value": "85.00"}, ["e4"]),
        ({"field": "rate", "operator": "lessThanOrEqual", "value": "85.00"}, ["e1", "e2", "e3"]),
        ({"field": "rate", "operator": "between", "value": ["10.00", "100.00"]}, ["e1", "e3"]),
        ({"field": "hours", "operator": "isBlank", "value": None}, ["e1", "e2"]),
        ({"field": "hours", "operator": "isNotBlank", "value": None}, ["e3", "e4"]),
        ({"field": "call", "operator": "contains", "value": "BILLABLE"}, ["e3", "e4"]),
        ({"field": "call", "operator": "startsWith", "value": "scope"}, ["e1"]),
        ({"field": "id", "operator": "isIn", "value": ["e1", "e4"]}, ["e1", "e4"]),
    ],
)
def test_each_operator_means_what_it_says(node, expected):
    assert [r["id"] for r in ROWS if matches(r, node)] == expected


def test_and_or_and_not_compose():
    tree = {
        "operator": "AND",
        "conditions": [
            {"field": "call", "operator": "equals", "value": "billable_extra"},
            {
                "operator": "NOT",
                "conditions": [{"field": "rate", "operator": "equals", "value": "120.00"}],
            },
        ],
    }
    assert [r["id"] for r in ROWS if matches(r, tree)] == ["e3"]


def test_an_operator_that_cannot_be_honoured_raises_rather_than_returning_everything():
    """This is the whole design, not an edge case.

    The engine has been told not to re-filter. An operator this cannot apply must not come
    back as unfiltered rows under the reader's filter — on a dashboard whose subject is money,
    that is the wrong number with nothing to doubt.
    """
    with pytest.raises(ValueError, match="not supported server-side"):
        matches(ROWS[0], {"field": "at", "operator": "inRelativeRange", "value": "last7"})

    with pytest.raises(ValueError, match="unknown logical operator"):
        matches(ROWS[0], {"operator": "XOR", "conditions": []})


def test_the_total_is_the_filtered_count_not_the_table_size():
    """It sits next to a filter, so it has to describe what the filter left."""
    got = window(
        ROWS,
        filter_tree={"field": "call", "operator": "equals", "value": "billable_extra"},
        page=1,
        page_size=50,
    )
    assert got["total"] == 2
    assert [r["id"] for r in got["rows"]] == ["e3", "e4"]


def test_the_window_is_cut_after_filtering_and_sorting_not_before():
    got = window(ROWS, sort=parse_sort("rate:desc"), page=1, page_size=2)
    assert [r["id"] for r in got["rows"]] == ["e4", "e1"]
    assert got["total"] == 4


def test_parse_sort_rejects_a_direction_it_does_not_understand():
    with pytest.raises(ValueError, match="asc or desc"):
        parse_sort("rate:sideways")


def test_parse_filter_says_so_when_the_tree_is_not_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_filter("{not json")


# -- through the actual endpoints ------------------------------------------------------------


def _filter(**kw):
    return json.dumps(kw)


def test_the_events_endpoint_filters_rather_than_ignoring_the_parameter():
    """`/api/events?source=slack` used to return all eight rows, byte for byte identical to
    the unfiltered call, because the parameter was not declared and FastAPI dropped it."""
    everything = client.get("/api/events").json()
    slack = client.get(
        "/api/events",
        params={"filter": _filter(field="source", operator="equals", value="slack")},
    ).json()

    assert everything["total"] > slack["total"] > 0
    assert {r["source"] for r in slack["rows"]} == {"slack"}
    assert slack["total"] == len(slack["rows"])


def test_the_verdicts_endpoint_sorts_rather_than_ignoring_the_parameter():
    descending = client.get("/api/verdicts", params={"sort": "event_id:desc"}).json()
    ids = [r["event_id"] for r in descending["rows"]]
    assert ids == sorted(ids, reverse=True)
    assert len(ids) > 1


def test_the_ledger_endpoint_takes_the_same_window_the_others_do():
    one = client.get("/api/ledger", params={"page": 1, "page_size": 1}).json()
    assert len(one["rows"]) <= 1
    assert "summary" in one, "the summary is the page's own figures and must survive paging"


def test_an_endpoint_refuses_an_operator_it_cannot_honour():
    refused = client.get(
        "/api/events",
        params={"filter": _filter(field="occurred_at", operator="inRelativeRange", value="last7")},
    )
    # 422, which is this app's own answer to a ValueError — the point is that it refuses and
    # says why, not that it invents a status code for this one case.
    assert refused.status_code == 422
    assert "not supported server-side" in refused.text
