// The two routes that spend the owner's OpenAI credit take no credential, because the caller
// is a browser. These bounds are what stands between a deployed demo and an open relay.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { resetRate, sameOrigin, withinRate } from '../lib/relay-guard.ts';

const req = (headers: Record<string, string>) =>
  new Request('https://unlogged.example/api/ai/responses', { method: 'POST', headers });

test('a request from another site is refused', () => {
  assert.equal(sameOrigin(req({ 'sec-fetch-site': 'cross-site' })), false);
  assert.equal(sameOrigin(req({ origin: 'https://evil.example' })), false);
});

test('the dashboard calling itself is allowed', () => {
  assert.equal(sameOrigin(req({ 'sec-fetch-site': 'same-origin' })), true);
  assert.equal(sameOrigin(req({ origin: 'https://unlogged.example' })), true);
});

test('a missing origin is not treated as hostile', () => {
  // Some engines omit it on same-origin navigations, and refusing those would break the
  // dashboard for real users to stop an attacker who can set headers anyway.
  assert.equal(sameOrigin(req({})), true);
  assert.equal(sameOrigin(req({ 'sec-fetch-site': 'none' })), true);
});

test('a malformed origin is refused rather than parsed hopefully', () => {
  assert.equal(sameOrigin(req({ origin: 'not a url' })), false);
});

test('one caller is capped and the cap is per caller', () => {
  resetRate();
  const mine = (ip: string) => req({ 'x-forwarded-for': ip });

  let allowed = 0;
  for (let i = 0; i < 40; i += 1) if (withinRate(mine('203.0.113.9'))) allowed += 1;
  assert.equal(allowed, 30, 'the brake should stop one caller at the cap');

  // A different caller is unaffected by the first one hitting it.
  assert.equal(withinRate(mine('198.51.100.4')), true);
});

test('a refused request does not extend the window', () => {
  // Counting refusals meant a caller already over the limit kept the array growing and the
  // filter re-scanning it, so the brake got more expensive the harder it was pushed.
  resetRate();
  const mine = req({ 'x-forwarded-for': '203.0.113.11' });

  for (let i = 0; i < 30; i += 1) assert.equal(withinRate(mine), true);
  for (let i = 0; i < 500; i += 1) assert.equal(withinRate(mine), false);

  // Still refused, and the refusals cost nothing: a fresh caller is unaffected.
  assert.equal(withinRate(req({ 'x-forwarded-for': '198.51.100.9' })), true);
});

test('varying the caller-supplied header does not buy unlimited requests', () => {
  // x-forwarded-for comes from the caller. Without a proxy overwriting it, the per-caller cap
  // identifies nobody — so a global cap stands behind it that nobody can vary their way past.
  resetRate();

  let allowed = 0;
  for (let i = 0; i < 400; i += 1) {
    if (withinRate(req({ 'x-forwarded-for': `203.0.113.${i % 254}` }))) allowed += 1;
  }

  assert.equal(allowed, 120, 'the global cap is the one that actually holds');
});
