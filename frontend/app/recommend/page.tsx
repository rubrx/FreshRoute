import type { Metadata } from "next";
import { RecommendForm } from "./RecommendForm";

export const metadata: Metadata = {
  title: "Best Mandi — FreshRoute",
  description:
    "Find the highest net ₹/tonne mandi after freight, spoilage, and commission.",
};

export default function RecommendPage() {
  return (
    <div className="mx-auto max-w-2xl px-5 pt-10 pb-28">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-[color:var(--color-fg)]">
          Find your best mandi
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-[color:var(--color-fg-muted)]">
          Ranked by net ₹/tonne after freight, spoilage, and mandi charges.
          Only mandis your produce can reach while still sellable.
        </p>
      </div>
      <RecommendForm />
    </div>
  );
}
