---
name: snowflake-dashboard-viz
description: "Reusable D3 + React chart library and dark fintech design system for Snowflake dashboards and apps. Use whenever building a dashboard, data app, or any data visualization — charts, KPIs, maps, trends, comparisons — especially in Next.js/React or Streamlit-in-Snowflake demos. Triggers: dashboard, data app, visualization, chart, graph, D3, choropleth, map, KPI, donut, treemap, heatmap, radar, gauge, scatter, benchmarking UI, 'make it look like D3 / better than Tableau', visualize my data, demo dashboard."
---

# Snowflake Dashboard Visualization Kit

A battle-tested kit of **15 custom D3 + React chart components** and a **premium dark fintech design system**, extracted from the ACH Benchmarking demo. Use it to assemble polished, animated, on-brand dashboards fast — no recharts, no chart-library lock-in.

**Design philosophy: D3 computes, React renders.** D3 does only the math (scales, `path`/`arc`/`line` generators, geo projection, color interpolation); JSX renders the SVG; `framer-motion` animates. No `d3.select`/imperative DOM. This keeps charts declarative, themable, and fast — and gives the "looks like D3, better than Tableau" feel.

## When to use

Building or restyling any dashboard / data app / visualization in React/Next.js (works as-is) or as a visual reference for Streamlit-in-Snowflake (port the palette + chart math). Start here instead of reaching for recharts/plotly.

## Stack

- **React 18/19 + TypeScript**, `d3` (^7.9), `framer-motion`, `lucide-react`, Tailwind v4.
- Optional (agent/markdown panels): `react-markdown`, `remark-gfm`.
- Install: `npm i d3 framer-motion lucide-react && npm i -D @types/d3`.

## Reuse workflow

1. **Copy the foundation** into the target app:
   - `assets/lib/theme.ts` → `lib/theme.ts` (color tokens, palettes, per-series accents)
   - `assets/lib/format.ts` → `lib/format.ts` (es-CO COP/number/percent/date formatters — adapt locale if needed)
   - `assets/lib/types.ts` → `lib/types.ts` (chart data contracts; trim to what you use)
   - `assets/styles/globals.css` → merge into `app/globals.css` (the `:root` tokens, `.panel`, `.chip`, `.text-gradient`, `@keyframes ach-*`, scrollbar + `.tick/.domain` SVG helpers)
2. **Copy the charts you need** from `assets/charts/` → `components/charts/`. Always include the two helpers: `useChartSize.ts` and `ChartFrame.tsx`.
3. **Wire data**: each chart takes a typed `data` prop (see Catalog) plus an optional `accent` color. Feed it server data shaped to the contract in `lib/types.ts`.
4. **Adapt branding**: change `theme.primary` + `MERCHANT_COLORS`/`CATEGORICAL` and the two ambient radial-gradients in `globals.css` `body`. Everything else recolors automatically.

> The bundled files import via the `@/` alias (`@/lib/theme`, `@/lib/format`, `@/lib/types`). Keep that tsconfig path or rewrite imports to relative.

## Design system (assets/styles/globals.css + assets/lib/theme.ts)

- **Palette**: near-black navy canvas (`--background #0A0E1A`), panel `#121A2E`, border `#23304D`, text `#EAF0FF`, muted `#8FA0C2`. Accents: ACH blue `#2E6BFF`, cyan `#22D3EE`, green `#16C784`, amber `#F5A623`, red `#FF5670`, violet `#A78BFA`.
- **`.panel`**: gradient card + 1px border + inset highlight + deep soft shadow + `backdrop-blur`. `.panel-hover` lifts 2px and tints the border on hover. This is the wrapper for every tile/chart.
- **`.chip`**: pill for tags/filters/tool labels. **`.text-gradient`**: headline gradient.
- **Ambient depth**: two fixed radial-gradients on `body` (blue top-right, cyan top-left) give the "fintech glass" backdrop.
- **Animations**: `@keyframes ach-pulse` (map beacons), `ach-shimmer` (`.skeleton` loaders), `ach-dash` (line draw-in).
- **SVG axis helpers**: `.tick text`, `.tick line`, `.domain` are pre-styled so D3 axes match the theme.
- **Per-series accent**: `merchantColor(id)` / `catColor(i)` keep a stable color per entity across every chart. `CANAL_COLORS` fixes payment-channel colors; `CHORO_RAMP` is the map's sequential ramp.

