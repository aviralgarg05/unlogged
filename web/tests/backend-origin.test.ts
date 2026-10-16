// The hosted demo's web half could not reach its own API.
//
// A Render blueprint cannot put a scheme in front of a `fromService` value — it hands over a
// bare host, or host:port — and both forms break `fetch` in different ways, one of them
// quietly. These are the exact strings Render produces.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { backendOrigin } from '../lib/backend-origin.ts';

const reach = async (base: string) => {
  try {
    await fetch(`${base}/api/engagement`);
    return 'resolved';
  } catch (e) {
    const err = e as Error & { cause?: { code?: string } };
    return err.cause?.code ?? err.message;
  }
};

test('a bare host gets a scheme, because Render can only give a bare host', () => {
  assert.equal(backendOrigin('unlogged-api.onrender.com'), 'https://unlogged-api.onrender.com');
});

test('and without one, fetch rejects the URL outright', async () => {
  assert.equal(await reach('unlogged-api.onrender.com'), 'ERR_INVALID_URL');
});

test('host:port is the quiet case — it parses, as a scheme called unlogged-api', async () => {
  // This is why the fix is not "trust the operator to set it properly": the failure reads as
  // the service being down, not as a malformed address.
  assert.notEqual(await reach('unlogged-api:10000'), 'ERR_INVALID_URL');
  assert.equal(backendOrigin('unlogged-api:10000'), 'https://unlogged-api:10000');
});

test("a scheme already there is left exactly alone", () => {
  // compose reaches the API over plain http on its own network, on a port that is not 443.
  assert.equal(backendOrigin('http://api:8000'), 'http://api:8000');
  assert.equal(backendOrigin('https://example.test'), 'https://example.test');
  assert.equal(backendOrigin('HTTP://api:8000'), 'HTTP://api:8000');
});

test('a trailing slash would double every path separator', () => {
  assert.equal(backendOrigin('http://api:8000/'), 'http://api:8000');
  assert.equal(backendOrigin('unlogged-api.onrender.com//'), 'https://unlogged-api.onrender.com');
});

test('unset or blank falls back to the local service', () => {
  assert.equal(backendOrigin(undefined), 'http://127.0.0.1:8000');
  assert.equal(backendOrigin(''), 'http://127.0.0.1:8000');
  assert.equal(backendOrigin('   '), 'http://127.0.0.1:8000');
});
