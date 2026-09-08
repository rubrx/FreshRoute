import { formatINR } from "@/app/lib/api";

type Props = {
  low: number;
  high: number;
  lowLabel: string;
  highLabel: string;
  /** Absolute cap so a 1000% outlier does not visually flatten normal spreads. */
  maxDisplayHigh?: number;
};

/**
 * Horizontal bar showing where lo and hi sit inside the max window.
 * lo and hi are the actual prices; the bar visualises their absolute
 * relationship rather than the percentage spread (percentages become
 * meaningless once the low value approaches zero).
 */
export function SpreadBar({ low, high, lowLabel, highLabel, maxDisplayHigh }: Props) {
  const ceiling = maxDisplayHigh ?? high * 1.1;
  const lowPct = Math.min(100, (low / ceiling) * 100);
  const highPct = Math.min(100, (high / ceiling) * 100);
  const bandWidth = Math.max(0.5, highPct - lowPct);

  return (
    <div className="w-full">
      <div className="relative h-2 w-full rounded-full bg-[color:var(--color-line-soft)]">
        <div
          className="absolute top-0 h-2 rounded-full bg-[color:var(--color-accent)]/25"
          style={{ left: `${lowPct}%`, width: `${bandWidth}%` }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 h-3 w-[2px] bg-[color:var(--color-fg-muted)]"
          style={{ left: `${lowPct}%` }}
          aria-hidden
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 h-3 w-[2px] bg-[color:var(--color-accent)]"
          style={{ left: `${highPct}%` }}
          aria-hidden
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-[11px] text-[color:var(--color-fg-dim)]">
        <span>
          <span className="tabular text-[color:var(--color-fg-muted)]">
            {formatINR(low)}
          </span>{" "}
          · {lowLabel}
        </span>
        <span className="text-right">
          <span className="tabular text-[color:var(--color-accent)]">
            {formatINR(high)}
          </span>{" "}
          · {highLabel}
        </span>
      </div>
    </div>
  );
}
