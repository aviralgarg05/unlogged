// The Python service is the only thing that talks to PayPal. The browser never sees a
// PayPal credential, and every mutation is executed server-side — which is also why the
// one mutating AI tool is declared client-side but runs through this proxy.

import { backendOrigin } from './backend-origin.ts';

export const BACKEND = backendOrigin(process.env.UNLOGGED_API);

export type EventRow = {
  id: string;
  source: string;
  author: string;
  occurred_at: string;
  text: string;
  permalink: string | null;
};

export type VerdictRow = {
  event_id: string;
  call: 'included' | 'billable_extra' | 'scope_request' | 'noise';
  clause_id: string | null;
  quoted_span: string | null;
  reason: string;
  category: string | null;
  hours: string | null;
  confidence: number;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

/** One page of work events. `page` is 1-based, matching the backend. */
export const fetchEvents = (page: number, pageSize: number) =>
  get<{ total: number; page: number; page_size: number; rows: EventRow[] }>(
    `/api/events?page=${page}&page_size=${pageSize}`,
  );

export const fetchVerdicts = () => get<{ arm: string; rows: VerdictRow[] }>('/api/verdicts');

export const fetchEngagement = () =>
  get<{
    id: string;
    client: string;
    currency: string;
    cap: string | null;
    opening_total: string;
    clauses: { id: string; text: string; kind: string }[];
    payer_note: string;
  }>('/api/engagement');

export const fetchLedger = () =>
  get<{ summary: Record<string, unknown>; rows: Record<string, unknown>[] }>('/api/ledger');

export async function applyExtras(invoiceId: string, eventIds: string[]) {
  const res = await fetch(`${BACKEND}/api/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ invoice_id: invoiceId, event_ids: eventIds, notify: true }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{
    invoice_id: string;
    total: string;
    added: string[];
    payer_url: string;
  }>;
}
