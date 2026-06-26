"use client"
import { useMemo, useState } from "react"
import * as d3 from "d3"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { CHORO_RAMP, theme } from "@/lib/theme"
import { formatCOP, formatNumber, formatPct } from "@/lib/format"
import type { GeoPunto } from "@/lib/types"
// Bundled GeoJSON (no runtime fetch). Generate once with mapshaper and export as a
// TS module — see SKILL.md "Special: ColombiaMap" for the exact command. The join
// key here is NOMBRE_DPT; change it if your GeoJSON uses a different property.
import { COLOMBIA_GEO } from "@/lib/colombia-geo"

interface Props {
  data: GeoPunto[]
  accent?: string
}

// Continental features only (drop the far-west San Andrés archipelago so the
// projection frames the mainland tightly where the activity sits).
const FEATURES: any[] = (COLOMBIA_GEO.features ?? []).filter(
  (f: any) => !String(f?.properties?.NOMBRE_DPT ?? "").toUpperCase().includes("SAN ANDRES"),
)

// Lon/lat bounds straight from the coordinates — trusted and winding-agnostic.
const BOUNDS = (() => {
  let minLon = 180, minLat = 90, maxLon = -180, maxLat = -90
  const scan = (c: any) => {
    if (typeof c[0] === "number") {
      minLon = Math.min(minLon, c[0]); maxLon = Math.max(maxLon, c[0])
      minLat = Math.min(minLat, c[1]); maxLat = Math.max(maxLat, c[1])
    } else c.forEach(scan)
  }
  FEATURES.forEach((f) => scan(f.geometry.coordinates))
  return { minLon, minLat, maxLon, maxLat }
})()

/** Choropleth of Colombia by transaction volume, with animated pulsing overlays
 *  on the top departments and click-to-pin popups.
 *
 *  Projection: a MANUAL equirectangular fit (not d3.geoMercator().fitSize/fitExtent).
 *  d3's spherical bounds are winding-sensitive and silently collapse mapshaper-
 *  simplified GeoJSON into one overlapping square (a solid fill). The linear fit
 *  below is winding-agnostic and exact for a near-equator country. The same
 *  `project(lon,lat)` powers both the department paths and any bubble cx/cy, so
 *  this pattern also drives activity-bubble maps (see SKILL.md). */
