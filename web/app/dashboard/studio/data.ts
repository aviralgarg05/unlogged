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

/** Translate Studio's filter tree into the query the backend understands. */
function filterToQuery(filter: AgDataSourceGetOptions['filter']): string {
  if (!filter) return '';
  const parts: string[] = [];
  const walk = (node: unknown): void => {
    if (!node || typeof node !== 'object') return;
    const n = node as Record<string, unknown>;
    if (Array.isArray(n.conditions)) {
      n.conditions.forEach(walk);
      return;
    }
    if (typeof n.field === 'string' && n.value !== undefined) {
      parts.push(`${encodeURIComponent(n.field)}=${encodeURIComponent(String(n.value))}`);
    }
  };
  walk(filter);
  return parts.length ? `&${parts.join('&')}` : '';
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

      if (tableId === 'events') {
        // The engine asks for a window; the backend returns exactly that window.
        const page = Math.floor(offset / limit) + 1;
        const body = await api<{ rows: Record<string, unknown>[] }>(
          `/api/events?page=${page}&page_size=${limit}${filterToQuery(options?.filter)}`,
        );
        return { data: body.rows };
      }
      if (tableId === 'verdicts') {
        const body = await api<{ rows: Record<string, unknown>[] }>('/api/verdicts');
        return { data: body.rows.slice(offset, offset + limit) };
      }
      const body = await api<{ rows: Record<string, unknown>[] }>('/api/ledger');
      return { data: body.rows.slice(offset, offset + limit) };
    },
  };
}
