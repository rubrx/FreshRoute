type Props = {
  spoilageFraction: number;
  slOptDays: number;
  slAtEffectiveDays: number;
};

export function FreshnessBar({ spoilageFraction, slOptDays, slAtEffectiveDays }: Props) {
  const survivingFraction = Math.max(0, 1 - spoilageFraction);
  const filledDots = Math.round(survivingFraction * 10);

  return (
    <div>
      <div className="flex items-center gap-1" aria-label={`${Math.round(survivingFraction * 100)}% of produce survives transit`}>
        {Array.from({ length: 10 }, (_, i) => (
          <span
            key={i}
            className={[
              "h-2 w-2 rounded-full transition-colors",
              i < filledDots
                ? "bg-[color:var(--color-success)]"
                : "bg-[color:var(--color-line)]",
            ].join(" ")}
            aria-hidden="true"
          />
        ))}
        <span className="ml-1.5 text-xs tabular text-[color:var(--color-fg-muted)]">
          {Math.round(survivingFraction * 100)}% survives
        </span>
      </div>
      <p className="mt-1 text-[11px] text-[color:var(--color-fg-dim)]">
        Shelf life: {slOptDays}d at optimal →{" "}
        <span className="text-[color:var(--color-fg-muted)]">
          {slAtEffectiveDays.toFixed(1)}d at transit temp
        </span>
      </p>
    </div>
  );
}
