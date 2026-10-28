"use client";

import { useEffect, useState, useTransition } from "react";
import { Loader2, MapPin, Navigation, Share2 } from "lucide-react";
import { RecommendCard } from "@/app/components/RecommendCard";
import { LoadingCard } from "@/app/components/LoadingCard";
import {
  fetchGeoDistricts,
  fetchRecommend,
  formatINR,
  type DistrictRow,
  type RecommendResponse,
} from "@/app/lib/api";

const COMMODITIES = ["Tomato", "Onion", "Potato", "Banana"] as const;
type Commodity = (typeof COMMODITIES)[number];

const VEHICLES = [
  { key: "tractor_trolley", label: "Tractor trolley",    caption: "~5 t" },
  { key: "pickup",          label: "Pickup",             caption: "~1 t" },
  { key: "truck_small",     label: "Small truck",        caption: "~5 t" },
  { key: "truck_medium",    label: "Medium truck",       caption: "~10 t" },
  { key: "reefer",          label: "Reefer",             caption: "~10 t · cold" },
] as const;

const STATES = [
  "Maharashtra", "Karnataka", "Uttar Pradesh", "Punjab",
  "Haryana", "Delhi", "Gujarat", "West Bengal",
  "Andhra Pradesh", "Tamil Nadu", "Madhya Pradesh", "Rajasthan",
] as const;

type FormState = {
  commodity: Commodity;
  lat: string;
  lon: string;
  quantity: string;
  vehicle: string;
  diesel: string;
};

const DEFAULT: FormState = {
  commodity: "Tomato",
  lat: "",
  lon: "",
  quantity: "5",
  vehicle: "truck_small",
  diesel: "95",
};

const LS_KEY = "freshroute_last_location";

type FieldError = Partial<Record<keyof FormState, string>>;

function validate(f: FormState): FieldError {
  const errs: FieldError = {};
  const lat = parseFloat(f.lat);
  const lon = parseFloat(f.lon);
  const qty = parseFloat(f.quantity);
  const diesel = parseFloat(f.diesel);

  if (!f.lat || isNaN(lat) || lat < 6 || lat > 37)
    errs.lat = "Enter a valid Indian latitude (6–37)";
  if (!f.lon || isNaN(lon) || lon < 68 || lon > 97)
    errs.lon = "Enter a valid Indian longitude (68–97)";
  if (!f.quantity || isNaN(qty) || qty <= 0)
    errs.quantity = "Enter a quantity > 0";
  if (!f.diesel || isNaN(diesel) || diesel < 50 || diesel > 200)
    errs.diesel = "Enter diesel price between ₹50–₹200/L";
  return errs;
}

