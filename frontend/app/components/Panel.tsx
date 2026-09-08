import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  className?: string;
};

export function Panel({ children, className = "" }: Props) {
  return (
    <div
      className={
        "rounded-2xl border border-[color:var(--color-line-soft)] " +
        "bg-[color:var(--color-bg-elev)] shadow-[var(--shadow-1)] " +
        className
      }
    >
      {children}
    </div>
  );
}
