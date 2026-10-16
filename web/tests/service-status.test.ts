// The one indicator on the page that claims the product is connected to anything.
//
// It was a green dot and the words "PayPal sandbox", drawn unconditionally — so starting the
// dashboard with the service down produced a healthy sandbox connection above three empty
// grids, and the page gave no hint which of the two halves was missing.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { statusLine } from '../lib/service-status.ts';

test('a service that answered reads as healthy, and says nothing else', () => {
  const line = statusLine({ reachable: true, currency: 'USD' });
  assert.equal(line.tone, 'ok');
  assert.equal(line.label, 'PayPal sandbox');
  assert.equal(line.hint, null);
});

test('a service that did not answer is never drawn as healthy', () => {
  const line = statusLine({ reachable: false });
  assert.notEqual(line.tone, 'ok');
  assert.ok(!/sandbox/i.test(line.label), `"${line.label}" still claims a connection`);
});

test('and it says what to do about it', () => {
  const line = statusLine({ reachable: false });
  assert.ok(line.hint && line.hint.includes('uvicorn'), 'the hint names no command to run');
});

test('reachability is what decides it, not whether a currency came back', () => {
  // A currency is the payload, not the signal. An engagement without one — or a response this
  // code has not seen — must not downgrade a service that answered.
  assert.equal(statusLine({ reachable: true }).tone, 'ok');
});
