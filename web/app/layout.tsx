import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";
import "./globals.css";

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    template: "%s · unlogged",
    default: "unlogged — the work you never wrote down",
  },
  description:
    "A contracting engagement has one PayPal invoice. As work turns up in Slack threads and " +
    "PR reviews, the billable parts are itemised onto that same invoice — same id, same link, " +
    "same QR.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
