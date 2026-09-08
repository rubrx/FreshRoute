"use client";

import { useState, useTransition } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { Panel } from "@/app/components/Panel";
import { fetchCostEstimate, formatINR, type CostEstimate } from "@/app/lib/api";

type FormState = {
  quote: string;
  quantity: string;
  distance: string;
  state: string;
  diesel: string;
};

type Props = {
  supportedStates: string[];
};

const INITIAL: FormState = {
  quote: "2587",
  quantity: "5",
  distance: "250",
  state: "Uttar Pradesh",
  diesel: "95",
};

export function EstimatorForm({ supportedStates }: Props) {
  const [form, setForm] = useState<FormState>(() => ({
    ...INITIAL,
    state: supportedStates.includes(INITIAL.state)
      ? INITIAL.state
      : supportedStates[0] ?? INITIAL.state,
  }));
  const [result, setResult] = useState<CostEstimate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function handleField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    const parsed = {
      quotePriceRsPerQuintal: Number(form.quote),
      quantityTonnes: Number(form.quantity),
      distanceKm: Number(form.distance),
      destState: form.state,
      dieselPriceRsPerL: Number(form.diesel),
    };

    if (
      !Number.isFinite(parsed.quotePriceRsPerQuintal) ||
      parsed.quotePriceRsPerQuintal <= 0 ||
      !Number.isFinite(parsed.quantityTonnes) ||
      parsed.quantityTonnes <= 0 ||
      !Number.isFinite(parsed.distanceKm) ||
      parsed.distanceKm < 0 ||
      !Number.isFinite(parsed.dieselPriceRsPerL) ||
      parsed.dieselPriceRsPerL <= 0
    ) {
      setError("All numeric fields must be positive (distance may be zero).");
      return;
    }

    startTransition(async () => {
      try {
        const estimate = await fetchCostEstimate(parsed);
        setResult(estimate);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Unknown error");
        setResult(null);
      }
    });
  }

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_1.4fr]">
      <Panel className="p-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          <NumberField
            label="Quote at destination"
            hint="₹ per quintal"
            value={form.quote}
            onChange={(v) => handleField("quote", v)}
          />
          <NumberField
            label="Quantity"
            hint="Tonnes"
            value={form.quantity}
            onChange={(v) => handleField("quantity", v)}
            step="0.1"
          />
          <NumberField
            label="Distance"
            hint="Kilometres (road)"
            value={form.distance}
            onChange={(v) => handleField("distance", v)}
          />
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-[color:var(--color-fg)]">
              Destination state
            </span>
            <select
              value={form.state}
              onChange={(e) => handleField("state", e.target.value)}
              className="rounded-md border border-[color:var(--color-line)] bg-[color:var(--color-bg-elev-2)] px-3 py-2 text-sm text-[color:var(--color-fg)] focus:border-[color:var(--color-accent)] focus:outline-none"
            >
              {supportedStates.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <NumberField
            label="Diesel price"
            hint="₹/litre"
            value={form.diesel}
            onChange={(v) => handleField("diesel", v)}
            step="0.5"
          />

          {error ? (
            <div className="flex items-start gap-2 rounded-md border border-[color:var(--color-danger)]/40 bg-[color:var(--color-danger)]/10 p-3 text-sm text-[color:var(--color-danger)]">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          ) : null}

          <button
            type="submit"
            disabled={pending}
            className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-[color:var(--color-accent)] px-5 py-3 text-sm font-semibold text-[color:var(--color-accent-ink)] transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {pending ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Calculating
              </>
            ) : (
              "Estimate net"
            )}
          </button>
        </form>
      </Panel>

      <div>
        {result ? (
          <ResultView result={result} />
        ) : (
          <Panel className="flex h-full min-h-[420px] items-center justify-center p-8 text-center text-sm text-[color:var(--color-fg-muted)]">
            The breakdown will appear here.
          </Panel>
        )}
      </div>
    </div>
  );
}

function NumberField({
  label,
  hint,
  value,
  onChange,
  step = "1",
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  step?: string;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-[color:var(--color-fg)]">
          {label}
        </span>
        <span className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-dim)]">
          {hint}
        </span>
      </span>
      <input
        type="number"
        inputMode="decimal"
        min="0"
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-[color:var(--color-line)] bg-[color:var(--color-bg-elev-2)] px-3 py-2 text-sm tabular text-[color:var(--color-fg)] focus:border-[color:var(--color-accent)] focus:outline-none"
      />
    </label>
  );
}

function ResultView({ result }: { result: CostEstimate }) {
  const deductionPct = (result.total_deductions_rs / result.gross_revenue_rs) * 100;
  return (
    <Panel className="p-6">
      <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-fg-dim)]">
        Net revenue
      </div>
      <div className="mt-2 flex items-baseline gap-3">
        <span
          className="text-4xl tabular text-[color:var(--color-fg)]"
          style={{ fontFamily: "var(--font-serif)", fontWeight: 500 }}
        >
          {formatINR(result.net_revenue_rs)}
        </span>
        <span className="text-sm tabular text-[color:var(--color-fg-muted)]">
          {formatINR(result.net_rs_per_tonne)} / tonne
        </span>
      </div>
      <p className="mt-2 text-xs text-[color:var(--color-fg-muted)]">
        {result.truck_size_tonnes}-t truck to {result.dest_state} ·{" "}
        {result.distance_km.toLocaleString("en-IN")} km · diesel ₹{result.diesel_price_rs_per_l}/L
      </p>

      <div className="mt-8">
        <div className="mb-3 flex items-baseline justify-between">
          <span className="text-xs uppercase tracking-wider text-[color:var(--color-fg-dim)]">
            Gross revenue
          </span>
          <span className="tabular text-sm font-medium text-[color:var(--color-fg)]">
            {formatINR(result.gross_revenue_rs)}
          </span>
        </div>
        <div className="space-y-2">
          {result.deductions.map((d) => {
            const pctOfGross = (d.amount_rs / result.gross_revenue_rs) * 100;
            return (
              <div key={d.label}>
                <div className="mb-1 flex items-baseline justify-between text-sm">
                  <span className="text-[color:var(--color-fg-muted)]">{d.label}</span>
                  <span className="tabular text-[color:var(--color-fg)]">
                    − {formatINR(d.amount_rs)}
                  </span>
                </div>
                <div className="h-[3px] w-full overflow-hidden rounded-full bg-[color:var(--color-line-soft)]">
                  <div
                    className="h-full bg-[color:var(--color-accent)]/70"
                    style={{ width: `${Math.min(100, pctOfGross)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-6 flex items-center justify-between border-t border-[color:var(--color-line-soft)] pt-4">
          <span className="text-xs uppercase tracking-wider text-[color:var(--color-fg-dim)]">
            Total deductions
          </span>
          <span className="tabular text-sm font-medium text-[color:var(--color-danger)]">
            − {formatINR(result.total_deductions_rs)}{" "}
            <span className="text-xs text-[color:var(--color-fg-dim)]">
              ({deductionPct.toFixed(1)}%)
            </span>
          </span>
        </div>
      </div>
    </Panel>
  );
}
