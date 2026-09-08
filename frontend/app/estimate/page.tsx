import { SectionHeader } from "@/app/components/Panel";
import { EstimatorForm } from "./EstimatorForm";
import { fetchFacets } from "@/app/lib/api";

// Only these 10 states have entries in data/reference/costs.csv today.
// The cost model raises KeyError for anything else; the client-side
// select prevents that gracefully.
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
  // Reuse the facets endpoint so we can intersect: only offer states
  // that both have live prices AND have a cost row.
  const facets = await fetchFacets();
  const supported = COST_MODEL_STATES.filter((s) => facets.states.includes(s));

  return (
    <div className="mx-auto max-w-5xl px-6 pt-12 pb-24">
      <SectionHeader
        eyebrow="Phase 2 · cost model v1"
        title="What does a truckload actually earn?"
        description="Enter a destination quote and consignment details; the model returns an itemised ₹ breakdown covering freight (diesel-linked), APMC commission, state cess, entry fee, labour, and weighment. All rates are seeded from data/reference/costs.csv and validated by 13 pytest cases."
      />
      <EstimatorForm supportedStates={supported} />
    </div>
  );
}
