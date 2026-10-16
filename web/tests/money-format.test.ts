// Money on a page about money.
//
// `currencyFormat` carries no currency: AG's default pattern for it is `#,##0.00`, the same
// string as the decimal format. Every figure on the dashboard therefore read `860.00` while
// the README wrote the same quantity as $902.50. These tests go through AG's own formatter
// rather than asserting the pattern we hand it, because the pattern is only worth what the
// library makes of it — `USD #,##0.00` looks right and renders `U 1,234.50`.

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { createFormats } from 'ag-studio';

import { moneyFormat } from '../app/dashboard/studio/data.ts';

const currencyFormat = (
  createFormats({}) as unknown as Record<
    string,
    { createValueFormatter: (o: unknown, p: unknown) => (v: number) => string }
  >
).currencyFormat;

const render = (currency: string | undefined, value: number) =>
  currencyFormat.createValueFormatter(moneyFormat(currency), { api: {}, context: {} })(value);

test("AG's own currency format ships no currency, which is the reason this exists", () => {
  const bare = currencyFormat.createValueFormatter(undefined, { api: {}, context: {} });
  assert.equal(bare(902.5), '902.50');
});

test('the engagement currency reaches the figure', () => {
  assert.equal(render('USD', 902.5), '$902.50');
  assert.equal(render('EUR', 902.5), '€902.50');
  assert.equal(render('INR', 902.5), '₹902.50');
});

test('currencies that share a symbol are still told apart', () => {
  // Intl's narrow symbol renders AUD, CAD and SGD as a bare `$`. On an invoice that is not a
  // cosmetic difference, so the wider symbol is the one used.
  assert.equal(render('AUD', 902.5), 'A$902.50');
  assert.equal(render('CAD', 902.5), 'CA$902.50');
});

test('a multi-character symbol is not read as format codes', () => {
  // Unquoted, `D` is a format code and `USD #,##0.00` renders as `U 1,234.50`.
  assert.equal(render('CHF', 1234.5), 'CHF1,234.50');
  assert.equal(moneyFormat('USD')?.format, '"$"#,##0.00');
});

test('an unknown code formats as itself rather than throwing', () => {
  assert.equal(render('ZZZ', 10), 'ZZZ10.00');
});

test('no currency means no symbol, not a guessed one', () => {
  assert.equal(moneyFormat(undefined), undefined);
  assert.equal(moneyFormat(''), undefined);
  assert.equal(render(undefined, 902.5), '902.50');
});

test('negatives keep the symbol inside the sign', () => {
  assert.equal(render('USD', -42.5), '-$42.50');
});
