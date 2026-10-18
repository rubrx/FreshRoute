"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, MapPin } from "lucide-react";

import type { RecommendItem } from "@/app/lib/api";
import { formatINR, formatNumber } from "@/app/lib/api";
import { CostWaterfall } from "./CostWaterfall";
import { FreshnessBar } from "./FreshnessBar";
import { SpoilageChip } from "./SpoilageChip";

type Props = {
  item: RecommendItem;
  defaultExpanded?: boolean;
};

function borderColor(fraction: number): string {
  if (fraction < 0.05) return "border-l-[color:var(--color-success)]";
  if (fraction <= 0.20) return "border-l-[color:var(--color-warning)]";
  return "border-l-[color:var(--color-danger)]";
}

export function RecommendCard({ item, defaultExpanded = false }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const spoilageLoss =
    item.gross_revenue_rs - item.expected_saleable_revenue_rs;

  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
    `${item.market_name} APMC mandi ${item.district} ${item.state} India`
  )}`;

  return (
    <article
      className={[
        "rounded-2xl border border-[color:var(--color-line-soft)] border-l-4",
        borderColor(item.spoilage.spoilage_fraction),
        "bg-[color:var(--color-bg-elev)] shadow-[var(--shadow-1)]",
      ].join(" ")}
    >
      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[color:var(--color-fg)] text-[11px] font-semibold text-[color:var(--color-bg)]">
                {item.rank}
              </span>
              <span
                className="truncate text-base font-medium text-[color:var(--color-fg)]"
                style={{ fontFamily: "var(--font-serif)" }}
              >
                {item.market_name}
              </span>
            </div>
            <p className="mt-0.5 pl-8 text-xs text-[color:var(--color-fg-muted)]">
              {item.district} · {item.state}
            </p>
          </div>
          <SpoilageChip
            fraction={item.spoilage.spoilage_fraction}
            className="shrink-0"
          />
        </div>

        {/* Decision number */}
        <div className="mt-4">
          <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-fg-dim)]">
            Net realization
          </div>
          <div
            className="mt-1 text-3xl tabular text-[color:var(--color-fg)] md:text-4xl"
            style={{ fontFamily: "var(--font-serif)", fontWeight: 500 }}
          >
            {formatINR(item.net_rs_per_tonne)}
            <span className="ml-1.5 text-base font-normal text-[color:var(--color-fg-muted)]">
              /tonne
            </span>
          </div>
        </div>

        {/* Metadata strip */}
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[color:var(--color-fg-muted)]">
          <span>{formatNumber(item.distance_km, 0)} km</span>
          <span>·</span>
          <span>{item.transit_hours.toFixed(1)} h transit</span>
          {item.trips > 1 && (
            <>
              <span>·</span>
              <span>{item.trips} trips</span>
            </>
          )}
          {item.distance_source === "state" && (
            <>
              <span>·</span>
              <span className="text-[color:var(--color-warning)]">approx. distance</span>
            </>
          )}
        </div>

        {/* Why text */}
        <p className="mt-2 text-sm leading-relaxed text-[color:var(--color-fg-muted)]">
          {item.why}
        </p>

        {/* Collapsible detail */}
        {expanded && (
          <div className="mt-5 space-y-4 border-t border-[color:var(--color-line-soft)] pt-4">
            <div>
              <div className="mb-2 text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
                Freshness
              </div>
              <FreshnessBar
                spoilageFraction={item.spoilage.spoilage_fraction}
                slOptDays={item.spoilage.sl_opt_days}
                slAtEffectiveDays={item.spoilage.sl_at_effective_days}
              />
              <p className="mt-1.5 text-[11px] text-[color:var(--color-fg-dim)]">
                {item.spoilage.reason}
              </p>
            </div>

            <div>
              <div className="mb-2 text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-fg-dim)]">
                Cost breakdown
              </div>
              <CostWaterfall
                costs={item.costs}
                grossRevenue={item.gross_revenue_rs}
                spoilageLoss={spoilageLoss}
                netRevenue={item.net_revenue_rs}
              />
            </div>

            <div className="rounded-lg bg-[color:var(--color-bg-elev-2)] px-3 py-2.5">
              <p className="text-[11px] leading-relaxed text-[color:var(--color-fg-dim)]">
                <span className="font-medium text-[color:var(--color-fg-muted)]">
                  Data note:
                </span>{" "}
                Price from data.gov.in snapshot · {item.price_snapshot_date} ·
                Freight and mandi charges are seed values, not live quotes.
              </p>
            </div>
          </div>
        )}

        {/* Footer actions */}
        <div className="mt-4 flex items-center gap-2">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-full border border-[color:var(--color-line)] px-4 text-sm font-medium text-[color:var(--color-fg)] transition-colors hover:bg-[color:var(--color-bg-elev-2)]"
            aria-expanded={expanded}
          >
            {expanded ? (
              <>
                <ChevronUp size={15} aria-hidden="true" /> Less
              </>
            ) : (
              <>
                <ChevronDown size={15} aria-hidden="true" /> Details
              </>
            )}
          </button>
          <a
            href={mapsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-full bg-[color:var(--color-accent)] px-4 text-sm font-semibold text-[color:var(--color-accent-ink)] transition-transform hover:-translate-y-0.5"
          >
            <MapPin size={15} aria-hidden="true" /> Directions
          </a>
        </div>
      </div>
    </article>
  );
}
