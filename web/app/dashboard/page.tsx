import type { Metadata } from "next";
import { connection } from "next/server";
import { aiEnabled, aiModels } from "@/lib/ai";
import { fetchEngagement } from "@/lib/backend";
import { Dashboard } from "./dashboard";

export const metadata: Metadata = {
  title: "Dashboard",
};

/**
 * The currency every money column on the page is formatted in.
 *
 * Read here rather than in the browser because the fields are declared when Studio is built,
 * and a second render to add a currency symbol would reset the open report. One cheap call;
 * the rows themselves are still fetched a page at a time by the data source.
 *
 * If the service is unreachable the page still renders — the data source reports that per
 * widget, which is where a reader can act on it — and the figures keep today's unsymbolled
 * form rather than being labelled with a currency nobody confirmed.
 */
async function engagementCurrency(): Promise<string | undefined> {
  try {
    return (await fetchEngagement()).currency;
  } catch {
    return undefined;
  }
}

export default async function DashboardPage() {
  // Rows are fetched per page by the Studio data source, not materialised here.
  await connection();

  // Only the model ids reach the client; the OpenAI key stays on the server (lib/ai.ts).
  return (
    <Dashboard
      licenseKey={process.env.AG_STUDIO}
      aiModels={aiEnabled() ? aiModels() : undefined}
      currency={await engagementCurrency()}
    />
  );
}
