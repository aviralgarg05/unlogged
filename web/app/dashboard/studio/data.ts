// AG Studio data sources for unlogged.
//
// This is the piece the rest of the field does not ship. The boilerplate — and every
// AG Studio entry surveyed — hands Studio a fully-materialised array and lets the engine
// filter, sort and page it in the browser. Here the source declares
// `capabilities: { pagination, filter, sort }`, so the engine sends `paging`, the applied
// filter tree and the sort order down to `getData`, trusts the returned window as-is, and
// never re-filters locally. The rows stay in the Python service; the browser receives one
// page at a time.
//
// `pageSize` is set to the backend's own page cap rather than a number chosen to look
// impressive, so the claim holds at any row count.

import type {
  AgDataSourceDefinition,
  AgDataSourceGetOptions,
  AgFieldDefinition,
  AgRowDataSourceResponse,
} from 'ag-studio';
import type { UnloggedRegistry } from './widgets/types';

const PAGE_SIZE = 50;

const EVENT_FIELDS: AgFieldDefinition<UnloggedRegistry>[] = [
  { id: 'id', name: 'Event', format: 'textFormat' },
  { id: 'source', name: 'Where', format: 'textFormat' },
  { id: 'author', name: 'Who', format: 'textFormat' },
  { id: 'occurred_at', name: 'When', format: 'dateTimeFormat' },
  { id: 'text', name: 'What was said', format: 'textFormat' },
];

const VERDICT_FIELDS: AgFieldDefinition<UnloggedRegistry>[] = [
  { id: 'event_id', name: 'Event', format: 'textFormat' },
  { id: 'call', name: 'Call', format: 'textFormat' },
  { id: 'clause_id', name: 'Clause relied on', format: 'textFormat' },
  { id: 'quoted_span', name: 'Evidence quoted', format: 'textFormat' },
  { id: 'reason', name: 'Reasoning', format: 'textFormat' },
  { id: 'hours', name: 'Hours', format: 'decimalFormat' },
  { id: 'confidence', name: 'Confidence', format: 'decimalFormat' },
];

/**
 * What a money column should be formatted with, for the engagement's own currency.
 *
 * `currencyFormat` sounds like it carries a currency and does not: AG's default pattern for
 * it is `#,##0.00`, byte for byte the decimal one. So every figure on the page a contractor
 * opens to see what a client owes read `860.00` — on a product whose entire subject is money,
 * next to a README that writes the same number as $902.50.
 *
 * The symbol is the engagement's, not a hardcoded dollar: the whole cross-border case rests on
 * the currency being whatever was agreed. `symbol` rather than `narrowSymbol` because narrow
 * renders AUD, CAD and SGD all as a bare `$`, which on an invoice is not a cosmetic difference.
 * An unknown code formats as itself. The symbol is quoted so a multi-character one (`CHF`,
 * `CA$`) is not read as format codes — unquoted, `USD #,##0.00` renders as `U 1,234.50`,
 * because `D` is one.
 *
 * Returns undefined when the currency is not known, which leaves the figures exactly as they
 * are today: a symbol nobody can check is worse than none.
 */
export function moneyFormat(currency?: string): { format: string } | undefined {
  if (!currency) return undefined;
  let symbol = currency;
  try {
    const parts = new Intl.NumberFormat('en', {
      style: 'currency',
      currency,
      currencyDisplay: 'symbol',
    }).formatToParts(0);
    symbol = parts.find((part) => part.type === 'currency')?.value ?? currency;
  } catch {
    // Intl throws on anything that is not a well-formed currency code. The code itself is
    // then the honest symbol.
  }
  return { format: `"${symbol}"#,##0.00` };
}

