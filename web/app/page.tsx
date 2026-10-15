import Image from 'next/image';
import Link from 'next/link';

// What a judge sees first. The rules let them score from text, images and video alone, so this
// page has one job: say what the product does and show it working, above the fold, before any
// explanation of how.

const EVIDENCE = [
  { n: '100%', label: 'precision and recall', sub: 'gpt-6.1-sol on the fixture engagement' },
  { n: '0%', label: 'for keyword triage', sub: 'the same events, the alternative people use' },
  { n: '$425', label: 'of work it missed', sub: 'real out-of-scope engineering, never billed' },
];

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-4xl px-6 py-16 font-paypal text-pp-ink">
      <p className="text-sm font-semibold uppercase tracking-wider text-pp-muted">unlogged</p>
      <h1 className="mt-3 max-w-2xl text-[34px] font-semibold leading-tight text-pp-navy">
        The work you never wrote down is the work you never got paid for.
      </h1>
      <p className="mt-5 max-w-2xl text-lg leading-relaxed text-pp-ink">
        A contracting engagement has <strong>one</strong> PayPal invoice, and the client keeps the
        link from day one. As work turns up in Slack threads, PR reviews and commits, it is judged
        against the agreed scope and the billable parts are itemised onto that same invoice — same
        id, same link, same QR, each line naming where the work came from.
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Link
          href="/dashboard"
          className="rounded-full bg-pp-blue px-6 py-3 font-semibold text-white hover:opacity-90"
        >
          Open the dashboard →
        </Link>
        <a
          href="https://github.com/aviralgarg05/unlogged"
          className="rounded-full border border-pp-border px-6 py-3 font-semibold hover:border-pp-blue"
        >
          Read the code
        </a>
      </div>

      <figure className="mt-12">
        <div className="grid gap-4 sm:grid-cols-2">
          <Image
            src="/payer-before.jpg"
            alt="The client's PayPal invoice at $520.00, showing one line: the agreed scope"
            width={800}
            height={563}
            className="rounded-lg border border-pp-border"
            priority
          />
          <Image
            src="/payer-after.jpg"
            alt="The same invoice at $945.00, with two discovered lines added, each naming its source"
            width={800}
            height={563}
            className="rounded-lg border border-pp-border"
          />
        </div>
        <figcaption className="mt-3 text-sm leading-relaxed text-pp-muted">
          The same live PayPal invoice, before and after. <strong>$520.00 → $945.00.</strong> Same
          invoice id, same payer link, same QR — PayPal emailed the client that it changed. Nothing
          was reissued and nothing was voided.
        </figcaption>
      </figure>

      <dl className="mt-12 grid gap-6 sm:grid-cols-3">
        {EVIDENCE.map((e) => (
          <div key={e.label} className="border-t border-pp-border pt-4">
            <dt className="text-[32px] font-semibold leading-none text-pp-navy">{e.n}</dt>
            <dd className="mt-2 font-semibold">{e.label}</dd>
            <dd className="mt-1 text-sm text-pp-muted">{e.sub}</dd>
          </div>
        ))}
      </dl>

      <p className="mt-10 max-w-2xl text-sm leading-relaxed text-pp-muted">
        Eight events is a smoke test, not a benchmark, and the repo says so. Every verdict cites the
        scope clause it relied on and quotes the span of text that decided it; the recorded verdicts
        ship with the code, so the comparison above reproduces with no OpenAI account.
      </p>
    </main>
  );
}
