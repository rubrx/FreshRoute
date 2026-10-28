import Link from "next/link";

import { MandiChart } from "@/app/components/MandiChart";
import { Panel } from "@/app/components/Panel";
import {
  fetchCommodityOverview,
  fetchFacets,
  fetchPrices,
  formatINR,
  type MandiPrice,
} from "@/app/lib/api";

type Search = { commodity?: string; state?: string; view?: string };

type StateRanking = {
  state: string;
  medianPrice: number;
  topMandi: { market: string; price: number };
  mandisCount: number;
};

export default async function MandisPage({
  searchParams,
}: PageProps<"/mandis">) {
  const params = (await searchParams) as Search;
  const facets = await fetchFacets();

  const commodity = params.commodity ?? facets.commodities[0] ?? "Tomato";
  const state = params.state ?? "";
  const view = params.view === "state" ? "state" : "price";

  const [prices, overview] = await Promise.all([
    fetchPrices({ commodity, state: state || undefined, limit: 60 }),
    fetchCommodityOverview().catch(() => null),
  ]);

  const nationalMedian =
    overview?.commodities.find(
      (c) => c.commodity.toLowerCase() === commodity.toLowerCase()
    )?.national_median ?? undefined;

  const stats =
    prices.rows.length > 0
      ? {
          count: prices.rows.length,
          median: median(prices.rows.map((r) => r.modal_price_rs_per_quintal)),
          hi: prices.rows[0],
          lo: prices.rows[prices.rows.length - 1],
        }
      : null;

  const stateRankings = !state ? computeStateRankings(prices.rows) : [];

  const chartRows =
    view === "state" && stateRankings.length > 0
      ? stateRankings.map((s) => ({
          market: s.state,
          district: `${s.mandisCount} mandi${s.mandisCount !== 1 ? "s" : ""}`,
          modal_price: s.medianPrice,
        }))
      : prices.rows.map((r) => ({
          market: r.market,
          district: r.district,
          modal_price: r.modal_price_rs_per_quintal,
        }));

  const title = state ? `${commodity} · ${state}` : commodity;
  const baseHref = `/mandis?commodity=${encodeURIComponent(commodity)}${
    state ? `&state=${encodeURIComponent(state)}` : ""
  }`;

  return (
    <div className="mx-auto max-w-6xl px-6 pt-20 pb-24">
      <div className="mb-10">
        <div className="mb-2 text-[10px] uppercase tracking-[0.2em] text-[color:var(--color-fg-dim)]">
          {prices.snapshot_date ?? "—"}
        </div>
        <h1 className="text-4xl font-bold leading-tight tracking-[-0.02em] text-[color:var(--color-fg)]">
          {title}
        </h1>
        <p className="mt-3 max-w-xl text-sm text-[color:var(--color-fg-muted)]">
          Every reporting mandi, ranked by today&rsquo;s modal price.
        </p>
      </div>

      <form action="/mandis" className="mb-10 flex flex-wrap items-end gap-3">
        <input type="hidden" name="view" value={view} />
        <Field label="Commodity">
          <select
            name="commodity"
            defaultValue={commodity}
            className="rounded-md border border-[color:var(--color-line)] bg-[color:var(--color-bg-elev)] px-3 py-2 text-sm text-[color:var(--color-fg)] focus:border-[color:var(--color-accent)] focus:outline-none"
          >
            {facets.commodities.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </Field>
        <Field label="State">
          <select
            name="state"
            defaultValue={state}
            className="rounded-md border border-[color:var(--color-line)] bg-[color:var(--color-bg-elev)] px-3 py-2 text-sm text-[color:var(--color-fg)] focus:border-[color:var(--color-accent)] focus:outline-none"
          >
            <option value="">Any</option>
            {facets.states.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </Field>
        <button
          type="submit"
          className="rounded-full bg-[color:var(--color-fg)] px-4 py-2 text-sm font-medium text-[color:var(--color-bg)]"
        >
          Apply
        </button>
        {state ? (
          <Link
            href={`/mandis?commodity=${encodeURIComponent(commodity)}`}
            className="text-xs text-[color:var(--color-fg-muted)] hover:text-[color:var(--color-fg)]"
          >
            Reset state
          </Link>
        ) : null}
      </form>

      {stats ? (
        <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4">
          <SmallStat label="Reporting" value={String(stats.count)} caption="mandis" />
          <SmallStat
            label="Median"
            value={formatINR(stats.median)}
            caption={nationalMedian ? `nat. median ${formatINR(nationalMedian)}` : "₹/qtl"}
          />
          <SmallStat
            label="High"
            value={formatINR(stats.hi.modal_price_rs_per_quintal)}
            caption={stats.hi.market}
          />
          <SmallStat
            label="Low"
            value={formatINR(stats.lo.modal_price_rs_per_quintal)}
            caption={stats.lo.market}
          />
        </div>
      ) : null}

      {prices.rows.length === 0 ? (
        <Panel className="p-8 text-center text-[color:var(--color-fg-muted)]">
          Nothing in today&rsquo;s snapshot for this filter.
        </Panel>
      ) : (
        <>
          <Panel className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h3 className="text-sm font-medium text-[color:var(--color-fg)]">
                  {view === "state" ? "By state (median)" : "Top 30"}
                </h3>
                {!state && (
                  <div className="flex overflow-hidden rounded-full border border-[color:var(--color-line)] text-xs">
                    <Link
                      href={`${baseHref}&view=price`}
                      className={[
                        "px-3 py-1 font-medium transition-colors",
                        view !== "state"
                          ? "bg-[color:var(--color-fg)] text-[color:var(--color-bg)]"
                          : "text-[color:var(--color-fg-muted)] hover:bg-[color:var(--color-bg-elev-2)]",
                      ].join(" ")}
                    >
                      By price
                    </Link>
                    <Link
                      href={`${baseHref}&view=state`}
                      className={[
                        "px-3 py-1 font-medium transition-colors",
                        view === "state"
                          ? "bg-[color:var(--color-fg)] text-[color:var(--color-bg)]"
                          : "text-[color:var(--color-fg-muted)] hover:bg-[color:var(--color-bg-elev-2)]",
                      ].join(" ")}
                    >
                      By state
                    </Link>
                  </div>
                )}
              </div>
              <span className="text-xs text-[color:var(--color-fg-muted)]">₹/quintal</span>
            </div>
            <MandiChart
              rows={chartRows}
              nationalMedian={view === "price" ? nationalMedian : undefined}
            />
          </Panel>

          {/* State ranking table */}
          {stateRankings.length > 1 && (
            <Panel className="mt-6 overflow-hidden">
              <div className="border-b border-[color:var(--color-line-soft)] px-5 py-4">
                <h3 className="text-sm font-medium text-[color:var(--color-fg)]">
                  State ranking — {commodity}
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 border-b border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] text-left text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">
                    <tr>
                      <th className="px-5 py-2.5 font-medium">#</th>
                      <th className="px-5 py-2.5 font-medium">State</th>
                      <th className="px-5 py-2.5 text-right font-medium">Median</th>
                      <th className="hidden px-5 py-2.5 font-medium md:table-cell">Top mandi</th>
                      <th className="px-5 py-2.5 text-right font-medium">Reporting</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stateRankings.map((s, i) => (
                      <tr
                        key={s.state}
                        className="border-b border-[color:var(--color-line-soft)]/60 last:border-none hover:bg-[color:var(--color-bg-elev-2)]/60"
                      >
                        <td className="px-5 py-2.5 tabular text-[color:var(--color-fg-dim)]">
                          {i + 1}
                        </td>
                        <td className="px-5 py-2.5 font-medium text-[color:var(--color-fg)]">
                          <Link
                            href={`/mandis?commodity=${encodeURIComponent(commodity)}&state=${encodeURIComponent(s.state)}`}
                            className="transition-colors hover:text-[color:var(--color-accent)]"
                          >
                            {s.state}
                          </Link>
                        </td>
                        <td className="px-5 py-2.5 text-right tabular font-medium text-[color:var(--color-fg)]">
                          {formatINR(s.medianPrice)}
                        </td>
                        <td className="hidden px-5 py-2.5 text-[color:var(--color-fg-muted)] md:table-cell">
                          {s.topMandi.market}
                        </td>
                        <td className="px-5 py-2.5 text-right tabular text-[color:var(--color-fg-muted)]">
                          {s.mandisCount}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          {/* Mobile card list */}
          <div className="mt-6 space-y-2 md:hidden">
            <div className="mb-3 text-xs text-[color:var(--color-fg-dim)]">
              All {prices.count} mandis
            </div>
            {prices.rows.map((r) => (
              <div
                key={r.market_id}
                className="flex items-center justify-between gap-3 rounded-xl border border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-[color:var(--color-fg)]">
                    {r.market}
                  </div>
                  <div className="mt-0.5 text-xs text-[color:var(--color-fg-dim)]">
                    {r.district} · {r.state}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="tabular text-base font-medium text-[color:var(--color-fg)]">
                    {formatINR(r.modal_price_rs_per_quintal)}
                  </div>
                  <div className="text-[10px] text-[color:var(--color-fg-dim)]">₹/qtl modal</div>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop table */}
          <Panel className="mt-6 hidden overflow-hidden md:block">
            <div className="border-b border-[color:var(--color-line-soft)] px-5 py-4 text-sm text-[color:var(--color-fg)]">
              All {prices.count} mandis
            </div>
            <div className="max-h-[540px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 border-b border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] text-left text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">State</th>
                    <th className="px-5 py-2.5 font-medium">District</th>
                    <th className="px-5 py-2.5 font-medium">Mandi</th>
                    <th className="px-5 py-2.5 text-right font-medium">Min</th>
                    <th className="px-5 py-2.5 text-right font-medium">Modal</th>
                    <th className="px-5 py-2.5 text-right font-medium">Max</th>
                  </tr>
                </thead>
                <tbody>
                  {prices.rows.map((r) => (
                    <tr
                      key={r.market_id}
                      className="border-b border-[color:var(--color-line-soft)]/60 last:border-none hover:bg-[color:var(--color-bg-elev-2)]/60"
                    >
                      <td className="px-5 py-2 text-[color:var(--color-fg-muted)]">{r.state}</td>
                      <td className="px-5 py-2 text-[color:var(--color-fg-muted)]">{r.district}</td>
                      <td className="px-5 py-2 text-[color:var(--color-fg)]">{r.market}</td>
                      <td className="px-5 py-2 text-right tabular text-[color:var(--color-fg-muted)]">
                        {r.min_price_rs_per_quintal !== null
                          ? formatINR(r.min_price_rs_per_quintal)
                          : "—"}
                      </td>
                      <td className="px-5 py-2 text-right tabular font-medium text-[color:var(--color-fg)]">
                        {formatINR(r.modal_price_rs_per_quintal)}
                      </td>
                      <td className="px-5 py-2 text-right tabular text-[color:var(--color-fg-muted)]">
                        {r.max_price_rs_per_quintal !== null
                          ? formatINR(r.max_price_rs_per_quintal)
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">
        {label}
      </span>
      {children}
    </label>
  );
}

function SmallStat({
  label,
  value,
  caption,
}: {
  label: string;
  value: string;
  caption?: string;
}) {
  return (
    <Panel className="p-4">
      <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">
        {label}
      </div>
      <div className="mt-2 text-xl font-semibold tabular text-[color:var(--color-fg)]">
        {value}
      </div>
      {caption ? (
        <div className="mt-1 truncate text-xs text-[color:var(--color-fg-muted)]">{caption}</div>
      ) : null}
    </Panel>
  );
}

function median(nums: number[]): number {
  if (nums.length === 0) return 0;
  const sorted = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

function computeStateRankings(rows: MandiPrice[]): StateRanking[] {
  const map = new Map<string, { prices: number[]; topMandi: { market: string; price: number } }>();

  for (const r of rows) {
    const entry = map.get(r.state);
    if (!entry) {
      map.set(r.state, {
        prices: [r.modal_price_rs_per_quintal],
        topMandi: { market: r.market, price: r.modal_price_rs_per_quintal },
      });
    } else {
      entry.prices.push(r.modal_price_rs_per_quintal);
      if (r.modal_price_rs_per_quintal > entry.topMandi.price) {
        entry.topMandi = { market: r.market, price: r.modal_price_rs_per_quintal };
      }
    }
  }

  return [...map.entries()]
    .map(([state, { prices: ps, topMandi }]) => ({
      state,
      medianPrice: median(ps),
      topMandi,
      mandisCount: ps.length,
    }))
    .sort((a, b) => b.medianPrice - a.medianPrice);
}
