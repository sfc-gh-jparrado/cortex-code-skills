"use client"
import { useMemo, useState } from "react"
import * as d3 from "d3"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme } from "@/lib/theme"
import { formatCOP, formatMesCorto, formatPct } from "@/lib/format"
import type { TendenciaPunto, SectorTendenciaPunto } from "@/lib/types"

interface Props {
  tendencia: TendenciaPunto[]
  sector: SectorTendenciaPunto[]
  accent?: string
}

export function MerchantVsSectorLine({ tendencia, sector, accent = theme.primary }: Props) {
  const height = 300
  const { ref, width } = useChartSize(height)
  const [hover, setHover] = useState<{ x: number; y: number; idx: number } | null>(null)

  const margin = { top: 24, right: 20, bottom: 36, left: 64 }

  const sectorByMes = useMemo(() => {
    const m = new Map<string, SectorTendenciaPunto>()
    for (const s of sector) m.set(s.mes, s)
    return m
  }, [sector])

  const { xScale, yScale, merchantLine, sectorLine, ticks, meses } = useMemo(() => {
    if (!tendencia.length || width === 0)
      return { xScale: null, yScale: null, merchantLine: "", sectorLine: "", ticks: [] as number[], meses: [] as string[] }
    const innerW = width - margin.left - margin.right
    const innerH = height - margin.top - margin.bottom
    const meses = tendencia.map((d) => d.mes)

    const xScale = d3.scalePoint<string>().domain(meses).range([0, innerW]).padding(0.1)

    const allVals = [
      ...tendencia.map((d) => d.monto),
      ...sector.map((d) => d.monto_prom),
    ]
    const yMax = d3.max(allVals) ?? 1
    const yScale = d3.scaleLinear().domain([0, yMax * 1.1]).nice().range([innerH, 0])

    const lineMerchant = d3.line<TendenciaPunto>()
      .x((d) => xScale(d.mes)!)
      .y((d) => yScale(d.monto))
      .curve(d3.curveMonotoneX)

    const lineSector = d3.line<SectorTendenciaPunto>()
      .x((d) => xScale(d.mes)!)
      .y((d) => yScale(d.monto_prom))
      .curve(d3.curveMonotoneX)

    const ticks = yScale.ticks(5)

    return {
      xScale,
      yScale,
      merchantLine: lineMerchant(tendencia) ?? "",
      sectorLine: lineSector(sector) ?? "",
      ticks,
      meses,
    }
  }, [tendencia, sector, width, margin.left, margin.right, margin.top, margin.bottom])

  const handleMouseMove = (e: React.MouseEvent<SVGRectElement>) => {
    if (!xScale || !tendencia.length) return
    const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
    const mx = e.clientX - rect.left - margin.left
    const step = xScale.step()
    let idx = Math.round(mx / step)
    idx = Math.max(0, Math.min(tendencia.length - 1, idx))
    setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top, idx })
  }

  if (!tendencia.length) {
    return (
      <div ref={ref} className="relative w-full grid place-items-center text-sm text-[var(--muted-foreground)]" style={{ height }}>
        Sin datos
      </div>
    )
  }

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && xScale && yScale && (
        <svg width={width} height={height}>
          <g transform={`translate(${margin.left},${margin.top})`}>
            {/* Grid */}
            {ticks.map((t) => (
              <line key={t} x1={0} x2={width - margin.left - margin.right} y1={yScale(t)} y2={yScale(t)} stroke={theme.borderSoft} strokeDasharray="2,3" />
            ))}

            {/* Y ticks */}
            {ticks.map((t) => (
              <text key={`yt-${t}`} x={-10} y={yScale(t)} textAnchor="end" dominantBaseline="middle" fill="var(--muted-foreground)" fontSize={11}>
                {formatCOP(t)}
              </text>
            ))}

            {/* X ticks */}
            {meses.map((m, i) => {
              const show = meses.length <= 12 || i % Math.ceil(meses.length / 8) === 0
              if (!show) return null
              return (
                <text key={m} x={xScale(m)!} y={height - margin.top - margin.bottom + 22} textAnchor="middle" fill="var(--muted-foreground)" fontSize={11}>
                  {formatMesCorto(m)}
                </text>
              )
            })}

            {/* Sector line (dashed, behind) */}
            <motion.path
              d={sectorLine}
              fill="none"
              stroke={theme.textMuted}
              strokeWidth={2}
              strokeDasharray="6,4"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1.2, ease: "easeOut" }}
            />

            {/* Merchant line (solid) */}
            <motion.path
              d={merchantLine}
              fill="none"
              stroke={accent}
              strokeWidth={2.5}
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1.2, ease: "easeOut", delay: 0.1 }}
            />

            {/* Merchant dots */}
            {tendencia.map((d, i) => (
              <motion.circle
                key={d.mes}
                cx={xScale(d.mes)!}
                cy={yScale(d.monto)}
                r={3.5}
                fill={accent}
                stroke={theme.bg}
                strokeWidth={1.5}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.3 + i * 0.04, type: "spring", stiffness: 200, damping: 14 }}
              />
            ))}

            {/* Hover guide */}
            {hover != null && (() => {
              const d = tendencia[hover.idx]
              const cx = xScale(d.mes)!
              return (
                <line x1={cx} x2={cx} y1={0} y2={height - margin.top - margin.bottom} stroke={accent} strokeWidth={1} strokeDasharray="3,3" opacity={0.5} />
              )
            })()}

            {/* Hover rect */}
            <rect
              x={0}
              y={0}
              width={width - margin.left - margin.right}
              height={height - margin.top - margin.bottom}
              fill="transparent"
              onMouseMove={handleMouseMove}
              onMouseLeave={() => setHover(null)}
            />
          </g>
        </svg>
      )}

      {/* Legend */}
      <div className="absolute top-2 right-3 flex items-center gap-4 text-[11px]">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded" style={{ background: accent }} />
          <span style={{ color: theme.text }}>Tu comercio</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded border-b border-dashed" style={{ borderColor: theme.textMuted }} />
          <span style={{ color: theme.textMuted }}>Promedio sector</span>
        </span>
      </div>

      {/* Tooltip */}
      {hover != null && (() => {
        const d = tendencia[hover.idx]
        const s = sectorByMes.get(d.mes)
        const sVal = s?.monto_prom ?? 0
        const gap = sVal > 0 ? ((d.monto - sVal) / sVal) * 100 : 0
        const gapLabel = gap >= 0 ? `+${formatPct(gap)} vs sector` : `${formatPct(gap)} vs sector`
        return (
          <div
            className="pointer-events-none absolute z-20 panel px-3 py-2 text-xs"
            style={{ left: Math.min(hover.x + 14, width - 180), top: hover.y - 70 }}
          >
            <div className="font-semibold">{formatMesCorto(d.mes)}</div>
            <div style={{ color: accent }}>Comercio: {formatCOP(d.monto)}</div>
            <div style={{ color: theme.textMuted }}>Sector: {formatCOP(sVal)}</div>
            <div className="mt-0.5" style={{ color: gap >= 0 ? theme.green : theme.red }}>{gapLabel}</div>
          </div>
        )
      })()}
    </div>
  )
}
