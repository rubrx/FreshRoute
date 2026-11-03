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

/* Recharts sets SVG attributes directly — CSS variables don't work here. */
const GRID  = "#E8E5E0";
const AXIS  = "#E0DDD8";
const TICK  = "#5C5C5C";
const BAR   = "#1B5E20";
const HOVER = "rgba(27, 94, 32, 0.06)";
const PANEL = "#FFFFFF";
const INK   = "#1A1A1A";
const MED   = "#F57C00";

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
              border: `1px solid ${GRID}`,
              borderRadius: 8,
              color: INK,
              fontSize: 12,
            }}
            formatter={(v) => [
              `₹${Number(v).toLocaleString("en-IN")} / quintal`,
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
