import { Panel } from "./Panel";

type Props = {
  label: string;
  value: string;
  caption?: string | null;
  accent?: boolean;
};

export function KpiCard({ label, value, caption, accent = false }: Props) {
  return (
    <Panel className="p-5">
      <div className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
        {label}
      </div>
      <div
        className={
          "mt-3 text-3xl leading-tight tabular md:text-4xl " +
          (accent
            ? "text-[color:var(--color-accent)]"
            : "text-[color:var(--color-fg)]")
        }
        style={{ fontFamily: "var(--font-serif)", fontWeight: 500 }}
      >
        {value}
      </div>
      {caption ? (
        <div className="mt-3 text-xs leading-5 text-[color:var(--color-fg-muted)]">
          {caption}
        </div>
      ) : null}
    </Panel>
  );
}
