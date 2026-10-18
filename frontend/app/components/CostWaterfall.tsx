import type { RecommendCostBreakdown } from "@/app/lib/api";
import { formatINR } from "@/app/lib/api";

type Props = {
  costs: RecommendCostBreakdown;
  grossRevenue: number;
  spoilageLoss: number;
  netRevenue: number;
};

type Row = { label: string; amount: number; accent?: boolean };

export function CostWaterfall({ costs, grossRevenue, spoilageLoss, netRevenue }: Props) {
  const rows: Row[] = [
    { label: "Fuel",            amount: costs.fuel_rs },
    { label: "APMC commission", amount: costs.apmc_commission_rs },
    { label: "Cess",            amount: costs.cess_rs },
    { label: "Entry fee",       amount: costs.entry_fee_rs },
    { label: "Labour",          amount: costs.labour_rs },
    { label: "Weighment",       amount: costs.weighment_rs },
    { label: "Spoilage loss",   amount: spoilageLoss, accent: true },
  ].filter((r) => r.amount > 0);

  return (
    <div className="space-y-1 text-sm">
      <div className="flex items-baseline justify-between py-1.5 text-[color:var(--color-fg-muted)]">
        <span>Gross revenue</span>
        <span className="tabular font-medium text-[color:var(--color-fg)]">
          {formatINR(grossRevenue)}
        </span>
      </div>

      {rows.map((row) => {
        const barPct = Math.min(100, (row.amount / grossRevenue) * 100);
        return (
          <div key={row.label}>
            <div className="flex items-baseline justify-between py-1">
              <span className="text-[color:var(--color-fg-muted)]">{row.label}</span>
              <span
                className={[
                  "tabular",
                  row.accent
                    ? "text-[color:var(--color-warning)]"
                    : "text-[color:var(--color-fg-muted)]",
                ].join(" ")}
              >
                − {formatINR(row.amount)}
              </span>
            </div>
            <div className="h-[3px] w-full overflow-hidden rounded-full bg-[color:var(--color-line-soft)]">
              <div
                className={[
                  "h-full rounded-full",
                  row.accent
                    ? "bg-[color:var(--color-warning)]/60"
                    : "bg-[color:var(--color-accent)]/50",
                ].join(" ")}
                style={{ width: `${barPct}%` }}
              />
            </div>
          </div>
        );
      })}

      <div className="flex items-baseline justify-between border-t border-[color:var(--color-line-soft)] pt-2 mt-2">
        <span className="font-medium text-[color:var(--color-fg)]">Net revenue</span>
        <span
          className={[
            "tabular font-semibold",
            netRevenue >= 0
              ? "text-[color:var(--color-fg)]"
              : "text-[color:var(--color-danger)]",
          ].join(" ")}
          style={{ fontFamily: "var(--font-serif)" }}
        >
          {formatINR(netRevenue)}
        </span>
      </div>
    </div>
  );
}
