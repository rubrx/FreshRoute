type Props = {
  fraction: number;
  className?: string;
};

function severity(f: number): "low" | "mid" | "high" {
  if (f < 0.05) return "low";
  if (f <= 0.20) return "mid";
  return "high";
}

const STYLES = {
  low:  "bg-[color:var(--color-success-soft)] text-[color:var(--color-success)]",
  mid:  "bg-[color:var(--color-warning-soft)] text-[color:var(--color-warning)]",
  high: "bg-[color:var(--color-danger-soft)]  text-[color:var(--color-danger)]",
} as const;

export function SpoilageChip({ fraction, className = "" }: Props) {
  const level = severity(fraction);
  const pct = Math.round(fraction * 100);

  return (
    <span
      className={[
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium",
        STYLES[level],
        className,
      ].join(" ")}
      aria-label={`${pct}% expected spoilage`}
    >
      {pct}% loss
    </span>
  );
}
