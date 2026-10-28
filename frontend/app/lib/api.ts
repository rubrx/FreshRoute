/**
 * Typed fetchers for the FreshRoute FastAPI backend.
 *
 * All requests use the App Router server-side fetch cache with
 * `revalidate: 60` so a demo click doesn't hammer the API, but data
 * refreshes minute-by-minute during the panel walkthrough.
 */

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type SummaryCard = {
  label: string;
  value: string;
  caption: string | null;
};

export type SummaryResponse = {
  snapshot_date: string | null;
  cards: SummaryCard[];
};

export type ArbitrageRow = {
  commodity: string;
  state: string;
  snapshot_date: string;
  mandis_reporting: number;
  min_price_rs_per_quintal: number;
  max_price_rs_per_quintal: number;
  spread_rs_per_quintal: number;
  spread_pct: number;
  high_market: string;
  low_market: string;
};

export type ArbitrageResponse = {
  snapshot_date: string | null;
  count: number;
  rows: ArbitrageRow[];
};

export type MandiPrice = {
  market_id: number;
  state: string;
  district: string;
  market: string;
  commodity: string;
  variety: string | null;
  modal_price_rs_per_quintal: number;
  min_price_rs_per_quintal: number | null;
  max_price_rs_per_quintal: number | null;
  date: string;
};

export type MandiPriceList = {
  commodity: string;
  state: string | null;
  snapshot_date: string | null;
  count: number;
  rows: MandiPrice[];
};

export type Facets = {
  commodities: string[];
  states: string[];
};

export type CostLineItem = { label: string; amount_rs: number };

