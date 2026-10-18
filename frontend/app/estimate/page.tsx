import { EstimatorForm } from "./EstimatorForm";
import { fetchFacets } from "@/app/lib/api";

// Only these ten states have entries in data/reference/costs.csv today.
// Filtering the UI select prevents a KeyError from the cost model.
const COST_MODEL_STATES = [
  "Maharashtra",
  "Karnataka",
  "Uttar Pradesh",
  "Punjab",
  "Haryana",
  "Delhi",
  "Gujarat",
  "West Bengal",
  "Andhra Pradesh",
  "Tamil Nadu",
];

export default async function EstimatePage() {
  const facets = await fetchFacets();
  const supported = COST_MODEL_STATES.filter((s) => facets.states.includes(s));

  return (
    <div className="mx-auto max-w-5xl px-6 pt-20 pb-24">
      <div className="mb-10">
        <h1 className="text-4xl font-bold leading-tight tracking-[-0.02em] text-[color:var(--color-fg)]">
          What does a shipment earn?
        </h1>
        <p className="mt-3 max-w-xl text-sm text-[color:var(--color-fg-muted)]">
          Enter a destination quote and consignment details. Net revenue after
          freight, commission, cess, entry fee, labour, and weighment.
        </p>
      </div>
      <EstimatorForm supportedStates={supported} />
    </div>
  );
}
