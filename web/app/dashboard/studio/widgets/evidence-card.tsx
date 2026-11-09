'use client';

// A custom widget: each piece of work outside the agreed scope, beside the sentence that put
// it there.
//
// A grid can show that a verdict cites clause X1. It cannot put the clause and the quoted span
// side by side at a size a reader will actually read, and that juxtaposition is the argument —
// the claim is not "the AI decided" but "the AI decided, and here is the sentence it decided
// on". A row that would bill a client without one is drawn as a defect rather than left to be
// noticed.

import { useEffect, useState } from 'react';
import type { AgWidgetParams } from 'ag-studio';
import type { EvidenceState } from './types';

type Row = {
  event_id?: string;
  call?: string;
  clause_id?: string | null;
  quoted_span?: string | null;
  reason?: string;
  hours?: number | null;
};

/** Rows from the widget api are keyed by qualified field id (`verdicts.call`); rows straight
 *  from the backend are keyed plainly (`call`). Normalise to the plain form. */
function unqualify(rows: Record<string, unknown>[]): Row[] {
  return rows.map((row) => {
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(row)) {
      out[key.includes('.') ? key.slice(key.lastIndexOf('.') + 1) : key] = value;
    }
    return out as Row;
  });
}

// Which invoice this engagement bills to is the service's answer, not this file's. It used to
// be a constant here — which meant the button could only ever write to the one id that was
// committed, and once that invoice had been grown to its final total the button answered 409
// and there was no way to point it anywhere else without editing a React component.
async function liveInvoiceId(): Promise<string | null> {
  const res = await fetch('/api/backend/api/engagement', { cache: 'no-store' });
  if (!res.ok) return null;
  const body = (await res.json()) as { invoice_id?: string | null };
  return body.invoice_id ?? null;
}

const LABEL: Record<string, string> = {
  billable_extra: 'Billable extra',
  scope_request: 'Asked for, not yet done',
  included: 'Inside the agreement',
  noise: 'Not work',
};

