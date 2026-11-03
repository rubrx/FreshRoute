import Image from "next/image";
import Link from "next/link";
import { MapPin } from "lucide-react";

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
          <Link href="/" className="shrink-0">
            <Image
              src="/logo.jpg"
              alt="FreshRoute"
              width={120}
              height={36}
              className="h-9 w-auto object-contain"
              priority
            />
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
