import { Panel } from "./Panel";

type Props = {
  label: string;
  value: string;
  caption?: string | null;
};

export function KpiCard({ label, value, caption }: Props) {
  return (
    <Panel className="p-5">
      <div className="text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
        {label}
      </div>
      <div className="mt-3 text-2xl font-bold leading-tight tabular text-[color:var(--color-fg)] md:text-3xl">
        {value}
      </div>
      {caption ? (
        <div className="mt-2 text-xs leading-5 text-[color:var(--color-fg-muted)] line-clamp-2">
          {caption}
        </div>
      ) : null}
    </Panel>
  );
}