export function EvidenceCard(params: AgWidgetParams<EvidenceState>) {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Whether these rows came through the page's filters, or straight from the backend.
  const [filtered, setFiltered] = useState(false);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState<{
    total: string;
    currency?: string;
    added: string[];
  } | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const mapped = params.dataMapping?.rows;
  // Studio rebuilds `dataMapping` on every render, so depending on the array itself makes the
  // effect cancel its own in-flight fetch each time. Depend on the field ids instead.
  const mappedKey = (mapped ?? []).map((f) => (f as { id?: string }).id ?? '').join(',');

  useEffect(() => {
    let live = true;
    // Preferred path: read through the widget's own api, so whatever filters the reader has
    // applied on the page apply here too. `projection` is the detail-row form of a query;
    // axes/measures would aggregate, which is the wrong shape for reading sentences.
    //
    // Fallback: go straight to the backend. The api path returns no rows when the saved
    // report's field mapping has not resolved, and a card that silently shows nothing is
    // worse than one that shows the right rows without respecting a filter. Which path ran
    // is reported in the footer rather than hidden.
    const fields = mapped ?? [];
    const viaApi =
      fields.length > 0
        ? params.widgetApi
            .getData({ projection: fields.map((f) => ({ field: f })) } as never)
            .then((res) =>
              unqualify(
                (res as unknown as { results?: { rows?: Record<string, unknown>[] } }).results?.rows ??
                  [],
              ),
            )
            .catch(() => [] as Row[])
        : Promise.resolve([] as Row[]);

    viaApi
      .then(async (apiRows) => {
        if (apiRows.length > 0) {
          if (live) {
            setRows(apiRows);
            setFiltered(true);
          }
          return;
        }
        const res = await fetch('/api/backend/api/verdicts', { cache: 'no-store' });
        if (!res.ok) throw new Error(`verdicts -> ${res.status}`);
        const body = (await res.json()) as { rows?: Row[] };
        if (live) {
          setRows(body.rows ?? []);
          setFiltered(false);
        }
      })
      .catch((e: unknown) => live && setError(e instanceof Error ? e.message : 'no data'));
    return () => {
      live = false;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.widgetApi, mappedKey]);

  if (error) return <div className="ic-evidence ic-evidence--empty">{error}</div>;

  const outside = rows.filter((r) => r.call === 'billable_extra' || r.call === 'scope_request');
  if (outside.length === 0) {
    return <div className="ic-evidence ic-evidence--empty">Nothing outside the agreed scope.</div>;
  }

  const billable = outside.filter((r) => r.call === 'billable_extra' && r.event_id);

  async function apply() {
    setApplying(true);
    setFailure(null);
    try {
      const invoiceId = await liveInvoiceId();
      if (!invoiceId) throw new Error('the service did not name an invoice for this engagement');
      const res = await fetch('/api/backend/api/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          invoice_id: invoiceId,
          event_ids: [...picked],
          notify: true,
        }),
      });
      const body = await res.json();
      // A refusal is information, not an error to swallow: the backend rejects anything that
      // is not a billable extra, and anything already billed to this invoice.
      if (!res.ok) throw new Error(body?.detail ?? `apply failed (${res.status})`);
      setApplied({ total: body.total, currency: body.currency, added: body.added ?? [] });
      setPicked(new Set());
    } catch (e: unknown) {
      setFailure(e instanceof Error ? e.message : 'apply failed');
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="ic-evidence">
      {billable.length > 0 ? (
        <div className="ic-apply">
          <p className="ic-apply__lead">
            {picked.size === 0
              ? 'Select what to put on the invoice.'
              : `${picked.size} selected.`}
          </p>
          <button
            type="button"
            className="ic-apply__btn"
            disabled={picked.size === 0 || applying}
            onClick={apply}
          >
            {applying ? 'Writing to PayPal…' : 'Add to the live invoice'}
          </button>
          {applied ? (
            <p className="ic-apply__ok">
              Invoice now{' '}
              <strong>
                {applied.currency ? `${applied.currency} ` : ''}
                {applied.total}
              </strong>
              . PayPal emailed the client.
              {applied.added.length ? ` Added: ${applied.added.join('; ')}` : ''}
            </p>
          ) : null}
          {failure ? <p className="ic-apply__err">{failure}</p> : null}
        </div>
      ) : null}
      {!filtered ? (
        <p className="ic-evidence__note">
          Showing every adjudication. Page filters do not apply to this card.
        </p>
      ) : null}
      {outside.map((r) => {
        // Billing someone without citing the sentence that justifies it is the failure this
        // product exists to avoid, so it is shown, not hidden.
        const uncited = r.call === 'billable_extra' && (!r.clause_id || !r.quoted_span);
        return (
          <article
            key={r.event_id}
            className={`ic-evidence__item${uncited ? ' ic-evidence__item--uncited' : ''}`}
          >
            <header>
              {r.call === 'billable_extra' && r.event_id ? (
                <label className="ic-evidence__pick">
                  <input
                    type="checkbox"
                    checked={picked.has(r.event_id)}
                    onChange={(e) =>
                      setPicked((prev) => {
                        const next = new Set(prev);
                        if (e.target.checked) next.add(r.event_id as string);
                        else next.delete(r.event_id as string);
                        return next;
                      })
                    }
                  />
                  <span className="ic-evidence__call">{LABEL[r.call] ?? r.call}</span>
                </label>
              ) : (
                <span className="ic-evidence__call">{LABEL[r.call ?? ''] ?? r.call}</span>
              )}
              {r.hours ? <span className="ic-evidence__hours">{r.hours}h</span> : null}
            </header>
            {r.quoted_span ? (
              <blockquote className="ic-evidence__span">&ldquo;{r.quoted_span}&rdquo;</blockquote>
            ) : null}
            <p className="ic-evidence__reason">{r.reason}</p>
            <footer>
              {r.clause_id ? (
                <span className="ic-evidence__clause">against clause {r.clause_id}</span>
              ) : (
                <span className="ic-evidence__warning">
                  no clause cited — do not bill this without checking
                </span>
              )}
            </footer>
          </article>
        );
      })}
    </div>
  );
}