export function ColombiaMap({ data, accent = theme.primary }: Props) {
  const { ref, width } = useChartSize(460)
  const height = 460
  const [hover, setHover] = useState<{ x: number; y: number; key: string } | null>(null)
  const [pinned, setPinned] = useState<string | null>(null)

  const byKey = useMemo(() => {
    const m = new Map<string, GeoPunto>()
    for (const d of data) m.set(d.depto_key, d)
    return m
  }, [data])

  const maxMonto = useMemo(() => d3.max(data, (d) => d.monto) ?? 1, [data])
  const colorOf = useMemo(() => {
    const interp = d3.interpolateRgbBasis(CHORO_RAMP)
    const scale = d3.scaleSqrt().domain([0, maxMonto]).range([0, 1])
    return (v: number | undefined) => (v == null ? "#0d1426" : interp(scale(v)))
  }, [maxMonto])

  const { paths, bubbles } = useMemo(() => {
    if (width === 0) return { paths: [], bubbles: [] as { cx: number; cy: number; r: number; key: string; monto: number }[] }
    const pad = 14
    const { minLon, minLat, maxLon, maxLat } = BOUNDS
    const spanLon = maxLon - minLon || 1
    const spanLat = maxLat - minLat || 1
    const s = Math.min((width - 2 * pad) / spanLon, (height - 2 * pad) / spanLat)
    const ox = pad + ((width - 2 * pad) - spanLon * s) / 2
    const oy = pad + ((height - 2 * pad) - spanLat * s) / 2
    const project = (lon: number, lat: number): [number, number] => [ox + (lon - minLon) * s, oy + (maxLat - lat) * s]

    // Feed the linear projection to d3.geoPath via a geoTransform stream.
    const transform = d3.geoTransform({
      point(lon: number, lat: number) {
        const [x, y] = project(lon, lat)
        ;(this as any).stream.point(x, y)
      },
    })
    const path = d3.geoPath(transform as any)
    const rScale = d3.scaleSqrt().domain([0, maxMonto]).range([0, Math.min(width, height) * 0.085])

    const paths = FEATURES.map((f) => {
      const key = String(f.properties?.NOMBRE_DPT ?? "")
      const rec = byKey.get(key)
      return { key, d: path(f as any) ?? "", fill: colorOf(rec?.monto), monto: rec?.monto }
    })
    const bubbles = FEATURES
      .map((f) => {
        const key = String(f.properties?.NOMBRE_DPT ?? "")
        const rec = byKey.get(key)
        const c = path.centroid(f as any)
        return rec ? { cx: c[0], cy: c[1], r: rScale(rec.monto), key, monto: rec.monto } : null
      })
      .filter(Boolean)
      .sort((a, b) => (b!.monto - a!.monto))
      .slice(0, 8) as { cx: number; cy: number; r: number; key: string; monto: number }[]
    return { paths, bubbles }
  }, [width, height, byKey, colorOf, maxMonto])

  const activeKey = pinned ?? hover?.key ?? null
  const activeRec = activeKey ? byKey.get(activeKey) : null

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label="Mapa de Colombia por volumen">
          <defs>
            <filter id="map-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          {paths.map((p, i) => (
            <motion.path
              key={p.key}
              d={p.d}
              fill={p.fill}
              stroke={activeKey === p.key ? accent : "#0a0e1a"}
              strokeWidth={activeKey === p.key ? 1.6 : 0.6}
              strokeLinejoin="round"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: Math.min(i * 0.012, 0.5), duration: 0.4 }}
              style={{ cursor: p.monto != null ? "pointer" : "default" }}
              onMouseMove={(e) => {
                const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top, key: p.key })
              }}
              onMouseLeave={() => setHover(null)}
              onClick={() => setPinned((cur) => (cur === p.key ? null : p.key))}
            />
          ))}

          {/* Animated pulsing overlays on the top departments */}
          {bubbles.map((b, i) => (
            <g key={`b-${b.key}`} transform={`translate(${b.cx},${b.cy})`} style={{ pointerEvents: "none" }}>
              <circle r={b.r} fill={accent} opacity={0.18} style={{ transformOrigin: "center", animation: `ach-pulse 2.6s ${i * 0.25}s ease-out infinite` }} />
              <motion.circle
                r={Math.max(2.5, b.r * 0.38)} fill={accent} filter="url(#map-glow)"
                initial={{ scale: 0 }} animate={{ scale: 1 }}
                transition={{ delay: 0.5 + i * 0.06, type: "spring", stiffness: 220, damping: 12 }}
              />
            </g>
          ))}
        </svg>
      )}

      {/* Legend */}
      <div className="absolute left-3 bottom-3 flex items-center gap-2 text-[10px] text-[var(--muted-foreground)]">
        <span>Menor</span>
        <div className="h-2 w-28 rounded-full" style={{ background: `linear-gradient(90deg, ${CHORO_RAMP.join(",")})` }} />
        <span>Mayor volumen</span>
      </div>

      {/* Hover tooltip */}
      {hover && activeRec && !pinned && (
        <div
          className="pointer-events-none absolute z-20 panel px-3 py-2 text-xs"
          style={{ left: Math.min(hover.x + 12, width - 180), top: hover.y + 12 }}
        >
          <div className="font-semibold">{activeRec.depto}</div>
          <div className="text-[var(--muted-foreground)]">{formatCOP(activeRec.monto)} · {formatPct(activeRec.share)}</div>
        </div>
      )}

      {/* Pinned info card */}
      {pinned && activeRec && (
        <div className="absolute right-3 top-3 z-20 panel p-3 w-52 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm">{activeRec.depto}</span>
            <button className="text-[var(--muted-foreground)] hover:text-white" onClick={() => setPinned(null)}>✕</button>
          </div>
          <div className="chip mt-1">{activeRec.region}</div>
          <dl className="mt-2 space-y-1">
            <div className="flex justify-between"><dt className="text-[var(--muted-foreground)]">Volumen</dt><dd className="font-semibold" style={{ color: accent }}>{formatCOP(activeRec.monto)}</dd></div>
            <div className="flex justify-between"><dt className="text-[var(--muted-foreground)]">Transacciones</dt><dd>{formatNumber(activeRec.num_tx)}</dd></div>
            <div className="flex justify-between"><dt className="text-[var(--muted-foreground)]">Clientes</dt><dd>{formatNumber(activeRec.clientes)}</dd></div>
            <div className="flex justify-between"><dt className="text-[var(--muted-foreground)]">Participación</dt><dd>{formatPct(activeRec.share)}</dd></div>
          </dl>
        </div>
      )}
    </div>
  )
}