## Chart catalog (assets/charts/)

All are `"use client"`, responsive via `useChartSize()`, animate in with framer-motion, and render their own hover tooltip / legend. `accent` defaults to `theme.primary`.

| Component | Use it for | `data` contract (see types.ts) | Key D3 |
|---|---|---|---|
| `KpiCounter.tsx` | Animated count-up KPI value | `value:number`, `format` fn | (framer spring, no d3) |
| `AreaTrend.tsx` | Single-series volume/amount over time | `TendenciaPunto[]` `{mes, valor}` | `scaleLinear`, `area`, `line`, `curveMonotoneX` |
| `MerchantVsSectorLine.tsx` | Two-line "you vs sector" comparison | `{mes, comercio, sector}[]` | `scalePoint`, `line`, `ach-dash` draw-in |
| `Donut.tsx` | Part-to-whole share (payment channels) | `CanalPunto[]` `{canal, monto, share, num_tx}` | `pie`, `arc` (cornerRadius, hover expand) |
| `ChannelStackBar.tsx` | 100% stacked composition bar | `CanalPunto[]` | manual stack on `scaleLinear` |
| `Treemap.tsx` | Nested magnitude (device families) | `{name, value}[]` | `d3.treemap`, `hierarchy` |
| `CalendarHeatmap.tsx` | Daily intensity / seasonality grid | `{fecha, valor}[]` | `timeParse/timeWeek/timeDay`, `scaleQuantize` |
| `DayHourHeatmap.tsx` | Day-of-week × hour-of-day volume matrix (when do peaks happen) | `HoraPunto[]` `{dia_semana, dia, hora, num_tx, monto}` | `interpolateRgbBasis`, `scaleSqrt`, 7×24 cell grid |
| `BubbleScatter.tsx` | 2-metric + size scatter | `{x, y, r, label}[]` | `scaleLinear`, `scaleSqrt` |
| `RadarBenchmark.tsx` | Multi-axis profile vs sector | `{eje, comercio, sector}[]` | polar math + `lineRadial`-style path |
| `PercentileGauge.tsx` | Single percentile/score arc | `value:number (0-100)` | `arc`, `scaleLinear` to angle |
| `FamilyCompareBars.tsx` | Grouped/diverging category bars | `{familia, propio, sector}[]` | `scaleBand`, `scaleLinear` |
| `ColombiaMap.tsx` | Choropleth + pulsing beacons + click-popups | `GeoPunto[]` `{depto_key, depto, region, monto, num_tx, clientes, share}` | `geoMercator`, `geoPath`, `scaleSqrt`, `interpolateRgbBasis` |
| `AgentChart.tsx` | Render a Cortex Agent `data_to_chart` spec (bar/line/donut), auto-detects label vs value field | `{mark, values[], x?, y?}` | `scaleBand/Linear`, `pie/arc`, `line` |
| `ChartFrame.tsx` | Panel wrapper (title + subtitle + right slot + body) | — | — |

### Two reusable helpers (always copy these)

- **`useChartSize(initialHeight)`** — `ResizeObserver` hook → `{ ref, width, height }`. Attach `ref` to the chart's container `div`; render the `<svg>` only when `width > 0`. This is how every chart is responsive without a chart lib.
- **`ChartFrame`** — wraps any chart in a `.panel` with a title/subtitle and optional right-side control slot. Use for consistent tile chrome.

## Core pattern (how every chart is built)

