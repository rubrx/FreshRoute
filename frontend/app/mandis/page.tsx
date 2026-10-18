import Link from "next/link";

import { MandiChart } from "@/app/components/MandiChart";
import { Panel } from "@/app/components/Panel";
import { fetchFacets, fetchPrices, formatINR } from "@/app/lib/api";

type Search = { commodity?: string; state?: string };

export default async function MandisPage({
  searchParams,
}: PageProps<"/mandis">) {
  const params = (await searchParams) as Search;
  const facets = await fetchFacets();

  const commodity = params.commodity ?? facets.commodities[0] ?? "Tomato";
  const state = params.state ?? "";

  const prices = await fetchPrices({
    commodity,
    state: state || undefined,
    limit: 60,
  });

  const stats =
    prices.rows.length > 0
      ? {
          count: prices.rows.length,
          median: median(prices.rows.map((r) => r.modal_price_rs_per_quintal)),
          hi: prices.rows[0],
          lo: prices.rows[prices.rows.length - 1],
        }
      : null;

  const title = state ? `${commodity} · ${state}` : commodity;

  return (
    <div className="mx-auto max-w-6xl px-6 pt-20 pb-24">
      <div className="mb-10">
        <div className="mb-2 text-[10px] uppercase tracking-[0.2em] text-[color:var(--color-fg-dim)]">
          {prices.snapshot_date ?? "—"}
        </div>
        <h1
          className="text-4xl leading-tight tracking-[-0.02em] text-[color:var(--color-fg)]"
          style={{ fontFamily: "var(--font-serif)", fontWeight: 500 }}
        >
          {title}
        </h1>
        <p className="mt-3 max-w-xl text-sm text-[color:var(--color-fg-muted)]">
          Every reporting mandi, ranked by today&rsquo;s modal price.
        </p>
      </div>

      <form action="/mandis" className="mb-10 flex flex-wrap items-end gap-3">
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
          <SmallStat label="Median" value={formatINR(stats.median)} caption="₹/qtl" />
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
              <h3 className="text-sm text-[color:var(--color-fg)]">Top 15</h3>
              <span className="text-xs text-[color:var(--color-fg-muted)]">₹/quintal</span>
            </div>
            <MandiChart
              rows={prices.rows.map((r) => ({
                market: r.market,
                district: r.district,
                modal_price: r.modal_price_rs_per_quintal,
              }))}
            />
          </Panel>

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
                  <div
                    className="tabular text-base font-medium text-[color:var(--color-fg)]"
                    style={{ fontFamily: "var(--font-serif)" }}
                  >
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
      <div
        className="mt-2 text-xl tabular text-[color:var(--color-fg)]"
        style={{ fontFamily: "var(--font-serif)", fontWeight: 500 }}
      >
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
