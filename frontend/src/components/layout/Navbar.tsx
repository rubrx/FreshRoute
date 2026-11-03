import Link from "next/link";
import { Leaf, MapPin } from "lucide-react";

const NAV_LINKS = [
  { href: "/",          label: "Home" },
  { href: "/recommend", label: "Best Mandi" },
  { href: "/mandis",    label: "Prices" },
  { href: "/arbitrage", label: "Spreads" },
  { href: "/estimate",  label: "Calculator" },
] as const;

export function Navbar() {
  return (
    <header className="sticky top-0 z-30 border-b border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)]/95 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3.5">

        {/* Logo + nav */}
        <div className="flex items-center gap-8">
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
                className="rounded-lg px-4 py-2 text-[15px] font-medium text-[color:var(--color-fg-muted)] transition-colors hover:border-[color:var(--color-accent)] hover:bg-[color:var(--color-accent-soft)] hover:text-[color:var(--color-accent)]"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>

        {/* CTA */}
        <Link
          href="/recommend"
          className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--color-accent)] bg-[color:var(--color-accent)] px-4 py-2 text-sm font-semibold text-[color:var(--color-accent-ink)] transition-colors hover:border-[color:var(--color-accent-mid)] hover:bg-[color:var(--color-accent-mid)] shadow-[var(--shadow-1)]"
        >
          <MapPin size={14} aria-hidden="true" />
          <span>Find Mandi</span>
        </Link>
      </div>
    </header>
  );
}
