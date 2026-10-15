// The report a judge sees on first load. Three pages, each answering one question, rather
// than a wall of charts. Field ids are 'tableId.fieldId' against ./data.ts.

import type { AgPageState, AgReportState, AgWidgetLayoutState } from 'ag-studio';

// Canvas grid position, in tracks: 24 columns wide.
const at = (xTrack: number, yTrack: number, xSpan: number, ySpan: number): AgWidgetLayoutState => ({
  xTrack,
  yTrack,
  xSpan,
  ySpan,
});
const title = (text: string) => ({ title: { enabled: true, text } });

export const PAGE_TITLES: Record<string, string> = {
  thread: 'The thread',
  calls: 'What was decided',
  bill: 'What reached the bill',
};

// Everything that happened, unjudged. This is the raw material.
const thread: AgPageState = {
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

// The judgement, with its evidence. A row with no clause is not auditable.
const calls: AgPageState = {
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
  },
  widgetLayout: { verdicts: at(0, 0, 24, 30) },
};

// What actually moved money, append-only.
const bill: AgPageState = {
  id: 'bill',
  widgets: {
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
  widgetLayout: { ledger: at(0, 0, 24, 30) },
};

export const dashboardReport: AgReportState = {
  selectedPageId: thread.id,
  pages: [thread, calls, bill],
};
