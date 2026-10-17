// What getData puts on the wire.
//
// The source declares `capabilities: { pagination, filter, sort }`, and AG Studio's contract
// for that is that it forwards the filter tree and the sort order and then does not re-apply
// either. It kept its half. `getData` never read `options.sort` — the word does not appear in
// the file — and the filter was flattened into bare `&field=value` pairs that can carry
// neither the operator nor the shape of the tree, sent to an endpoint that did not declare
// them, so FastAPI dropped them without a word. Filtering the Adjudications grid to
// `call = billable_extra` returned every row with the reader's own filter chip above it.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { queryFor } from '../app/dashboard/studio/data.ts';

const params = (q: string) => new URLSearchParams(q);

test('the window is always sent', () => {
  const p = params(queryFor(undefined, 100, 50));
  assert.equal(p.get('page'), '3');
  assert.equal(p.get('page_size'), '50');
});

test('the filter goes over whole, as a tree, not flattened into pairs', () => {
  const filter = {
    operator: 'AND',
    conditions: [
      { field: 'call', operator: 'equals', value: 'billable_extra' },
      { field: 'hours', operator: 'greaterThan', value: 2 },
    ],
  };
  const p = params(queryFor({ filter } as never, 0, 50));
  assert.deepEqual(JSON.parse(p.get('filter') as string), filter);
  // The old shape could not have carried either of these.
  assert.equal(p.get('operator'), null);
  assert.equal(p.get('call'), null);
});

test('the sort is sent at all, which it never was', () => {
  const p = params(
    queryFor({ sort: [{ field: 'hours', direction: 'desc' }] } as never, 0, 50),
  );
  assert.equal(p.get('sort'), 'hours:desc');
});

test('a multi-column sort keeps its priority order', () => {
  const p = params(
    queryFor(
      { sort: [{ field: 'call', direction: 'asc' }, { field: 'hours', direction: 'desc' }] } as never,
      0,
      50,
    ),
  );
  assert.equal(p.get('sort'), 'call:asc,hours:desc');
});

test('nothing is sent for a filter or sort that was not applied', () => {
  const p = params(queryFor({ sort: [] } as never, 0, 50));
  assert.equal(p.get('filter'), null);
  assert.equal(p.get('sort'), null);
});
