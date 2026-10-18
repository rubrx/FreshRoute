"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// Tokens duplicated as literals — Recharts sets SVG attributes at render
// and cannot read CSS custom properties.
const GRID  = "oklch(90% 0.003 270)";
const AXIS  = "oklch(86% 0.004 270)";
const TICK  = "oklch(45% 0.006 270)";
const BAR   = "oklch(59% 0.149 163)";
const HOVER = "oklch(95% 0.003 270 / 0.6)";
const PANEL = "oklch(99% 0.002 270)";
const INK   = "oklch(18% 0.006 270)";

type Row = { market: string; district: string; modal_price: number };

type Props = {
  rows: Row[];
};

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
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: TICK, fontSize: 11 }}
            tickFormatter={(v) => `₹${v.toLocaleString("en-IN")}`}
            stroke={AXIS}
          />
          <YAxis
            dataKey="label"
            type="category"
            tick={{ fill: TICK, fontSize: 11 }}
            width={190}
            stroke={AXIS}
          />
          <Tooltip
            cursor={{ fill: HOVER }}
            contentStyle={{
              background: PANEL,
              border: `1px solid ${AXIS}`,
              borderRadius: 8,
              color: INK,
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
          <Bar dataKey="price" fill={BAR} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
