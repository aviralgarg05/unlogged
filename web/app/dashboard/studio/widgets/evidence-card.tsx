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

  return (
    <div className="ic-evidence">
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
              <span className="ic-evidence__call">{LABEL[r.call ?? ''] ?? r.call}</span>
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
