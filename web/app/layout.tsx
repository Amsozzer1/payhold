import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "payhold: seed 1 replay",
  description: "A paperwork-to-payout check for factored freight invoices, run on synthetic data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
