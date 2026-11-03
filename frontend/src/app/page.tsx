import Link from "next/link";
import { ArrowRight, CheckCircle, MapPin, TrendingUp } from "lucide-react";

import { Panel } from "@/components/ui/Panel";
import { SpreadBar } from "@/components/features/SpreadBar";
import {
  fetchArbitrage,
  fetchCommodityOverview,
  fetchSummary,
  formatINR,
  formatNumber,
} from "@/lib/api";

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

      {/* ── Hero ──────────────────────────────────────────────── */}
      <section className="bg-[color:var(--color-bg)] pt-16 pb-14 md:pt-24 md:pb-20">
        <div className="mx-auto max-w-3xl px-5 text-center">

          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[color:var(--color-warm-soft)] bg-[color:var(--color-warm-soft)] px-3.5 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-[color:var(--color-warm)]" aria-hidden="true" />
            <span className="text-sm font-medium text-[color:var(--color-warm)]">
              Kisan Ka Saathi
            </span>
          </div>

          <h1 className="text-[2.75rem] leading-[1.08] tracking-tight font-bold text-[color:var(--color-fg)] md:text-[3.5rem] lg:text-[4rem]">
            Apni Fasal Ka{" "}
            <span className="text-[color:var(--color-accent)]">Best Mandi</span>{" "}
            Yahan Milega.
          </h1>

          <p className="mt-5 text-lg leading-relaxed text-[color:var(--color-fg-muted)] max-w-xl mx-auto">
            We rank every nearby mandi by what you actually pocket — after
            freight, spoilage, and all seven fees. No guesswork.
          </p>

          {/* Illustration */}
          <div className="my-10 flex justify-center">
            <MandiIllustration />
          </div>

          {/* CTAs */}
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/recommend"
              className="inline-flex min-h-[52px] items-center gap-2 rounded-full border border-[color:var(--color-accent)] bg-[color:var(--color-accent)] px-7 py-3.5 text-base font-semibold text-[color:var(--color-accent-ink)] shadow-[var(--shadow-1)] transition-colors hover:border-[color:var(--color-accent-mid)] hover:bg-[color:var(--color-accent-mid)]"
            >
              <MapPin size={17} aria-hidden="true" />
              Find Best Mandi
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
            <Link
              href="/arbitrage"
              className="inline-flex min-h-[52px] items-center gap-1 text-base font-medium text-[color:var(--color-fg-muted)] underline underline-offset-4 decoration-[color:var(--color-line)] transition-colors hover:text-[color:var(--color-fg)] hover:decoration-[color:var(--color-fg-muted)]"
            >
              Today&rsquo;s spreads
              <ArrowRight size={14} aria-hidden="true" />
            </Link>
          </div>

          {/* Trust badges */}
          <div className="mt-7 flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
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
      </section>

      {/* ── Today's Widest Spread ─────────────────────────────── */}
      {featured && (
        <section className="bg-[color:var(--color-bg-elev)] py-14 border-y border-[color:var(--color-line-soft)]">
          <div className="mx-auto max-w-2xl px-5">
            <div className="mb-2 flex items-center gap-2">
              <span className="rounded-full bg-[color:var(--color-warm-soft)] px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-[color:var(--color-warm)]">
                Live
              </span>
              <span className="text-sm text-[color:var(--color-fg-dim)]">
                Today&rsquo;s widest spread
              </span>
            </div>

            <h2 className="text-2xl font-bold text-[color:var(--color-fg)] md:text-3xl">
              {featured.commodity}{" "}
              <span className="font-normal text-[color:var(--color-fg-muted)]">in</span>{" "}
              {featured.state}
            </h2>
            <p className="mt-1 text-sm text-[color:var(--color-fg-muted)]">
              {featured.mandis_reporting} mandis reporting today
            </p>

            <div className="mt-6">
              <SpreadBar
                low={featured.min_price_rs_per_quintal}
                high={featured.max_price_rs_per_quintal}
                lowLabel={featured.low_market}
                highLabel={featured.high_market}
                animate
              />
            </div>

            <div className="mt-5 flex items-center justify-between border-t border-[color:var(--color-line-soft)] pt-4">
              <div>
                <div className="text-xs text-[color:var(--color-fg-dim)]">
                  Price surplus
                </div>
                <div className="mt-0.5 text-2xl font-bold tabular text-[color:var(--color-fg)]">
                  {formatINR(featured.spread_rs_per_quintal)}
                  <span className="ml-1 text-sm font-normal text-[color:var(--color-fg-dim)]">
                    / quintal (100 kg)
                  </span>
                </div>
              </div>
              <span className="rounded-full bg-[color:var(--color-accent-soft)] px-3.5 py-1.5 text-sm font-semibold tabular text-[color:var(--color-accent)]">
                +{formatNumber(featured.spread_pct, 1)}%
              </span>
            </div>

            <Link
              href="/recommend"
              className="mt-6 inline-flex min-h-[48px] w-full items-center justify-center gap-2 rounded-full border border-[color:var(--color-accent)] bg-[color:var(--color-accent)] px-6 py-3 text-sm font-semibold text-[color:var(--color-accent-ink)] transition-colors hover:border-[color:var(--color-accent-mid)] hover:bg-[color:var(--color-accent-mid)]"
            >
              <MapPin size={15} aria-hidden="true" />
              Find mandi near me
            </Link>
          </div>
        </section>
      )}

      {/* ── Ramesh scenario — before/after ────────────────────── */}
      <section className="bg-[color:var(--color-bg-elev-2)] py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-5">
          <div className="mb-10 text-center">
            <div className="mb-2 text-sm font-semibold uppercase tracking-[0.18em] text-[color:var(--color-warm)]">
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
                <div className="mt-1 text-3xl font-bold tabular text-[color:var(--color-fg)]">
                  ₹2,100
                  <span className="text-base font-normal text-[color:var(--color-fg-muted)]"> per quintal</span>
                </div>
              </div>
              <div className="mt-3">
                <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">Net after all costs</div>
                <div className="mt-1 text-2xl font-semibold tabular text-[color:var(--color-danger)]">₹2,100 / quintal</div>
                <div className="mt-0.5 text-xs text-[color:var(--color-fg-dim)]">0 km — no freight cost</div>
              </div>
            </Panel>

            {/* Middle: difference */}
            <div className="flex flex-col items-center gap-3 py-4">
              <TrendingUp size={36} className="text-[color:var(--color-accent)]" aria-hidden="true" />
              <div className="text-center">
                <div className="text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">Difference per consignment</div>
                <div className="mt-1 text-4xl font-bold tabular text-[color:var(--color-accent)]">+₹2,900</div>
                <div className="mt-0.5 text-sm text-[color:var(--color-fg-muted)]">on 5 tonnes</div>
              </div>
              <ArrowRight
                size={20}
                className="text-[color:var(--color-fg-dim)] rotate-90 md:rotate-0"
                aria-hidden="true"
              />
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
                <div className="mt-1 text-3xl font-bold tabular text-[color:var(--color-fg)]">
                  ₹3,100
                  <span className="text-base font-normal text-[color:var(--color-fg-muted)]"> per quintal</span>
                </div>
              </div>
              <div className="mt-3">
                <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">Net after freight + market fees</div>
                <div className="mt-1 text-2xl font-semibold tabular text-[color:var(--color-success)]">₹2,680 / quintal</div>
                <div className="mt-0.5 text-xs text-[color:var(--color-fg-dim)]">80 km · small truck · 2.5% market fee</div>
              </div>
            </Panel>
          </div>

          <div className="mt-10 text-center">
            <Link
              href="/recommend"
              className="inline-flex min-h-[52px] items-center gap-2 rounded-full border border-[color:var(--color-accent)] bg-[color:var(--color-accent)] px-8 py-3.5 text-base font-semibold text-[color:var(--color-accent-ink)] shadow-[var(--shadow-1)] transition-colors hover:border-[color:var(--color-accent-mid)] hover:bg-[color:var(--color-accent-mid)]"
            >
              <MapPin size={18} aria-hidden="true" />
              Find my best mandi
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── Today's Market Snapshot ────────────────────────────── */}
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
                  className="group rounded-2xl border border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] p-6 transition-colors hover:border-[color:var(--color-accent)]"
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
                      <span className="ml-1 text-xs font-normal text-[color:var(--color-fg-muted)]">
                        /quintal
                      </span>
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

      {/* ── Why FreshRoute ────────────────────────────────────── */}
      <section className="bg-[color:var(--color-bg-elev-2)] py-16 md:py-20">
        <div className="mx-auto max-w-6xl px-5">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold text-[color:var(--color-fg)] md:text-4xl">
              Why Farmers Choose FreshRoute
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] p-6 transition-colors hover:border-[color:var(--color-accent)]"
              >
                <div className="mb-4 text-3xl">{f.icon}</div>
                <h3 className="mb-2 font-semibold text-[color:var(--color-fg)]">{f.title}</h3>
                <p className="text-sm leading-relaxed text-[color:var(--color-fg-muted)]">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

    </div>
  );
}