export function RecommendForm() {
  const [form, setForm] = useState<FormState>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(LS_KEY);
      if (saved) {
        try {
          const { lat, lon } = JSON.parse(saved);
          return { ...DEFAULT, lat, lon };
        } catch { /* ignore */ }
      }
    }
    return DEFAULT;
  });
  const [errors, setErrors] = useState<FieldError>({});
  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [pending, startTransition] = useTransition();

  // District picker state
  const [gpsDenied, setGpsDenied] = useState(false);
  const [selectedState, setSelectedState] = useState("");
  const [districts, setDistricts] = useState<DistrictRow[]>([]);
  const [loadingDistricts, setLoadingDistricts] = useState(false);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: undefined }));
  }

  function useGps() {
    if (!navigator.geolocation) {
      setGpsDenied(true);
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude.toFixed(5);
        const lon = pos.coords.longitude.toFixed(5);
        set("lat", lat);
        set("lon", lon);
        setLocating(false);
        setGpsDenied(false);
        if (typeof window !== "undefined") {
          localStorage.setItem(LS_KEY, JSON.stringify({ lat, lon }));
        }
      },
      () => {
        setLocating(false);
        setGpsDenied(true);
      },
    );
  }

  useEffect(() => {
    if (!selectedState) { setDistricts([]); return; }
    setLoadingDistricts(true);
    fetchGeoDistricts(selectedState)
      .then((r) => setDistricts(r.districts))
      .catch(() => setDistricts([]))
      .finally(() => setLoadingDistricts(false));
  }, [selectedState]);

  function pickDistrict(district: DistrictRow) {
    set("lat", district.lat.toFixed(5));
    set("lon", district.lon.toFixed(5));
    if (typeof window !== "undefined") {
      localStorage.setItem(LS_KEY, JSON.stringify({
        lat: district.lat.toFixed(5),
        lon: district.lon.toFixed(5),
      }));
    }
  }

  function shareResult() {
    if (!result) return;
    const url = new URL(window.location.href);
    url.searchParams.set("lat", String(result.origin_lat));
    url.searchParams.set("lon", String(result.origin_lon));
    url.searchParams.set("commodity", result.commodity);
    url.searchParams.set("qty", String(result.quantity_tonnes));
    url.searchParams.set("vehicle", result.vehicle_key);
    navigator.clipboard?.writeText(url.toString()).catch(() => {});
    window.history.replaceState(null, "", url.toString());
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate(form);
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }
    setApiError(null);
    startTransition(async () => {
      try {
        const data = await fetchRecommend({
          originLat: parseFloat(form.lat),
          originLon: parseFloat(form.lon),
          commodity: form.commodity,
          quantityTonnes: parseFloat(form.quantity),
          vehicle: form.vehicle,
          dieselPriceRsPerL: parseFloat(form.diesel),
        });
        setResult(data);
      } catch (err) {
        setApiError(err instanceof Error ? err.message : "Request failed");
      }
    });
  }

  const nearest = result?.nearest_mandi;
  const top = result?.ranked[0];
  const showSavings =
    nearest && top && nearest.market_id !== top.market_id;
  const savingsPerTonne = showSavings
    ? top!.net_rs_per_tonne - nearest!.net_rs_per_tonne
    : 0;
  const savingsTotal = showSavings && result
    ? savingsPerTonne * result.quantity_tonnes
    : 0;

  return (
    <div className="space-y-8">
      {/* ── Form ─────────────────────────────────────────────────── */}
      <form onSubmit={submit} noValidate className="space-y-5">

        {/* Commodity */}
        <fieldset>
          <legend className="mb-2 text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
            Commodity
          </legend>
          <div className="flex flex-wrap gap-2">
            {COMMODITIES.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => set("commodity", c)}
                className={[
                  "rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
                  form.commodity === c
                    ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]"
                    : "border-[color:var(--color-line)] text-[color:var(--color-fg-muted)] hover:border-[color:var(--color-fg-dim)] hover:text-[color:var(--color-fg)]",
                ].join(" ")}
              >
                {c}
              </button>
            ))}
          </div>
        </fieldset>

        {/* Location */}
        <fieldset>
          <legend className="mb-2 text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
            Your location
          </legend>
          <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
            <div>
              <input
                type="number"
                step="any"
                placeholder="Latitude"
                value={form.lat}
                onChange={(e) => set("lat", e.target.value)}
                aria-label="Latitude"
                aria-invalid={!!errors.lat}
                className={inputCls(!!errors.lat)}
              />
              {errors.lat && <p className="mt-1 text-[11px] text-[color:var(--color-danger)]">{errors.lat}</p>}
            </div>
            <div>
              <input
                type="number"
                step="any"
                placeholder="Longitude"
                value={form.lon}
                onChange={(e) => set("lon", e.target.value)}
                aria-label="Longitude"
                aria-invalid={!!errors.lon}
                className={inputCls(!!errors.lon)}
              />
              {errors.lon && <p className="mt-1 text-[11px] text-[color:var(--color-danger)]">{errors.lon}</p>}
            </div>
            <button
              type="button"
              onClick={useGps}
              disabled={locating}
              aria-label="Use GPS location"
              title="Use GPS location"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[color:var(--color-line)] text-[color:var(--color-fg-muted)] transition-colors hover:bg-[color:var(--color-bg-elev-2)] disabled:opacity-50"
            >
              {locating ? (
                <Loader2 size={16} className="animate-spin" aria-hidden="true" />
              ) : (
                <Navigation size={16} aria-hidden="true" />
              )}
            </button>
          </div>

          {/* District picker fallback */}
          {gpsDenied && (
            <div className="mt-3 rounded-xl border border-[color:var(--color-line-soft)] bg-[color:var(--color-bg-elev-2)] p-3 space-y-2">
              <p className="text-xs text-[color:var(--color-fg-muted)]">
                GPS unavailable — pick your state and district instead:
              </p>
              <div className="flex flex-wrap gap-2">
                <select
                  value={selectedState}
                  onChange={(e) => setSelectedState(e.target.value)}
                  className={inputCls(false) + " flex-1 min-w-[140px]"}
                  aria-label="Select state"
                >
                  <option value="">Select state…</option>
                  {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                {loadingDistricts && (
                  <Loader2 size={16} className="animate-spin self-center text-[color:var(--color-fg-dim)]" aria-hidden="true" />
                )}
                {districts.length > 0 && (
                  <select
                    defaultValue=""
                    onChange={(e) => {
                      const d = districts.find((x) => x.district === e.target.value);
                      if (d) pickDistrict(d);
                    }}
                    className={inputCls(false) + " flex-1 min-w-[140px]"}
                    aria-label="Select district"
                  >
                    <option value="">Select district…</option>
                    {districts.map((d) => <option key={d.district} value={d.district}>{d.district}</option>)}
                  </select>
                )}
              </div>
              {form.lat && form.lon && (
                <p className="text-[11px] text-[color:var(--color-accent)]">
                  Location set: {parseFloat(form.lat).toFixed(3)}, {parseFloat(form.lon).toFixed(3)}
                </p>
              )}
            </div>
          )}
        </fieldset>

        {/* Quantity + diesel on one row */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1.5 block text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
              Quantity (tonnes)
            </label>
            <input
              type="number"
              step="0.5"
              min="0.1"
              value={form.quantity}
              onChange={(e) => set("quantity", e.target.value)}
              aria-invalid={!!errors.quantity}
              className={inputCls(!!errors.quantity)}
            />
            {errors.quantity && (
              <p className="mt-1 text-[11px] text-[color:var(--color-danger)]">{errors.quantity}</p>
            )}
          </div>
          <div>
            <label className="mb-1.5 block text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
              Diesel (₹/L)
            </label>
            <input
              type="number"
              step="0.5"
              min="50"
              max="200"
              value={form.diesel}
              onChange={(e) => set("diesel", e.target.value)}
              aria-invalid={!!errors.diesel}
              className={inputCls(!!errors.diesel)}
            />
            {errors.diesel && (
              <p className="mt-1 text-[11px] text-[color:var(--color-danger)]">{errors.diesel}</p>
            )}
          </div>
        </div>

        {/* Vehicle */}
        <div>
          <label className="mb-2 block text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
            Vehicle
          </label>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {VEHICLES.map((v) => (
              <button
                key={v.key}
                type="button"
                onClick={() => set("vehicle", v.key)}
                className={[
                  "flex items-center justify-between rounded-xl border px-4 py-3 text-left text-sm transition-colors",
                  form.vehicle === v.key
                    ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)]"
                    : "border-[color:var(--color-line)] hover:border-[color:var(--color-fg-dim)]",
                ].join(" ")}
              >
                <span
                  className={
                    form.vehicle === v.key
                      ? "font-medium text-[color:var(--color-accent)]"
                      : "text-[color:var(--color-fg)]"
                  }
                >
                  {v.label}
                </span>
                <span className="text-[11px] text-[color:var(--color-fg-dim)]">{v.caption}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={pending}
          className="flex w-full min-h-[48px] items-center justify-center gap-2 rounded-full bg-[color:var(--color-accent)] px-6 text-sm font-semibold text-[color:var(--color-accent-ink)] transition-transform hover:-translate-y-0.5 disabled:opacity-60 disabled:translate-y-0"
        >
          {pending ? (
            <><Loader2 size={16} className="animate-spin" aria-hidden="true" /> Finding mandis…</>
          ) : (
            <><MapPin size={16} aria-hidden="true" /> Find best mandi</>
          )}
        </button>
      </form>

      {/* ── API error ─────────────────────────────────────────────── */}
      {apiError && (
        <div
          role="alert"
          className="rounded-xl border border-[color:var(--color-danger-soft)] bg-[color:var(--color-danger-soft)] px-4 py-3 text-sm text-[color:var(--color-danger)]"
        >
          {apiError}
        </div>
      )}

      {/* ── Loading skeleton ──────────────────────────────────────── */}
      {pending && !result && (
        <div className="space-y-3" aria-label="Loading recommendations">
          <LoadingCard />
          <LoadingCard />
          <LoadingCard />
        </div>
      )}

      {/* ── Results ───────────────────────────────────────────────── */}
      {result && !pending && (
        <div className="space-y-6">
          {/* Meta strip + share */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[color:var(--color-fg-dim)]">
              <span>{result.commodity}</span>
              <span>·</span>
              <span>{result.quantity_tonnes} t</span>
              <span>·</span>
              <span>{result.vehicle_label}</span>
              <span>·</span>
              <span>{result.considered} mandis considered</span>
            </div>
            <button
              onClick={shareResult}
              className="flex items-center gap-1.5 rounded-full border border-[color:var(--color-line)] px-3 py-1.5 text-xs text-[color:var(--color-fg-muted)] transition-colors hover:bg-[color:var(--color-bg-elev-2)]"
            >
              <Share2 size={12} aria-hidden="true" /> Share result
            </button>
          </div>

          {/* Savings snapshot */}
          {showSavings && nearest && top && (
            <div className="rounded-2xl border border-[color:var(--color-accent-soft)] bg-[color:var(--color-accent-soft)] px-5 py-4">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-accent)] mb-1">
                Savings vs nearest mandi
              </div>
              <p className="text-sm leading-relaxed text-[color:var(--color-fg)]">
                If you had taken the nearest mandi (
                <span className="font-semibold">{nearest.market_name}</span>,{" "}
                <span className="tabular">{formatINR(nearest.net_rs_per_tonne)}/t net</span>) instead of
                our #1 pick (
                <span className="font-semibold">{top.market_name}</span>,{" "}
                <span className="tabular">{formatINR(top.net_rs_per_tonne)}/t net</span>), you would
                have lost{" "}
                <span className="font-bold tabular text-[color:var(--color-accent)]">
                  {formatINR(savingsTotal)}
                </span>{" "}
                on this consignment.
              </p>
            </div>
          )}

          {/* Ranked cards */}
          {result.ranked.length === 0 ? (
            <p className="rounded-xl border border-[color:var(--color-line-soft)] px-5 py-8 text-center text-sm text-[color:var(--color-fg-muted)]">
              No {result.commodity.toLowerCase()} prices reported near this location in the last 3 days — try expanding
              the radius or check the{" "}
              <a href="/mandis" className="underline hover:text-[color:var(--color-fg)]">
                Prices page
              </a>{" "}
              for your state.
            </p>
          ) : (
            <div className="space-y-3">
              {result.ranked.map((item, i) => (
                <RecommendCard
                  key={item.market_id}
                  item={item}
                  defaultExpanded={i === 0}
                />
              ))}
            </div>
          )}

          {/* Infeasible section */}
          {result.infeasible.length > 0 && (
            <details className="group">
              <summary className="cursor-pointer list-none text-xs text-[color:var(--color-fg-dim)] [&::-webkit-details-marker]:hidden">
                <span className="underline underline-offset-2 decoration-dashed">
                  {result.infeasible.length} mandi{result.infeasible.length !== 1 ? "s" : ""} ruled infeasible
                </span>{" "}
                — click to see why
              </summary>
              <ul className="mt-3 space-y-2">
                {result.infeasible.map((m) => (
                  <li
                    key={`${m.market_name}-${m.district}`}
                    className="flex items-start justify-between gap-3 rounded-lg px-3 py-2.5 text-xs text-[color:var(--color-fg-muted)] bg-[color:var(--color-bg-elev-2)]"
                  >
                    <span className="font-medium">
                      {m.market_name}
                      <span className="ml-1.5 font-normal text-[color:var(--color-fg-dim)]">
                        {m.district}
                      </span>
                    </span>
                    <span className="shrink-0 text-[color:var(--color-danger)]">{m.reason}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}

          {/* Caveats */}
          {result.caveats.length > 0 && (
            <div className="rounded-xl bg-[color:var(--color-bg-elev-2)] px-4 py-3 space-y-1">
              {result.caveats.map((c, i) => (
                <p key={i} className="text-[11px] leading-relaxed text-[color:var(--color-fg-dim)]">
                  {c}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function inputCls(hasError: boolean): string {
  return [
    "w-full rounded-lg border bg-[color:var(--color-bg-elev)] px-3 py-2 text-sm text-[color:var(--color-fg)]",
    "placeholder:text-[color:var(--color-fg-dim)] outline-none transition-colors",
    "focus:border-[color:var(--color-accent)]",
    hasError
      ? "border-[color:var(--color-danger)]"
      : "border-[color:var(--color-line)]",
  ].join(" ");
}
