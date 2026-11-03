export function LoadingCard() {
  return (
    <div
      className="rounded-2xl border border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] p-5 shadow-[var(--shadow-1)]"
      aria-busy="true"
      aria-label="Loading mandi recommendation"
    >
      <div className="animate-pulse space-y-3">
        <div className="flex items-center justify-between">
          <div className="h-4 w-32 rounded bg-[color:var(--color-line-soft)]" />
          <div className="h-6 w-16 rounded-full bg-[color:var(--color-line-soft)]" />
        </div>
        <div className="h-8 w-48 rounded bg-[color:var(--color-line-soft)]" />
        <div className="h-3 w-full rounded bg-[color:var(--color-line-soft)]" />
        <div className="h-3 w-3/4 rounded bg-[color:var(--color-line-soft)]" />
        <div className="flex gap-2 pt-1">
          <div className="h-10 flex-1 rounded-full bg-[color:var(--color-line-soft)]" />
          <div className="h-10 flex-1 rounded-full bg-[color:var(--color-line-soft)]" />
        </div>
      </div>
    </div>
  );
}
