"use client"
import { useMemo, useState } from "react"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme } from "@/lib/theme"
import { formatCOP, formatPct, formatNumber } from "@/lib/format"
import type { BenchmarkPunto } from "@/lib/types"

interface Props {
  data: BenchmarkPunto[]
  accent?: string
}

function formatVal(etiqueta: string, valor: number): string {
  const low = etiqueta.toLowerCase()
  if (low.includes("cop") || low.includes("volumen") || low.includes("ticket") || low.includes("monto")) return formatCOP(valor)
  if (low.includes("tasa") || low.includes("crecimiento") || low.includes("recurrencia")) return formatPct(valor)
  if (low.includes("transacciones") || low.includes("clientes")) return formatNumber(valor)
  return formatNumber(valor)
}

export function RadarBenchmark({ data, accent = theme.primary }: Props) {
  const height = 340
  const { ref, width } = useChartSize(height)
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)

  const n = data.length
  const cx = width / 2
  const cy = height / 2
  const radius = Math.min(cx, cy) - 48

  const angleSlice = (2 * Math.PI) / (n || 1)

  const rings = [25, 50, 75, 100]

  const getPoint = (idx: number, val: number) => {
    const angle = angleSlice * idx - Math.PI / 2
    const r = (val / 100) * radius
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) }
  }

  const merchantPath = useMemo(() => {
    if (n === 0) return ""
    return data.map((d, i) => {
      const p = getPoint(i, d.percentil)
      return `${i === 0 ? "M" : "L"}${p.x},${p.y}`
    }).join(" ") + " Z"
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, width, height])

  const medianPath = useMemo(() => {
    if (n === 0) return ""
    return data.map((_, i) => {
      const p = getPoint(i, 50)
      return `${i === 0 ? "M" : "L"}${p.x},${p.y}`
    }).join(" ") + " Z"
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, width, height])

  const hovered = hoverIdx != null ? data[hoverIdx] : null

  if (!data || data.length === 0) {
    return (
      <div ref={ref} className="relative w-full" style={{ height }}>
        <div className="absolute inset-0 grid place-items-center text-sm text-[var(--muted-foreground)]">Sin datos</div>
      </div>
    )
  }

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height}>
          {/* Concentric rings */}
          {rings.map((r) => (
            <polygon
              key={r}
              points={Array.from({ length: n }, (_, i) => {
                const p = getPoint(i, r)
                return `${p.x},${p.y}`
              }).join(" ")}
              fill="none"
              stroke={theme.borderSoft}
              strokeWidth={0.7}
              strokeDasharray={r === 50 ? "none" : "2,3"}
            />
          ))}

          {/* Radial axes */}
          {data.map((_, i) => {
            const end = getPoint(i, 100)
            return <line key={`ax-${i}`} x1={cx} y1={cy} x2={end.x} y2={end.y} stroke={theme.border} strokeWidth={0.6} />
          })}

          {/* Median reference polygon */}
          <polygon
            points={Array.from({ length: n }, (_, i) => {
              const p = getPoint(i, 50)
              return `${p.x},${p.y}`
            }).join(" ")}
            fill={theme.textMuted}
            fillOpacity={0.06}
            stroke={theme.textMuted}
            strokeWidth={1}
            strokeDasharray="4,3"
          />

          {/* Merchant polygon animated */}
          <motion.path
            d={merchantPath}
            fill={accent}
            fillOpacity={0.25}
            stroke={accent}
            strokeWidth={2}
            initial={{ opacity: 0, scale: 0.3 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, ease: "easeOut" }}
            style={{ transformOrigin: `${cx}px ${cy}px` }}
          />

          {/* Vertex dots */}
          {data.map((d, i) => {
            const p = getPoint(i, d.percentil)
            return (
              <motion.circle
                key={`dot-${i}`}
                cx={p.x}
                cy={p.y}
                r={hoverIdx === i ? 5 : 3.5}
                fill={accent}
                stroke={theme.bg}
                strokeWidth={1.5}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.3 + i * 0.06, type: "spring", stiffness: 260, damping: 18 }}
              />
            )
          })}

          {/* Hover hit areas */}
          {data.map((_, i) => {
            const p = getPoint(i, 100)
            return (
              <circle
                key={`hit-${i}`}
                cx={p.x}
                cy={p.y}
                r={20}
                fill="transparent"
                onMouseEnter={() => setHoverIdx(i)}
                onMouseLeave={() => setHoverIdx(null)}
                style={{ cursor: "pointer" }}
              />
            )
          })}

          {/* Axis labels */}
          {data.map((d, i) => {
            const p = getPoint(i, 115)
            const angle = angleSlice * i - Math.PI / 2
            const isLeft = Math.cos(angle) < -0.1
            const isCenter = Math.abs(Math.cos(angle)) < 0.1
            const anchor = isCenter ? "middle" : isLeft ? "end" : "start"
            const lbl = d.etiqueta.length > 16 ? d.etiqueta.slice(0, 15) + "…" : d.etiqueta
            return (
              <text
                key={`lbl-${i}`}
                x={p.x}
                y={p.y}
                textAnchor={anchor}
                dominantBaseline="middle"
                fill="var(--muted-foreground)"
                fontSize={11}
              >
                {lbl}
              </text>
            )
          })}

          {/* Center median label */}
          <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle" fill={theme.textFaint} fontSize={9}>
            Mediana sector
          </text>
        </svg>
      )}

      {/* Tooltip */}
      {hoverIdx != null && hovered && (
        <div
          className="pointer-events-none absolute z-20 panel px-3 py-2 text-xs"
          style={{ left: Math.min(getPoint(hoverIdx, hovered.percentil).x + 12, width - 180), top: getPoint(hoverIdx, hovered.percentil).y - 10 }}
        >
          <div className="font-semibold" style={{ color: accent }}>{hovered.etiqueta}</div>
          <div className="text-[var(--muted-foreground)]">Percentil {Math.round(hovered.percentil)}</div>
          <div>{formatVal(hovered.etiqueta, hovered.valor)}</div>
          <div className="text-[var(--muted-foreground)]">Puesto {hovered.ranking} de {hovered.total_sector}</div>
        </div>
      )}
    </div>
  )
}