export type CostEstimate = {
  quote_price_rs_per_quintal: number;
  quantity_tonnes: number;
  distance_km: number;
  dest_state: string;
  diesel_price_rs_per_l: number;
  truck_size_tonnes: number;
  gross_revenue_rs: number;
  deductions: CostLineItem[];
  total_deductions_rs: number;
  net_revenue_rs: number;
  net_rs_per_tonne: number;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    next: { revalidate: 60 },
    headers: { accept: "application/json" },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${path} → ${res.status}${body ? `: ${body}` : ""}`);
  }
  return (await res.json()) as T;
}

export function fetchSummary(): Promise<SummaryResponse> {
  return get<SummaryResponse>("/summary");
}

export function fetchArbitrage(params: {
  commodity?: string;
  limit?: number;
  minReporters?: number;
}): Promise<ArbitrageResponse> {
  const qs = new URLSearchParams();
  if (params.commodity) qs.set("commodity", params.commodity);
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.minReporters) qs.set("min_reporters", String(params.minReporters));
  const q = qs.toString();
  return get<ArbitrageResponse>(`/markets/arbitrage${q ? `?${q}` : ""}`);
}

export function fetchFacets(): Promise<Facets> {
  return get<Facets>("/markets/facets");
}

export function fetchPrices(params: {
  commodity: string;
  state?: string;
  limit?: number;
}): Promise<MandiPriceList> {
  const qs = new URLSearchParams({ commodity: params.commodity });
  if (params.state) qs.set("state", params.state);
  if (params.limit) qs.set("limit", String(params.limit));
  return get<MandiPriceList>(`/markets/prices?${qs}`);
}

export function fetchCostEstimate(params: {
  quotePriceRsPerQuintal: number;
  quantityTonnes: number;
  distanceKm: number;
  destState: string;
  dieselPriceRsPerL: number;
}): Promise<CostEstimate> {
  const qs = new URLSearchParams({
    quote_price_rs_per_quintal: String(params.quotePriceRsPerQuintal),
    quantity_tonnes: String(params.quantityTonnes),
    distance_km: String(params.distanceKm),
    dest_state: params.destState,
    diesel_price_rs_per_l: String(params.dieselPriceRsPerL),
  });
  return get<CostEstimate>(`/cost/estimate?${qs}`);
}

// ── Phase 5: Recommendation types ────────────────────────────────────────────

export type RecommendSpoilage = {
  ambient_c: number;
  effective_c: number;
  sl_opt_days: number;
  sl_at_effective_days: number;
  spoilage_fraction: number;
  feasible: boolean;
  reason: string;
};

export type RecommendCostBreakdown = {
  fuel_litres: number;
  fuel_rs: number;
  other_freight_rs: number;
  apmc_commission_rs: number;
  cess_rs: number;
  entry_fee_rs: number;
  labour_rs: number;
  weighment_rs: number;
  total_deductions_rs: number;
};

export type RecommendItem = {
  rank: number;
  market_id: number;
  market_name: string;
  district: string;
  state: string;
  distance_km: number;
  distance_source: string;
  transit_hours: number;
  trips: number;
  modal_price_rs_per_quintal: number;
  gross_revenue_rs: number;
  expected_saleable_revenue_rs: number;
  net_revenue_rs: number;
  net_rs_per_tonne: number;
  price_status: string;
  price_snapshot_date: string;
  why: string;
  costs: RecommendCostBreakdown;
  spoilage: RecommendSpoilage;
  price_pct_rank_in_state: number;
  vs_state_median_rs_per_qtl: number;
  vs_national_median_rs_per_qtl: number;
};

export type RecommendInfeasible = {
  market_name: string;
  district: string;
  state: string;
  distance_km: number;
  reason: string;
};

export type RecommendResponse = {
  origin_lat: number;
  origin_lon: number;
  radius_km: number;
  commodity: string;
  quantity_tonnes: number;
  vehicle_key: string;
  vehicle_label: string;
  diesel_price_rs_per_l: number;
  ambient_c: number;
  snapshot_date: string | null;
  considered: number;
  caveats: string[];
  infeasible: RecommendInfeasible[];
  ranked: RecommendItem[];
  nearest_mandi: RecommendItem | null;
};

export type CommodityOverviewItem = {
  commodity: string;
  national_median: number;
  national_max: number;
  mandis_count: number;
  best_state: string;
  best_state_median: number;
};

export type CommodityOverviewResponse = {
  snapshot_date: string | null;
  commodities: CommodityOverviewItem[];
};

export type DistrictRow = {
  district: string;
  lat: number;
  lon: number;
};

export type DistrictsResponse = {
  state: string;
  count: number;
  districts: DistrictRow[];
};

export type SeasonalWeek = {
  iso_week: number;
  arrival_index: number;
  label: "glut" | "lean" | "normal";
};

export type SeasonalResponse = {
  available: boolean;
  reason: string | null;
  commodity: string | null;
  state: string | null;
  current_week: number | null;
  weeks: SeasonalWeek[];
};

export function fetchRecommend(params: {
  originLat: number;
  originLon: number;
  commodity: string;
  quantityTonnes: number;
  vehicle: string;
  dieselPriceRsPerL: number;
  radiusKm?: number;
}): Promise<RecommendResponse> {
  const qs = new URLSearchParams({
    origin_lat: String(params.originLat),
    origin_lon: String(params.originLon),
    commodity: params.commodity,
    quantity_tonnes: String(params.quantityTonnes),
    vehicle: params.vehicle,
    diesel_price_rs_per_l: String(params.dieselPriceRsPerL),
  });
  if (params.radiusKm) qs.set("radius_km", String(params.radiusKm));
  return get<RecommendResponse>(`/recommend?${qs}`);
}

export function fetchCommodityOverview(): Promise<CommodityOverviewResponse> {
  return get<CommodityOverviewResponse>("/intel/commodity-overview");
}

export function fetchGeoDistricts(state: string): Promise<DistrictsResponse> {
  return get<DistrictsResponse>(
    `/geo/districts?${new URLSearchParams({ state })}`
  );
}

export function fetchSeasonal(
  commodity: string,
  state: string
): Promise<SeasonalResponse> {
  return get<SeasonalResponse>(
    `/intel/seasonal?${new URLSearchParams({ commodity, state })}`
  );
}

export const formatINR = (rs: number): string =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(rs);

export const formatNumber = (n: number, digits = 0): string =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(n);
