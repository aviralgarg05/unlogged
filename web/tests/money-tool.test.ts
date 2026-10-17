// The one tool that changes what a client owes, and whether it can run at all.
//
// It was declared `kind: 'server'`. In ag-studio@3.0.0 that builds a tool with a schema and
// `execute: undefined` — the library advertises it to the model and leaves execution to the
// host, and there is no hook in the bundle that hands the call back. The host never executed
// it: `/api/ai/tool` exists for exactly this and nothing in the repository called it. So the
// headline differentiator was a tool offered to a model that could not run, which is worse
// than not offering it: the model is told it can bill, calls it, and reports what it believes.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { unloggedTools } from '../app/dashboard/studio/tools.ts';

/** Just enough of the Studio api surface for the tool definitions to be built. */
const fakeApi = {
  defineAiTool: (config: Record<string, unknown>) => config,
} as never;

const moneyTool = () =>
  (unloggedTools(fakeApi) as unknown as Record<string, unknown>[]).find(
    (t) => t.name === 'add_billable_work',
  ) as Record<string, unknown>;

const ctx = {
  success: (response: string, data?: unknown) => ({ ok: true, response, data }),
  error: (messages: string | string[]) => ({ ok: false, messages }),
} as never;

test('the money tool is executable at all', () => {
  const tool = moneyTool();
  assert.ok(tool, 'add_billable_work is not declared');
  assert.equal(typeof tool.execute, 'function', 'declared to the model with nothing to run it');
});

test('it is not declared with a kind the library will not execute', () => {
  // `kind: 'server'` makes ag-studio drop the execute entirely — see the file header.
  assert.notEqual(moneyTool().kind, 'server');
});

test('it runs through our own route, never the Python service directly', async () => {
  const seen: { url: string; body: unknown }[] = [];
  const original = globalThis.fetch;
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    seen.push({ url: String(url), body: JSON.parse(String(init.body)) });
    return new Response(JSON.stringify({ ok: true, data: { total: '902.50' } }), { status: 200 });
  }) as never;
  try {
    const execute = moneyTool().execute as (a: unknown, c: unknown) => Promise<unknown>;
    const out = (await execute({ invoice_id: 'INV2-X', event_ids: ['e3'] }, ctx)) as {
      ok: boolean;
      data: unknown;
    };
    assert.equal(seen.length, 1);
    assert.equal(seen[0].url, '/api/ai/tool');
    assert.deepEqual(seen[0].body, {
      name: 'add_billable_work',
      arguments: { invoice_id: 'INV2-X', event_ids: ['e3'] },
    });
    assert.equal(out.ok, true);
    assert.deepEqual(out.data, { total: '902.50' });
  } finally {
    globalThis.fetch = original;
  }
});

test('a refusal reaches the model rather than being reported as a success', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = (async () =>
    new Response(JSON.stringify({ ok: false, error: 'already billed to INV2-X: e3' }), {
      status: 400,
    })) as never;
  try {
    const execute = moneyTool().execute as (a: unknown, c: unknown) => Promise<unknown>;
    const out = (await execute({ invoice_id: 'INV2-X', event_ids: ['e3'] }, ctx)) as {
      ok: boolean;
      messages: string;
    };
    assert.equal(out.ok, false);
    assert.match(out.messages, /already billed/);
  } finally {
    globalThis.fetch = original;
  }
});

test('a route that answers with something unreadable still fails loudly', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = (async () => new Response('<html>502</html>', { status: 502 })) as never;
  try {
    const execute = moneyTool().execute as (a: unknown, c: unknown) => Promise<unknown>;
    const out = (await execute({}, ctx)) as { ok: boolean; messages: string };
    assert.equal(out.ok, false);
    assert.match(out.messages, /502/);
  } finally {
    globalThis.fetch = original;
  }
});
