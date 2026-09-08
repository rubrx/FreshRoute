import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { Panel, SectionHeader } from "@/app/components/Panel";
import { SpreadBar } from "@/app/components/SpreadBar";
import { fetchArbitrage, formatINR, formatNumber } from "@/app/lib/api";

type Search = { commodity?: string };

export default async function ArbitragePage({
  searchParams,
}: PageProps<"/arbitrage">) {
  const { commodity } = (await searchParams) as Search;

  const arb = await fetchArbitrage({
    commodity,
    limit: 30,
    minReporters: 3,
  });

  const commodities = ["Tomato", "Onion", "Potato", "Banana"];
  const displayCommodity = commodity ?? "All commodities";

  return (
    <div className="mx-auto max-w-7xl px-6 pt-12 pb-24">
      <SectionHeader
        eyebrow={`Snapshot · ${arb.snapshot_date ?? "—"}`}
        title="Today’s same-day arbitrage spreads"
        description="Each row is one (commodity × state) with at least three reporting mandis. The bar shows where the low and the high sit inside the state’s price range; the percentage is high ÷ low − 1."
      />

      <div className="mb-8 flex flex-wrap items-center gap-2">
        <FilterChip href="/arbitrage" label="All" active={!commodity} />
        {commodities.map((c) => (
          <FilterChip
            key={c}
            href={`/arbitrage?commodity=${encodeURIComponent(c)}`}
            label={c}
            active={commodity === c}
          />
        ))}
      </div>

      {arb.rows.length === 0 ? (
        <Panel className="p-8 text-center text-[color:var(--color-fg-muted)]">
          No spreads to show for <span className="italic">{displayCommodity}</span>{" "}
          yet. Try another commodity or wait for tomorrow&rsquo;s snapshot.
        </Panel>
      ) : (
        <div className="space-y-3">
          {arb.rows.map((row) => (
            <Panel key={`${row.commodity}-${row.state}`} className="p-5">
              <div className="grid grid-cols-1 gap-6 md:grid-cols-[1.2fr_2fr_auto] md:items-center">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
                    {row.commodity}
                  </div>
                  <div
                    className="mt-1 text-lg font-medium text-[color:var(--color-fg)]"
                    style={{ fontFamily: "var(--font-serif)" }}
                  >
                    {row.state}
                  </div>
                  <div className="mt-1 text-xs text-[color:var(--color-fg-muted)]">
                    {row.mandis_reporting} mandis reporting
                  </div>
                </div>

                <SpreadBar
                  low={row.min_price_rs_per_quintal}
                  high={row.max_price_rs_per_quintal}
                  lowLabel={row.low_market}
                  highLabel={row.high_market}
                />

                <div className="flex flex-col items-end justify-between gap-2 md:h-full">
                  <span
                    className="rounded-full bg-[color:var(--color-accent)]/10 px-3 py-1 text-sm font-semibold tabular text-[color:var(--color-accent)]"
                  >
                    +{formatNumber(row.spread_pct, 1)}%
                  </span>
                  <span className="text-xs tabular text-[color:var(--color-fg-muted)]">
                    surplus {formatINR(row.spread_rs_per_quintal)}/qtl
                  </span>
                  <Link
                    href={`/mandis?commodity=${encodeURIComponent(row.commodity)}&state=${encodeURIComponent(row.state)}`}
                    className="inline-flex items-center gap-1 text-xs text-[color:var(--color-fg-muted)] transition-colors hover:text-[color:var(--color-fg)]"
                  >
                    Explore mandis <ArrowUpRight size={12} />
                  </Link>
                </div>
              </div>
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}

function FilterChip({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={
        "rounded-full border px-3 py-1.5 text-xs transition-colors " +
        (active
          ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent)]"
          : "border-[color:var(--color-line)] text-[color:var(--color-fg-muted)] hover:bg-[color:var(--color-bg-elev)]")
      }
    >
      {label}
    </Link>
  );
}