const ledgerFields = (currency?: string): AgFieldDefinition<UnloggedRegistry>[] => {
  const money = moneyFormat(currency);
  return [
    { id: 'at', name: 'Written at', format: 'dateTimeFormat' },
    // Present because the ledger spans billing periods: the seeded rows belong to an earlier
    // invoice. Without this column the money tiles above read as one invoice's figures when
    // they are the engagement's, and nothing on the page says which.
    { id: 'invoice_id', name: 'Invoice', format: 'textFormat' },
    { id: 'event_id', name: 'From event', format: 'textFormat' },
    { id: 'line_name', name: 'Line added to the invoice', format: 'textFormat' },
    { id: 'clause_id', name: 'Clause', format: 'textFormat' },
    { id: 'hours', name: 'Hours', format: 'decimalFormat' },
    { id: 'unit_price', name: 'Rate', format: 'currencyFormat', formatOptions: money },
    {
      id: 'line_total',
      name: 'Added by this line',
      format: 'currencyFormat',
      formatOptions: money,
    },
    {
      id: 'total_after',
      name: 'Invoice total after',
      format: 'currencyFormat',
      formatOptions: money,
    },
    { id: 'adjudicator', name: 'Decided by', format: 'textFormat' },
  ];
};

/** Same-origin proxy, so the browser never needs the backend's address or its credentials. */
async function api<T>(path: string): Promise<T> {
  const res = await fetch(`/api/backend${path}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

/**
 * The query string for one getData call: the window, the filter tree and the sort order.
 *
 * The filter goes over as one JSON parameter. It used to be flattened into bare
 * `&field=value` pairs, which can carry neither the operator nor the shape of the tree — and
 * the endpoint it was sent to did not declare those parameters, so FastAPI dropped them
 * silently. The sort was never sent at all. Both are declared capabilities, and AG Studio's
 * contract for declaring them is that it will not filter or sort locally, so what came back
 * was every row with the reader's filter chip showing above it.
 */
export function queryFor(
  options: AgDataSourceGetOptions | undefined,
  offset: number,
  limit: number,
): string {
  const params = new URLSearchParams({
    page: String(Math.floor(offset / limit) + 1),
    page_size: String(limit),
  });
  if (options?.filter) params.set('filter', JSON.stringify(options.filter));
  const sort = (options?.sort ?? [])
    .filter((s) => s && typeof s.field === 'string')
    .map((s) => `${s.field}:${s.direction === 'desc' ? 'desc' : 'asc'}`)
    .join(',');
  if (sort) params.set('sort', sort);
  return params.toString();
}

export function unloggedDataSource(
  currency?: string,
): AgDataSourceDefinition<'row', UnloggedRegistry> {
  return {
    id: 'unlogged',
    name: 'Engagement',
    // Declared independently, exactly as the engine treats them.
    capabilities: { pagination: true, filter: true, sort: true },
    pageSize: PAGE_SIZE,
    tables: [
      {
        id: 'events',
        name: 'Work events',
        description:
          'Everything that happened on the real work surface: Slack and Discord messages, ' +
          'commits, PR reviews, calendar entries. One row per event, unjudged.',
        fields: EVENT_FIELDS,
      },
      {
        id: 'verdicts',
        name: 'Adjudications',
        description:
          'One row per event, placing it against the engagement scope: included, billable ' +
          'extra, scope request, or noise. Every row carries the clause it relied on and the ' +
          'span of text that decided it. A row with no clause is not auditable.',
        fields: VERDICT_FIELDS,
      },
      {
        id: 'ledger',
        name: 'Invoice changes',
        description:
          'The append-only record of every line this system added to a live PayPal invoice, ' +
          'with the running total after each one.',
        fields: ledgerFields(currency),
      },
    ],
    dataShape: 'row',
    async getData(
      tableId: string,
      _fieldIds: string[],
      options?: AgDataSourceGetOptions,
    ): Promise<AgRowDataSourceResponse> {
      const offset = options?.paging?.offset ?? 0;
      const limit = options?.paging?.pageLimit ?? PAGE_SIZE;
      // One path for all three tables. Two of them used to fetch everything and slice in the
      // browser while the source declared the rows never materialise here, and neither of
      // them passed the filter or the sort on at all.
      const path =
        tableId === 'events' ? '/api/events' : tableId === 'verdicts' ? '/api/verdicts' : '/api/ledger';
      const body = await api<{ rows: Record<string, unknown>[] }>(
        `${path}?${queryFor(options, offset, limit)}`,
      );
      return { data: body.rows };
    },
  };
}
