// Custom widget registration.
//
// The `ai` block says what the widget is for AND when not to use it — the second half is what
// stops an agent reaching for it to render a plain list. `aiDescription` on the data mapping
// tells it which fields to map.
//
// On `formatShape`, see the comment where it would go: the public API does not make one
// constructible, which is a defect rather than a decision.

import { createWidgets } from 'ag-studio-react';
import type { AgWidgetsConfig } from 'ag-studio';
import { EvidenceCard } from './evidence-card';
import type { EvidenceWidget, UnloggedRegistry } from './types';

const evidenceCard: EvidenceWidget = {
  id: 'evidence-card',
  label: 'Evidence',
  comp: EvidenceCard,
  defaultSize: { width: 10, height: 24 },
  minSize: { width: 6, height: 12 },
  dataMapping: {
    rows: {
      type: 'fieldset',
      supportedRoles: ['category', 'numeric', 'temporal'],
      required: true,
      intent: 'category',
      aiDescription:
        'Map the verdicts table: event_id, call, clause_id, quoted_span, reason and hours. ' +
        'The widget reads them by name, so all six should be present.',
    },
  },
  // NO formatShape, and not by choice. The docs say the shape is required for AI, and a shape
  // has to be built with a shape builder — but `AgFormatShapeParams` is `{ api, context }` and
  // `ag-studio` exports no builder at all (50 runtime exports, none shape-related). Probed at
  // runtime, the params object carries a `Symbol(ag.internal)` that presumably holds it, which
  // is private. Returning a plain object instead throws `formatShape.parse is not a function`
  // and takes the whole dashboard down. Reported in docs/UPSTREAM.md.
  //
  // The cost is bounded: the agent can place this widget and map its fields, and `ai` plus
  // `aiDescription` below tell it how. It cannot configure the widget's *format*, which here
  // is only the title.
  form: ({ createDefaults }) => createDefaults({ supportsCrossHighlight: false }),
  ai: {
    label: 'Evidence',
    description:
      'Each piece of work that falls outside the agreed scope, beside the exact sentence that ' +
      'put it there, with any that would bill the client without citing a clause flagged.',
    usage:
      'Use when the question is WHY something is billable, or to review what is about to be ' +
      'added to an invoice. Do NOT use it to list or count events — a grid is better for that, ' +
      'and this widget deliberately hides everything inside scope.',
    configuration:
      'Map all six verdict fields. Most useful beside the invoice-changes grid, where a reader ' +
      'can compare what was decided against what was actually billed.',
  },
};

export function unloggedWidgets(): AgWidgetsConfig<UnloggedRegistry> {
  return createWidgets<UnloggedRegistry>({ additionalTypes: [evidenceCard] });
}
