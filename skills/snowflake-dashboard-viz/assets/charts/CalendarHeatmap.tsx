"use client"
import { useMemo, useState } from "react"
import * as d3 from "d3"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme } from "@/lib/theme"
import { formatCOP } from "@/lib/format"
import type { DiarioPunto } from "@/lib/types"

interface Props {
  data: DiarioPunto[]
  accent?: string
}

const DAYS = ["L", "M", "M", "J", "V", "S", "D"]
const MESES_CORTO = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

export function CalendarHeatmap({ data, accent = theme.primary }: Props) {
  const HEIGHT = 190
  const { ref, width } = useChartSize(HEIGHT)
  const [hover, setHover] = useState<{ x: number; y: number; d: DiarioPunto } | null>(null)

  const { cells, monthLabels, cellSize, marginLeft, marginTop } = useMemo(() => {
    if (!data.length || width === 0)
      return { cells: [] as any[], monthLabels: [] as any[], cellSize: 0, marginLeft: 0, marginTop: 0 }

    const sorted = [...data].sort((a, b) => a.fecha.localeCompare(b.fecha))
    const byDate = new Map<string, number>()
    for (const d of sorted) byDate.set(d.fecha, d.monto)

    const maxVal = d3.max(sorted, (d) => d.monto) ?? 1
    const buckets = 5
    const colorScale = d3.scaleQuantize<string>().domain([0, maxVal]).range(
      d3.quantize(d3.interpolateRgb("#16203a", accent), buckets)
    )

    const marginLeft = 22
    const marginTop = 18
    const firstDate = d3.timeParse("%Y-%m-%d")(sorted[0].fecha)!
    const lastDate = d3.timeParse("%Y-%m-%d")(sorted[sorted.length - 1].fecha)!

    const weeks = d3.timeWeeks(d3.timeWeek.floor(firstDate), d3.timeDay.offset(lastDate, 1))
    const numWeeks = weeks.length || 1
    const cellSize = Math.min(Math.floor((width - marginLeft - 4) / numWeeks) - 1, 14)
    const gap = 1

    const cells: { x: number; y: number; size: number; fill: string; datum: DiarioPunto; week: number }[] = []
    const fmt = d3.timeFormat("%Y-%m-%d")
    const weekFloor = d3.timeWeek.floor

    for (const d of sorted) {
      const date = d3.timeParse("%Y-%m-%d")(d.fecha)!
      const weekIdx = weeks.findIndex((w) => weekFloor(date).getTime() === w.getTime())
      if (weekIdx < 0) continue
      const dow = (date.getDay() + 6) % 7 // Mon=0
      const x = marginLeft + weekIdx * (cellSize + gap)
      const y = marginTop + dow * (cellSize + gap)
      cells.push({ x, y, size: cellSize, fill: d.monto > 0 ? colorScale(d.monto) : "#0d1426", datum: d, week: weekIdx })
    }

    // Month labels
    const monthLabels: { label: string; x: number }[] = []
    let lastMonth = -1
    for (let wi = 0; wi < weeks.length; wi++) {
      const m = weeks[wi].getMonth()
      if (m !== lastMonth) {
        lastMonth = m
        monthLabels.push({ label: MESES_CORTO[m], x: marginLeft + wi * (cellSize + gap) })
      }
    }

    return { cells, monthLabels, cellSize, marginLeft, marginTop }
  }, [data, width, accent])

  if (!data.length) {
    return (
      <div ref={ref} className="relative w-full" style={{ height: HEIGHT }}>
        <div className="absolute inset-0 grid place-items-center text-sm text-[var(--muted-foreground)]">Sin datos</div>
      </div>
    )
  }

  return (
    <div ref={ref} className="relative w-full" style={{ height: HEIGHT }}>
      {width > 0 && (
        <svg width={width} height={HEIGHT} role="img" aria-label="Heatmap calendario">
          {/* Month labels */}
          {monthLabels.map((m, i) => (
            <text key={i} x={m.x} y={marginTop - 6} fill={theme.textMuted} fontSize={10}>{m.label}</text>
          ))}
          {/* Weekday labels */}
          {DAYS.map((d, i) =>
            i % 2 === 0 ? (
              <text key={d + i} x={2} y={marginTop + i * (cellSize + 1) + cellSize * 0.8} fill={theme.textFaint} fontSize={9}>{d}</text>
            ) : null
          )}
          {/* Cells */}
          {cells.map((c, i) => (
            <motion.rect
              key={c.datum.fecha}
              x={c.x}
              y={c.y}
              width={c.size}
              height={c.size}
              rx={2}
              fill={c.fill}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: Math.min(c.week * 0.02, 1.2), duration: 0.3 }}
              onMouseMove={(e) => {
                const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top, d: c.datum })
              }}
              onMouseLeave={() => setHover(null)}
              style={{ cursor: "pointer" }}
            />
          ))}
        </svg>
      )}

      {/* Legend */}
      <div className="absolute right-3 bottom-3 flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]">
        <span>Menos</span>
        {d3.quantize(d3.interpolateRgb("#16203a", accent), 5).map((c, i) => (
          <div key={i} className="w-3 h-3 rounded-sm" style={{ background: c }} />
        ))}
        <span>Más</span>
      </div>

      {hover && (
        <div
          className="pointer-events-none absolute z-20 panel px-3 py-2 text-xs"
          style={{ left: Math.min(hover.x + 12, width - 160), top: Math.min(hover.y + 12, HEIGHT - 50) }}
        >
          <div className="font-semibold">{formatFechaLarga(hover.d.fecha)}</div>
          <div className="text-[var(--muted-foreground)]">{formatCOP(hover.d.monto)}</div>
        </div>
      )}
    </div>
  )
}

function formatFechaLarga(fecha: string): string {
  const d = new Date(fecha + "T12:00:00")
  const day = d.getDate()
  const mes = MESES_CORTO[d.getMonth()]
  const year = d.getFullYear()
  return `${day} ${mes} ${year}`
}
