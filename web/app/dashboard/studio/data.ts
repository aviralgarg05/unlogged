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

const LEDGER_FIELDS: AgFieldDefinition<UnloggedRegistry>[] = [
  { id: 'at', name: 'Written at', format: 'dateTimeFormat' },
  // Present because the ledger spans billing periods: the seeded rows belong to an earlier
  // invoice. Without this column the money tiles above read as one invoice's figures when
  // they are the engagement's, and nothing on the page says which.
  { id: 'invoice_id', name: 'Invoice', format: 'textFormat' },
  { id: 'event_id', name: 'From event', format: 'textFormat' },
  { id: 'line_name', name: 'Line added to the invoice', format: 'textFormat' },
  { id: 'clause_id', name: 'Clause', format: 'textFormat' },
  { id: 'hours', name: 'Hours', format: 'decimalFormat' },
  { id: 'unit_price', name: 'Rate', format: 'currencyFormat' },
  { id: 'line_total', name: 'Added by this line', format: 'currencyFormat' },
  { id: 'total_after', name: 'Invoice total after', format: 'currencyFormat' },
  { id: 'adjudicator', name: 'Decided by', format: 'textFormat' },
];

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

export function unloggedDataSource(): AgDataSourceDefinition<'row', UnloggedRegistry> {
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
        fields: LEDGER_FIELDS,
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

export const hasData = (_data?: unknown) => true;
