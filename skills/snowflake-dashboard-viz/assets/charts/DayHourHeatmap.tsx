"use client"
import { useMemo, useState } from "react"
import * as d3 from "d3"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme, CHORO_RAMP } from "@/lib/theme"
import { formatCOP, formatNumber } from "@/lib/format"
import type { HoraPunto } from "@/lib/types"

interface Props { data: HoraPunto[]; accent?: string }

const DIAS = [
  { n: 1, label: "Lun" }, { n: 2, label: "Mar" }, { n: 3, label: "Mié" },
  { n: 4, label: "Jue" }, { n: 5, label: "Vie" }, { n: 6, label: "Sáb" }, { n: 7, label: "Dom" },
]
const HORAS = Array.from({ length: 24 }, (_, h) => h)

/** Heatmap día-de-semana × hora-del-día por volumen de transacciones. */
export function DayHourHeatmap({ data, accent = theme.cyan }: Props) {
  const height = 248
  const { ref, width } = useChartSize(height)
  const [hover, setHover] = useState<{ x: number; y: number; d: HoraPunto } | null>(null)

  const { byKey, maxTx, peak, color } = useMemo(() => {
    const byKey = new Map<string, HoraPunto>()
    let maxTx = 0
    let peak: HoraPunto | null = null
    for (const d of data) {
      byKey.set(`${d.dia_semana}-${d.hora}`, d)
      if (d.num_tx > maxTx) maxTx = d.num_tx
      if (!peak || d.num_tx > peak.num_tx) peak = d
    }
    const interp = d3.interpolateRgbBasis(CHORO_RAMP)
    const scale = d3.scaleSqrt().domain([0, maxTx || 1]).range([0, 1])
    const color = (v: number) => (v <= 0 ? "#0d1426" : interp(scale(v)))
    return { byKey, maxTx, peak, color }
  }, [data])

  if (!data.length) {
    return <div ref={ref} className="grid place-items-center text-sm text-[var(--muted-foreground)]" style={{ height }}>Sin datos</div>
  }

  const m = { top: 6, right: 10, bottom: 22, left: 38 }
  const iw = Math.max(10, width - m.left - m.right)
  const ih = height - m.top - m.bottom
  const cellW = iw / 24
  const cellH = ih / 7
  const gap = 1.5

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height}>
          <g transform={`translate(${m.left},${m.top})`}>
            {/* Day labels */}
            {DIAS.map((d, r) => (
              <text key={d.n} x={-8} y={r * cellH + cellH / 2} dy="0.32em" textAnchor="end" fill={theme.textMuted} fontSize={10}>{d.label}</text>
            ))}
            {/* Hour axis (cada 3h) */}
            {HORAS.filter((h) => h % 3 === 0).map((h) => (
              <text key={h} x={h * cellW + cellW / 2} y={ih + 14} textAnchor="middle" fill={theme.textMuted} fontSize={9}>{h}h</text>
            ))}
            {/* Cells */}
            {DIAS.map((d, r) =>
              HORAS.map((h) => {
                const rec = byKey.get(`${d.n}-${h}`)
                const v = rec?.num_tx ?? 0
                const isPeak = peak && rec === peak
                return (
                  <motion.rect
                    key={`${d.n}-${h}`}
                    x={h * cellW + gap / 2}
                    y={r * cellH + gap / 2}
                    width={Math.max(1, cellW - gap)}
                    height={Math.max(1, cellH - gap)}
                    rx={2}
                    fill={color(v)}
                    stroke={isPeak ? accent : "transparent"}
                    strokeWidth={isPeak ? 1.6 : 0}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: Math.min((r * 24 + h) * 0.0025, 0.6), duration: 0.3 }}
                    style={{ cursor: rec ? "pointer" : "default" }}
                    onMouseMove={(e) => {
                      if (!rec) return
                      const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                      setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top, d: rec })
                    }}
                    onMouseLeave={() => setHover(null)}
                  />
                )
              })
            )}
          </g>
        </svg>
      )}

      {/* Leyenda */}
      <div className="absolute right-3 -top-1 flex items-center gap-2 text-[10px] text-[var(--muted-foreground)]">
        <span>Menos</span>
        <div className="h-2 w-20 rounded-full" style={{ background: `linear-gradient(90deg, ${CHORO_RAMP.join(",")})` }} />
        <span>Más tx</span>
      </div>

      {hover && (
        <div className="pointer-events-none absolute z-20 panel px-3 py-2 text-xs" style={{ left: Math.min(hover.x + 12, width - 160), top: hover.y + 12 }}>
          <div className="font-semibold">{hover.d.dia} · {String(hover.d.hora).padStart(2, "0")}:00</div>
          <div className="text-[var(--muted-foreground)]">{formatNumber(hover.d.num_tx)} tx · {formatCOP(hover.d.monto)}</div>
        </div>
      )}
    </div>
  )
}
