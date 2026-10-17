// The AG Studio assistant.
//
// The boilerplate wires AG's five built-in agents to one model and stops there. This adds a
// sixth that owns the thing this product does — deciding what reaches the bill — and hands
// layout work to the built-ins through `delegateTo`, which is the division of labour the
// framework is built for.
//
// Three pieces here are unoccupied across the AG Studio entries surveyed in this hackathon:
// `defaultToolCalls` seeding the agent before its first turn, a money tool whose execution
// lives in our own Next route so the PayPal write never enters the browser bundle, and a
// telemetry observer feeding a published evaluation rather than a console.
//
// The adapter calls `${endpoint}/responses`, i.e. this app's proxy at app/api/ai/responses,
// which holds the OpenAI key. Nothing secret is sent from the browser.

import {
  createAiHarness,
  directLlmRunner,
  type AgAiHarnessSetup,
  type AgAiPromptStarter,
} from 'ag-studio';
import { openaiAdapter } from './openai-adapter';
import { unloggedTelemetry } from './telemetry';
import { unloggedTools } from './tools';

const PROMPT_STARTERS: AgAiPromptStarter[] = [
  {
    label: 'What is unbilled?',
    prompt:
      'Which work has been adjudicated as a billable extra but has not yet been added to the ' +
      'invoice? For each one, quote the clause it falls outside of.',
  },
  {
    label: 'Check for double billing',
    prompt:
      'Compare the adjudications against the invoice changes already made. Is anything at risk ' +
      'of being billed twice — in particular, a request and the work that answered it?',
  },
  {
    label: 'Where is the evidence thin?',
    prompt:
      'Show me every verdict that bills the client without citing a clause and a quoted span. ' +
      'Those are the ones I should not trust.',
  },
];

const INSTRUCTIONS = `You help a contractor decide what reaches an invoice, on an engagement \
that has one live PayPal invoice the client has had since day one.

Four things govern every answer:

1. Read the scope clauses before judging anything. A claim that work is outside scope means \
nothing without the clause it falls outside of.
2. A request and the work that answers it are separate events. The obligation is created when \
the client asks; the money attaches when the work is done. Billing both charges them twice.
3. Check what has already been added before proposing anything. The ledger is append-only and \
nothing in this product removes a line.
4. This bills a real person. Where two readings are both defensible, prefer the one that bills \
less, and say that is what you did.

You may add lines to the live invoice with add_billable_work, but only for events already \
adjudicated as billable_extra. Say what you are adding and what it will cost before you call it.

For anything about the dashboard itself — pages, widgets, charts, layout — delegate to the \
built-in agents rather than describing what the reader should click.`;

export function buildAi(models: string[]): AgAiHarnessSetup {
  const adapter = openaiAdapter({ endpoint: '/api/ai', model: models[0] });

  return ({ api }) =>
    createAiHarness(api, ({ builtIn, tools }) => ({
      agents: [
        directLlmRunner({
          id: 'engagement',
          name: 'Engagement',
          description:
            'Decides what reaches the invoice: reads the agreed scope, the adjudications and ' +
            'the changes already made, and can itemise billable extras onto the live invoice.',
          adapter,
          instructions: () => INSTRUCTIONS,
          // Re-resolved per turn, because a tool's advertised schema reads live state.
          // The plan tools hold a visible, mutating plan the reader can see and edit before
          // any money moves; delegateTo hands layout work to the built-in agents.
          tools: () => [
            ...unloggedTools(api),
            tools.delegateTo(['data', 'page', 'widget', 'planning']),
            tools.renameThread(),
            tools.plan.view(),
            tools.plan.create(),
            tools.plan.update(),
            tools.plan.clear(),
          ],
          // Seeded before the first turn, so the opening reply is a decision rather than a
          // question. Nobody else in the surveyed field does this.
          defaultToolCalls: () => [
            { tool: 'read_engagement' },
            { tool: 'read_verdicts' },
            { tool: 'read_invoice_changes' },
          ],
          // Conversational, with a backstop well under the default.
          maxTurns: 12,
        }),
        directLlmRunner({ ...builtIn.lead, adapter }),
        directLlmRunner({ ...builtIn.data, adapter }),
        directLlmRunner({ ...builtIn.page, adapter }),
        directLlmRunner({ ...builtIn.widget, adapter }),
        directLlmRunner({ ...builtIn.planning, adapter }),
      ],
      primary: 'engagement',
      promptStarters: PROMPT_STARTERS,
      models: models.length > 1 ? models.map((id) => ({ id, label: id })) : undefined,
      observers: [unloggedTelemetry(api)],
    }));
}
