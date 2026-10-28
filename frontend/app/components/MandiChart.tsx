"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// Tokens duplicated as literals — Recharts sets SVG attributes at render
// and cannot read CSS custom properties.
const GRID  = "oklch(90% 0.003 270)";
const AXIS  = "oklch(86% 0.004 270)";
const TICK  = "oklch(45% 0.006 270)";
const BAR   = "oklch(59% 0.149 163)";
const HOVER = "oklch(95% 0.003 270 / 0.6)";
const PANEL = "oklch(99% 0.002 270)";
const INK   = "oklch(18% 0.006 270)";
const MED   = "oklch(62% 0.17 30)";

type Row = { market: string; district: string; modal_price: number };

type Props = {
  rows: Row[];
  nationalMedian?: number;
};

export function MandiChart({ rows, nationalMedian }: Props) {
  const data = rows.slice(0, 30).map((r) => ({
    label: r.market,
    tooltip: `${r.market} · ${r.district}`,
    price: r.modal_price,
  }));

  const height = Math.max(380, data.length * 24 + 40);

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 96, bottom: 8, left: 32 }}
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
          {nationalMedian != null && (
            <ReferenceLine
              x={nationalMedian}
              stroke={MED}
              strokeDasharray="5 3"
              strokeWidth={2}
              label={{
                value: `₹${Math.round(nationalMedian).toLocaleString("en-IN")} nat. med`,
                position: "insideTopRight",
                fill: MED,
                fontSize: 10,
              }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
