import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { KpiCard } from "./components/KpiCard";
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
    <div className="mx-auto max-w-6xl px-6 pt-24 pb-28">
      <section className="grid grid-cols-1 items-start gap-12 lg:grid-cols-[1.35fr_1fr] lg:gap-20">
        <div>
          <h1
            className="text-5xl leading-[1.02] tracking-[-0.025em] text-[color:var(--color-fg)] md:text-6xl"
            style={{ fontFamily: "var(--font-serif)", fontWeight: 400 }}
          >
            Where your produce{" "}
            <span className="italic text-[color:var(--color-accent)]">sells for more.</span>
          </h1>
          <p className="mt-6 max-w-md text-lg leading-8 text-[color:var(--color-fg-muted)]">
            Live mandi prices across India, netted for freight and commission.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-3">
            <Link
              href="/arbitrage"
              className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-accent)] px-5 py-2.5 text-sm font-medium text-[color:var(--color-accent-ink)] transition-transform hover:-translate-y-0.5"
            >
              See today&rsquo;s spreads <ArrowUpRight size={15} />
            </Link>
            <Link
              href="/estimate"
              className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] px-5 py-2.5 text-sm font-medium text-[color:var(--color-fg)] transition-colors hover:bg-[color:var(--color-bg-elev-2)]"
            >
              Estimate a shipment
            </Link>
          </div>
        </div>

        {featured ? (
          <Panel className="p-7">
            <div className="mb-5 flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-fg-dim)]">
                Today&rsquo;s widest spread
              </span>
              <span className="tabular text-[11px] font-medium text-[color:var(--color-accent)]">
                +{formatNumber(featured.spread_pct, 1)}%
              </span>
            </div>
            <div
              className="text-2xl text-[color:var(--color-fg)]"
              style={{ fontFamily: "var(--font-serif)", fontWeight: 500 }}
            >
              {featured.commodity}{" "}
              <span className="text-[color:var(--color-fg-muted)]">in</span>{" "}
              {featured.state}
            </div>
            <div className="mt-1 text-xs text-[color:var(--color-fg-muted)]">
              {featured.mandis_reporting} mandis reporting
            </div>
            <div className="mt-6">
              <SpreadBar
                low={featured.min_price_rs_per_quintal}
                high={featured.max_price_rs_per_quintal}
                lowLabel={featured.low_market}
                highLabel={featured.high_market}
              />
            </div>
            <div className="mt-6 flex items-center justify-between border-t border-[color:var(--color-line-soft)] pt-4 text-sm">
              <span className="text-[color:var(--color-fg-dim)]">Surplus</span>
              <span
                className="tabular text-[color:var(--color-fg)]"
                style={{ fontFamily: "var(--font-serif)" }}
              >
                {formatINR(featured.spread_rs_per_quintal)}
                <span className="ml-1 text-xs text-[color:var(--color-fg-dim)]">/ qtl</span>
              </span>
            </div>
          </Panel>
        ) : null}
      </section>

      <section className="mt-24 grid grid-cols-2 gap-3 md:grid-cols-4">
        {summary.cards.map((c) => (
          <KpiCard
            key={c.label}
            label={c.label}
            value={c.value}
            caption={c.caption}
          />
        ))}
      </section>
    </div>
  );
}
