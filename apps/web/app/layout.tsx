import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { Providers } from "@/components/providers";
import "./globals.css";
import "./theme.css";
export const metadata: Metadata = {
  title: "Pehchaan · Merchant Growth OS",
  description:
    "An agentic merchant growth operating system. Bring customers back, negotiate better deals, and keep every action within your mandate.",
  other: { "page-type": "software", "site-kind": "software" },
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-type="software">
      <body className={GeistSans.variable}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
