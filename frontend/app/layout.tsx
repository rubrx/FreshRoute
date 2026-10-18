import type { Metadata } from "next";
import Link from "next/link";
import { Leaf, MapPin } from "lucide-react";
import { Inter, JetBrains_Mono, Noto_Sans_Devanagari } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const notoDevanagari = Noto_Sans_Devanagari({
  variable: "--font-noto-devanagari",
  subsets: ["devanagari"],
  weight: ["400", "500"],
  display: "swap",
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
      className={`${inter.variable} ${notoDevanagari.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[color:var(--color-bg)]">

        {/* ── Header ──────────────────────────────────────────── */}
        <header className="sticky top-0 z-30 border-b border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)]/95 backdrop-blur-md">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-5 py-3.5">

            <Link href="/" className="flex items-center gap-2.5 shrink-0">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[color:var(--color-accent-soft)]">
                <Leaf size={18} className="text-[color:var(--color-accent)]" aria-hidden="true" />
              </div>
              <div className="leading-none">
                <div className="text-[17px] font-semibold text-[color:var(--color-accent)] leading-tight tracking-tight">
                  FreshRoute
                </div>
                <div className="text-[10px] text-[color:var(--color-fg-dim)] tracking-wide">
                  Kisan Ka Saathi
                </div>
              </div>
            </Link>

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

            <Link
              href="/recommend"
              className="hidden md:inline-flex items-center gap-1.5 rounded-full bg-[color:var(--color-accent)] px-4 py-2 text-sm font-semibold text-[color:var(--color-accent-ink)] transition-all hover:bg-[color:var(--color-accent-mid)] hover:-translate-y-0.5 shadow-[var(--shadow-1)]"
            >
              <MapPin size={14} aria-hidden="true" />
              Find Mandi
            </Link>

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
        <main className="flex-1">
          {children}
        </main>

        {/* ── Footer ───────────────────────────────────────── */}
        <footer className="bg-[oklch(20%_0.006_270)] px-6 py-10">
          <div className="mx-auto max-w-6xl">
            <div className="flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">

              {/* Brand */}
              <div>
                <div className="flex items-center gap-2">
                  <Leaf size={16} className="text-[color:var(--color-accent-soft)]" aria-hidden="true" />
                  <span className="font-semibold text-white">FreshRoute</span>
                </div>
                <p className="mt-2 max-w-[260px] text-sm leading-relaxed text-white/55">
                  Mandi routing for Indian farmers. Ranked by what you actually pocket after all costs.
                </p>
              </div>

              {/* Social links */}
              <div className="flex items-center gap-2">
                <a
                  href="https://github.com/rubrx/FreshRoute"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="GitHub repository"
                  className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/15 text-white/50 transition-colors hover:border-white/30 hover:text-white/80"
                >
                  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                  </svg>
                </a>
                <a
                  href="https://www.linkedin.com/in/rubrangsokri/"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="LinkedIn profile"
                  className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/15 text-white/50 transition-colors hover:border-white/30 hover:text-white/80"
                >
                  <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                  </svg>
                </a>
              </div>
            </div>

            <div className="mt-8 border-t border-white/10 pt-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-[10px] uppercase tracking-widest text-white/35 mb-1.5">Data sources</p>
                <p className="text-xs text-white/45">data.gov.in</p>
                <p className="text-xs text-white/45">Agmarknet</p>
              </div>
              <span className="text-xs text-white/30">
                &copy; 2026 FreshRoute
              </span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
