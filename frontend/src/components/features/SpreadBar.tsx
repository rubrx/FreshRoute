import { formatINR } from "@/lib/api";

type Props = {
  low: number;
  high: number;
  lowLabel: string;
  highLabel: string;
  maxDisplayHigh?: number;
  /** Animate the fill on mount (CSS clip-path reveal). */
  animate?: boolean;
};

export function SpreadBar({ low, high, lowLabel, highLabel, maxDisplayHigh, animate = false }: Props) {
  const ceiling = maxDisplayHigh ?? high * 1.1;
  const lowPct = Math.min(100, (low / ceiling) * 100);
  const highPct = Math.min(100, (high / ceiling) * 100);
  const bandWidth = Math.max(0.5, highPct - lowPct);

  return (
    <div className="w-full">
      <div className="relative h-2.5 w-full rounded-full bg-[color:var(--color-line-soft)]">
        <div
          className={[
            "absolute top-0 h-2.5 rounded-full bg-[color:var(--color-accent)]/30",
            animate ? "spread-band-animate" : "",
          ].join(" ")}
          style={{ left: `${lowPct}%`, width: `${bandWidth}%` }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 h-3.5 w-0.5 bg-[color:var(--color-fg-muted)] rounded-full"
          style={{ left: `${lowPct}%` }}
          aria-hidden
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 h-3.5 w-0.5 bg-[color:var(--color-accent)] rounded-full"
          style={{ left: `${highPct}%` }}
          aria-hidden
        />
      </div>
      <div className="mt-2.5 flex items-center justify-between text-[11px] text-[color:var(--color-fg-dim)]">
        <span>
          <span className="tabular font-medium text-[color:var(--color-fg-muted)]">
            {formatINR(low)}
          </span>{" "}
          · {lowLabel}
        </span>
        <span className="text-right">
          <span className="tabular font-medium text-[color:var(--color-accent)]">
            {formatINR(high)}
          </span>{" "}
          · {highLabel}
        </span>
      </div>
    </div>
  );
}
