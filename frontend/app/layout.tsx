import type { Metadata } from "next";
import Link from "next/link";
import { Leaf, MapPin } from "lucide-react";
import { Fraunces, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { BottomNav } from "./components/BottomNav";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "FreshRoute — Kisan Ka Saathi",
  description:
    "Find the mandi that earns you the most — after freight, spoilage, and commission. Live prices across India.",
};

const NAV_LINKS = [
  { href: "/",          label: "Home" },
  { href: "/recommend", label: "Best Mandi" },
  { href: "/mandis",    label: "Prices" },
  { href: "/arbitrage", label: "Alerts" },
] as const;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${fraunces.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[color:var(--color-bg)]">

        {/* ── Header — GreenBasket style ──────────────────────── */}
        <header className="sticky top-0 z-30 border-b border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)]/95 backdrop-blur-md">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-5 py-3.5">

            {/* Logo: leaf icon + name + tagline */}
            <Link href="/" className="flex items-center gap-2.5 shrink-0">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[color:var(--color-accent-soft)]">
                <Leaf size={18} className="text-[color:var(--color-accent)]" aria-hidden="true" />
              </div>
              <div className="leading-none">
                <div
                  className="text-[17px] font-semibold text-[color:var(--color-accent)] leading-tight"
                  style={{ fontFamily: "var(--font-serif)" }}
                >
                  FreshRoute
                </div>
                <div className="text-[10px] text-[color:var(--color-fg-dim)] tracking-wide">
                  Kisan Ka Saathi
                </div>
              </div>
            </Link>

            {/* Desktop nav links */}
            <nav className="hidden md:flex items-center gap-0.5" aria-label="Main navigation">
              {NAV_LINKS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-lg px-3.5 py-2 text-sm font-medium text-[color:var(--color-fg-muted)] transition-colors hover:bg-[color:var(--color-accent-soft)] hover:text-[color:var(--color-accent)]"
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            {/* Desktop CTA button — GreenBasket "Shop Now" equivalent */}
            <Link
              href="/recommend"
              className="hidden md:inline-flex items-center gap-1.5 rounded-full bg-[color:var(--color-accent)] px-4 py-2 text-sm font-semibold text-[color:var(--color-accent-ink)] transition-all hover:bg-[color:var(--color-accent-mid)] hover:-translate-y-0.5 shadow-[var(--shadow-1)]"
            >
              <MapPin size={14} aria-hidden="true" />
              Find Mandi
            </Link>

            {/* Mobile: small CTA only */}
            <Link
              href="/recommend"
              className="md:hidden inline-flex items-center gap-1 rounded-full bg-[color:var(--color-accent)] px-3.5 py-2 text-xs font-semibold text-[color:var(--color-accent-ink)]"
            >
              <MapPin size={13} aria-hidden="true" />
              Find
            </Link>
          </div>
        </header>

        {/* ── Page content ──────────────────────────────────── */}
        <main className="flex-1 pb-16">
          {children}
        </main>

        {/* ── Bottom nav — always visible ───────────────────── */}
        <BottomNav />

        {/* ── Footer ───────────────────────────────────────── */}
        <footer className="border-t border-[color:var(--color-line-soft)] bg-[color:var(--color-accent)] px-6 py-8">
          <div className="mx-auto flex max-w-6xl items-center justify-between">
            <div className="flex items-center gap-2">
              <Leaf size={16} className="text-[color:var(--color-accent-ink)]/70" aria-hidden="true" />
              <span
                className="text-base font-semibold text-[color:var(--color-accent-ink)]"
                style={{ fontFamily: "var(--font-serif)" }}
              >
                FreshRoute
              </span>
            </div>
            <span className="text-xs text-[color:var(--color-accent-ink)]/60 tabular">
              Data · data.gov.in · Agmarknet
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
