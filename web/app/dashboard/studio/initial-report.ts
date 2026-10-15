// The report a judge sees on first load. Three pages, each answering one question, rather
// than a wall of charts. Field ids are 'tableId.fieldId' against ./data.ts.

import type { AgPageState, AgReportState, AgWidgetLayoutState } from 'ag-studio';
import type { UnloggedRegistry } from './widgets/types';

// Canvas grid position, in tracks: 24 columns wide.
const at = (xTrack: number, yTrack: number, xSpan: number, ySpan: number): AgWidgetLayoutState => ({
  xTrack,
  yTrack,
  xSpan,
  ySpan,
});
const title = (text: string) => ({ title: { enabled: true, text } });

const sum = (id: string) => ({ id, aggregation: 'sum' as const });
const countd = (id: string) => ({ id, aggregation: 'countd' as const });

// A number worth its own tile is one a reader would otherwise have to compute by scanning rows.
const kpi = (text: string, value: { id: string; aggregation?: 'sum' | 'countd' | 'max' }) => ({
  type: 'value' as const,
  dataMapping: { value: [value] },
  format: { title: { enabled: true, text } },
});

export const PAGE_TITLES: Record<string, string> = {
  thread: 'The thread',
  calls: 'What was decided',
  bill: 'What reached the bill',
};

// Everything that happened, unjudged. This is the raw material.
const thread: AgPageState<UnloggedRegistry> = {
  id: 'thread',
  widgets: {
    events: {
      type: 'grid',
      dataMapping: {
        cols: [
          { id: 'events.occurred_at' },
          { id: 'events.source' },
          { id: 'events.author' },
          { id: 'events.text' },
        ],
      },
      sort: [{ field: { id: 'events.occurred_at' }, direction: 'asc' }],
      format: title('Every message, commit and call on the engagement'),
    },
  },
  widgetLayout: { events: at(0, 0, 24, 30) },
};

// The judgement, with its evidence. The grid is the whole set; the evidence card beside it
// shows only what falls outside the agreement, at a size where the quoted sentence can be read.
// A verdict that would bill without citing one is drawn as a defect there.
const calls: AgPageState<UnloggedRegistry> = {
  id: 'calls',
  widgets: {
    verdicts: {
      type: 'grid',
      dataMapping: {
        cols: [
          { id: 'verdicts.event_id' },
          { id: 'verdicts.call' },
          { id: 'verdicts.clause_id' },
          { id: 'verdicts.quoted_span' },
          { id: 'verdicts.reason' },
          { id: 'verdicts.hours' },
        ],
      },
      format: title('Each event placed against the agreed scope, and the clause it relied on'),
    },
    evidence: {
      type: 'evidence-card',
      dataMapping: {
        rows: [
          { id: 'verdicts.event_id' },
          { id: 'verdicts.call' },
          { id: 'verdicts.clause_id' },
          { id: 'verdicts.quoted_span' },
          { id: 'verdicts.reason' },
          { id: 'verdicts.hours' },
        ],
      },
      format: title('Why each of these is outside the agreement'),
    },
  },
  widgetLayout: { verdicts: at(0, 0, 14, 30), evidence: at(14, 0, 10, 30) },
};

// What actually moved money, append-only. The tiles answer the two questions a contractor
// asks about a bill — how much, and how much of it was work nobody wrote down — and the chart
// shows the thing the product is for: a bill that grows after it was sent.
const bill: AgPageState<UnloggedRegistry> = {
  id: 'bill',
  widgets: {
    // total_after is a RUNNING total, so the latest row is the answer and summing it
    // double-counts every earlier write.
    'kpi-total': kpi('Invoice total now', { id: 'ledger.total_after', aggregation: 'max' }),
    'kpi-added': kpi('Added after sending', sum('ledger.unit_price')),
    'kpi-lines': kpi('Lines discovered', countd('ledger.event_id')),
    growth: {
      type: 'column-chart-grouped',
      dataMapping: {
        categoryKey: [{ id: 'ledger.line_name' }],
        valueKey: [sum('ledger.unit_price')],
      },
      format: {
        ...title('What each discovered line added to the bill'),
        style: { theme: { common: { legend: { enabled: false } } } },
      },
    },
    ledger: {
      type: 'grid',
      dataMapping: {
        cols: [
          { id: 'ledger.at' },
          { id: 'ledger.line_name' },
          { id: 'ledger.clause_id' },
          { id: 'ledger.hours' },
          { id: 'ledger.unit_price' },
          { id: 'ledger.total_after' },
          { id: 'ledger.adjudicator' },
        ],
      },
      sort: [{ field: { id: 'ledger.at' }, direction: 'asc' }],
      format: title('Every line this system added to the live PayPal invoice'),
    },
  },
  widgetLayout: {
    'kpi-total': at(0, 0, 8, 7),
    'kpi-added': at(8, 0, 8, 7),
    'kpi-lines': at(16, 0, 8, 7),
    growth: at(0, 7, 24, 18),
    ledger: at(0, 25, 24, 20),
  },
};

export const dashboardReport: AgReportState<UnloggedRegistry> = {
  selectedPageId: thread.id,
  pages: [thread, calls, bill],
};
