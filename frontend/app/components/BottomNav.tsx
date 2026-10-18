"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Home, MapPin, TrendingUp, User } from "lucide-react";

type Tab = {
  href: string;
  label: string;
  icon: React.ElementType;
  disabled?: boolean;
};

const TABS: Tab[] = [
  { href: "/",          label: "Home",       icon: Home },
  { href: "/recommend", label: "Best Mandi", icon: MapPin },
  { href: "/mandis",    label: "Prices",     icon: TrendingUp },
  { href: "/arbitrage", label: "Alerts",     icon: Bell },
  { href: "#",          label: "Account",    icon: User, disabled: true },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)]/97 backdrop-blur-md"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      aria-label="Main navigation"
    >
      <div className="flex h-14 items-stretch">
        {TABS.map(({ href, label, icon: Icon, disabled }) => {
          const active =
            href === "/"
              ? pathname === "/"
              : pathname.startsWith(href) && href !== "#";

          if (disabled) {
            return (
              <span
                key={label}
                className="flex flex-1 flex-col items-center justify-center gap-0.5 text-[10px] uppercase tracking-wide opacity-30 select-none cursor-not-allowed"
                aria-label={`${label} (coming soon)`}
              >
                <Icon size={20} strokeWidth={1.5} />
                <span>{label}</span>
              </span>
            );
          }

          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={[
                "relative flex flex-1 flex-col items-center justify-center gap-0.5 text-[10px] uppercase tracking-wide transition-colors",
                active
                  ? "text-[color:var(--color-accent)]"
                  : "text-[color:var(--color-fg-dim)] hover:text-[color:var(--color-fg-muted)]",
              ].join(" ")}
            >
              {active && (
                <span className="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-8 rounded-full bg-[color:var(--color-accent)]" />
              )}
              <Icon
                size={20}
                strokeWidth={active ? 2 : 1.5}
                aria-hidden="true"
              />
              <span>{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
