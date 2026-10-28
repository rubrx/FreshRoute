import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { Panel } from "@/app/components/Panel";
import { SpreadBar } from "@/app/components/SpreadBar";
import { fetchArbitrage, formatINR, formatNumber } from "@/app/lib/api";

type Search = { commodity?: string };

const COMMODITIES = ["Tomato", "Onion", "Potato", "Banana"] as const;

export default async function ArbitragePage({
  searchParams,
}: PageProps<"/arbitrage">) {
  const { commodity } = (await searchParams) as Search;
  const arb = await fetchArbitrage({ commodity, limit: 30, minReporters: 3 });

  return (
    <div className="mx-auto max-w-6xl px-6 pt-20 pb-24">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div>
          <div className="mb-2 text-[10px] uppercase tracking-[0.2em] text-[color:var(--color-fg-dim)]">
            {arb.snapshot_date ?? "—"}
          </div>
          <h1 className="text-4xl font-bold leading-tight tracking-[-0.02em] text-[color:var(--color-fg)]">
            Same-day spreads
          </h1>
          <p className="mt-3 max-w-xl text-sm text-[color:var(--color-fg-muted)]">
            The gap between the highest and lowest mandi, within each state, today.
          </p>
          <p className="mt-2 max-w-xl text-xs text-[color:var(--color-fg-dim)]">
            A spread is only worth acting on if it exceeds your freight cost.
            The <span className="font-medium text-[color:var(--color-fg-muted)]">est. net spread</span> column
            subtracts an indicative ₹4/km/tonne × 150 km (≈ ₹60/qtl) as a rough freight proxy — consult
            your transporter for a real quote before acting.
          </p>
        </div>
        <FilterRow active={commodity} />
      </div>

      {arb.rows.length === 0 ? (
        <Panel className="p-8 text-center text-[color:var(--color-fg-muted)]">
          Nothing to show for this filter yet.
        </Panel>
      ) : (
        <div className="space-y-2">
          {arb.rows.map((row) => (
            <Panel key={`${row.commodity}-${row.state}`} className="p-5">
              <div className="grid grid-cols-1 gap-6 md:grid-cols-[1.1fr_2fr_auto] md:items-center">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
                    {row.commodity}
                  </div>
                  <div className="mt-1 text-lg font-semibold text-[color:var(--color-fg)]">
                    {row.state}
                  </div>
                  <div className="mt-0.5 text-xs text-[color:var(--color-fg-muted)]">
                    {row.mandis_reporting} mandis
                  </div>
                </div>

                <SpreadBar
                  low={row.min_price_rs_per_quintal}
                  high={row.max_price_rs_per_quintal}
                  lowLabel={row.low_market}
                  highLabel={row.high_market}
                />

                <div className="flex flex-col items-end gap-2 text-right md:h-full md:justify-between">
                  <span className="tabular text-lg font-semibold text-[color:var(--color-accent)]">
                    +{formatNumber(row.spread_pct, 1)}%
                  </span>
                  <div className="space-y-0.5">
                    <div className="text-xs tabular text-[color:var(--color-fg-muted)]">
                      {formatINR(row.spread_rs_per_quintal)} / qtl gross
                    </div>
                    {(() => {
                      const netSpread = row.spread_rs_per_quintal - 60;
                      return (
                        <div className={[
                          "text-xs tabular font-medium",
                          netSpread > 0
                            ? "text-[color:var(--color-success)]"
                            : "text-[color:var(--color-danger)]",
                        ].join(" ")}>
                          {netSpread > 0 ? "+" : ""}{formatINR(netSpread)} / qtl net est.
                        </div>
                      );
                    })()}
                  </div>
                  <Link
                    href={`/mandis?commodity=${encodeURIComponent(row.commodity)}&state=${encodeURIComponent(row.state)}`}
                    className="inline-flex items-center gap-1 text-[11px] text-[color:var(--color-fg-muted)] transition-colors hover:text-[color:var(--color-fg)]"
                  >
                    Mandis <ArrowUpRight size={11} />
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

function FilterRow({ active }: { active?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-1 text-xs">
      <Chip href="/arbitrage" label="All" active={!active} />
      {COMMODITIES.map((c) => (
        <Chip
          key={c}
          href={`/arbitrage?commodity=${encodeURIComponent(c)}`}
          label={c}
          active={active === c}
        />
      ))}
    </div>
  );
}

function Chip({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={
        "rounded-full border px-3 py-1.5 transition-colors " +
        (active
          ? "border-[color:var(--color-fg)] bg-[color:var(--color-fg)] text-[color:var(--color-bg)]"
          : "border-[color:var(--color-line)] text-[color:var(--color-fg-muted)] hover:bg-[color:var(--color-bg-elev-2)]")
      }
    >
      {label}
    </Link>
  );
}