const FEATURES = [
  {
    icon: "🚛",
    title: "Saves ₹300–800/quintal",
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
    desc: "Market commission, cess, entry fee, labour, weighment — all deducted before you see the number.",
  },
  {
    icon: "🕐",
    title: "700+ mandis by 6 AM",
    desc: "Prices from data.gov.in, refreshed daily. No calls to agents. No middlemen.",
  },
] as const;

function MandiIllustration() {
  return (
    <svg
      viewBox="0 0 420 260"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="w-full max-w-sm md:max-w-md"
      role="img"
      aria-hidden="true"
    >
      {/* Sky */}
      <rect width="420" height="260" rx="16" fill="#EEF7EE" />
      {/* Ground */}
      <rect x="0" y="208" width="420" height="52" fill="#D7ECD7" />

      {/* Mandi building */}
      <rect x="152" y="112" width="168" height="100" rx="4" fill="#FAFAF7" stroke="#E8E5E0" strokeWidth="1.5" />
      {/* Roof */}
      <path d="M136 117 L236 67 L336 117 Z" fill="#1B5E20" />
      <rect x="136" y="113" width="200" height="7" fill="#155017" />
      {/* Roof accent band */}
      <rect x="190" y="80" width="92" height="12" rx="3" fill="#FFFFFF" opacity="0.2" />
      {/* Door arch */}
      <path d="M208 212 L208 165 Q236 150 264 165 L264 212 Z" fill="#DCEDC8" />
      {/* Windows */}
      <rect x="170" y="138" width="24" height="18" rx="3" fill="#C8E6C9" />
      <rect x="278" y="138" width="24" height="18" rx="3" fill="#C8E6C9" />

      {/* Produce at base */}
      <ellipse cx="173" cy="220" rx="12" ry="8" fill="#E53935" opacity="0.88" />
      <ellipse cx="191" cy="224" rx="10" ry="7" fill="#BF360C" opacity="0.82" />
      <ellipse cx="280" cy="222" rx="11" ry="7" fill="#F9A825" opacity="0.88" />
      <ellipse cx="297" cy="219" rx="11" ry="7" fill="#558B2F" opacity="0.88" />
      <ellipse cx="162" cy="226" rx="8" ry="6" fill="#795548" opacity="0.75" />
      <ellipse cx="308" cy="226" rx="8" ry="6" fill="#795548" opacity="0.75" />

      {/* Farm (left) */}
      <rect x="20" y="170" width="54" height="42" rx="3" fill="#FFF9C4" />
      <path d="M13 175 L47 149 L81 175 Z" fill="#F9A825" />
      <rect x="36" y="193" width="20" height="19" rx="3" fill="#A1887F" />
      {/* Tree */}
      <rect x="90" y="188" width="5" height="24" fill="#795548" />
      <circle cx="92" cy="183" r="12" fill="#4CAF50" opacity="0.75" />

      {/* Road / route */}
      <path d="M88 228 Q148 238 205 228" stroke="#C8C0B5" strokeWidth="9" strokeLinecap="round" fill="none" />
      <path d="M88 228 Q148 238 205 228" stroke="#F5F2EE" strokeWidth="5" strokeDasharray="10 7" strokeLinecap="round" fill="none" />

      {/* Truck */}
      <rect x="122" y="214" width="36" height="20" rx="3" fill="#37474F" />
      <rect x="122" y="217" width="13" height="17" rx="2" fill="#546E7A" />
      <circle cx="131" cy="236" r="5" fill="#263238" />
      <circle cx="131" cy="236" r="2.5" fill="#90A4AE" />
      <circle cx="149" cy="236" r="5" fill="#263238" />
      <circle cx="149" cy="236" r="2.5" fill="#90A4AE" />

      {/* Farm location pin */}
      <circle cx="47" cy="158" r="9" fill="#FFF3E0" stroke="#F57C00" strokeWidth="1.5" />
      <circle cx="47" cy="158" r="3.5" fill="#F57C00" />

      {/* Price badge (top right) */}
      <rect x="344" y="74" width="60" height="50" rx="10" fill="white" stroke="#E8E5E0" strokeWidth="1.5" />
      <circle cx="362" cy="96" r="12" fill="#FFF3E0" />
      <path d="M362 102 L362 90 M357 96 L362 90 L367 96" stroke="#F57C00" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="347" y="108" width="54" height="8" rx="4" fill="#1B5E20" opacity="0.65" />

      {/* Best price pill */}
      <rect x="334" y="140" width="76" height="28" rx="14" fill="#1B5E20" />
      <rect x="346" y="151" width="52" height="6" rx="2" fill="white" opacity="0.55" />

      {/* Decorative dots */}
      <circle cx="116" cy="74" r="4" fill="#F57C00" opacity="0.35" />
      <circle cx="104" cy="62" r="3" fill="#1B5E20" opacity="0.25" />
      <circle cx="128" cy="60" r="2.5" fill="#F57C00" opacity="0.25" />
    </svg>
  );
}
