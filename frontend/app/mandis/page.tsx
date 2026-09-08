import Link from "next/link";

import { MandiChart } from "@/app/components/MandiChart";
import { Panel, SectionHeader } from "@/app/components/Panel";
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

  return (
    <div className="mx-auto max-w-7xl px-6 pt-12 pb-24">
      <SectionHeader
        eyebrow={`Snapshot · ${prices.snapshot_date ?? "—"}`}
        title={`${commodity}${state ? ` in ${state}` : " — all reporting states"}`}
        description="Every reporting mandi ranked by modal price, high to low. The bars in the chart show the top 15; the full table sits below."
      />

      <form className="mb-8 flex flex-wrap items-end gap-4" action="/mandis">
        <Field label="Commodity">
          <select
            name="commodity"
            defaultValue={commodity}
            className="rounded-md border border-[color:var(--color-line)] bg-[color:var(--color-bg-elev)] px-3 py-2 text-sm text-[color:var(--color-fg)] focus:border-[color:var(--color-accent)] focus:outline-none"
          >
            {facets.commodities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="State (optional)">
          <select
            name="state"
            defaultValue={state}
            className="rounded-md border border-[color:var(--color-line)] bg-[color:var(--color-bg-elev)] px-3 py-2 text-sm text-[color:var(--color-fg)] focus:border-[color:var(--color-accent)] focus:outline-none"
          >
            <option value="">— all states —</option>
            {facets.states.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
        <button
          type="submit"
          className="rounded-full bg-[color:var(--color-accent)] px-4 py-2 text-sm font-semibold text-[color:var(--color-accent-ink)]"
        >
          Apply
        </button>
        {(commodity || state) && (
          <Link
            href="/mandis"
            className="text-xs text-[color:var(--color-fg-muted)] hover:text-[color:var(--color-fg)]"
          >
            Reset
          </Link>
        )}
      </form>

      {stats ? (
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <SmallStat label="Mandis reporting" value={String(stats.count)} />
          <SmallStat label="Median modal" value={formatINR(stats.median)} caption="₹/quintal" />
          <SmallStat
            label="Highest"
            value={formatINR(stats.hi.modal_price_rs_per_quintal)}
            caption={`${stats.hi.market} · ${stats.hi.district}`}
          />
          <SmallStat
            label="Lowest"
            value={formatINR(stats.lo.modal_price_rs_per_quintal)}
            caption={`${stats.lo.market} · ${stats.lo.district}`}
          />
        </div>
      ) : null}

      {prices.rows.length === 0 ? (
        <Panel className="p-8 text-center text-[color:var(--color-fg-muted)]">
          No prices in this snapshot for your filter. Try widening it.
        </Panel>
      ) : (
        <>
          <Panel className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-medium text-[color:var(--color-fg)]">
                Top 15 mandis
              </h3>
              <span className="text-xs text-[color:var(--color-fg-muted)]">
                Modal price · ₹/quintal
              </span>
            </div>
            <MandiChart
              rows={prices.rows.map((r) => ({
                market: r.market,
                district: r.district,
                modal_price: r.modal_price_rs_per_quintal,
              }))}
            />
          </Panel>

          <Panel className="mt-6 overflow-hidden">
            <div className="border-b border-[color:var(--color-line-soft)] px-5 py-4">
              <h3 className="text-sm font-medium text-[color:var(--color-fg)]">
                All reporting mandis ({prices.count})
              </h3>
            </div>
            <div className="max-h-[540px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 border-b border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] text-left text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">
                  <tr>
                    <th className="px-5 py-2 font-medium">State</th>
                    <th className="px-5 py-2 font-medium">District</th>
                    <th className="px-5 py-2 font-medium">Mandi</th>
                    <th className="px-5 py-2 text-right font-medium">Min</th>
                    <th className="px-5 py-2 text-right font-medium">Modal</th>
                    <th className="px-5 py-2 text-right font-medium">Max</th>
                  </tr>
                </thead>
                <tbody>
                  {prices.rows.map((r) => (
                    <tr
                      key={r.market_id}
                      className="border-b border-[color:var(--color-line-soft)]/50 last:border-none hover:bg-[color:var(--color-bg-elev-2)]/50"
                    >
                      <td className="px-5 py-2 text-[color:var(--color-fg-muted)]">
                        {r.state}
                      </td>
                      <td className="px-5 py-2 text-[color:var(--color-fg-muted)]">
                        {r.district}
                      </td>
                      <td className="px-5 py-2 text-[color:var(--color-fg)]">
                        {r.market}
                      </td>
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
        className="mt-2 text-xl font-medium tabular text-[color:var(--color-fg)]"
        style={{ fontFamily: "var(--font-serif)" }}
      >
        {value}
      </div>
      {caption ? (
        <div className="mt-1 text-xs text-[color:var(--color-fg-muted)]">{caption}</div>
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
