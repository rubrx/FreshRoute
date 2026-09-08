import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { KpiCard } from "./components/KpiCard";
import { Panel, SectionHeader } from "./components/Panel";
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
    fetchArbitrage({ limit: 5 }),
  ]);

  const featured = arb.rows[0];

  return (
    <div className="mx-auto max-w-7xl px-6 pt-16 pb-24">
      {/* ─── Hero ─────────────────────────────────────────────── */}
      <section className="grain grid grid-cols-1 gap-10 lg:grid-cols-[1.4fr_1fr] lg:gap-16">
        <div>
          <div className="mb-6 text-[11px] uppercase tracking-[0.24em] text-[color:var(--color-accent)]">
            Practicum · Phase 1 evaluation
          </div>
          <h1
            className="text-4xl leading-[1.05] tracking-[-0.02em] text-[color:var(--color-fg)] md:text-6xl"
            style={{ fontFamily: "var(--font-serif)", fontWeight: 500 }}
          >
            The same tomato is worth{" "}
            <span className="italic text-[color:var(--color-accent)]">₹800</span>{" "}
            in one mandi and{" "}
            <span className="italic text-[color:var(--color-accent)]">₹3,000</span>{" "}
            in another —{" "}
            <span className="italic text-[color:var(--color-fg-muted)]">today</span>.
          </h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-[color:var(--color-fg-muted)] md:text-lg">
            FreshRoute ingests free public price data every day, computes the
            same-day arbitrage spread between mandis, and — once Phase 3 and
            Phase 4 land — ranks destinations by expected net ₹/tonne after
            spoilage, freight, and commission.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href="/arbitrage"
              className="inline-flex items-center gap-2 rounded-full bg-[color:var(--color-accent)] px-5 py-2.5 text-sm font-semibold text-[color:var(--color-accent-ink)] transition-transform hover:-translate-y-0.5"
            >
              See today&rsquo;s biggest spreads <ArrowUpRight size={16} />
            </Link>
            <Link
              href="/estimate"
              className="inline-flex items-center gap-2 rounded-full border border-[color:var(--color-line)] px-5 py-2.5 text-sm font-medium text-[color:var(--color-fg)] transition-colors hover:bg-[color:var(--color-bg-elev)]"
            >
              Try the cost estimator
            </Link>
          </div>
        </div>

        {featured ? (
          <Panel className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-fg-dim)]">
                Featured spread · {featured.snapshot_date}
              </span>
              <span className="rounded-full bg-[color:var(--color-accent)]/10 px-2 py-1 text-[11px] font-semibold text-[color:var(--color-accent)]">
                +{formatNumber(featured.spread_pct, 1)}%
              </span>
            </div>
            <div
              className="text-2xl font-medium text-[color:var(--color-fg)]"
              style={{ fontFamily: "var(--font-serif)" }}
            >
              {featured.commodity}{" "}
              <span className="text-[color:var(--color-fg-muted)]">in</span>{" "}
              {featured.state}
            </div>
            <div className="mt-1 text-sm text-[color:var(--color-fg-muted)]">
              {featured.mandis_reporting} mandis reporting today
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
              <span className="text-[color:var(--color-fg-dim)]">
                Arbitrage surplus
              </span>
              <span
                className="tabular text-[color:var(--color-fg)]"
                style={{ fontFamily: "var(--font-serif)" }}
              >
                {formatINR(featured.spread_rs_per_quintal)}
                <span className="ml-1 text-xs text-[color:var(--color-fg-dim)]">
                  / quintal
                </span>
              </span>
            </div>
          </Panel>
        ) : null}
      </section>

      {/* ─── KPI grid ───────────────────────────────────────────── */}
      <section className="mt-16">
        <SectionHeader
          eyebrow="Live snapshot"
          title="What Phase 1 produces, every day"
          description="Ingested from data.gov.in resource 9ef84268-… into a TimescaleDB hypertable, normalised, deduped on the natural key, and quality-checked. These numbers refresh every minute."
        />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {summary.cards.map((c, i) => (
            <KpiCard
              key={c.label}
              label={c.label}
              value={c.value}
              caption={c.caption}
              accent={i === summary.cards.length - 1}
            />
          ))}
        </div>
      </section>

      {/* ─── Roadmap ──────────────────────────────────────────── */}
      <section className="mt-20">
        <SectionHeader
          eyebrow="Where we are"
          title="Seven phases, twelve weeks, three hard gates"
          description="The evaluation panel is seeing Phases 1 and 2 complete end-to-end. Phase 5 (the ranker + dashboard) is the surface you are looking at now; Phases 3 (forecasting) and 4 (freshness engine) plug into it in weeks 5–7."
        />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
          <RoadmapCard n="1" title="Data foundation" status="Shipped"
            body="Postgres+Timescale, migrations, ingestion via data.gov.in, quality report." />
          <RoadmapCard n="2" title="Cost + freshness data" status="Shipped"
            body="AH-66 shelf life, 13 pytest cases for the cost model, seasonal index code, OSRM." />
          <RoadmapCard n="3" title="Forecasting" status="Weeks 3, 5–7"
            body="LightGBM quantile P10/P50/P90 with rolling-origin backtest vs three baselines." />
          <RoadmapCard n="4" title="Freshness engine" status="Weeks 5–6"
            body="Q₁₀ analytical decay integrator, Open-Meteo along the OSRM route polyline." />
          <RoadmapCard n="5" title="Decision engine + UI" status="This surface"
            body="Ranker + FastAPI + mobile-first dashboard (what you are viewing right now)." />
          <RoadmapCard n="6" title="Alerts + ledger" status="Weeks 9–11"
            body="WhatsApp / SMS alerts + 90-day counterfactual ₹/tonne uplift report." />
          <RoadmapCard n="7" title="Field validation" status="Weeks 11–12"
            body="12–15 trader / FPO interviews; thesis, defence deck, live demo checklist." />
          <RoadmapCard n="—" title="Stretch" status="Post-Gate 3"
            body="Cold storage, split-lot allocation, procurement mode, harvest wave map." />
        </div>
      </section>
    </div>
  );
}

function RoadmapCard({
  n,
  title,
  status,
  body,
}: {
  n: string;
  title: string;
  status: string;
  body: string;
}) {
  const shipped = status === "Shipped" || status === "This surface";
  return (
    <Panel className="p-5">
      <div className="flex items-center justify-between">
        <span
          className="text-xl text-[color:var(--color-fg-dim)]"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          {n}
        </span>
        <span
          className={
            "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider " +
            (shipped
              ? "bg-[color:var(--color-success)]/12 text-[color:var(--color-success)]"
              : "bg-[color:var(--color-bg-elev-2)] text-[color:var(--color-fg-muted)]")
          }
        >
          {status}
        </span>
      </div>
      <div className="mt-3 text-base font-medium text-[color:var(--color-fg)]">
        {title}
      </div>
      <div className="mt-2 text-xs leading-5 text-[color:var(--color-fg-muted)]">
        {body}
      </div>
    </Panel>
  );
}
