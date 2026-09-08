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
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "FreshRoute — mandi price intelligence",
  description:
    "Live mandi prices across India, netted for freight, commission, and cess. See where your produce sells for more.",
};

const nav: readonly { href: string; label: string }[] = [
  { href: "/arbitrage", label: "Arbitrage" },
  { href: "/mandis",    label: "Mandis" },
  { href: "/estimate",  label: "Estimator" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${fraunces.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="sticky top-0 z-30 border-b border-[color:var(--color-line-soft)] bg-[color:var(--color-bg)]/85 backdrop-blur-md">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-8 px-6 py-5">
            <Link
              href="/"
              className="text-lg tracking-tight text-[color:var(--color-fg)]"
              style={{ fontFamily: "var(--font-serif)", fontWeight: 500 }}
            >
              Fresh<span className="text-[color:var(--color-accent)]">Route</span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-md px-3 py-1.5 text-[color:var(--color-fg-muted)] transition-colors hover:bg-[color:var(--color-bg-elev-2)] hover:text-[color:var(--color-fg)]"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-[color:var(--color-line-soft)] px-6 py-8">
          <div className="mx-auto flex max-w-6xl items-center justify-between text-xs text-[color:var(--color-fg-dim)]">
            <span
              className="text-sm text-[color:var(--color-fg-muted)]"
              style={{ fontFamily: "var(--font-serif)", fontWeight: 500 }}
            >
              FreshRoute
            </span>
            <span className="tabular">Data · data.gov.in</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
