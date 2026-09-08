import type { Metadata } from "next";
import Link from "next/link";
import { Fraunces, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "FreshRoute — spoilage-aware mandi routing",
  description:
    "Rank Indian mandis by expected net ₹/tonne after freight, commission, and spoilage. Capstone project, IIIT Una.",
};

const nav: readonly { href: string; label: string }[] = [
  { href: "/",          label: "Overview" },
  { href: "/arbitrage", label: "Arbitrage" },
  { href: "/mandis",    label: "Mandi prices" },
  { href: "/estimate",  label: "Cost estimator" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${fraunces.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="sticky top-0 z-30 border-b border-[color:var(--color-line-soft)] backdrop-blur-md bg-[color:var(--color-bg)]/85">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-8 px-6 py-4">
            <Link href="/" className="flex items-baseline gap-2">
              <span
                className="text-lg font-semibold tracking-tight"
                style={{ fontFamily: "var(--font-serif)" }}
              >
                Fresh<span className="text-[color:var(--color-accent)]">Route</span>
              </span>
              <span className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-fg-dim)]">
                capstone · IIIT Una
              </span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-md px-3 py-1.5 text-[color:var(--color-fg-muted)] transition-colors hover:bg-[color:var(--color-bg-elev)] hover:text-[color:var(--color-fg)]"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-[color:var(--color-line-soft)] px-6 py-6">
          <div className="mx-auto flex max-w-7xl items-center justify-between text-xs text-[color:var(--color-fg-dim)]">
            <span>
              Phase 1 &amp; 2 shipped · Phase 3–5 in build · powered by data.gov.in
            </span>
            <span className="tabular">v0.1.0 · {new Date().getFullYear()}</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
