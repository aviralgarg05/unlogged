import assert from 'node:assert/strict';
import { test } from 'node:test';
import { isServerTool, runServerTool } from '../lib/server-tools.ts';

const ok = (body: unknown) =>
  (async () => new Response(JSON.stringify(body), { status: 200 })) as unknown as typeof fetch;

test('only the declared server tool is executable', async () => {
  assert.equal(isServerTool('add_billable_work'), true);
  assert.equal(isServerTool('read_verdicts'), false);

  const r = await runServerTool({ name: 'read_verdicts', arguments: {} });
  assert.deepEqual(r, { ok: false, error: 'read_verdicts is not a server tool' });
});

test('arguments are validated before anything reaches the backend', async () => {
  let called = false;
  const spy = (async () => {
    called = true;
    return new Response('{}', { status: 200 });
  }) as unknown as typeof fetch;

  for (const args of [{}, { invoice_id: 'INV2-X' }, { invoice_id: 'INV2-X', event_ids: [] }]) {
    const r = await runServerTool({ name: 'add_billable_work', arguments: args }, spy);
    assert.equal(r.ok, false);
  }
  assert.equal(called, false, 'a malformed call must not reach the money path');
});

test('a well-formed call is forwarded and its result returned', async () => {
  const r = await runServerTool(
    { name: 'add_billable_work', arguments: { invoice_id: 'INV2-X', event_ids: ['e3'] } },
    ok({ invoice_id: 'INV2-X', total: '817.50', added: ['Retry logic (github 03 Oct)'] }),
  );
  assert.equal(r.ok, true);
  assert.equal((r as { ok: true; data: { total: string } }).data.total, '817.50');
});

test('a backend refusal is surfaced, not swallowed', async () => {
  const refuse = (async () =>
    new Response('none of the selected events are billable extras', {
      status: 400,
    })) as unknown as typeof fetch;
  const r = await runServerTool(
    { name: 'add_billable_work', arguments: { invoice_id: 'INV2-X', event_ids: ['e2'] } },
    refuse,
  );
  assert.equal(r.ok, false);
  assert.match((r as { ok: false; error: string }).error, /backend refused: 400/);
});
