"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Row = { market: string; district: string; modal_price: number };

type Props = {
  rows: Row[];
};

/**
 * Horizontal bar chart of top mandis by modal price.
 * Client component because Recharts uses DOM measurement + hooks.
 */
export function MandiChart({ rows }: Props) {
  const data = rows.slice(0, 15).map((r) => ({
    label: r.market,
    tooltip: `${r.market} · ${r.district}`,
    price: r.modal_price,
  }));

  return (
    <div className="h-[420px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 24, bottom: 8, left: 32 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="oklch(30% 0.018 60)" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: "oklch(72% 0.020 70)", fontSize: 11 }}
            tickFormatter={(v) => `₹${v.toLocaleString("en-IN")}`}
            stroke="oklch(30% 0.018 60)"
          />
          <YAxis
            dataKey="label"
            type="category"
            tick={{ fill: "oklch(72% 0.020 70)", fontSize: 11 }}
            width={190}
            stroke="oklch(30% 0.018 60)"
          />
          <Tooltip
            cursor={{ fill: "oklch(23% 0.016 60 / 0.5)" }}
            contentStyle={{
              background: "oklch(19% 0.014 60)",
              border: "1px solid oklch(30% 0.018 60)",
              borderRadius: 8,
              color: "oklch(96% 0.015 80)",
              fontSize: 12,
            }}
            formatter={(v) => [
              `₹${Number(v).toLocaleString("en-IN")} / qtl`,
              "Modal",
            ]}
            labelFormatter={(_, payload) =>
              (payload?.[0]?.payload as { tooltip?: string } | undefined)?.tooltip ?? ""
            }
          />
          <Bar dataKey="price" fill="oklch(72% 0.170 55)" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
