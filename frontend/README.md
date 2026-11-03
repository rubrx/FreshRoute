# FreshRoute frontend

Next.js App Router, TypeScript, Tailwind CSS.

## Dev

```bash
pnpm install
pnpm dev        # http://localhost:3000
```

Backend must be running at `http://127.0.0.1:8000` (or set `NEXT_PUBLIC_API_URL` in your env).

## Pages

| Route | What |
|---|---|
| `/` | Home — KPIs + recent spreads |
| `/recommend` | Core screen — find best mandi |
| `/mandis` | Price browser by commodity + state |
| `/estimate` | Manual cost estimator |
| `/arbitrage` | Spread explorer |

## Structure

```
src/
├── app/            Next.js pages (RSC by default, "use client" where needed)
├── components/
│   ├── features/   RecommendCard, MandiChart, CostWaterfall, SpreadBar …
│   ├── layout/     Navbar, Footer
│   └── ui/         Panel, KpiCard, LoadingCard
├── lib/api.ts      Typed fetch wrappers + formatters (formatINR etc.)
└── styles/         Design tokens (CSS custom properties)
```
