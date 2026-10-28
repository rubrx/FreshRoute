import Link from "next/link";
import { ArrowRight, CheckCircle, Leaf, MapPin, TrendingUp } from "lucide-react";

import { Panel } from "./components/Panel";
import { SpreadBar } from "./components/SpreadBar";
import {
  fetchArbitrage,
  fetchCommodityOverview,
  fetchSummary,
  formatINR,
  formatNumber,
} from "./lib/api";

export const revalidate = 3600;

export default async function Home() {
  const [summary, arb, overview] = await Promise.all([
    fetchSummary(),
    fetchArbitrage({ limit: 1 }),
    fetchCommodityOverview().catch(() => null),
  ]);
  const featured = arb.rows[0];

  const statesCard = summary.cards.find((c) => c.label === "States");
  const pricesCard = summary.cards.find((c) => c.label === "Prices");

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

              {/* Trust badges from API */}
              <div className="mt-8 flex flex-wrap items-center gap-5">
                {statesCard && (
                  <div className="flex items-center gap-1.5 text-sm text-[color:var(--color-fg-muted)]">
                    <CheckCircle size={14} className="text-[color:var(--color-accent)] shrink-0" aria-hidden="true" />
                    {statesCard.value} states · {statesCard.caption}
                  </div>
                )}
                {pricesCard && (
                  <div className="flex items-center gap-1.5 text-sm text-[color:var(--color-fg-muted)]">
                    <CheckCircle size={14} className="text-[color:var(--color-accent)] shrink-0" aria-hidden="true" />
                    {pricesCard.value} prices reported today
                  </div>
                )}
                <div className="flex items-center gap-1.5 text-sm text-[color:var(--color-fg-muted)]">
                  <CheckCircle size={14} className="text-[color:var(--color-accent)] shrink-0" aria-hidden="true" />
                  Updated daily from data.gov.in
                </div>
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

      {/* ── Ramesh scenario — before/after ────────────────────────── */}
      <section className="bg-[color:var(--color-bg-elev-2)] py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-5">
          <div className="mb-10 text-center">
            <div className="mb-2 text-sm font-semibold uppercase tracking-[0.18em] text-[color:var(--color-accent)]">
              Real Impact
            </div>
            <h2 className="text-3xl font-bold text-[color:var(--color-fg)] md:text-4xl">
              What this looks like for Ramesh
            </h2>
            <p className="mt-3 max-w-md mx-auto text-[color:var(--color-fg-muted)]">
              5 tonnes of tomatoes. Two choices. One very different outcome.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-3 items-center">
            {/* Before */}
            <Panel className="p-6 border-l-4 border-l-[color:var(--color-danger)]">
              <div className="mb-1 text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-danger)]">
                Without FreshRoute
              </div>
              <div className="text-lg font-semibold text-[color:var(--color-fg)]">
                Nearest mandi (Kanpur)
              </div>
              <div className="mt-4">
                <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">Gate price</div>
                <div className="mt-1 text-3xl font-bold tabular text-[color:var(--color-fg)]">₹2,100<span className="text-base font-normal text-[color:var(--color-fg-muted)]">/qtl</span></div>
              </div>
              <div className="mt-3">
                <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">Net after all costs</div>
                <div className="mt-1 text-2xl font-semibold tabular text-[color:var(--color-danger)]">₹2,100/qtl</div>
                <div className="mt-0.5 text-xs text-[color:var(--color-fg-dim)]">0 km — no freight</div>
              </div>
            </Panel>

            {/* Arrow */}
            <div className="flex flex-col items-center gap-3 py-4">
              <TrendingUp size={36} className="text-[color:var(--color-accent)]" aria-hidden="true" />
              <div className="text-center">
                <div className="text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">Difference per consignment</div>
                <div className="mt-1 text-4xl font-bold tabular text-[color:var(--color-accent)]">+₹2,900</div>
                <div className="mt-0.5 text-sm text-[color:var(--color-fg-muted)]">on 5 tonnes</div>
              </div>
              <ArrowRight size={20} className="text-[color:var(--color-fg-dim)] rotate-90 md:rotate-0" aria-hidden="true" />
            </div>

            {/* After */}
            <Panel className="p-6 border-l-4 border-l-[color:var(--color-success)]">
              <div className="mb-1 text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-success)]">
                With FreshRoute
              </div>
              <div className="text-lg font-semibold text-[color:var(--color-fg)]">
                Nashik Mandi (80 km)
              </div>
              <div className="mt-4">
                <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">Gate price</div>
                <div className="mt-1 text-3xl font-bold tabular text-[color:var(--color-fg)]">₹3,100<span className="text-base font-normal text-[color:var(--color-fg-muted)]">/qtl</span></div>
              </div>
              <div className="mt-3">
                <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">Net after freight + fees</div>
                <div className="mt-1 text-2xl font-semibold tabular text-[color:var(--color-success)]">₹2,680/qtl</div>
                <div className="mt-0.5 text-xs text-[color:var(--color-fg-dim)]">80 km · small truck · 2.5% APMC</div>
              </div>
            </Panel>
          </div>

          <div className="mt-10 text-center">
            <Link
              href="/recommend"
              className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-accent)] px-8 py-4 text-base font-semibold text-[color:var(--color-accent-ink)] shadow-[var(--shadow-1)] transition-all hover:bg-[color:var(--color-accent-mid)] hover:-translate-y-0.5"
            >
              <MapPin size={18} aria-hidden="true" />
              Find my best mandi
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── Commodity health cards ─────────────────────────────────── */}
      <section className="py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-5">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold text-[color:var(--color-fg)] md:text-4xl">
              Today&rsquo;s Market Snapshot
            </h2>
            <p className="mt-3 text-[color:var(--color-fg-muted)]">
              National median prices and best-paying states, right now.
            </p>
          </div>

          {overview && overview.commodities.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {overview.commodities.slice(0, 4).map((c) => (
                <Link
                  key={c.commodity}
                  href={`/mandis?commodity=${encodeURIComponent(c.commodity)}`}
                  className="group rounded-2xl border border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] p-6 transition-shadow hover:shadow-[var(--shadow-1)]"
                >
                  <div className="mb-3 text-lg font-semibold text-[color:var(--color-fg)] group-hover:text-[color:var(--color-accent)] transition-colors">
                    {c.commodity}
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">
                      National median
                    </div>
                    <div className="mt-1 text-2xl font-bold tabular text-[color:var(--color-fg)]">
                      {formatINR(c.national_median)}
                      <span className="ml-1 text-xs font-normal text-[color:var(--color-fg-muted)]">/qtl</span>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center gap-1.5">
                    <span className="rounded-full bg-[color:var(--color-accent-soft)] px-2.5 py-0.5 text-xs font-medium text-[color:var(--color-accent)]">
                      Best: {c.best_state}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-[color:var(--color-fg-muted)]">
                    {c.mandis_count} mandis reporting
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {["Tomato", "Onion", "Potato", "Banana"].map((name) => (
                <Link
                  key={name}
                  href={`/mandis?commodity=${encodeURIComponent(name)}`}
                  className="rounded-2xl border border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] p-6 opacity-50"
                >
                  <div className="mb-3 text-lg font-semibold text-[color:var(--color-fg)]">{name}</div>
                  <div className="h-6 w-24 rounded bg-[color:var(--color-line-soft)] animate-pulse" />
                  <div className="mt-3 text-xs text-[color:var(--color-fg-dim)]">No data yet</div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ── Why FreshRoute — precise feature grid ────────────────── */}
      <section className="bg-[color:var(--color-bg-elev-2)] py-16 md:py-20">
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
                title: "Saves ₹300–800/qtl",
                desc: "Hidden freight costs — fuel, driver, loading — are calculated for your vehicle and distance.",
              },
              {
                icon: "🍅",
                title: "Spoilage filter on",
                desc: "We never show a mandi your produce can't reach alive. Destinations are filtered before ranking.",
              },
              {
                icon: "📊",
                title: "All 7 fees netted",
                desc: "APMC commission, cess, entry fee, labour, weighment — all deducted before you see the number.",
              },
              {
                icon: "🕐",
                title: "700+ mandis by 6 AM",
                desc: "Prices from data.gov.in, refreshed daily. No calls to agents. No middlemen.",
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
