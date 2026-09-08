import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  className?: string;
};

export function Panel({ children, className = "" }: Props) {
  return (
    <div
      className={
        "rounded-[18px] border border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev)] " +
        "shadow-[var(--shadow-1)] " +
        className
      }
    >
      {children}
    </div>
  );
}

type SectionHeaderProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  right?: ReactNode;
};

export function SectionHeader({ eyebrow, title, description, right }: SectionHeaderProps) {
  return (
    <div className="flex items-end justify-between gap-6 mb-6">
      <div className="max-w-2xl">
        {eyebrow ? (
          <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-accent)]">
            {eyebrow}
          </div>
        ) : null}
        <h2
          className="text-2xl font-medium tracking-tight text-[color:var(--color-fg)] md:text-3xl"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          {title}
        </h2>
        {description ? (
          <p className="mt-2 text-sm leading-6 text-[color:var(--color-fg-muted)]">
            {description}
          </p>
        ) : null}
      </div>
      {right}
    </div>
  );
}
