import Link from "next/link";
import { ArrowRight, CheckCircle, Leaf, MapPin } from "lucide-react";

import { Panel } from "./components/Panel";
import { SpreadBar } from "./components/SpreadBar";
import {
  fetchArbitrage,
  fetchSummary,
  formatINR,
  formatNumber,
} from "./lib/api";

export default async function Home() {
  const [summary, arb] = await Promise.all([
    fetchSummary(),
    fetchArbitrage({ limit: 1 }),
  ]);
  const featured = arb.rows[0];

  return (
    <div>

      {/* ── Hero ──────────────────────────────────────────────────── */}
      <section className="bg-[color:var(--color-bg)] pt-6 pb-16 md:pt-10 md:pb-24">
        <div className="mx-auto max-w-6xl px-5 md:px-8">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-[1.15fr_1fr] lg:gap-20">

            {/* Left: headline + CTAs */}
            <div>
              <div className="mb-3 flex items-center gap-2">
                <Leaf
                  size={15}
                  className="text-[color:var(--color-accent)]"
                  aria-hidden="true"
                />
                <span className="text-[color:var(--color-accent)] text-sm font-medium leading-none tracking-wide">
                  Kisan Ka Saathi
                </span>
              </div>

              <h1
                className="text-[3rem] leading-[1.05] tracking-tight font-bold text-[color:var(--color-fg)] md:text-[3.75rem] lg:text-[4.25rem]"
              >
                Apni Fasal Ka{" "}
                <span className="text-[color:var(--color-accent)]">Best Mandi</span>{" "}
                Yahan Milega.
              </h1>

              <p className="mt-5 max-w-md text-xl leading-relaxed text-[color:var(--color-fg-muted)]">
                We rank every nearby mandi by what you actually pocket, after
                freight, spoilage, and all fees. No guesswork.
              </p>

              {/* CTAs */}
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link
                  href="/recommend"
                  className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-accent)] px-7 py-4 text-base font-semibold text-[color:var(--color-accent-ink)] shadow-[var(--shadow-1)] transition-all hover:bg-[color:var(--color-accent-mid)] hover:-translate-y-0.5"
                >
                  <MapPin size={17} aria-hidden="true" />
                  Find Best Mandi
                  <ArrowRight size={15} aria-hidden="true" />
                </Link>
                <Link
                  href="/arbitrage"
                  className="inline-flex items-center gap-2 rounded-full border-2 border-[color:var(--color-accent)] px-7 py-[14px] text-base font-semibold text-[color:var(--color-accent)] transition-colors hover:bg-[color:var(--color-accent-soft)]"
                >
                  Today&rsquo;s Spreads
                </Link>
              </div>

              {/* Trust badges */}
              <div className="mt-8 flex flex-wrap items-center gap-5">
                {[
                  "27 States covered",
                  "781 Mandis tracked",
                  "Updated daily",
                ].map((badge) => (
                  <div
                    key={badge}
                    className="flex items-center gap-1.5 text-sm text-[color:var(--color-fg-muted)]"
                  >
                    <CheckCircle
                      size={14}
                      className="text-[color:var(--color-accent)] shrink-0"
                      aria-hidden="true"
                    />
                    {badge}
                  </div>
                ))}
              </div>
            </div>

            {/* Right: Today's opportunity card */}
            {featured ? (
              <Panel className="p-6 md:p-7">
                <div className="mb-5 flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-fg-dim)]">
                      Today&rsquo;s widest spread
                    </div>
                    <div className="mt-2 text-2xl font-semibold text-[color:var(--color-fg)]">
                      {featured.commodity}{" "}
                      <span className="text-[color:var(--color-fg-muted)]">
                        in
                      </span>{" "}
                      {featured.state}
                    </div>
                    <div className="mt-1 text-xs text-[color:var(--color-fg-muted)]">
                      {featured.mandis_reporting} mandis reporting
                    </div>
                  </div>
                  <span className="shrink-0 rounded-full bg-[color:var(--color-accent-soft)] px-3 py-1 text-sm font-semibold tabular text-[color:var(--color-accent)]">
                    +{formatNumber(featured.spread_pct, 1)}%
                  </span>
                </div>

                <SpreadBar
                  low={featured.min_price_rs_per_quintal}
                  high={featured.max_price_rs_per_quintal}
                  lowLabel={featured.low_market}
                  highLabel={featured.high_market}
                />

                <div className="mt-5 flex items-center justify-between border-t border-[color:var(--color-line-soft)] pt-4">
                  <span className="text-sm text-[color:var(--color-fg-dim)]">
                    Price surplus
                  </span>
                  <span className="tabular text-xl font-semibold text-[color:var(--color-fg)]">
                    {formatINR(featured.spread_rs_per_quintal)}
                    <span className="ml-1.5 text-xs font-normal text-[color:var(--color-fg-dim)]">
                      / qtl
                    </span>
                  </span>
                </div>

                <Link
                  href="/recommend"
                  className="mt-5 flex w-full items-center justify-center gap-2 rounded-full bg-[color:var(--color-accent-soft)] py-3 text-sm font-semibold text-[color:var(--color-accent)] transition-colors hover:bg-[color:var(--color-accent)] hover:text-[color:var(--color-accent-ink)]"
                >
                  <MapPin size={14} aria-hidden="true" />
                  Find mandi near me
                </Link>
              </Panel>
            ) : null}
          </div>
        </div>
      </section>

      {/* ── Stats bar ─────────────────────────────────────────────── */}
      <section className="bg-[oklch(18%_0.010_250)] py-10">
        <div className="mx-auto max-w-6xl px-5">
          <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
            {summary.cards.map((c) => (
              <div key={c.label} className="text-center">
                <div className="text-3xl font-bold tabular text-[color:var(--color-accent-ink)] md:text-4xl tracking-tight">
                  {c.value}
                </div>
                <div className="mt-1.5 text-sm font-medium text-[color:var(--color-accent-ink)]/80">
                  {c.label}
                </div>
                {c.caption && (
                  <div className="mt-0.5 text-xs text-[color:var(--color-accent-ink)]/55">
                    {c.caption}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works — 3-step cards ─────────────────────────── */}
      <section className="bg-[color:var(--color-bg-elev-2)] py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-5">
          <div className="mb-12 text-center">
            <div className="mb-2 text-sm font-semibold uppercase tracking-[0.18em] text-[color:var(--color-accent)]">
              Simple as 1-2-3
            </div>
            <h2 className="text-3xl font-bold text-[color:var(--color-fg)] md:text-4xl">
              Find Your Best Mandi in 3 Taps
            </h2>
            <p className="mt-3 text-[color:var(--color-fg-muted)]">
              No spreadsheet. No calls to agents.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            {[
              {
                step: "1",
                emoji: "🌿",
                title: "Pick Your Produce",
                desc: "Select tomato, onion, potato, or banana. We'll handle the rest.",
              },
              {
                step: "2",
                emoji: "📍",
                title: "Share Your Location",
                desc: "Tap to share your GPS location or enter your district name.",
              },
              {
                step: "3",
                emoji: "₹",
                title: "See Net Earnings",
                desc: "Get mandis ranked by what you actually pocket after all costs.",
              },
            ].map((item) => (
              <div
                key={item.step}
                className="rounded-2xl bg-[color:var(--color-bg-elev)] p-7 shadow-[var(--shadow-1)] text-center"
              >
                <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-[color:var(--color-accent-soft)] text-3xl">
                  {item.emoji}
                </div>
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--color-accent)]">
                  Step {item.step}
                </div>
                <h3 className="text-lg font-semibold text-[color:var(--color-fg)]">
                  {item.title}
                </h3>
                <p className="mt-2.5 text-sm leading-relaxed text-[color:var(--color-fg-muted)]">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-10 text-center">
            <Link
              href="/recommend"
              className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-accent)] px-8 py-4 text-base font-semibold text-[color:var(--color-accent-ink)] shadow-[var(--shadow-1)] transition-all hover:bg-[color:var(--color-accent-mid)] hover:-translate-y-0.5"
            >
              <MapPin size={18} aria-hidden="true" />
              Try It Free
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── Why FreshRoute — feature grid ────────────────────────── */}
      <section className="py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-5">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold text-[color:var(--color-fg)] md:text-4xl">
              Why Farmers Choose FreshRoute
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: "🚛",
                title: "Freight Included",
                desc: "Diesel cost calculated for your vehicle type and distance.",
              },
              {
                icon: "🍅",
                title: "Spoilage Check",
                desc: "Only shows mandis your produce can reach before spoiling.",
              },
              {
                icon: "📊",
                title: "All Fees Netted",
                desc: "All APMC fees and levies deducted before ranking.",
              },
              {
                icon: "🕐",
                title: "Daily Updates",
                desc: "Price data refreshed every day from official sources.",
              },
            ].map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] p-6"
              >
                <div className="mb-4 text-3xl">{f.icon}</div>
                <h3 className="mb-2 font-semibold text-[color:var(--color-fg)]">
                  {f.title}
                </h3>
                <p className="text-sm leading-relaxed text-[color:var(--color-fg-muted)]">
                  {f.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

    </div>
  );
}