```tsx
"use client"
import { useMemo, useState } from "react"
import * as d3 from "d3"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme } from "@/lib/theme"

export function MyChart({ data, accent = theme.primary }: Props) {
  const height = 300
  const { ref, width } = useChartSize(height)         // 1. responsive size
  const [hover, setHover] = useState<...>(null)

  const scene = useMemo(() => {                        // 2. D3 = MATH ONLY (no DOM)
    if (!data.length || width === 0) return null
    const x = d3.scaleBand().domain(...).range([0, iw]).padding(0.25)
    const y = d3.scaleLinear().domain([0, d3.max(data, d => d.v)!]).nice().range([ih, 0])
    return { x, y }
  }, [data, width])

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && scene && (
        <svg width={width} height={height}>          {/* 3. React renders SVG */}
          {data.map((d, i) => (
            <motion.rect key={i} x={scene.x(d.label)} width={scene.x.bandwidth()}
              fill={accent} rx={4}
              initial={{ y: ih, height: 0 }}            {/* 4. framer animates */}
              animate={{ y: scene.y(d.v), height: ih - scene.y(d.v) }}
              transition={{ delay: i * 0.03, duration: 0.5 }}
              onMouseMove={(e) => setHover(...)} onMouseLeave={() => setHover(null)} />
          ))}
        </svg>
      )}
      {hover && <div className="pointer-events-none absolute z-20 panel px-2.5 py-1.5 text-xs" style={{ left, top }}>…</div>}
    </div>
  )
}
```

### Conventions that keep it cohesive
- **Tooltip** = an absolutely-positioned `.panel` div (HTML, not SVG); compute `left/top` from the SVG's `getBoundingClientRect()` and clamp to width.
- **Margins** `{top,right,bottom,left}` → `iw = width - left - right`, `ih = height - top - bottom`; render axes/marks inside a `<g transform="translate(left,top)">`.
- **Empty state**: return a centered "Sin datos" `<div>` when `!data.length`.
- **Animation in**: bars grow from baseline, arcs spring in with `delay: i * 0.08`, lines draw via `pathLength 0→1` or the `ach-dash` keyframe, map beacons use `ach-pulse`.
- **Stagger** with `delay: i * 0.03–0.08` for the premium cascade.

## Special: ColombiaMap (choropleth + beacons + popups)

A reusable geo pattern: `fetch('/colombia-departamentos.geo.json')` (place GeoJSON in `public/`, keyed by `NOMBRE_DPT`), `d3.geoMercator().fitSize([w,h], geo)`, fill each department via a `scaleSqrt` → `interpolateRgbBasis(CHORO_RAMP)`. Top-N departments get animated `ach-pulse` beacons at `path.centroid`. **Hover** shows a tooltip; **click** pins a detail card (`pinned` state). To retarget another country, swap the GeoJSON + the property key used for the join.

## Special: AgentChart (Cortex Agent → chart)

Renders a Cortex Agent `data_to_chart` `chart_spec`. Robustness trick: it **ignores the spec's x/y orientation** and instead picks the **string field as the category label and the numeric field as the value**, so horizontal/vertical bar specs both render correctly. Supports `bar`, `line`, `arc/pie`. Pair it with a markdown answer panel (`react-markdown` + `remark-gfm`) for an agentic insights tab.

## Output

A set of copied, themed chart components + design tokens wired to the target app's data — a cohesive, animated dark dashboard. Verify by running the app and checking each tile renders with data, tooltips, and the panel styling.

## Notes / gotchas
- **Render only when `width > 0`** (first paint has width 0 before `ResizeObserver` fires) or paths compute as empty.
- **`useMemo` the D3 scene** on `[data, width]` so scales/paths don't recompute every render.
- **Locale**: `format.ts` is es-CO (`.` thousands, `,` decimals, COP). Swap `Intl.NumberFormat` locale/currency for other markets.
- **No recharts/plotly** — adding one defeats the purpose and bloats the bundle; extend the D3 pattern instead.
- For Streamlit-in-Snowflake, reuse `theme.ts` colors + the chart math, rendering via `st`-friendly components (the React `.tsx` files are for React/Next apps).
